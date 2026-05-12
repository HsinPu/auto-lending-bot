from auto_lending_bot.cli import run_cli
from auto_lending_bot.domain.models import CurrencyBalance, LoanOrder


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
    assert "Latest run: none" in output


def test_cli_run_blocks_live_mode_without_allowance(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("BOT_DRY_RUN", "false")
    monkeypatch.setenv("ALLOW_LIVE_TRADING", "false")

    exit_code = run_cli(["run"])

    assert exit_code == 2
    assert "Safety check failed" in capsys.readouterr().err


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
    def get_lending_balances(self):
        return [CurrencyBalance(currency="BTC", amount=0.1)]

    def get_loan_orders(self, currency: str):
        return [LoanOrder(currency=currency, amount=1.0, daily_rate=0.00008)]

    def get_open_loan_offers(self):
        return []

    def create_loan_offer(self, offer):
        raise AssertionError("smoke-exchange must not create offers")

    def cancel_loan_offer(self, offer_id: str):
        raise AssertionError("smoke-exchange must not cancel offers")
