---
paths:
  - "backend/app/**"
---

How the application writes logs on top of the structured JSON logger in `app/core/logger.py`:
where a logger comes from, what a record carries, which level an event gets, what never goes
into a record and which layer owns which events. `setup_logging()` installs one stdout handler
with `JSONFormatter`, which renders `message` plus every `extra` key as a top-level JSON field,
and `RequestIdFilter`, which attaches `request_id` from `app/core/request_context.py`. Layer
imports are in `backend/layering.md`.

### Log through `app.core.logger`, never `print`

`get_logger(__name__)` returns a stdlib logger whose records reach the JSON handler and carry
the `request_id` of the request that produced them; a `print` writes an unstructured line with
no level and no correlation. A dedicated stream takes a literal `app.<channel>` name, as the
access log does with `get_logger("app.access")`. The CLI entry points under `app/commands/`
are the only place `print` is allowed, because their stdout is the command's output, not a log.

**Incorrect:**

```python
import logging

logger = logging.getLogger("users")
print(f"user {user_id} created")
```

**Correct:**

```python
from app.core.logger import get_logger

logger = get_logger(__name__)
```

Enforced by: ruff: T201, backend/tests/unit/architecture/test_logging_contracts.py

### Configure handlers, levels and formatters only in `setup_logging`

`setup_logging()` clears the root handlers and installs the JSON handler once, from the
lifespan in `main.py`, at `settings.LOG_LEVEL`. A `logging.basicConfig()`, an extra
`StreamHandler` or a per-module `setLevel` elsewhere adds a second, unformatted copy of every
line or silences a module nobody remembers touching. `app/core/logger.py` is the only module
under `app/` that imports `logging`.

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py

### Keep the message constant and put data in `extra`

The message names the event and never changes between occurrences; every variable value goes
into `extra={...}`, which the formatter emits as its own JSON field. A message built with an
f-string, `.format`, concatenation or `%s` arguments turns each occurrence into a different
string, so the event cannot be counted or filtered and its values cannot be queried by key.
`extra` is a dict literal with stable snake_case keys that never shadow a `LogRecord`
attribute (`message`, `name`, `args`, `msg`, `levelname`, ...), which the stdlib rejects or the
formatter drops. Reuse the existing key names: `http_method`, `http_path`, `http_status_code`,
`duration_ms`, `error_code`.

**Incorrect:**

```python
logger.warning(f"API exception {exc.code} on {request.url.path}")
logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
```

**Correct:**

```python
logger.warning(
    "api exception",
    extra={
        "request_id": request_id,
        "error_code": exc.code,
        "http_status_code": exc.status_code,
        "http_path": request.url.path,
    },
)
```

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py

### Leave `request_id` to `RequestIdFilter`

`RequestIDMiddleware` binds the request ID to a context var for the whole request, and the
filter copies it onto every record that does not already have one, so a service never passes it. Only `app/core/` passes it explicitly, because the exception handlers
can run in `ServerErrorMiddleware`, outside the middleware that bound the context var, and read
it from `request.state` instead.

**Incorrect:**

```python
logger.info("user created", extra={"user_id": str(user.id), "request_id": get_request_id()})
```

**Correct:**

```python
logger.info("user created", extra={"user_id": str(user.id)})
```

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py

### Pick the level by who has to act

`debug` is developer detail, off at the default `LOG_LEVEL=INFO`. `info` is a lifecycle or
completed-operation event nobody has to act on: startup, database ready, shutdown, the one
access-log line per request. `warning` is an expected failure or a degraded mode: a domain error
or a request validation failure, handled by `app/core/exceptions.py`, and the database disabled
in isolated test mode. `error` is an unexpected failure that someone must look at, always with
its traceback. A client mistake logged at `error` pages someone for nothing.

Enforced by: review

### Leave expected domain errors to `api_exception_handler`

An `APIException` is an expected outcome with a stable `code`, not a fault.
`api_exception_handler` logs each one exactly once, at `warning`, with `error_code`,
`http_status_code` and `http_path`; a service that also logs it doubles the line and, at
`error`, reports a client mistake as an incident. Raise it and let the handler log it.

**Incorrect:**

```python
try:
    user = await self._users.get_or_raise(user_id)
except NotFoundException:
    logger.error("user not found", extra={"user_id": str(user_id)})
    raise
```

**Correct:**

```python
user = await self._users.get(user_id)
if user is None:
    raise NotFoundException("User not found")
```

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py

### Log an unexpected exception once, with its traceback, where it stops

`general_exception_handler` turns an unexpected exception into the generic 500 envelope and logs
it once with the traceback (`logger.error(..., exc_info=exc)`). Code that catches an exception,
logs it and re-raises it produces a second copy of the same traceback at the boundary; either
handle it there, or let it propagate unlogged.

**Incorrect:**

```python
try:
    await self._mailer.send(message)
except Exception:
    logger.exception("sending failed")
    raise
```

**Correct:**

```python
await self._mailer.send(message)
```

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py

### Never log secrets, credentials or personal data

Log records leave the process in plain text. Never put a password or its hash, a JWT, a
refresh or CSRF token, a cookie, an `Authorization` header, an API key, an email, a phone
number, a national ID or a person's name into a message or an `extra` value, and never log a whole
request, header map, payload or model. Log the owning record's ID instead: `user_id`, not the
user's email. The check rejects `extra` keys whose snake_case parts name a secret or personal
field (`password`, `token`, `secret`, `cookie`, `authorization`, `credential`, `email`,
`phone`, `ssn`); what goes into the values stays a review decision.

**Incorrect:**

```python
logger.info("login succeeded", extra={"user_email": user.email, "access_token": token})
```

**Correct:**

```python
logger.info("login succeeded", extra={"user_id": str(user.id)})
```

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py, review

### Log from the layer that owns the event

`app/core/` logs the HTTP boundary (access log, error handlers), `main.py` logs the application
lifecycle, and a service may log a domain event it
completed, at `info`, by ID. Routers, repositories, models, schemas, dependencies and `app/config/`
do not log: a router's request is already in the access log, a repository's
failure propagates to the service that decides what it means, and the rest hold no events of
their own. A repository that logs its queries duplicates what the database already records and
leaks row data.

Enforced by: backend/tests/unit/architecture/test_logging_contracts.py
