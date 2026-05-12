from auto_lending_bot.cli import run_cli


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
