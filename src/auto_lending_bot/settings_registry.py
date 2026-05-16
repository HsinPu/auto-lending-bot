from dataclasses import dataclass
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


GLOBAL_SETTING_SCOPE = "global"
PROFILE_SETTING_SCOPE = "profile"
PROFILE_SECRET_SETTING_SCOPE = "profile_secret"
PROFILE_SAFETY_SETTING_SCOPE = "profile_safety"


@dataclass(frozen=True)
class SettingDefinition:
    key: str
    category: str
    value_type: str
    default: str
    secret: bool = False
    danger_level: str = "normal"
    hot_reload: bool = True
    description: str = ""
    choices: tuple[str, ...] = ()
    scope: str = PROFILE_SETTING_SCOPE


SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition("BOT_LABEL", "General", "string", "Auto Lending Bot"),
    SettingDefinition(
        "BOT_DRY_RUN", "Safety", "bool", "true", danger_level="high", scope=PROFILE_SAFETY_SETTING_SCOPE
    ),
    SettingDefinition(
        "ALLOW_LIVE_TRADING",
        "Safety",
        "bool",
        "false",
        danger_level="critical",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition(
        "ALLOW_BALANCE_TRANSFERS",
        "Safety",
        "bool",
        "false",
        danger_level="critical",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition("BOT_SLEEP_SECONDS", "General", "int", "60", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("BOT_INACTIVE_SLEEP_SECONDS", "General", "int", "300", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("AUTO_REBALANCE_OPEN_OFFERS", "Operations", "bool", "false"),
    SettingDefinition("AUTO_CANCEL_OPEN_OFFERS", "Operations", "bool", "false", danger_level="high"),
    SettingDefinition("KEEP_STUCK_ORDERS", "Operations", "bool", "true"),
    SettingDefinition("BOT_MAX_LOOPS", "General", "int", "1", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("RETRY_ATTEMPTS", "General", "int", "3", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("RETRY_BACKOFF_SECONDS", "General", "int", "30", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("EXCHANGE", "Exchange", "enum", "mock", choices=("mock", "bitfinex")),
    SettingDefinition(
        "EXCHANGE_API_KEY", "Exchange", "secret", "", secret=True, scope=PROFILE_SECRET_SETTING_SCOPE
    ),
    SettingDefinition(
        "EXCHANGE_API_SECRET", "Exchange", "secret", "", secret=True, scope=PROFILE_SECRET_SETTING_SCOPE
    ),
    SettingDefinition(
        "BITFINEX_ENABLE_LIVE_OFFERS",
        "Safety",
        "bool",
        "false",
        danger_level="critical",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition(
        "BITFINEX_ENABLE_LIVE_TRANSFERS",
        "Safety",
        "bool",
        "false",
        danger_level="critical",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition("HTTP_TIMEOUT_SECONDS", "Exchange", "int", "30", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("OUTPUT_CURRENCY", "General", "string", "BTC"),
    SettingDefinition("DISPLAY_TIMEZONE", "General", "timezone", "UTC", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("TRANSFERABLE_CURRENCIES", "Transfers", "csv", ""),
    SettingDefinition("SMOKE_TEST_CURRENCY", "General", "string", "BTC"),
    SettingDefinition("STRATEGY_DEBUG", "Advanced", "bool", "false"),
    SettingDefinition("MIN_DAILY_RATE", "Strategy", "float", "0.00005"),
    SettingDefinition("MAX_DAILY_RATE", "Strategy", "float", "0.05"),
    SettingDefinition("MIN_LOAN_SIZE", "Strategy", "float", "0.01"),
    SettingDefinition("MAX_PERCENT_TO_LEND", "Strategy", "float", "100"),
    SettingDefinition("MAX_TO_LEND", "Strategy", "optional_float", ""),
    SettingDefinition("MAX_TO_LEND_RATE", "Strategy", "float", "0"),
    SettingDefinition("MAX_AMOUNT_TO_LEND", "Strategy", "optional_float", ""),
    SettingDefinition("MAX_ACTIVE_AMOUNT", "Strategy", "optional_float", ""),
    SettingDefinition(
        "MAX_TOTAL_LEND_AMOUNT",
        "Safety",
        "optional_float",
        "",
        danger_level="high",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition(
        "MAX_SINGLE_OFFER_AMOUNT",
        "Safety",
        "optional_float",
        "",
        danger_level="high",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition(
        "MAX_TOTAL_TRANSFER_AMOUNT",
        "Safety",
        "optional_float",
        "",
        danger_level="critical",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition(
        "MAX_SINGLE_TRANSFER_AMOUNT",
        "Safety",
        "optional_float",
        "",
        danger_level="critical",
        scope=PROFILE_SAFETY_SETTING_SCOPE,
    ),
    SettingDefinition("HIDE_COINS", "Strategy", "bool", "true"),
    SettingDefinition("ALLOW_ABOVE_MARKET_OFFERS", "Strategy", "bool", "true"),
    SettingDefinition("SPREAD_LEND", "Strategy", "int", "0"),
    SettingDefinition("MAX_OFFER_AMOUNT", "Strategy", "optional_float", "500"),
    SettingDefinition("MIN_OFFER_REMAINDER", "Strategy", "float", "100"),
    SettingDefinition(
        "GAP_MODE",
        "Strategy",
        "enum",
        "raw_btc",
        choices=("off", "raw", "relative", "raw_btc", "rawbtc"),
    ),
    SettingDefinition("GAP_BOTTOM", "Strategy", "float", "40"),
    SettingDefinition("GAP_TOP", "Strategy", "float", "200"),
    SettingDefinition("XDAY_THRESHOLD", "Strategy", "float", "0.0005479452054794521"),
    SettingDefinition("XDAYS", "Strategy", "int", "120"),
    SettingDefinition("XDAY_SPREAD", "Strategy", "float", "0"),
    SettingDefinition("END_DATE", "Strategy", "date", ""),
    SettingDefinition("FRR_AS_MIN", "Strategy", "bool", "true"),
    SettingDefinition("FRR_DELTA", "Strategy", "float", "0"),
    SettingDefinition(
        "RATE_OPTIMIZATION_MODE",
        "Strategy",
        "enum",
        "fill_probability",
        choices=("off", "fill_probability"),
    ),
    SettingDefinition("RATE_OPTIMIZATION_MIN_PROBABILITY", "Strategy", "float", "0.10"),
    SettingDefinition("RATE_OPTIMIZATION_SAMPLE_SIZE", "Strategy", "int", "50"),
    SettingDefinition("MARKET_RATE_RETENTION_DAYS", "Market Analysis", "int", "30", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("MARKET_ANALYSIS_RETENTION_DAYS", "Market Analysis", "int", "30", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("MARKET_ANALYSIS_CURRENCIES", "Market Analysis", "csv", ""),
    SettingDefinition("MARKET_ANALYSIS_INTERVAL_SECONDS", "Market Analysis", "int", "60", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("MARKET_ANALYSIS_LEVELS", "Market Analysis", "int", "10", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition("MARKET_ANALYSIS_MIN_SAMPLES", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_MAX_AGE_SECONDS", "Market Analysis", "int", "0", scope=GLOBAL_SETTING_SCOPE),
    SettingDefinition(
        "MARKET_ANALYSIS_METHOD",
        "Market Analysis",
        "enum",
        "off",
        choices=("off", "percentile", "macd"),
    ),
    SettingDefinition("MARKET_ANALYSIS_PERCENTILE", "Market Analysis", "float", "75"),
    SettingDefinition("MARKET_ANALYSIS_MACD_SHORT_SAMPLES", "Market Analysis", "int", "3"),
    SettingDefinition("MARKET_ANALYSIS_MACD_LONG_SAMPLES", "Market Analysis", "int", "10"),
    SettingDefinition("MARKET_ANALYSIS_MACD_SHORT_SECONDS", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_MACD_LONG_SECONDS", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_MULTIPLIER", "Market Analysis", "float", "1.0"),
    SettingDefinition(
        "TELEGRAM_BOT_TOKEN",
        "Notifications",
        "secret",
        "",
        secret=True,
        scope=PROFILE_SECRET_SETTING_SCOPE,
    ),
    SettingDefinition("TELEGRAM_CHAT_ID", "Notifications", "string", ""),
    SettingDefinition("NOTIFY_PREFIX", "Notifications", "string", ""),
    SettingDefinition("NOTIFY_CAUGHT_EXCEPTION", "Notifications", "bool", "false"),
    SettingDefinition("NOTIFY_SUMMARY_MINUTES", "Notifications", "int", "0"),
    SettingDefinition("NOTIFY_XDAY_THRESHOLD", "Notifications", "bool", "false"),
    SettingDefinition(
        "LOG_LEVEL",
        "Advanced",
        "enum",
        "INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        scope=GLOBAL_SETTING_SCOPE,
    ),
)


SETTING_DEFINITIONS_BY_KEY = {definition.key: definition for definition in SETTING_DEFINITIONS}


def setting_schema() -> list[dict[str, object]]:
    return [definition.__dict__ for definition in SETTING_DEFINITIONS]


def setting_scope(key: str) -> str:
    definition = SETTING_DEFINITIONS_BY_KEY.get(key)
    if definition is None:
        return PROFILE_SETTING_SCOPE
    return definition.scope


def validate_setting_value(definition: SettingDefinition, value: str) -> str:
    value = value.strip() if definition.value_type != "string" else value
    if definition.value_type in {"string", "secret", "csv"}:
        return value
    if definition.value_type == "bool":
        if value.lower() not in {"true", "false", "1", "0", "yes", "no", "on", "off"}:
            msg = f"{definition.key} must be a boolean value."
            raise ValueError(msg)
        return value.lower()
    if definition.value_type == "int":
        try:
            int(value)
        except ValueError as error:
            msg = f"{definition.key} must be an integer."
            raise ValueError(msg) from error
        return value
    if definition.value_type == "float":
        try:
            float(value)
        except ValueError as error:
            msg = f"{definition.key} must be a number."
            raise ValueError(msg) from error
        return value
    if definition.value_type == "optional_float":
        if value == "":
            return value
        try:
            float(value)
        except ValueError as error:
            msg = f"{definition.key} must be blank or a number."
            raise ValueError(msg) from error
        return value
    if definition.value_type == "date":
        if value == "":
            return value
        try:
            date.fromisoformat(value)
        except ValueError as error:
            msg = f"{definition.key} must use YYYY-MM-DD format."
            raise ValueError(msg) from error
        return value
    if definition.value_type == "timezone":
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            msg = f"{definition.key} must be a valid IANA timezone, such as UTC or Asia/Taipei."
            raise ValueError(msg) from error
        return value
    if definition.value_type == "enum":
        if definition.choices and value not in definition.choices:
            msg = f"{definition.key} must be one of: {', '.join(definition.choices)}."
            raise ValueError(msg)
        return value

    msg = f"Unsupported setting type for {definition.key}: {definition.value_type}"
    raise ValueError(msg)
