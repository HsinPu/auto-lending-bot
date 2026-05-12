from auto_lending_bot.cli import run_cli
from auto_lending_bot.domain.models import LoanOffer
from auto_lending_bot.persistence.repository import BotRunRepository, LoanOfferRepository


def test_cli_dashboard_writes_html_report(tmp_path, monkeypatch, capsys) -> None:
    report_path = tmp_path / "dashboard.html"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("REPORT_PATH", str(report_path))

    exit_code = run_cli(["dashboard"])

    assert exit_code == 0
    assert "Wrote dashboard" in capsys.readouterr().out
    report_html = report_path.read_text(encoding="utf-8")
    assert "Auto Lending Bot 儀表板" in report_html
    assert "產生時間" in report_html
    assert "模式：<span class=\"badge\">模擬模式</span>" in report_html
    assert "最新執行狀態：尚無執行紀錄" in report_html
    assert "最近執行紀錄" in report_html
    assert "目前沒有資料" in report_html


def test_cli_dashboard_highlights_latest_run_and_failed_offers(
    tmp_path,
    monkeypatch,
) -> None:
    report_path = tmp_path / "dashboard.html"
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("REPORT_PATH", str(report_path))
    monkeypatch.setenv("BOT_DRY_RUN", "false")

    assert run_cli(["init-db"]) == 0
    bot_run_id = BotRunRepository(database_url).start(dry_run=False)
    BotRunRepository(database_url).finish(bot_run_id, "completed")
    loan_offer_id = LoanOfferRepository(database_url).add(
        bot_run_id,
        LoanOffer(currency="BTC", amount=0.1, daily_rate=0.0001, duration_days=2),
        status="intent",
        dry_run=False,
    )
    LoanOfferRepository(database_url).update_status(
        loan_offer_id,
        "failed",
        message="test failure",
    )

    assert run_cli(["dashboard"]) == 0

    report_html = report_path.read_text(encoding="utf-8")
    assert "模式：<span class=\"badge live\">Live 模式</span>" in report_html
    assert f"最新執行狀態：#{bot_run_id} completed（模擬模式：否）" in report_html
    assert "警示：目前有 1 筆失敗貸出委託" in report_html
