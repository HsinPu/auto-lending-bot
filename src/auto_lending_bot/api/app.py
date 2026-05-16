from fastapi import FastAPI

from auto_lending_bot.api.routes import create_api_router
from auto_lending_bot.config import Settings, load_effective_settings, load_settings
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import BotJobRepository
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or load_effective_settings()
    initialize_database(resolved_settings.database_url)
    BotJobRepository(resolved_settings.database_url).mark_stopping_jobs_stopped(
        "API process restarted while job was stopping."
    )

    app = FastAPI(title="Auto Lending Bot API")
    app.state.settings = resolved_settings
    if settings is None:
        app.include_router(
            create_api_router(
                lambda: load_effective_settings(
                    resolved_settings.database_url,
                    profile_context=DEFAULT_PROFILE_CONTEXT,
                )
            ),
            prefix="/api",
        )
    else:
        app.include_router(create_api_router(resolved_settings), prefix="/api")
    return app
