---
paths:
  - "backend/app/**"
---

Structural rules for the FastAPI application package: which layer may import what, how errors
leave it, and the file-level conventions every module under `app/` follows. Persistence detail
lives in `backend/persistence.md`, the CRUD recipe in `backend/api-crud.md`, the reasoning in
`docs/architecture/backend.md`.

### Route every request through router, service, repository, model

One direction, no shortcuts: a router calls a service, a service calls a repository, a
repository touches models. A router that reaches a model skips validation, RBAC and the
transaction boundary at once, and nothing in the test suite can tell that it did.

| Layer | May import | Must not import |
|---|---|---|
| `app/routers/**` | `app.dependencies`, `app.schemas`, `fastapi` | `app.repositories`, `app.models`, `sqlalchemy`, `app.core.database` |
| `app/services/**` | `app.repositories`, `app.models`, `app.schemas`, `app.core.*` | `fastapi` |
| `app/repositories/**` | `app.models`, `sqlalchemy` | `app.services`, `app.routers`, `app.core.exceptions` |
| `app/models/**` | `sqlalchemy`, sibling models | `app.services`, `app.repositories`, `app.routers`, `app.dependencies` |
| `app/dependencies/**` | everything below it, plus `fastapi` | — |

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Keep routers HTTP-only

A handler parses the request, calls exactly one service method, and wraps the result in an
envelope. Business logic in a handler cannot be unit-tested without a TestClient and cannot
be reused by a command or a background job.

**Incorrect:**

```python
@router.get("/{user_id}", response_model=SuccessResponse[UserRead])
async def get_user(user_id: uuid.UUID, session: SessionDep) -> SuccessResponse[UserRead]:
    # DO NOT DO THIS
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return SuccessResponse(data=UserRead.model_validate(user))
```

**Correct:**

```python
@router.get("/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    _actor: SelfOrAdmin,
    service: UserServiceDep,
) -> SuccessResponse[UserRead]:
    data = await service.get_user(user_id)
    return SuccessResponse(data=data)
```

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Own validation, RBAC and the transaction boundary in the service

The service is the only layer that knows the domain rules, so it is the only layer allowed to
decide what is valid, who may do it, and where the transaction starts and ends. Every mutation
runs inside `async with transaction(self._session):` from `app/core/transactions.py`; a
bespoke `@asynccontextmanager` or a bare `.commit()` reintroduces the duplication this repo
already removed once. The one recorded exception is the best-effort `rollback()` in
`services/auth.py`'s logout path, listed by function name in `KNOWN_SESSION_CONTROL_DEVIATIONS`
in the layer test; any other rollback in a service fails the build.

**Incorrect:**

```python
async def disable_user(self, user_id: uuid.UUID) -> UserRead:
    # DO NOT DO THIS
    user = await self._users.get_for_update(user_id)
    await self._users.disable(user)
    await self._session.commit()
    return to_user_read(user)
```

**Correct:**

```python
async def disable_user(self, user_id: uuid.UUID) -> UserRead:
    async with transaction(self._session):
        user = await self._users.get_for_update(user_id)
        if user is None:
            raise NotFoundException("User not found")
        await self._guard_last_admin_disable(user)
        await self._users.disable(user)
    return to_user_read(user)
```

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Give repositories a session and let them flush only

A repository takes `session: AsyncSession` in its constructor, returns models or `None`, and
calls `.flush()` so generated keys are available without ending the caller's transaction. It
raises no `APIException`: an `IntegrityError` propagates and the service decides it is a
`ConflictException`.

**Incorrect:**

```python
async def create(self, *, name: str, email: str, password_hash: str) -> User:
    user = User(name=name, email=email, password_hash=password_hash)
    self._session.add(user)
    # DO NOT DO THIS
    await self._session.commit()
    return user
```

**Correct:**

```python
async def create(self, *, name: str, email: str, password_hash: str) -> User:
    user = User(
        name=name,
        email=email.strip(),
        email_normalized=normalize_email(email),
        password_hash=password_hash,
        role=UserRole.MEMBER,
    )
    self._session.add(user)
    await self._session.flush()
    return user
```

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Declare models with SQLAlchemy 2.0 `Mapped[...]` and import nothing upward

Models are the bottom of the graph. A model that imports a service or a repository makes the
import graph cyclic and makes Alembic autogenerate import half the application to read
metadata. Cross-model relationship types go behind `if TYPE_CHECKING:`.

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py

### Wire every service in `app/dependencies/<x>.py`

`app/dependencies/` is the only layer that imports both `Depends` and concrete service and
repository classes, so it is the only place construction happens. Each feature exports one
`get_<x>_service` function and one `XServiceDep = Annotated[XService, Depends(get_<x>_service)]`
alias, re-exported from `app/dependencies/__init__.py`. Service `__init__` takes no defaulted
parameters — a default makes a missing wire silently produce a half-built service.

**Incorrect:**

```python
class UserService:
    # DO NOT DO THIS
    def __init__(self, session: AsyncSession, users: UserRepository | None = None) -> None:
        self._session = session
        self._users = users or UserRepository(session)
```

**Correct:**

```python
class UserService:
    def __init__(self, *, session: AsyncSession, users: UserRepository) -> None:
        self._session = session
        self._users = users


def get_user_service(session: SessionDep) -> UserService:
    return UserService(session=session, users=UserRepository(session))


UserServiceDep = Annotated[UserService, Depends(get_user_service)]
```

Enforced by: backend/tests/unit/architecture/test_dependency_contracts.py

### Raise `APIException` subclasses, never `HTTPException`

Every domain error is an `APIException` subclass from `app/core/exceptions.py` carrying a
stable lower-case `code`. The three handlers registered in `main.py` are the only place a
response body for an error is built, so a raw `HTTPException` escapes the envelope and reaches
the frontend in a shape `parse-response.ts` cannot read.

Enforced by: backend/tests/unit/architecture/test_layer_boundaries.py, backend/tests/unit/architecture/test_route_contracts.py

### Write `async def` end to end

The stack is asyncpg and `AsyncSession`; a sync `def` handler runs in FastAPI's threadpool and
cannot await the request-scoped session at all. The packaged FastAPI skill's advice to default
to `def` does not apply in this repo. No blocking call belongs on the event loop.

Enforced by: backend/tests/unit/architecture/test_route_contracts.py

### Pair module stems across layers

`routers/users.py`, `services/users.py`, `repositories/users.py`, `dependencies/users.py` and
`schemas/api/users.py` share one stem so discovery-based tests and scaffolds can pair them
without a registry. Models stay singular per entity (`models/user.py`, `models/auth_session.py`).

Enforced by: backend/tests/unit/architecture/test_test_conventions.py

### Write docstrings, never explanatory comments

A comment explaining code is a naming problem deferred. Public modules, classes and non-obvious
functions carry docstrings; functional directives (`# noqa`, `# type:`, `# pragma:`) are the
only `#` lines allowed anywhere under `app/`.

Enforced by: backend/tests/unit/architecture/test_no_comments.py

### Split a function before it hits the complexity limits

Ruff caps cyclomatic complexity at 10 and statements at 50. Reaching either means the function
holds more than one decision; extract a helper — a `# noqa` on these two codes is never the
answer.

Enforced by: ruff: C901, ruff: PLR0915

### Log through `app.core.logger`, never `print`

`get_logger(__name__)` emits structured records that carry the `request_id` from the context
var, so a line can be traced to the request that produced it. A `print` writes to stdout with
no correlation and no level.

Enforced by: ruff: T201
