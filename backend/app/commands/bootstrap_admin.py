"""Explicitly create or promote an administrator."""

import argparse
import asyncio
import getpass

from app.config import settings
from app.core.database import create_engine, create_session_factory
from app.core.security import hash_password
from app.core.transactions import transaction
from app.models.user import UserRole
from app.repositories.users import UserRepository


async def run(email: str, password: str, *, confirm: bool = False) -> None:
    if not confirm:
        raise ValueError("Explicit confirmation is required")
    if not password:
        raise ValueError("Password cannot be empty")
    engine = create_engine(db_settings=settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            users = UserRepository(session)
            async with transaction(session):
                user = await users.get_by_email(email)
                if user is None:
                    await users.create_bootstrap_user(
                        email=email,
                        password_hash=hash_password(password),
                        role=UserRole.ADMIN,
                    )
                elif user.role is not UserRole.ADMIN:
                    await users.promote_admin(user)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--password")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm creation/promotion explicitly",
    )
    args = parser.parse_args()
    password = args.password or getpass.getpass("Password: ")
    if not args.yes:
        raise SystemExit("Pass --yes to confirm the admin change")
    asyncio.run(run(args.email, password, confirm=True))


if __name__ == "__main__":
    main()
