from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def transaction(session: AsyncSession) -> AsyncIterator[None]:
    """Run the wrapped block inside the session's transaction boundary.

    Joins an already-open transaction, committing on success and rolling back
    on failure, or opens and owns a new one when none is in flight.
    """
    if not session.in_transaction():
        async with session.begin():
            yield
        return

    try:
        yield
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
