from auto_lending_bot.config import load_settings, strategy_config_for


def test_strategy_config_uses_global_settings(monkeypatch) -> None:
    monkeypatch.setenv("MIN_DAILY_RATE", "0.00007")
    monkeypatch.setenv("MAX_PERCENT_TO_LEND", "75")
    monkeypatch.setenv("MAX_TO_LEND", "0.5")
    monkeypatch.setenv("MAX_ACTIVE_AMOUNT", "1.5")
    monkeypatch.setenv("MAX_TO_LEND_RATE", "0.00008")
    monkeypatch.setenv("END_DATE", "2027-01-15")
    monkeypatch.setenv("OUTPUT_CURRENCY", "usd")
    monkeypatch.setenv("MARKET_ANALYSIS_METHOD", "percentile")
    monkeypatch.setenv("MARKET_ANALYSIS_PERCENTILE", "80")
    monkeypatch.setenv("MARKET_ANALYSIS_MACD_SHORT_SAMPLES", "4")
    monkeypatch.setenv("MARKET_ANALYSIS_MACD_LONG_SAMPLES", "12")
    monkeypatch.setenv("NOTIFY_SUMMARY_MINUTES", "120")
    monkeypatch.setenv("NOTIFY_XDAY_THRESHOLD", "true")
    monkeypatch.setenv("GAP_MODE", "raw")
    monkeypatch.setenv("GAP_BOTTOM", "10")
    monkeypatch.setenv("GAP_TOP", "50")
    monkeypatch.setenv("XDAY_THRESHOLD", "0.001")
    monkeypatch.setenv("XDAYS", "30")
    monkeypatch.setenv("FRR_AS_MIN", "true")
    monkeypatch.setenv("FRR_DELTA", "0.00001")

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert settings.output_currency == "USD"
    assert settings.market_analysis_method == "percentile"
    assert settings.market_analysis_percentile == 80
    assert settings.market_analysis_macd_short_samples == 4
    assert settings.market_analysis_macd_long_samples == 12
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
