---
paths:
  - "backend/tests/**"
---

How the backend test suite is organized: two tiers, what each one may touch, which modules must
have a test, and what a good test asserts. Production-code rules live in `backend/layering.md`,
`backend/persistence.md` and `backend/api-crud.md`.

### Keep two test tiers and apply markers from the tier's `conftest.py`

`tests/unit` does no I/O and runs everywhere; `tests/integration` needs a real Postgres through
`DATABASE_URL` and is skipped without it. The marker and the skip are applied once by each
tier's `conftest.py`, never repeated per file — per-file boilerplate drifts, and a file that
forgets it fails the whole run on a machine with no database.

**Incorrect:**

```python
# DO NOT DO THIS
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"), reason="integration tier requires a database"
)
```

**Correct:**

```python
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark the whole integration tier and skip it when no database is configured."""
    skip = pytest.mark.skip(reason="DATABASE_URL is not set")
    for item in items:
        item.add_marker(pytest.mark.integration)
        if not os.getenv("DATABASE_URL"):
            item.add_marker(skip)
```

Enforced by: backend/tests/unit/architecture/test_test_conventions.py

### Pair every service and router with its test module

`app/services/<x>.py` has `tests/unit/services/test_<x>.py`; `app/routers/<x>.py` has
`tests/integration/api/test_<x>.py`. The pairing is mechanical so a new slice cannot ship with
its business rules untested and nobody has to notice during review.

Enforced by: backend/tests/unit/architecture/test_test_conventions.py

### Build fakes, never mocks, in the unit tier

`unittest.mock` asserts that a call happened, not that the behaviour is right, and a
`MagicMock` session accepts every method a real `AsyncSession` would reject. Use the shared
`tests/support/fakes.py` — `FakeSession`, `FakeTransaction`, in-memory repositories — so a
test that passes against the fake also describes something the real session can do.

Enforced by: backend/tests/unit/architecture/test_test_conventions.py

### Cover the happy path, every raised exception and every authorization branch

A service unit test is complete when it exercises the success case, each `APIException` the
method can raise, each role branch, and the commit/rollback counts recorded by `FakeSession`.
The last one is the only place the transaction boundary itself is asserted.

Enforced by: review

### Drive integration API tests through `TestClient` with dependency overrides

Override `get_session` and `get_settings` on the app rather than patching modules, seed through
the repositories with uuid-unique data so parallel runs do not collide, and assert both the
status code and the envelope shape. A test that only checks the status passes against an
endpoint that returns the wrong body.

Enforced by: review

### Keep architecture tests discovery-based

An architecture test globs the tree and checks every match, so adding a feature never requires
adding a test file. The retired per-feature `test_<x>_boundaries.py` pattern failed exactly
when someone forgot to write one — which is the case it existed to catch.

Enforced by: review

### Name tests `test_<behaviour>_<condition>` and assert one behaviour

The name is the failure message a reader sees first. One behaviour per test, no `sleep`, no
dependence on execution order, and `--strict-markers` stays on so a typo in a marker fails
instead of silently selecting nothing.

Enforced by: review

### Treat a run without `DATABASE_URL` as incomplete

`uv run pytest` is green without a database because the whole integration tier is skipped. That
is a fast inner loop, not evidence: the Definition of Done and CI both run with `DATABASE_URL`
set, and a claim that tests pass means the full run.

Enforced by: ci: pytest-with-database

### Keep test modules comment-free

The no-comments rule covers `tests/` as well as `app/`. A test that needs a comment to explain
what it asserts needs a better name or a smaller assertion; docstrings on the module or a
complex fixture are allowed.

Enforced by: backend/tests/unit/architecture/test_no_comments.py
