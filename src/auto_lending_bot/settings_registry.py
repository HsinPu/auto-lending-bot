from dataclasses import dataclass


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


SETTING_DEFINITIONS: tuple[SettingDefinition, ...] = (
    SettingDefinition("BOT_LABEL", "General", "string", "Auto Lending Bot"),
    SettingDefinition("BOT_DRY_RUN", "Safety", "bool", "true", danger_level="high"),
    SettingDefinition("ALLOW_LIVE_TRADING", "Safety", "bool", "false", danger_level="critical"),
    SettingDefinition("ALLOW_BALANCE_TRANSFERS", "Safety", "bool", "false", danger_level="critical"),
    SettingDefinition("BOT_SLEEP_SECONDS", "General", "int", "60"),
    SettingDefinition("BOT_INACTIVE_SLEEP_SECONDS", "General", "int", "300"),
    SettingDefinition("AUTO_REBALANCE_OPEN_OFFERS", "Operations", "bool", "false"),
    SettingDefinition("AUTO_CANCEL_OPEN_OFFERS", "Operations", "bool", "false", danger_level="high"),
    SettingDefinition("KEEP_STUCK_ORDERS", "Operations", "bool", "true"),
    SettingDefinition("BOT_MAX_LOOPS", "General", "int", "1"),
    SettingDefinition("RETRY_ATTEMPTS", "General", "int", "3"),
    SettingDefinition("RETRY_BACKOFF_SECONDS", "General", "int", "30"),
    SettingDefinition("EXCHANGE", "Exchange", "enum", "mock"),
    SettingDefinition("EXCHANGE_API_KEY", "Exchange", "secret", "", secret=True),
    SettingDefinition("EXCHANGE_API_SECRET", "Exchange", "secret", "", secret=True),
    SettingDefinition("BITFINEX_ENABLE_LIVE_OFFERS", "Safety", "bool", "false", danger_level="critical"),
    SettingDefinition("BITFINEX_ENABLE_LIVE_TRANSFERS", "Safety", "bool", "false", danger_level="critical"),
    SettingDefinition("HTTP_TIMEOUT_SECONDS", "Exchange", "int", "30"),
    SettingDefinition("OUTPUT_CURRENCY", "General", "string", "BTC"),
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
    SettingDefinition("MAX_TOTAL_LEND_AMOUNT", "Safety", "optional_float", "", danger_level="high"),
    SettingDefinition("MAX_SINGLE_OFFER_AMOUNT", "Safety", "optional_float", "", danger_level="high"),
    SettingDefinition("MAX_TOTAL_TRANSFER_AMOUNT", "Safety", "optional_float", "", danger_level="critical"),
    SettingDefinition("MAX_SINGLE_TRANSFER_AMOUNT", "Safety", "optional_float", "", danger_level="critical"),
    SettingDefinition("HIDE_COINS", "Strategy", "bool", "true"),
    SettingDefinition("SPREAD_LEND", "Strategy", "int", "3"),
    SettingDefinition("GAP_MODE", "Strategy", "enum", "off"),
    SettingDefinition("GAP_BOTTOM", "Strategy", "float", "0"),
    SettingDefinition("GAP_TOP", "Strategy", "float", "0"),
    SettingDefinition("XDAY_THRESHOLD", "Strategy", "float", "0"),
    SettingDefinition("XDAYS", "Strategy", "int", "2"),
    SettingDefinition("XDAY_SPREAD", "Strategy", "float", "0"),
    SettingDefinition("END_DATE", "Strategy", "date", ""),
    SettingDefinition("FRR_AS_MIN", "Strategy", "bool", "false"),
    SettingDefinition("FRR_DELTA", "Strategy", "float", "0"),
    SettingDefinition("MARKET_RATE_RETENTION_DAYS", "Market Analysis", "int", "30"),
    SettingDefinition("MARKET_ANALYSIS_RETENTION_DAYS", "Market Analysis", "int", "30"),
    SettingDefinition("MARKET_ANALYSIS_CURRENCIES", "Market Analysis", "csv", ""),
    SettingDefinition("MARKET_ANALYSIS_LEVELS", "Market Analysis", "int", "10"),
    SettingDefinition("MARKET_ANALYSIS_MIN_SAMPLES", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_MAX_AGE_SECONDS", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_METHOD", "Market Analysis", "enum", "off"),
    SettingDefinition("MARKET_ANALYSIS_PERCENTILE", "Market Analysis", "float", "75"),
    SettingDefinition("MARKET_ANALYSIS_MACD_SHORT_SAMPLES", "Market Analysis", "int", "3"),
    SettingDefinition("MARKET_ANALYSIS_MACD_LONG_SAMPLES", "Market Analysis", "int", "10"),
    SettingDefinition("MARKET_ANALYSIS_MACD_SHORT_SECONDS", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_MACD_LONG_SECONDS", "Market Analysis", "int", "0"),
    SettingDefinition("MARKET_ANALYSIS_MULTIPLIER", "Market Analysis", "float", "1.0"),
    SettingDefinition("TELEGRAM_BOT_TOKEN", "Notifications", "secret", "", secret=True),
    SettingDefinition("TELEGRAM_CHAT_ID", "Notifications", "string", ""),
    SettingDefinition("NOTIFY_PREFIX", "Notifications", "string", ""),
    SettingDefinition("NOTIFY_CAUGHT_EXCEPTION", "Notifications", "bool", "false"),
    SettingDefinition("NOTIFY_SUMMARY_MINUTES", "Notifications", "int", "0"),
    SettingDefinition("NOTIFY_XDAY_THRESHOLD", "Notifications", "bool", "false"),
    SettingDefinition("LOG_LEVEL", "Advanced", "enum", "INFO"),
)


SETTING_DEFINITIONS_BY_KEY = {definition.key: definition for definition in SETTING_DEFINITIONS}


def setting_schema() -> list[dict[str, object]]:
    return [definition.__dict__ for definition in SETTING_DEFINITIONS]
