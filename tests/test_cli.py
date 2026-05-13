from auto_lending_bot.cli import run_cli
from auto_lending_bot.domain.models import CurrencyBalance, LoanOffer, LoanOrder
from auto_lending_bot.persistence.repository import AppSettingRepository


def test_cli_init_db_creates_database(tmp_path, monkeypatch, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)

    exit_code = run_cli(["init-db"])

    assert exit_code == 0
    assert "Initialized database" in capsys.readouterr().out
    assert (tmp_path / "test.db").exists()


def test_cli_status_prints_counts(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    exit_code = run_cli(["status"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Exchange: mock" in output
    assert "Bot runs: 0" in output
    assert "Open loan offers: 0" in output
    assert "Active loans: 0" in output
    assert "Lending history: 0" in output
    assert "Latest run: none" in output


def test_cli_sync_history_writes_lending_history(tmp_path, monkeypatch, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("EXCHANGE", "mock")

    exit_code = run_cli(["sync-history"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Synced 1 lending history row(s) for BTC." in output


def test_cli_sync_open_offers_writes_snapshot(tmp_path, monkeypatch, capsys) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("EXCHANGE", "mock")
    exchange = FakeExchange()
    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", lambda settings: exchange)

    exit_code = run_cli(["sync-open-offers"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Synced 1 open loan offer row(s)." in output


def test_cli_cancel_open_offers_dry_run_does_not_cancel(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("EXCHANGE", "mock")
    exchange = FakeExchange()
    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", lambda settings: exchange)

    exit_code = run_cli(["cancel-open-offers"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Dry run: would cancel 1 open loan offer(s)." in output
    assert exchange.canceled_offer_ids == []


def test_cli_record_market_analysis_writes_rows(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("EXCHANGE", "mock")
    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", lambda settings: FakeExchange())

    exit_code = run_cli(["record-market-analysis", "--currency", "BTC", "--levels", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded 1 market analysis rate row(s) for BTC." in output


def test_cli_record_market_analysis_uses_configured_currencies(
    tmp_path, monkeypatch, capsys
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("EXCHANGE", "mock")
    monkeypatch.setenv("MARKET_ANALYSIS_CURRENCIES", "BTC,ETH")
    monkeypatch.setattr(
        "auto_lending_bot.cli.create_exchange_client",
        lambda settings: FakeExchange(),
    )

    exit_code = run_cli(["record-market-analysis", "--levels", "1"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Recorded 2 market analysis rate row(s) for BTC, ETH." in output


def test_cli_cleanup_reports_market_data_counts(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    exit_code = run_cli(["cleanup"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Deleted 0 old market data row(s) (0 market rate, 0 market analysis)." in output


def test_cli_transfer_preview_reports_matching_balances(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("EXCHANGE", "mock")
    monkeypatch.setenv("TRANSFERABLE_CURRENCIES", "BTC")
    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", lambda settings: FakeExchange())

    exit_code = run_cli(["transfer-preview"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Would transfer 0.25 BTC from exchange to lending." in output


def test_cli_transfer_funds_dry_run_does_not_transfer(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("EXCHANGE", "mock")
    monkeypatch.setenv("TRANSFERABLE_CURRENCIES", "BTC")
    exchange = FakeExchange()
    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", lambda settings: exchange)

    exit_code = run_cli(["transfer-funds"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Dry run: would transfer 1 balance(s)." in output
    assert exchange.transfer_calls == []


def test_cli_run_blocks_live_mode_without_allowance(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("BOT_DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "false")

    exit_code = run_cli(["run"])

    assert exit_code == 2
    assert "Safety check failed" in capsys.readouterr().err


def test_cli_run_reloads_database_settings_between_loops(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BOT_MAX_LOOPS", "2")
    monkeypatch.setenv("BOT_SLEEP_SECONDS", "0")
    monkeypatch.setenv("BOT_INACTIVE_SLEEP_SECONDS", "0")
    seen_labels = []
    reloaded = False

    def create_exchange(settings):
        seen_labels.append(settings.bot_label)
        return ReloadingExchange()

    class ReloadingExchange(FakeExchange):
        def get_lending_balances(self):
            nonlocal reloaded
            if not reloaded:
                AppSettingRepository(database_url).set_many({"BOT_LABEL": "Reloaded Bot"})
                reloaded = True
            return super().get_lending_balances()

    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", create_exchange)

    exit_code = run_cli(["run"])

    assert exit_code == 0
    assert seen_labels == ["Auto Lending Bot", "Reloaded Bot"]


def test_cli_smoke_exchange_prints_read_only_summary(monkeypatch, capsys) -> None:
    monkeypatch.setenv("EXCHANGE", "mock")
    monkeypatch.setattr("auto_lending_bot.cli.create_exchange_client", lambda settings: FakeExchange())

    exit_code = run_cli(["smoke-exchange"])

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "Exchange: mock" in output
    assert "Lending balances: 1" in output
    assert "Loan orders: 1" in output
    assert "Best daily rate: 0.00008000" in output


class FakeExchange:
    def __init__(self) -> None:
        self.canceled_offer_ids = []
        self.transfer_calls = []

    def get_lending_balances(self):
        return [CurrencyBalance(currency="BTC", amount=0.1)]

    def get_exchange_balances(self):
        return [
            CurrencyBalance(currency="BTC", amount=0.25),
            CurrencyBalance(currency="ETH", amount=1.0),
        ]

    def get_loan_orders(self, currency: str):
        return [LoanOrder(currency=currency, amount=1.0, daily_rate=0.00008)]

    def get_open_loan_offers(self):
        return [
            LoanOffer(
                currency="BTC",
                amount=0.1,
                daily_rate=0.00008,
                duration_days=2,
                external_offer_id="offer-1",
            )
        ]

    def get_active_loans(self):
        return []

    def get_lending_history(self, currency: str, limit: int = 500):
        return []

    def create_loan_offer(self, offer):
        raise AssertionError("smoke-exchange must not create offers")

    def cancel_loan_offer(self, offer_id: str):
        self.canceled_offer_ids.append(offer_id)

    def transfer_to_lending(self, currency: str, amount: float):
        self.transfer_calls.append((currency, amount))
        return "transfer-1"
