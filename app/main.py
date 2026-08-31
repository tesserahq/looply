import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
import rollbar
from rollbar.logger import RollbarHandler
from rollbar.contrib.fastapi import ReporterMiddleware as RollbarMiddleware
from fastapi_pagination import add_pagination
from fastapi_pagination.utils import disable_installed_extensions_check
from tessera_sdk.server.health import get_livez_readyz_router
from tessera_sdk.server.dependencies.auth import get_current_user
from fastapi.openapi.utils import get_openapi
from app.models.user import User
from .routers import (
    contact,
    contact_list,
    contact_interaction,
    waiting_list,
    stats,
    campaign,
    segment,
    custom_field,
    custom_event,
    event_field_mapping,
    tracked_event_type,
)
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.telemetry import setup_tracing
from app.exceptions.handlers import register_exception_handlers
from app.core.logging_config import get_logger
from app.db import db_manager
from prometheus_fastapi_instrumentator import Instrumentator

SKIP_AUTH_PATHS = ["/livez", "/readyz", "/metrics"]


class EndpointFilter(logging.Filter):
    # Uvicorn endpoint access log filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


def create_app(testing: bool = False, auth_middleware=None) -> FastAPI:
    logger = get_logger()
    settings = get_settings()

    app = FastAPI(redoc_url=None, openapi_url=None)
    if settings.is_production:
        # Initialize Rollbar SDK with your server-side access token
        rollbar.init(settings.rollbar_access_token, environment=settings.environment)

        # Report ERROR and above to Rollbar
        rollbar_handler = RollbarHandler()
        rollbar_handler.setLevel(logging.ERROR)

        # Attach Rollbar handler to the root logger
        logger.addHandler(rollbar_handler)
        app.add_middleware(RollbarMiddleware)

    if not testing and not settings.disable_auth:
        logger.info("Main: Adding authentication middleware")
        from tessera_sdk.server.middleware.authentication import (
            AuthenticationMiddleware,
        )
        from tessera_sdk.server.middleware.user_onboarding import (
            UserOnboardingMiddleware,
        )
        from tessera_sdk.infra.service_factory import create_service_factory
        from app.repositories.user_repository import UserRepository

        # Create repository factory for UserRepository
        user_service_factory = create_service_factory(UserRepository, db_manager)

        app.add_middleware(
            UserOnboardingMiddleware,
            user_service_factory=user_service_factory,
        )
        app.add_middleware(
            AuthenticationMiddleware,
            skip_paths=SKIP_AUTH_PATHS,
            user_service_factory=user_service_factory,
        )
    else:
        logger.info("Main: No authentication middleware")
        if auth_middleware:
            app.add_middleware(auth_middleware)

    # TODO: Restrict this to the allowed origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Puedes restringir esto a dominios específicos
        allow_credentials=True,
        allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
        allow_headers=["*"],  # Permitir todos los headers
    )

    app.include_router(contact.router)
    app.include_router(contact_list.router)
    app.include_router(contact_interaction.router)
    app.include_router(contact_interaction.nested_router)
    app.include_router(waiting_list.router)
    app.include_router(stats.router)
    app.include_router(campaign.router)
    app.include_router(segment.router)
    app.include_router(custom_field.router)
    app.include_router(custom_field.nested_router)
    app.include_router(custom_event.router)
    app.include_router(custom_event.nested_router)
    app.include_router(event_field_mapping.router)
    app.include_router(tracked_event_type.router)

    app.include_router(get_livez_readyz_router())

    register_exception_handlers(app)

    # Add pagination support
    add_pagination(app)
    # A few endpoints (e.g. /contacts/contact-types) paginate a fixed in-memory list rather
    # than a SQLAlchemy query, which would otherwise trigger a spurious "use the sqlalchemy
    # extension" warning on every request.
    disable_installed_extensions_check()

    return app


# Production app instance
app = create_app()

settings = get_settings()
if settings.otel_enabled:
    Instrumentator(
        should_group_status_codes=False,
        excluded_handlers=["^/$", "/livez", "/readyz", "/metrics", "none"],
    ).instrument(app).expose(app)
    tracer_provider = setup_tracing()  # Or use env/config
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    tracer_provider = setup_tracing()  # Or use env/config
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


@app.get("/")
def main_route():
    return {"message": "Hey, It is me Goku"}


@app.get("/openapi.json")
async def openapi(_user: User = Depends(get_current_user)):
    return get_openapi(title="FastAPI", version="0.1.0", routes=app.routes)
