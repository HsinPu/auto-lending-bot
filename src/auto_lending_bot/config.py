import os
from dataclasses import dataclass
from pathlib import Path

from auto_lending_bot.domain.strategy import StrategyConfig

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
    hide_coins: bool
    max_amount_to_lend: float | None
    min_daily_rate: float
    max_daily_rate: float
    min_loan_size: float
    max_percent_to_lend: float
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
        hide_coins=_get_bool("HIDE_COINS", default=True),
        max_amount_to_lend=_get_optional_float("MAX_AMOUNT_TO_LEND"),
        min_daily_rate=_get_float("MIN_DAILY_RATE", default=0.00005),
        max_daily_rate=_get_float("MAX_DAILY_RATE", default=0.05),
        min_loan_size=_get_float("MIN_LOAN_SIZE", default=0.01),
        max_percent_to_lend=_get_float("MAX_PERCENT_TO_LEND", default=100.0),
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


def _get_optional_float(name: str) -> float | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None

    return float(raw_value)


def strategy_config_for(settings: Settings, currency: str) -> StrategyConfig:
    prefix = currency.upper()
    return StrategyConfig(
        min_daily_rate=_get_float(f"{prefix}_MIN_DAILY_RATE", settings.min_daily_rate),
        max_daily_rate=_get_float(f"{prefix}_MAX_DAILY_RATE", settings.max_daily_rate),
        min_loan_size=_get_float(f"{prefix}_MIN_LOAN_SIZE", settings.min_loan_size),
        spread_lend=_get_int(f"{prefix}_SPREAD_LEND", settings.spread_lend),
        max_percent_to_lend=_get_float(
            f"{prefix}_MAX_PERCENT_TO_LEND", settings.max_percent_to_lend
        ),
        max_amount_to_lend=_get_optional_float(f"{prefix}_MAX_AMOUNT_TO_LEND")
        if os.getenv(f"{prefix}_MAX_AMOUNT_TO_LEND") is not None
        else settings.max_amount_to_lend,
        hide_coins=_get_bool(f"{prefix}_HIDE_COINS", settings.hide_coins),
    )


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        msg = "Only sqlite:/// database URLs are supported for now."
        raise ValueError(msg)

    return Path(database_url.removeprefix("sqlite:///"))
