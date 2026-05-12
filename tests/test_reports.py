from auto_lending_bot.cli import run_cli


def test_cli_dashboard_writes_html_report(tmp_path, monkeypatch, capsys) -> None:
    report_path = tmp_path / "dashboard.html"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("REPORT_PATH", str(report_path))

    exit_code = run_cli(["dashboard"])

    assert exit_code == 0
    assert "Wrote dashboard" in capsys.readouterr().out
    assert "Auto Lending Bot Dashboard" in report_path.read_text(encoding="utf-8")
