from pathlib import Path

import pytest

from auto_lending_bot.config import sqlite_path_from_url


def test_sqlite_path_from_url() -> None:
    assert sqlite_path_from_url("sqlite:///data/test.db") == Path("data/test.db")


def test_sqlite_path_from_url_rejects_non_sqlite_url() -> None:
    with pytest.raises(ValueError, match="Only sqlite"):
        sqlite_path_from_url("postgresql://localhost/app")
