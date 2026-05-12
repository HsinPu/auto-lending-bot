from auto_lending_bot.cli import run_cli


def test_cli_dashboard_writes_html_report(tmp_path, monkeypatch, capsys) -> None:
    report_path = tmp_path / "dashboard.html"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("REPORT_PATH", str(report_path))

    exit_code = run_cli(["dashboard"])

    assert exit_code == 0
    assert "Wrote dashboard" in capsys.readouterr().out
    report_html = report_path.read_text(encoding="utf-8")
    assert "Auto Lending Bot 儀表板" in report_html
    assert "最近執行紀錄" in report_html
    assert "目前沒有資料" in report_html
