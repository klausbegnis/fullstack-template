from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import ExceptionHandler

from .config import settings
from .core import (
    REQUEST_ID_HEADER,
    AccessLogMiddleware,
    APIException,
    RequestIDMiddleware,
    api_exception_handler,
    create_engine,
    create_session_factory,
    dispose_engine,
    general_exception_handler,
    get_logger,
    setup_logging,
    validation_exception_handler,
    verify_connection,
)
from .routers import auth_router, health_router, users_router
from .schemas.api.errors import ERROR_RESPONSES

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialize and release shared application resources."""
    setup_logging()
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    logger.info("Debug mode: %s", settings.DEBUG)

    app.state.db_engine = None
    app.state.db_session_factory = None
    try:
        if settings.DATABASE_URL:
            logger.info("Connecting to PostgreSQL")
            app.state.db_engine = create_engine(db_settings=settings)
            await verify_connection(app.state.db_engine)
            app.state.db_session_factory = create_session_factory(app.state.db_engine)
            logger.info("PostgreSQL SQLAlchemy engine ready")
        else:
            logger.warning("Database disabled in explicitly isolated test mode")
        yield
    finally:
        await dispose_engine(getattr(app.state, "db_engine", None))
        app.state.db_engine = None
        app.state.db_session_factory = None
        logger.info("Shutting down")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_exception_handler(APIException, cast(ExceptionHandler, api_exception_handler))
app.add_exception_handler(
    RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
)
app.add_exception_handler(Exception, general_exception_handler)

app.include_router(health_router, responses=ERROR_RESPONSES)
app.include_router(auth_router, responses=ERROR_RESPONSES)
app.include_router(users_router, responses=ERROR_RESPONSES)


@app.get("/")
async def read_root() -> dict[str, str]:
    """Return basic application metadata."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "message": "Hello, World!",
    }
