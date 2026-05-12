from fastapi import FastAPI

from auto_lending_bot.api.routes import create_api_router
from auto_lending_bot.config import Settings, load_settings
from auto_lending_bot.persistence.database import initialize_database


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or load_settings()
    initialize_database(resolved_settings.database_url)

    app = FastAPI(title="Auto Lending Bot API")
    app.state.settings = resolved_settings
    app.include_router(create_api_router(resolved_settings), prefix="/api")
    return app
