import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from auto_lending_bot.config import sqlite_path_from_url
from auto_lending_bot.profiles import DEFAULT_PROFILE_ID, DEFAULT_PROFILE_NAME


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
    profile_id TEXT NOT NULL DEFAULT 'default',
    job_id INTEGER,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    status TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    message TEXT,
    FOREIGN KEY (job_id) REFERENCES bot_jobs (id)
);

CREATE TABLE IF NOT EXISTS loan_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    bot_run_id INTEGER NOT NULL,
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    daily_rate REAL NOT NULL,
    duration_days INTEGER NOT NULL,
    status TEXT NOT NULL,
    dry_run INTEGER NOT NULL,
    external_offer_id TEXT,
    message TEXT,
    submitted_at TEXT,
    filled_at TEXT,
    canceled_at TEXT,
    time_to_fill_seconds REAL,
    initial_daily_rate REAL,
    final_status TEXT,
    reprice_count INTEGER NOT NULL DEFAULT 0,
    strategy_snapshot_json TEXT NOT NULL DEFAULT '{}',
    rate_candidate_snapshot_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bot_run_id) REFERENCES bot_runs (id)
);

CREATE TABLE IF NOT EXISTS bot_run_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    bot_run_id INTEGER NOT NULL,
    currency TEXT NOT NULL,
    balance REAL NOT NULL,
    active_amount REAL NOT NULL,
    open_offer_amount REAL NOT NULL,
    best_market_rate REAL NOT NULL,
    configured_min_daily_rate REAL NOT NULL,
    suggested_min_daily_rate REAL,
    effective_min_daily_rate REAL NOT NULL,
    max_daily_rate REAL NOT NULL,
    max_to_lend REAL,
    max_percent_to_lend REAL NOT NULL,
    max_active_amount REAL,
    offer_count INTEGER NOT NULL,
    offers_json TEXT NOT NULL,
    rate_candidates_json TEXT NOT NULL DEFAULT '[]',
    market_regime_json TEXT NOT NULL DEFAULT '{}',
    allocation_mode TEXT NOT NULL DEFAULT '',
    allocation_reason TEXT NOT NULL DEFAULT '',
    stale_reprice_minutes INTEGER,
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (bot_run_id) REFERENCES bot_runs (id)
);

CREATE TABLE IF NOT EXISTS bot_run_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    bot_run_id INTEGER NOT NULL,
    step_key TEXT NOT NULL,
    label TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT,
    message TEXT,
    FOREIGN KEY (bot_run_id) REFERENCES bot_runs (id)
);

CREATE TABLE IF NOT EXISTS market_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    currency TEXT NOT NULL,
    daily_rate REAL NOT NULL,
    available_amount REAL NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS active_loans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    daily_rate REAL NOT NULL,
    duration_days INTEGER NOT NULL,
    external_loan_id TEXT,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lending_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
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
    dry_run INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'exchange',
    synced_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(profile_id, external_entry_id, currency)
);

CREATE TABLE IF NOT EXISTS open_loan_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    currency TEXT NOT NULL,
    amount REAL NOT NULL,
    daily_rate REAL NOT NULL,
    duration_days INTEGER NOT NULL,
    external_offer_id TEXT,
    created_at TEXT,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS market_analysis_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL DEFAULT 'default',
    currency TEXT NOT NULL,
    level INTEGER NOT NULL,
    daily_rate REAL NOT NULL,
    available_amount REAL NOT NULL,
    captured_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notification_state (
    profile_id TEXT NOT NULL DEFAULT 'default',
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, key)
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app_setting_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bot_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    settings_snapshot_json TEXT NOT NULL,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    stopped_at TEXT,
    stop_reason TEXT,
    loops_completed INTEGER NOT NULL DEFAULT 0,
    last_run_id INTEGER,
    last_error TEXT,
    FOREIGN KEY (profile_id) REFERENCES bot_profiles (id)
);

CREATE TABLE IF NOT EXISTS profile_app_settings (
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    value_type TEXT NOT NULL,
    is_secret INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (profile_id, key),
    FOREIGN KEY (profile_id) REFERENCES bot_profiles (id)
);

CREATE TABLE IF NOT EXISTS profile_app_setting_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id TEXT NOT NULL,
    key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source TEXT NOT NULL,
    FOREIGN KEY (profile_id) REFERENCES bot_profiles (id)
);

"""


def initialize_database(database_url: str) -> None:
    database_path = sqlite_path_from_url(database_url)
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.executescript(SCHEMA)
        _seed_default_profile(connection)
        _ensure_profile_column(connection, "bot_runs")
        _ensure_column(connection, "bot_runs", "started_at", "TEXT NOT NULL DEFAULT ''")
        _ensure_column(connection, "bot_runs", "job_id", "INTEGER")
        _ensure_column(connection, "bot_runs", "status", "TEXT NOT NULL DEFAULT 'unknown'")
        _ensure_column(connection, "bot_runs", "dry_run", "INTEGER NOT NULL DEFAULT 1")
        _ensure_column(connection, "bot_runs", "finished_at", "TEXT")
        _ensure_column(connection, "bot_runs", "message", "TEXT")
        _ensure_profile_column(connection, "loan_offers")
        _ensure_column(connection, "loan_offers", "external_offer_id", "TEXT")
        _ensure_column(connection, "loan_offers", "message", "TEXT")
        _ensure_column(connection, "loan_offers", "submitted_at", "TEXT")
        _ensure_column(connection, "loan_offers", "filled_at", "TEXT")
        _ensure_column(connection, "loan_offers", "canceled_at", "TEXT")
        _ensure_column(connection, "loan_offers", "time_to_fill_seconds", "REAL")
        _ensure_column(connection, "loan_offers", "initial_daily_rate", "REAL")
        _ensure_column(connection, "loan_offers", "final_status", "TEXT")
        _ensure_column(connection, "loan_offers", "reprice_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "loan_offers", "strategy_snapshot_json", "TEXT NOT NULL DEFAULT '{}'")
        _ensure_column(connection, "loan_offers", "rate_candidate_snapshot_json", "TEXT NOT NULL DEFAULT '[]'")
        _ensure_profile_column(connection, "bot_run_decisions")
        _ensure_column(
            connection,
            "bot_run_decisions",
            "rate_candidates_json",
            "TEXT NOT NULL DEFAULT '[]'",
        )
        _ensure_column(
            connection,
            "bot_run_decisions",
            "market_regime_json",
            "TEXT NOT NULL DEFAULT '{}'",
        )
        _ensure_column(
            connection,
            "bot_run_decisions",
            "allocation_mode",
            "TEXT NOT NULL DEFAULT ''",
        )
        _ensure_column(
            connection,
            "bot_run_decisions",
            "allocation_reason",
            "TEXT NOT NULL DEFAULT ''",
        )
        _ensure_column(connection, "bot_run_decisions", "stale_reprice_minutes", "INTEGER")
        _ensure_profile_column(connection, "bot_run_steps")
        _ensure_profile_column(connection, "market_rates")
        _ensure_profile_column(connection, "active_loans")
        _ensure_profile_column(connection, "lending_history")
        _ensure_column(connection, "lending_history", "dry_run", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(connection, "lending_history", "source", "TEXT NOT NULL DEFAULT 'exchange'")
        _ensure_profile_column(connection, "open_loan_offers")
        _ensure_column(connection, "open_loan_offers", "created_at", "TEXT")
        _ensure_profile_column(connection, "market_analysis_rates")
        _ensure_profile_column(connection, "notification_state")
        _ensure_runtime_indexes(connection)
        connection.execute(
            """
            UPDATE lending_history
            SET dry_run = 1,
                source = 'mock'
            WHERE external_entry_id LIKE 'mock-%'
            """
        )


def _seed_default_profile(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        INSERT INTO bot_profiles (id, name)
        VALUES (?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (DEFAULT_PROFILE_ID, DEFAULT_PROFILE_NAME),
    )


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


def _ensure_profile_column(connection: sqlite3.Connection, table_name: str) -> None:
    _ensure_column(connection, table_name, "profile_id", "TEXT NOT NULL DEFAULT 'default'")


def _ensure_runtime_indexes(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_bot_runs_profile_started
            ON bot_runs (profile_id, started_at DESC);
        CREATE INDEX IF NOT EXISTS idx_bot_runs_profile_job
            ON bot_runs (profile_id, job_id);
        CREATE INDEX IF NOT EXISTS idx_loan_offers_profile_created
            ON loan_offers (profile_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_bot_run_decisions_profile_run
            ON bot_run_decisions (profile_id, bot_run_id);
        CREATE INDEX IF NOT EXISTS idx_bot_run_steps_profile_run
            ON bot_run_steps (profile_id, bot_run_id);
        CREATE INDEX IF NOT EXISTS idx_market_rates_profile_currency_captured
            ON market_rates (profile_id, currency, captured_at DESC);
        CREATE INDEX IF NOT EXISTS idx_active_loans_profile_captured
            ON active_loans (profile_id, captured_at DESC);
        CREATE INDEX IF NOT EXISTS idx_lending_history_profile_synced
            ON lending_history (profile_id, synced_at DESC);
        CREATE INDEX IF NOT EXISTS idx_open_loan_offers_profile_captured
            ON open_loan_offers (profile_id, captured_at DESC);
        CREATE INDEX IF NOT EXISTS idx_market_analysis_profile_currency_captured
            ON market_analysis_rates (profile_id, currency, captured_at DESC);
        CREATE INDEX IF NOT EXISTS idx_notification_state_profile_key
            ON notification_state (profile_id, key);
        """
    )


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
