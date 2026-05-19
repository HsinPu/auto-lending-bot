import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from auto_lending_bot.domain.strategy import StrategyConfig
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext, ensure_default_profile

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - used before dependencies are installed.
    load_dotenv = None


@dataclass(frozen=True)
class Settings:
    allow_live_trading: bool
    allow_balance_transfers: bool
    api_key: str
    api_secret: str
    bitfinex_enable_live_offers: bool
    bitfinex_enable_live_transfers: bool
    bot_label: str
    bot_sleep_seconds: int
    bot_inactive_sleep_seconds: int
    auto_rebalance_open_offers: bool
    auto_cancel_open_offers: bool
    keep_stuck_orders: bool
    dry_run: bool
    exchange: str
    http_timeout_seconds: int
    market_rate_retention_days: int
    market_analysis_retention_days: int
    market_analysis_currencies: tuple[str, ...]
    market_analysis_levels: int
    market_analysis_min_samples: int
    market_analysis_max_age_seconds: int
    market_analysis_method: str
    market_analysis_percentile: float
    market_analysis_macd_short_samples: int
    market_analysis_macd_long_samples: int
    market_analysis_macd_short_seconds: int
    market_analysis_macd_long_seconds: int
    market_analysis_multiplier: float
    max_loops: int
    retry_attempts: int
    retry_backoff_seconds: int
    output_currency: str
    transferable_currencies: tuple[str, ...]
    smoke_test_currency: str
    strategy_debug: bool
    telegram_bot_token: str
    telegram_chat_id: str
    notify_prefix: str
    notify_caught_exception: bool
    notify_summary_minutes: int
    notify_xday_threshold: bool
    hide_coins: bool
    gap_mode: str
    gap_bottom: float
    gap_top: float
    xday_threshold: float
    xdays: int
    xday_spread: float
    frr_as_min: bool
    frr_delta: float
    rate_optimization_mode: str
    rate_optimization_min_probability: float
    rate_optimization_sample_size: int
    max_amount_to_lend: float | None
    max_active_amount: float | None
    max_single_transfer_amount: float | None
    max_single_offer_amount: float | None
    max_total_transfer_amount: float | None
    max_total_lend_amount: float | None
    min_daily_rate: float
    max_daily_rate: float
    min_loan_size: float
    max_percent_to_lend: float
    max_to_lend_rate: float
    end_date: date | None
    spread_lend: int
    database_url: str
    log_level: str
    market_analysis_interval_seconds: int = 60
    display_timezone: str = "UTC"
    allow_above_market_offers: bool = False
    max_offer_amount: float | None = None
    min_offer_remainder: float = 0.0
    min_offer_value_usd: float = 150.0
    lending_risk_level: str = "balanced"
    dynamic_duration_enabled: bool = True
    duration_low_days: int = 2
    duration_medium_daily_rate: float = 0.0002191780821917808
    duration_medium_days: int = 7
    duration_high_daily_rate: float = 0.000410958904109589
    duration_high_days: int = 30
    duration_extreme_daily_rate: float = 0.0006849315068493151
    duration_extreme_days: int = 120


def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv()

    return Settings(
        allow_live_trading=_get_bool("ALLOW_LIVE_TRADING", default=False),
        allow_balance_transfers=_get_bool("ALLOW_BALANCE_TRANSFERS", default=False),
        api_key=os.getenv("EXCHANGE_API_KEY", ""),
        api_secret=os.getenv("EXCHANGE_API_SECRET", ""),
        bitfinex_enable_live_offers=_get_bool("BITFINEX_ENABLE_LIVE_OFFERS", default=False),
        bitfinex_enable_live_transfers=_get_bool(
            "BITFINEX_ENABLE_LIVE_TRANSFERS", default=False
        ),
        bot_label=os.getenv("BOT_LABEL", "Auto Lending Bot"),
        bot_sleep_seconds=_get_int("BOT_SLEEP_SECONDS", default=60),
        bot_inactive_sleep_seconds=_get_int("BOT_INACTIVE_SLEEP_SECONDS", default=300),
        auto_rebalance_open_offers=_get_bool("AUTO_REBALANCE_OPEN_OFFERS", default=False),
        auto_cancel_open_offers=_get_bool("AUTO_CANCEL_OPEN_OFFERS", default=False),
        keep_stuck_orders=_get_bool("KEEP_STUCK_ORDERS", default=True),
        dry_run=_get_bool("BOT_DRY_RUN", default=True),
        exchange=os.getenv("EXCHANGE", "mock"),
        http_timeout_seconds=_get_int("HTTP_TIMEOUT_SECONDS", default=30),
        market_rate_retention_days=_get_int("MARKET_RATE_RETENTION_DAYS", default=30),
        market_analysis_retention_days=_get_int(
            "MARKET_ANALYSIS_RETENTION_DAYS", default=30
        ),
        market_analysis_currencies=_get_csv("MARKET_ANALYSIS_CURRENCIES"),
        market_analysis_interval_seconds=_get_int(
            "MARKET_ANALYSIS_INTERVAL_SECONDS", default=60
        ),
        market_analysis_levels=_get_int("MARKET_ANALYSIS_LEVELS", default=10),
        market_analysis_min_samples=_get_int("MARKET_ANALYSIS_MIN_SAMPLES", default=0),
        market_analysis_max_age_seconds=_get_int(
            "MARKET_ANALYSIS_MAX_AGE_SECONDS", default=0
        ),
        market_analysis_method=os.getenv("MARKET_ANALYSIS_METHOD", "off").lower(),
        market_analysis_percentile=_get_float("MARKET_ANALYSIS_PERCENTILE", default=75.0),
        market_analysis_macd_short_samples=_get_int(
            "MARKET_ANALYSIS_MACD_SHORT_SAMPLES", default=3
        ),
        market_analysis_macd_long_samples=_get_int("MARKET_ANALYSIS_MACD_LONG_SAMPLES", default=10),
        market_analysis_macd_short_seconds=_get_int("MARKET_ANALYSIS_MACD_SHORT_SECONDS", default=0),
        market_analysis_macd_long_seconds=_get_int("MARKET_ANALYSIS_MACD_LONG_SECONDS", default=0),
        market_analysis_multiplier=_get_float("MARKET_ANALYSIS_MULTIPLIER", default=1.0),
        max_loops=_get_int("BOT_MAX_LOOPS", default=1),
        retry_attempts=_get_int("RETRY_ATTEMPTS", default=3),
        retry_backoff_seconds=_get_int("RETRY_BACKOFF_SECONDS", default=30),
        output_currency=os.getenv("OUTPUT_CURRENCY", "BTC").upper(),
        transferable_currencies=_get_csv("TRANSFERABLE_CURRENCIES"),
        smoke_test_currency=os.getenv("SMOKE_TEST_CURRENCY", "BTC"),
        strategy_debug=_get_bool("STRATEGY_DEBUG", default=False),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        notify_prefix=os.getenv("NOTIFY_PREFIX", ""),
        notify_caught_exception=_get_bool("NOTIFY_CAUGHT_EXCEPTION", default=False),
        notify_summary_minutes=_get_int("NOTIFY_SUMMARY_MINUTES", default=0),
        notify_xday_threshold=_get_bool("NOTIFY_XDAY_THRESHOLD", default=False),
        hide_coins=_get_bool("HIDE_COINS", default=True),
        gap_mode=os.getenv("GAP_MODE", "raw_btc"),
        gap_bottom=_get_float("GAP_BOTTOM", default=40.0),
        gap_top=_get_float("GAP_TOP", default=200.0),
        xday_threshold=_get_float("XDAY_THRESHOLD", default=0.0005479452054794521),
        xdays=_get_int("XDAYS", default=120),
        xday_spread=_get_float("XDAY_SPREAD", default=0.0),
        frr_as_min=_get_bool("FRR_AS_MIN", default=False),
        frr_delta=_get_float("FRR_DELTA", default=0.0),
        rate_optimization_mode=os.getenv("RATE_OPTIMIZATION_MODE", "fill_probability").lower(),
        rate_optimization_min_probability=_get_float("RATE_OPTIMIZATION_MIN_PROBABILITY", default=0.10),
        rate_optimization_sample_size=_get_int("RATE_OPTIMIZATION_SAMPLE_SIZE", default=50),
        max_amount_to_lend=_get_optional_float("MAX_TO_LEND")
        if os.getenv("MAX_TO_LEND") is not None
        else _get_optional_float("MAX_AMOUNT_TO_LEND"),
        max_active_amount=_get_optional_float("MAX_ACTIVE_AMOUNT"),
        max_single_transfer_amount=_get_optional_float("MAX_SINGLE_TRANSFER_AMOUNT"),
        max_single_offer_amount=_get_optional_float("MAX_SINGLE_OFFER_AMOUNT", default=0.0),
        max_total_transfer_amount=_get_optional_float("MAX_TOTAL_TRANSFER_AMOUNT"),
        max_total_lend_amount=_get_optional_float("MAX_TOTAL_LEND_AMOUNT", default=0.0),
        min_daily_rate=_get_float("MIN_DAILY_RATE", default=0.00005),
        max_daily_rate=_get_float("MAX_DAILY_RATE", default=0.05),
        min_loan_size=_get_float("MIN_LOAN_SIZE", default=0.01),
        max_percent_to_lend=_get_float("MAX_PERCENT_TO_LEND", default=100.0),
        max_to_lend_rate=_get_float("MAX_TO_LEND_RATE", default=0.0),
        end_date=_get_optional_date("END_DATE"),
        spread_lend=_get_int("SPREAD_LEND", default=0),
        max_offer_amount=_get_optional_float("MAX_OFFER_AMOUNT")
        if os.getenv("MAX_OFFER_AMOUNT") is not None
        else 500.0,
        min_offer_remainder=_get_float("MIN_OFFER_REMAINDER", default=100.0),
        min_offer_value_usd=_get_float("MIN_OFFER_VALUE_USD", default=150.0),
        lending_risk_level=os.getenv("LENDING_RISK_LEVEL", "balanced").lower(),
        dynamic_duration_enabled=_get_bool("DYNAMIC_DURATION_ENABLED", default=True),
        duration_low_days=_get_int("DURATION_LOW_DAYS", default=2),
        duration_medium_daily_rate=_get_float(
            "DURATION_MEDIUM_DAILY_RATE",
            default=0.0002191780821917808,
        ),
        duration_medium_days=_get_int("DURATION_MEDIUM_DAYS", default=7),
        duration_high_daily_rate=_get_float(
            "DURATION_HIGH_DAILY_RATE",
            default=0.000410958904109589,
        ),
        duration_high_days=_get_int("DURATION_HIGH_DAYS", default=30),
        duration_extreme_daily_rate=_get_float(
            "DURATION_EXTREME_DAILY_RATE",
            default=0.0006849315068493151,
        ),
        duration_extreme_days=_get_int("DURATION_EXTREME_DAYS", default=120),
        allow_above_market_offers=_get_bool("ALLOW_ABOVE_MARKET_OFFERS", default=False),
        database_url=os.getenv("DATABASE_URL", "sqlite:///data/auto_lending_bot.db"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        display_timezone=os.getenv("DISPLAY_TIMEZONE", "UTC"),
    )


def load_effective_settings(
    database_url: str | None = None,
    encryption_key: str | None = None,
    profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
) -> Settings:
    ensure_default_profile(profile_context)
    base_settings = load_settings()
    resolved_database_url = database_url or base_settings.database_url
    from auto_lending_bot.persistence.repository import (
        AppSettingRepository,
        ProfileAppSettingRepository,
    )

    try:
        overrides = AppSettingRepository(
            resolved_database_url,
            encryption_key=encryption_key
            if encryption_key is not None
            else settings_encryption_key(),
        ).plain_values()
        profile_overrides = ProfileAppSettingRepository(
            resolved_database_url,
            encryption_key=encryption_key
            if encryption_key is not None
            else settings_encryption_key(),
        ).plain_values(profile_context)
    except sqlite3.OperationalError:
        overrides = {}
        profile_overrides = {}
    overrides.update(profile_overrides)
    with _temporary_environ(overrides):
        return load_settings()


def settings_encryption_key() -> str:
    if load_dotenv is not None:
        load_dotenv()

    return os.getenv("SETTINGS_ENCRYPTION_KEY", "")


def admin_auth_token() -> str:
    if load_dotenv is not None:
        load_dotenv()

    return os.getenv("ADMIN_AUTH_TOKEN", "")


@contextmanager
def _temporary_environ(overrides: dict[str, str]) -> Iterator[None]:
    old_values = {key: os.environ.get(key) for key in overrides}
    try:
        for key, value in overrides.items():
            os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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


def _get_optional_float(name: str, default: float | None = None) -> float | None:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    if raw_value.strip() == "":
        return None

    return float(raw_value)


def _get_csv(name: str) -> tuple[str, ...]:
    raw_value = os.getenv(name, "")
    return tuple(
        value.strip().upper()
        for value in raw_value.split(",")
        if value.strip()
    )


def _get_optional_date(name: str) -> date | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None

    return date.fromisoformat(raw_value)


def strategy_config_for(settings: Settings, currency: str) -> StrategyConfig:
    prefix = currency.upper()
    return StrategyConfig(
        min_daily_rate=_get_float(f"{prefix}_MIN_DAILY_RATE", settings.min_daily_rate),
        max_daily_rate=_get_float(f"{prefix}_MAX_DAILY_RATE", settings.max_daily_rate),
        min_loan_size=_get_float(f"{prefix}_MIN_LOAN_SIZE", settings.min_loan_size),
        spread_lend=_get_int(f"{prefix}_SPREAD_LEND", settings.spread_lend),
        max_offer_amount=_get_optional_float(f"{prefix}_MAX_OFFER_AMOUNT")
        if os.getenv(f"{prefix}_MAX_OFFER_AMOUNT") is not None
        else settings.max_offer_amount,
        min_offer_remainder=_get_float(
            f"{prefix}_MIN_OFFER_REMAINDER",
            settings.min_offer_remainder,
        ),
        gap_mode=os.getenv(f"{prefix}_GAP_MODE", settings.gap_mode),
        gap_bottom=_get_float(f"{prefix}_GAP_BOTTOM", settings.gap_bottom),
        gap_top=_get_float(f"{prefix}_GAP_TOP", settings.gap_top),
        xday_threshold=_get_float(f"{prefix}_XDAY_THRESHOLD", settings.xday_threshold),
        xdays=_get_int(f"{prefix}_XDAYS", settings.xdays),
        xday_spread=_get_float(f"{prefix}_XDAY_SPREAD", settings.xday_spread),
        frr_as_min=_get_bool(f"{prefix}_FRR_AS_MIN", settings.frr_as_min),
        frr_delta=_get_float(f"{prefix}_FRR_DELTA", settings.frr_delta),
        rate_optimization_mode=os.getenv(
            f"{prefix}_RATE_OPTIMIZATION_MODE",
            settings.rate_optimization_mode,
        ).lower(),
        rate_optimization_min_probability=_get_float(
            f"{prefix}_RATE_OPTIMIZATION_MIN_PROBABILITY",
            settings.rate_optimization_min_probability,
        ),
        rate_optimization_sample_size=_get_int(
            f"{prefix}_RATE_OPTIMIZATION_SAMPLE_SIZE",
            settings.rate_optimization_sample_size,
        ),
        max_percent_to_lend=_get_float(
            f"{prefix}_MAX_PERCENT_TO_LEND", settings.max_percent_to_lend
        ),
        max_amount_to_lend=_currency_max_to_lend(prefix, settings),
        max_active_amount=_get_optional_float(f"{prefix}_MAX_ACTIVE_AMOUNT")
        if os.getenv(f"{prefix}_MAX_ACTIVE_AMOUNT") is not None
        else settings.max_active_amount,
        max_to_lend_rate=_get_float(f"{prefix}_MAX_TO_LEND_RATE", settings.max_to_lend_rate),
        end_date=_get_optional_date(f"{prefix}_END_DATE")
        if os.getenv(f"{prefix}_END_DATE") is not None
        else settings.end_date,
        hide_coins=_get_bool(f"{prefix}_HIDE_COINS", settings.hide_coins),
        allow_above_market_offers=_get_bool(
            f"{prefix}_ALLOW_ABOVE_MARKET_OFFERS",
            settings.allow_above_market_offers,
        ),
        min_offer_value_usd=_get_float(
            f"{prefix}_MIN_OFFER_VALUE_USD",
            settings.min_offer_value_usd,
        ),
        lending_risk_level=os.getenv(
            f"{prefix}_LENDING_RISK_LEVEL",
            settings.lending_risk_level,
        ).lower(),
        dynamic_duration_enabled=_get_bool(
            f"{prefix}_DYNAMIC_DURATION_ENABLED",
            settings.dynamic_duration_enabled,
        ),
        duration_low_days=_get_int(f"{prefix}_DURATION_LOW_DAYS", settings.duration_low_days),
        duration_medium_daily_rate=_get_float(
            f"{prefix}_DURATION_MEDIUM_DAILY_RATE",
            settings.duration_medium_daily_rate,
        ),
        duration_medium_days=_get_int(
            f"{prefix}_DURATION_MEDIUM_DAYS",
            settings.duration_medium_days,
        ),
        duration_high_daily_rate=_get_float(
            f"{prefix}_DURATION_HIGH_DAILY_RATE",
            settings.duration_high_daily_rate,
        ),
        duration_high_days=_get_int(f"{prefix}_DURATION_HIGH_DAYS", settings.duration_high_days),
        duration_extreme_daily_rate=_get_float(
            f"{prefix}_DURATION_EXTREME_DAILY_RATE",
            settings.duration_extreme_daily_rate,
        ),
        duration_extreme_days=_get_int(
            f"{prefix}_DURATION_EXTREME_DAYS",
            settings.duration_extreme_days,
        ),
    )


def _currency_max_to_lend(prefix: str, settings: Settings) -> float | None:
    if os.getenv(f"{prefix}_MAX_TO_LEND") is not None:
        return _get_optional_float(f"{prefix}_MAX_TO_LEND")

    if os.getenv(f"{prefix}_MAX_AMOUNT_TO_LEND") is not None:
        return _get_optional_float(f"{prefix}_MAX_AMOUNT_TO_LEND")

    return settings.max_amount_to_lend


def sqlite_path_from_url(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        msg = "Only sqlite:/// database URLs are supported for now."
        raise ValueError(msg)

    return Path(database_url.removeprefix("sqlite:///"))
