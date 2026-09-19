"""Create the first identity in a fresh database (run explicitly by an operator)."""

import argparse
import asyncio
import getpass

from app.config import settings
from app.core.database import create_engine, create_session_factory
from app.core.security import hash_password
from app.models.user import UserRole
from app.repositories.users import UserRepository


async def run(email: str, password: str, role: UserRole = UserRole.ADMIN) -> None:
    engine = create_engine(db_settings=settings)
    factory = create_session_factory(engine)
    try:
        async with factory() as session:
            await UserRepository(session).create_bootstrap_user(
                email=email,
                password_hash=hash_password(password),
                role=role,
            )
            await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("email")
    parser.add_argument("--password")
    parser.add_argument(
        "--member",
        action="store_true",
        help="Create the user as a member instead of an admin",
    )
    args = parser.parse_args()
    password = args.password or getpass.getpass("Password: ")
    if not password:
        raise SystemExit("Password cannot be empty")
    role = UserRole.MEMBER if args.member else UserRole.ADMIN
    asyncio.run(run(args.email, password, role))


if __name__ == "__main__":
    main()
