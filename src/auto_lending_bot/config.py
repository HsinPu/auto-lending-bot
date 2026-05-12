import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - used before dependencies are installed.
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    allow_live_trading: bool
    bot_label: str
    bot_sleep_seconds: int
    dry_run: bool
    exchange: str
    max_loops: int
    min_daily_rate: float
    min_loan_size: float
    spread_lend: int
    database_url: str
    log_level: str


def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv()

    return Settings(
        allow_live_trading=_get_bool("ALLOW_LIVE_TRADING", default=False),
        bot_label=os.getenv("BOT_LABEL", "Auto Lending Bot"),
        bot_sleep_seconds=_get_int("BOT_SLEEP_SECONDS", default=60),
        dry_run=_get_bool("BOT_DRY_RUN", default=True),
        exchange=os.getenv("EXCHANGE", "mock"),
        max_loops=_get_int("BOT_MAX_LOOPS", default=1),
        min_daily_rate=_get_float("MIN_DAILY_RATE", default=0.00005),
        min_loan_size=_get_float("MIN_LOAN_SIZE", default=0.01),
        spread_lend=_get_int("SPREAD_LEND", default=3),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/auto_lending_bot.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )


def _get_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return int(raw_value)


def _get_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return float(raw_value)


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        msg = "Only sqlite:/// database URLs are supported for now."
        raise ValueError(msg)

    return Path(database_url.removeprefix("sqlite:///"))
