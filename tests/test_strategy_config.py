from auto_lending_bot.config import load_effective_settings, load_settings, strategy_config_for
from auto_lending_bot.persistence.database import initialize_database
from auto_lending_bot.persistence.repository import AppSettingRepository


def test_strategy_config_defaults_frr_as_min_enabled(monkeypatch) -> None:
    monkeypatch.delenv("FRR_AS_MIN", raising=False)
    monkeypatch.delenv("GAP_MODE", raising=False)
    monkeypatch.delenv("GAP_BOTTOM", raising=False)
    monkeypatch.delenv("GAP_TOP", raising=False)
    monkeypatch.delenv("XDAY_THRESHOLD", raising=False)
    monkeypatch.delenv("XDAYS", raising=False)
    monkeypatch.delenv("XDAY_SPREAD", raising=False)
    monkeypatch.delenv("RATE_OPTIMIZATION_MODE", raising=False)
    monkeypatch.delenv("RATE_OPTIMIZATION_MIN_PROBABILITY", raising=False)
    monkeypatch.delenv("RATE_OPTIMIZATION_SAMPLE_SIZE", raising=False)

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert settings.frr_as_min is True
    assert strategy.frr_as_min is True
    assert strategy.gap_mode == "raw_btc"
    assert strategy.gap_bottom == 40
    assert strategy.gap_top == 200
    assert strategy.xday_threshold == 0.0005479452054794521
    assert strategy.xdays == 120
    assert strategy.xday_spread == 0
    assert strategy.rate_optimization_mode == "fill_probability"
    assert strategy.rate_optimization_min_probability == 0.25
    assert strategy.rate_optimization_sample_size == 200


def test_strategy_config_uses_global_settings(monkeypatch) -> None:
    monkeypatch.setenv("MIN_DAILY_RATE", "0.00007")
    monkeypatch.setenv("MAX_PERCENT_TO_LEND", "75")
    monkeypatch.setenv("MAX_TO_LEND", "0.5")
    monkeypatch.setenv("MAX_ACTIVE_AMOUNT", "1.5")
    monkeypatch.setenv("MAX_TO_LEND_RATE", "0.00008")
    monkeypatch.setenv("END_DATE", "2027-01-15")
    monkeypatch.setenv("OUTPUT_CURRENCY", "usd")
    monkeypatch.setenv("DISPLAY_TIMEZONE", "Asia/Taipei")
    monkeypatch.setenv("TRANSFERABLE_CURRENCIES", "btc,ACTIVE")
    monkeypatch.setenv("ALLOW_BALANCE_TRANSFERS", "true")
    monkeypatch.setenv("BITFINEX_ENABLE_LIVE_TRANSFERS", "true")
    monkeypatch.setenv("MAX_SINGLE_TRANSFER_AMOUNT", "0.25")
    monkeypatch.setenv("MAX_TOTAL_TRANSFER_AMOUNT", "0.5")
    monkeypatch.setenv("BOT_INACTIVE_SLEEP_SECONDS", "900")
    monkeypatch.setenv("KEEP_STUCK_ORDERS", "false")
    monkeypatch.setenv("MARKET_ANALYSIS_RETENTION_DAYS", "14")
    monkeypatch.setenv("MARKET_ANALYSIS_CURRENCIES", "btc, eth, USDT")
    monkeypatch.setenv("MARKET_ANALYSIS_MIN_SAMPLES", "3")
    monkeypatch.setenv("MARKET_ANALYSIS_MAX_AGE_SECONDS", "900")
    monkeypatch.setenv("MARKET_ANALYSIS_METHOD", "percentile")
    monkeypatch.setenv("MARKET_ANALYSIS_PERCENTILE", "80")
    monkeypatch.setenv("MARKET_ANALYSIS_MACD_SHORT_SAMPLES", "4")
    monkeypatch.setenv("MARKET_ANALYSIS_MACD_LONG_SAMPLES", "12")
    monkeypatch.setenv("MARKET_ANALYSIS_MACD_SHORT_SECONDS", "150")
    monkeypatch.setenv("MARKET_ANALYSIS_MACD_LONG_SECONDS", "1800")
    monkeypatch.setenv("MARKET_ANALYSIS_MULTIPLIER", "1.05")
    monkeypatch.setenv("NOTIFY_PREFIX", "[Bot]")
    monkeypatch.setenv("NOTIFY_CAUGHT_EXCEPTION", "true")
    monkeypatch.setenv("NOTIFY_SUMMARY_MINUTES", "120")
    monkeypatch.setenv("NOTIFY_XDAY_THRESHOLD", "true")
    monkeypatch.setenv("GAP_MODE", "raw")
    monkeypatch.setenv("GAP_BOTTOM", "10")
    monkeypatch.setenv("GAP_TOP", "50")
    monkeypatch.setenv("XDAY_THRESHOLD", "0.001")
    monkeypatch.setenv("XDAYS", "30")
    monkeypatch.setenv("FRR_AS_MIN", "true")
    monkeypatch.setenv("FRR_DELTA", "0.00001")
    monkeypatch.setenv("RATE_OPTIMIZATION_MODE", "off")
    monkeypatch.setenv("RATE_OPTIMIZATION_MIN_PROBABILITY", "0.4")
    monkeypatch.setenv("RATE_OPTIMIZATION_SAMPLE_SIZE", "50")

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert settings.output_currency == "USD"
    assert settings.display_timezone == "Asia/Taipei"
    assert settings.transferable_currencies == ("BTC", "ACTIVE")
    assert settings.allow_balance_transfers is True
    assert settings.bitfinex_enable_live_transfers is True
    assert settings.max_single_transfer_amount == 0.25
    assert settings.max_total_transfer_amount == 0.5
    assert settings.bot_inactive_sleep_seconds == 900
    assert settings.keep_stuck_orders is False
    assert settings.market_analysis_retention_days == 14
    assert settings.market_analysis_currencies == ("BTC", "ETH", "USDT")
    assert settings.market_analysis_min_samples == 3
    assert settings.market_analysis_max_age_seconds == 900
    assert settings.market_analysis_method == "percentile"
    assert settings.market_analysis_percentile == 80
    assert settings.market_analysis_macd_short_samples == 4
    assert settings.market_analysis_macd_long_samples == 12
    assert settings.market_analysis_macd_short_seconds == 150
    assert settings.market_analysis_macd_long_seconds == 1800
    assert settings.market_analysis_multiplier == 1.05
    assert settings.notify_prefix == "[Bot]"
    assert settings.notify_caught_exception is True
    assert settings.notify_summary_minutes == 120
    assert settings.notify_xday_threshold is True
    assert strategy.min_daily_rate == 0.00007
    assert strategy.max_percent_to_lend == 75
    assert strategy.max_amount_to_lend == 0.5
    assert strategy.max_active_amount == 1.5
    assert strategy.max_to_lend_rate == 0.00008
    assert strategy.end_date.isoformat() == "2027-01-15"
    assert strategy.gap_mode == "raw"
    assert strategy.gap_bottom == 10
    assert strategy.gap_top == 50
    assert strategy.xday_threshold == 0.001
    assert strategy.xdays == 30
    assert strategy.frr_as_min is True
    assert strategy.frr_delta == 0.00001
    assert strategy.rate_optimization_mode == "off"
    assert strategy.rate_optimization_min_probability == 0.4
    assert strategy.rate_optimization_sample_size == 50


def test_strategy_config_uses_currency_overrides(monkeypatch) -> None:
    monkeypatch.setenv("MIN_DAILY_RATE", "0.00007")
    monkeypatch.setenv("BTC_MIN_DAILY_RATE", "0.00009")
    monkeypatch.setenv("BTC_MIN_LOAN_SIZE", "0.02")
    monkeypatch.setenv("BTC_MAX_AMOUNT_TO_LEND", "0.25")
    monkeypatch.setenv("BTC_MAX_ACTIVE_AMOUNT", "0.75")
    monkeypatch.setenv("BTC_MAX_TO_LEND_RATE", "0.00011")
    monkeypatch.setenv("BTC_END_DATE", "2027-02-20")
    monkeypatch.setenv("BTC_HIDE_COINS", "false")
    monkeypatch.setenv("BTC_GAP_MODE", "relative")
    monkeypatch.setenv("BTC_GAP_BOTTOM", "20")
    monkeypatch.setenv("BTC_XDAYS", "45")
    monkeypatch.setenv("BTC_FRR_AS_MIN", "true")
    monkeypatch.setenv("BTC_FRR_DELTA", "0.00002")

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert strategy.min_daily_rate == 0.00009
    assert strategy.min_loan_size == 0.02
    assert strategy.max_amount_to_lend == 0.25
    assert strategy.max_active_amount == 0.75
    assert strategy.max_to_lend_rate == 0.00011
    assert strategy.end_date.isoformat() == "2027-02-20"
    assert strategy.hide_coins is False
    assert strategy.gap_mode == "relative"
    assert strategy.gap_bottom == 20
    assert strategy.xdays == 45
    assert strategy.frr_as_min is True
    assert strategy.frr_delta == 0.00002


def test_load_effective_settings_uses_database_overrides(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BOT_LABEL", "Env Bot")
    initialize_database(database_url)
    AppSettingRepository(database_url).set_many(
        {"BOT_LABEL": "DB Bot", "DISPLAY_TIMEZONE": "Asia/Taipei"}
    )

    settings = load_effective_settings(database_url)

    assert settings.bot_label == "DB Bot"
    assert settings.display_timezone == "Asia/Taipei"
