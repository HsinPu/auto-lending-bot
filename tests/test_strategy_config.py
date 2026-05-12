from auto_lending_bot.config import load_settings, strategy_config_for


def test_strategy_config_uses_global_settings(monkeypatch) -> None:
    monkeypatch.setenv("MIN_DAILY_RATE", "0.00007")
    monkeypatch.setenv("MAX_PERCENT_TO_LEND", "75")
    monkeypatch.setenv("MAX_TO_LEND", "0.5")
    monkeypatch.setenv("MAX_TO_LEND_RATE", "0.00008")
    monkeypatch.setenv("GAP_MODE", "raw")
    monkeypatch.setenv("GAP_BOTTOM", "10")
    monkeypatch.setenv("GAP_TOP", "50")
    monkeypatch.setenv("XDAY_THRESHOLD", "0.001")
    monkeypatch.setenv("XDAYS", "30")
    monkeypatch.setenv("FRR_AS_MIN", "true")
    monkeypatch.setenv("FRR_DELTA", "0.00001")

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert strategy.min_daily_rate == 0.00007
    assert strategy.max_percent_to_lend == 75
    assert strategy.max_amount_to_lend == 0.5
    assert strategy.max_to_lend_rate == 0.00008
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
    monkeypatch.setenv("BTC_MAX_TO_LEND_RATE", "0.00011")
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
    assert strategy.max_to_lend_rate == 0.00011
    assert strategy.hide_coins is False
    assert strategy.gap_mode == "relative"
    assert strategy.gap_bottom == 20
    assert strategy.xdays == 45
    assert strategy.frr_as_min is True
    assert strategy.frr_delta == 0.00002
