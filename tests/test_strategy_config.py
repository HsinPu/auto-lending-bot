from auto_lending_bot.config import load_settings, strategy_config_for


def test_strategy_config_uses_global_settings(monkeypatch) -> None:
    monkeypatch.setenv("MIN_DAILY_RATE", "0.00007")
    monkeypatch.setenv("MAX_PERCENT_TO_LEND", "75")

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert strategy.min_daily_rate == 0.00007
    assert strategy.max_percent_to_lend == 75


def test_strategy_config_uses_currency_overrides(monkeypatch) -> None:
    monkeypatch.setenv("MIN_DAILY_RATE", "0.00007")
    monkeypatch.setenv("BTC_MIN_DAILY_RATE", "0.00009")
    monkeypatch.setenv("BTC_MAX_AMOUNT_TO_LEND", "0.25")
    monkeypatch.setenv("BTC_HIDE_COINS", "false")

    settings = load_settings()
    strategy = strategy_config_for(settings, "BTC")

    assert strategy.min_daily_rate == 0.00009
    assert strategy.max_amount_to_lend == 0.25
    assert strategy.hide_coins is False
