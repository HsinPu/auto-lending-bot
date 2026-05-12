import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from auto_lending_bot.config import sqlite_path_from_url


SCHEMA = """
CREATE TABLE IF NOT EXISTS loan_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    applicant_name TEXT NOT NULL,
    requested_amount INTEGER NOT NULL,
    annual_income INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bot_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS loan_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_run_id INTEGER NOT NULL,
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    daily_rate REAL NOT NULL,
    duration_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    external_offer_id TEXT,
    message TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bot_run_id) REFERENCES bot_runs (id)
);

CREATE TABLE IF NOT EXISTS market_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,
    daily_rate REAL NOT NULL,
    available_amount REAL NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS active_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    daily_rate REAL NOT NULL,
    duration_days INTEGER NOT NULL,
    external_loan_id TEXT,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lending_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_entry_id TEXT NOT NULL,
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    daily_rate REAL NOT NULL,
    duration_days REAL NOT NULL,
    interest REAL NOT NULL,
    fee REAL NOT NULL,
    earned REAL NOT NULL,
    opened_at TEXT,
    closed_at TEXT,
    synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(external_entry_id, currency)
);
"""


def initialize_database(database_url: str) -> None:
    database_path = sqlite_path_from_url(database_url)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        _ensure_column(connection, "bot_runs", "started_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "bot_runs", "status", "TEXT NOT NULL DEFAULT 'unknown'")
        _ensure_column(connection, "bot_runs", "dry_run", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(connection, "bot_runs", "finished_at", "TEXT")
        _ensure_column(connection, "bot_runs", "message", "TEXT")
        _ensure_column(connection, "loan_offers", "external_offer_id", "TEXT")
        _ensure_column(connection, "loan_offers", "message", "TEXT")


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    column_type: str,
) -> None:
    columns = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    if any(column[1] == column_name for column in columns):
        return

    connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


@contextmanager
def connect(database_url: str) -> Iterator[sqlite3.Connection]:
    database_path = sqlite_path_from_url(database_url)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
