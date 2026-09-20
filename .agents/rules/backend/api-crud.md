---
paths:
  - "backend/app/routers/**"
  - "backend/app/schemas/**"
  - "backend/app/services/**"
  - "backend/app/dependencies/**"
---

The end-to-end recipe for exposing a resource over HTTP: what a slice contains, how a router is
declared, what every route must carry, and how the service behind it orders its work. Import
rules live in `backend/layering.md`; tables and migrations in `backend/persistence.md`.

### Ship the whole vertical slice for a new resource

A resource is not usable until all of it exists: model, migration, repository, service, router,
`app/schemas/api/<x>.py`, `app/dependencies/<x>.py` re-exported from `__init__.py`, a unit test
for the service and an integration test for the router. A partial slice leaves an endpoint
whose failure modes are untested and a dependency alias nobody can import. Generate it with
`.agents/scaffold/backend_crud.py` and edit the domain fields rather than improvising structure.

Enforced by: scaffold: .agents/scaffold/backend_crud.py, backend/tests/unit/architecture/test_test_conventions.py

### Configure prefix, tags and dependencies on the `APIRouter`

The router object carries `prefix`, `tags` and any router-wide `dependencies`; `include_router`
carries only shared `responses`. Splitting the two means a reader has to open `main.py` to learn
a route's real path, and OpenAPI operation ids shift when the include changes.

**Incorrect:**

```python
router = APIRouter()
# DO NOT DO THIS
app.include_router(router, prefix="/users", tags=["users"])
```

**Correct:**

```python
router = APIRouter(prefix="/users", tags=["users"])
app.include_router(users_router, responses=ERROR_RESPONSES)
```

Enforced by: backend/tests/unit/architecture/test_route_contracts.py, review

### Declare an auth dependency on every route

`RequireAdmin`, `SelfOrAdmin` or `CurrentUser` appears as an explicit parameter on the handler,
so the authorization decision is visible where the route is read. `AuthContextDep`
(`get_auth_context`, the CSRF/origin gate) counts for the session endpoints `/auth/login`,
`/auth/refresh` and `/auth/logout`. The only public routes are `GET /` and `GET /health`
(`PUBLIC_ROUTES` in the test, asserted both ways); anything else without a dependency is an open
endpoint that no test will notice.

**Correct:**

```python
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _actor: RequireAdmin,
    service: UserServiceDep,
) -> SuccessResponse[UserRead]:
    data = await service.create_user(payload)
    return SuccessResponse(message="User created", data=data)
```

Enforced by: backend/tests/unit/architecture/test_route_contracts.py

### Return the envelope through the return annotation

One item returns `-> SuccessResponse[XRead]`, a list returns `-> PaginatedResponse[XRead]`.
The bare exceptions are `GET /` (a plain dict), `POST /auth/login` and `GET /auth/me` (the resource
itself, which the frontend envelope helper accounts for) and the 204 routes returning `None`;
they are `ENVELOPE_EXEMPT_ROUTES` in the test, asserted both ways.
The annotation is the contract mypy checks and the schema orval generates from, so
`response_model=` duplicates it, `-> Any` erases it, and `SuccessResponse[list[...]]` produces
a list with no pagination fields the frontend can read. `/auth/login` and `/auth/me` are the
two documented exceptions.

**Incorrect:**

```python
# DO NOT DO THIS
@router.get("", response_model=PaginatedResponse[UserRead])
async def list_users(...) -> Any: ...
```

**Correct:**

```python
@router.get("")
async def list_users(
    _actor: RequireAdmin,
    service: UserServiceDep,
    filters: Annotated[UserListFilters, Query()],
) -> PaginatedResponse[UserRead]:
    items, total = await service.list_users(filters)
    ...
```

Enforced by: backend/tests/unit/architecture/test_route_contracts.py

### Return 201 on create, 204 for no-body operations, 200 everywhere else

`POST` handlers whose name starts with `create` return 201 with the created `XRead` in an
envelope. Operations that legitimately have nothing to return (`/auth/refresh`, `/auth/logout`,
`DELETE /users/{user_id}`) return 204 with `-> None`; they are listed in `NO_CONTENT_ROUTES` in
the test, asserted both ways, so adding a 204 route is a deliberate edit to that list, not a
default. Everything else returns 200 with an envelope.

**Correct:**

```python
@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    _actor: RequireAdmin,
    service: UserServiceDep,
) -> SuccessResponse[UserRead]:
    data = await service.create_user(payload)
    return SuccessResponse(message="User created", data=data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disable_user(
    user_id: uuid.UUID, _actor: RequireAdmin, service: UserServiceDep
) -> None:
    await service.disable_user(user_id)
```

Enforced by: backend/tests/unit/architecture/test_route_contracts.py

### Keep operation ids stable: they derive from handler names

FastAPI builds `operationId` from the handler function name, path and method
(`list_users_users_get`), and orval derives the generated hook and function names from it.
Renaming a handler therefore renames a frontend import: do it only together with
`export_openapi`, `npm run generate:api` and the caller fixes, in the same PR. The test asserts
ids are unique across the app.

Enforced by: backend/tests/unit/architecture/test_route_contracts.py

### Register static paths before parameterized ones

FastAPI matches in declaration order, so `/users/{user_id}` declared first swallows `/users/me`
and the parameterized handler fails parsing `"me"` as a UUID.

Enforced by: backend/tests/unit/architecture/test_route_contracts.py

### Split schemas into `Create`, `Update`, `Read` and `ListFilters`

`XCreate` is the write contract, `XUpdate` has every field optional so a PATCH can send one,
`XRead` is the response shape, `XListFilters` holds the query parameters. A password hash or a
token never appears on a `Read` schema — that is how a secret reaches the browser. Declare
defaults with `Field(default=...)`; the `Field(...)` ellipsis form and `RootModel` both defeat
the generated client's typing.

Enforced by: review, mypy

### Validate, then authorize, then open the transaction

A `ForbiddenException` raised inside the transaction has already opened one and rolled it back
for nothing; raise it first. Self-service updates must not change `role`. An `IntegrityError`
is caught at the service boundary and re-raised as `ConflictException`, so the uniqueness rule
is stated once rather than duplicated as a pre-check that races.

**Correct:**

```python
async def update_user(self, actor: User, user_id: uuid.UUID, payload: UserUpdate) -> UserRead:
    if payload.role is not None and actor.role is not UserRole.ADMIN:
        raise ForbiddenException("Only an administrator may change a role")
    try:
        async with transaction(self._session):
            ...
    except IntegrityError:
        raise ConflictException("A user with this email already exists") from None
    return to_user_read(user)
```

Enforced by: backend/tests/unit/architecture/test_test_conventions.py, review

### Compute pagination with the shared helper in `schemas/api/base.py`

`page`/`page_size` convert to `offset`/`limit` and `total_pages` in one place. A router that
computes `total_pages` itself gets the empty-collection case wrong in a way no single test
catches, and the two routers then disagree.

Enforced by: review

### Re-export the OpenAPI schema after any contract change

The frontend client is generated from `backend/openapi.json`, which is committed. After
touching a router, a schema or `main.py`, run `uv run python -m app.commands.export_openapi`
and commit the result; `frontend/src/lib/api/generated/` itself is build output and is never
committed.

Enforced by: ci: openapi-current, hook: .agents/hooks/guard_paths.py

### Let the return annotation serialize the response

Returning `ORJSONResponse` or `UJSONResponse` bypasses the response model, so the endpoint
disappears from the OpenAPI schema's typed output and orval generates `unknown`.

Enforced by: review
