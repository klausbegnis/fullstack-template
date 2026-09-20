# PRD 0001: User management

Status: Shipped
Owner: Platform template maintainers
Last updated: 2026-09-19

## Problem

Every application built from this template needs an identity: something has to authenticate a
person, keep them signed in across requests, and let an administrator control who has access.
Without a reference implementation, each project copied from this template would build its own
auth stack from scratch, and a template's whole value is that new verticals copy an existing
shape instead of inventing one — badly, under time pressure, with tokens in `localStorage` and
no CSRF story. User management is also the one vertical every other feature in this template is
built to copy: it has to demonstrate the full backend layering (`router -> service -> repository
-> model`) and the full frontend layering (`app -> features -> components -> lib`) end to end, not
just authentication in isolation.

## Goals

- Authenticate with a password, hashed with Argon2id, never recoverable in plaintext.
- Keep a session alive past access-token expiry through rotating, single-use refresh tokens, with
  replay of a consumed or revoked token detected and the session revoked.
- Protect cookie-authenticated mutations with double-submit CSRF, not reliance on `SameSite`
  alone.
- Give an administrator full CRUD over user accounts (create, list, view, update, disable),
  gated by role, including a hard guard against removing the last active administrator.
- Ship a working frontend vertical (login, users list, user detail, create/edit forms) that is
  the pattern every future `features/<f>` copies, including the RSC/client split and the
  orval-generated API client with its anti-corruption mapper.

## Non-goals

- No OAuth, social login, or SSO.
- No email verification and no self-service password-reset flow.
- No self-service signup route — accounts are created by an administrator through `POST /users`,
  or seeded via the `bootstrap_user`/`bootstrap_admin` CLI commands for the very first identity in
  a fresh database.
- No multi-tenancy, organization, or team model — `User` is global, scoped only by `role`.
- No hard delete of a user. `DELETE /users/{id}` disables an account (`disabled_at`) and never
  removes the row.
- No login rate limiting or account lockout beyond the constant-time dummy-hash comparison that
  hides whether an email exists.

## Users and scenarios

- **A new deployment's operator** runs `bootstrap_user` (fresh database) or `bootstrap_admin`
  (promote-or-create against an existing one) from the CLI to get the first administrator account,
  since there is no signup route to bootstrap from.
- **An administrator** signs in at `/login`, is redirected to `/`, opens `/users`, and creates a
  new account by filling in the form at `/users/new` (`POST /users`, defaults to role `member`).
  They can change anyone's name, email, or role from `/users/[userId]`, and disable an account
  from the same page; the backend refuses the request if it would leave zero active admins.
- **A member** signs in the same way, cannot reach `/users` (`RequireAdmin` on `GET /users`
  returns 403), but can view and edit their own profile at `/users/[their-id]` because
  `SelfOrAdmin` allows a user to act on their own record; they cannot change their own `role`
  (`UserService.update_user` raises `ForbiddenException` unless the actor is an admin).
- **Any signed-in user's browser**, on access-token expiry, has its next request to `/auth/refresh`
  silently rotate the refresh token and re-issue an access token, invisible to the user, as long
  as the refresh token has not been replayed or the session revoked.
- **Any signed-in user** clicks "Log out" (`features/auth/containers/logout-button.tsx`), which
  revokes the session server-side and clears all three auth cookies.

## Requirements

- Passwords hashed with Argon2id (`app/core/security.py::hash_password`, `argon2-cffi`); a login
  against a nonexistent email still runs a verify against a fixed dummy hash
  (`_DUMMY_PASSWORD_HASH` in `app/services/auth.py`) so the response time does not disclose
  whether the email is registered.
- `users.password_hash` is constrained at the database level to start with `$argon2id$`
  (`CheckConstraint("password_hash LIKE '$argon2id$%'")` in `app/models/user.py`) and
  `users.email_normalized` is constrained to equal `lower(btrim(email))`, with a unique index on
  the normalized column — case-insensitive uniqueness enforced by Postgres, not just application
  code.
- Access tokens are JWTs (`PyJWT`, HS256) carrying `sub` (user id), `sid` (session id), `jti`,
  `iss`/`aud`/`iat`/`nbf`/`exp`, all required on decode (`app/core/security.py`); default lifetime
  900 seconds (`AUTH_ACCESS_TTL_SECONDS`).
- Refresh tokens are opaque (`"{token_id}.{secret}"`), single-use, and stored hashed
  (`AuthRefreshToken.secret_hash`, SHA-256 via `hash_secret`); consuming one issues a successor
  and sets `replaced_by_id`. Presenting an already-consumed or revoked token revokes the whole
  `AuthSession` (`"refresh_replay"`) instead of just failing the one request
  (`AuthService.refresh` in `app/services/auth.py`).
- Three httpOnly-where-appropriate cookies: `app_access` (path `/`), `app_refresh` (path
  `/api/auth`, so it is never sent to non-auth routes), and a JS-readable `app_csrf` used for
  double-submit CSRF on `/auth/refresh` and `/auth/logout` (`app/core/security.py::set_auth_cookies`
  / `check_csrf`). CSRF is verified by comparing the cookie, the `X-CSRF-Token` header, and the
  session's stored hash, all with `secrets.compare_digest`.
- `check_origin` rejects any `Origin` header not in `CORS_ORIGINS` on every auth-context-bearing
  request, ahead of CSRF and refresh logic.
- Role is a two-value enum, `admin`/`member` (`app/models/user.py::UserRole`), stored as a
  Postgres enum in the `iam` schema. `RequireAdmin` gates `GET /users`, `POST /users`, and
  `DELETE /users/{id}`; `SelfOrAdmin` gates `GET /users/{id}` and `PATCH /users/{id}`; only an
  admin actor may set `role` on `PATCH` (`UserService.update_user`).
- Demoting or disabling the last remaining active administrator is rejected with a
  `ValidationException` (`UserService._guard_last_admin_demotion` /
  `_guard_last_admin_disable`, backed by `UserRepository.count_active_admins(for_update=True)`
  to avoid a race under concurrent requests).
- All mutations run inside `transaction(self._session)` from `app/core/transactions.py`; no
  hand-rolled commit/rollback exists in `app/services/auth.py` or `app/services/users.py`.
- `GET /users` returns `PaginatedResponse[UserRead]`; `GET/POST/PATCH /users/{id}` return
  `SuccessResponse[UserRead]`; `POST /auth/login` and `GET /auth/me` return `AuthUserRead` bare,
  the two documented exceptions to the envelope rule (`docs/architecture/backend.md`).
- Frontend: `src/lib/auth/dal.ts::requireUser`/`getCurrentUser` is the actual authorization
  boundary (calls `GET /auth/me` server-side, wrapped in React `cache()`); `src/middleware.ts` only
  performs a cookie-presence redirect and says so in its own comment. Every route under
  `app/(app)/` calls `requireUser()` from its layout (`app/(app)/layout.tsx`).
- Frontend forms (`features/users/containers/create-user-form.tsx`,
  `edit-user-form.tsx`, `features/auth/containers/login-form.tsx`) use react-hook-form + zod +
  `zodResolver`, submit through TanStack Query mutations, and surface backend field errors via
  `applyFieldErrors`. `login-action.ts`/`logout-action.ts` are the only React 19 Actions in this
  vertical, reserved for setting/clearing the httpOnly session cookie.
- `features/users/api/user-mapper.ts::toUser` is the one place a generated `snake_case` DTO field
  is read, converting to the domain `User` type used everywhere else in `features/users`.

## Success metrics

- `uv run pytest` passes with `DATABASE_URL` set, including
  `tests/integration/api/test_error_contract.py` and `tests/integration/api/test_observability.py`
  exercising the auth and users routes end to end.
- `tests/unit/architecture/test_auth_boundaries.py` and `test_user_boundaries.py` pass, proving
  `app/routers/auth.py` and `app/routers/users.py` import no repository, model, or SQLAlchemy
  symbol, and that `AuthServiceDep`/`UserServiceDep` resolve to services with no defaulted
  constructor parameters.
- `uv run alembic check` reports no drift between `User`/`AuthSession`/`AuthRefreshToken` and the
  migration history.
- `npm run test` passes, including
  `features/users/__tests__/users-list-page.test.tsx` and
  `features/auth/__tests__/login-form.test.tsx`.
- Zero findings from `tests/unit/architecture/test_no_comments.py` (backend) and
  `local/no-comments-except-tsdoc` (frontend lint) inside `app/` and `features/{auth,users}/`.
- A fresh `docker compose up --build` followed by `bootstrap_user` produces a working login at
  `http://localhost:3000/login` with no manual database step beyond the migration Compose already
  runs.

## Risks and open questions

- The `/users` link and `/users/new`/`/users/[userId]` routes are not hidden from a signed-in
  member in the frontend; a member who navigates there directly gets a 403 from `GET /users`
  rendered by `app/(app)/users/error.tsx` rather than never seeing the option. Acceptable for a
  template, but a real product built on this should hide the entry points too, not just rely on
  the backend 403.
- There is no login rate limiting or lockout. The dummy-hash comparison hides whether an email
  exists but does not slow down or cap repeated attempts against a known one.
- `AUTH_JWT_SECRET` has no key ID / rotation support — rotating it invalidates every outstanding
  access token at once, with no overlap window.
- Refresh and session TTLs share one setting, `AUTH_SESSION_TTL_SECONDS` (30 days default); a
  refresh token and its parent session always expire together, which may not be the desired shape
  if a future requirement wants "remember me" tokens that outlive the session record they extend.
- No password strength policy is enforced beyond `min_length=1` on `UserCreate.password`
  (`app/schemas/api/users.py`) — deliberately permissive so template consumers set their own bar.

## Rollout

Shipped as the reference vertical from the first commit of this template rather than rolled out
incrementally to an existing user base — there is no prior state to migrate from. `alembic upgrade
head` creates the `iam` schema and its three tables (`users`, `auth_sessions`,
`auth_refresh_tokens`) on first run; `backend/entrypoint.sh` runs that migration automatically
under Docker Compose. The first identity in a new environment comes from `bootstrap_user`
(interactive `getpass` prompt if `--password` is omitted); `bootstrap_admin` exists to promote an
existing account or create an additional admin later with an explicit `--yes` confirmation flag,
distinct from day-zero bootstrap. There is no rollback path other than reverting the migration
before any real account exists — after that, rollback of this vertical means rolling back the
whole application.

## Work breakdown

| Issue | Title | Area | Type | Depends on |
|---|---|---|---|---|
| - | `iam` schema and `User` model with argon2id/email-normalization constraints | backend | feature | - |
| - | `AuthSession` and `AuthRefreshToken` models and migration | backend | feature | `iam` schema and `User` model |
| - | Argon2id hashing, JWT access tokens, opaque refresh-token secrets (`app/core/security.py`) | backend, security | feature | `iam` schema and `User` model |
| - | `AuthService`: login, rotating refresh with replay detection, CSRF check, logout | backend, security | feature | `AuthSession`/`AuthRefreshToken` models and migration; hashing and token helpers |
| - | `UserService`/`UserRepository`: CRUD, RBAC guard, last-admin-standing protection | backend | feature | `iam` schema and `User` model |
| - | `auth`/`users` routers, DI (`RequireAdmin`/`SelfOrAdmin`/`CurrentUser`), response envelopes | backend | feature | `AuthService`; `UserService`/`UserRepository` |
| - | Architecture boundary tests for auth and users routers | backend | chore | `auth`/`users` routers, DI, response envelopes |
| - | `bootstrap_user`/`bootstrap_admin` CLI commands | backend | chore | `UserService`/`UserRepository` |
| - | Frontend auth vertical: login form, session cookies, `dal.ts`, `middleware.ts` | frontend | feature | `auth`/`users` routers, DI, response envelopes |
| - | Frontend users vertical: list/detail/create/edit pages, mapper, forms | frontend | feature | Frontend auth vertical |
| - | `openapi.json` export and orval-generated client/zod schemas for `auth`/`users` | backend, frontend | chore | `auth`/`users` routers, DI, response envelopes |
