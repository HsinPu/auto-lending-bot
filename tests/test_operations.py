from auto_lending_bot.cli import run_cli


def test_cli_cleanup_runs(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")

    exit_code = run_cli(["cleanup"])

    assert exit_code == 0
    assert (
        "Deleted 0 old market data row(s) (0 market rate, 0 market analysis)."
        in capsys.readouterr().out
    )
