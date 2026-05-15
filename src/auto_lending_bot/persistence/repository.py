import json

from auto_lending_bot.domain.models import (
    ActiveLoan,
    LendingHistoryEntry,
    LoanApplication,
    LoanOffer,
    LoanOrder,
)
from auto_lending_bot.persistence.database import connect
from auto_lending_bot.settings_security import decrypt_secret, encrypt_secret, mask_secret
from auto_lending_bot.settings_registry import SETTING_DEFINITIONS_BY_KEY, validate_setting_value


class AppSettingRepository:
    def __init__(self, database_url: str, encryption_key: str = "") -> None:
        self._database_url = database_url
        self._encryption_key = encryption_key

    def get_many(self) -> dict[str, dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT key, value, value_type, is_secret, updated_at
                FROM app_settings
                ORDER BY key
                """
            ).fetchall()
            return {row["key"]: self._public_row(dict(row)) for row in rows}

    def plain_values(self) -> dict[str, str]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT key, value, is_secret
                FROM app_settings
                ORDER BY key
                """
            ).fetchall()
            values = {}
            for row in rows:
                value = str(row["value"])
                if int(row["is_secret"]):
                    value = decrypt_secret(value, self._encryption_key)
                values[str(row["key"])] = value
            return values

    def set_many(self, values: dict[str, str], source: str = "api") -> None:
        with connect(self._database_url) as connection:
            for key, value in values.items():
                definition = SETTING_DEFINITIONS_BY_KEY.get(key)
                if definition is None:
                    msg = f"Unknown setting: {key}"
                    raise ValueError(msg)

                old_row = connection.execute(
                    "SELECT value FROM app_settings WHERE key = ?",
                    (key,),
                ).fetchone()
                old_value = old_row["value"] if old_row is not None else None
                validated_value = validate_setting_value(definition, value)
                stored_value = (
                    encrypt_secret(validated_value, self._encryption_key)
                    if definition.secret
                    else validated_value
                )
                connection.execute(
                    """
                    INSERT INTO app_settings (key, value, value_type, is_secret, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(key) DO UPDATE SET
                        value = excluded.value,
                        value_type = excluded.value_type,
                        is_secret = excluded.is_secret,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (key, stored_value, definition.value_type, int(definition.secret)),
                )
                audit_old_value = "<secret updated>" if definition.secret and old_value else old_value
                audit_new_value = "<secret updated>" if definition.secret else validated_value
                connection.execute(
                    """
                    INSERT INTO app_setting_audit_log (key, old_value, new_value, source)
                    VALUES (?, ?, ?, ?)
                    """,
                    (key, audit_old_value, audit_new_value, source),
                )

    def reset(self, key: str, source: str = "api") -> None:
        with connect(self._database_url) as connection:
            old_row = connection.execute(
                "SELECT value FROM app_settings WHERE key = ?",
                (key,),
            ).fetchone()
            connection.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            connection.execute(
                """
                INSERT INTO app_setting_audit_log (key, old_value, new_value, source)
                VALUES (?, ?, ?, ?)
                """,
                (key, old_row["value"] if old_row is not None else None, None, source),
            )

    def reset_all(self, source: str = "api") -> None:
        for key in list(self.get_many()):
            self.reset(key, source=source)

    def audit_log(self, limit: int = 50) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, key, old_value, new_value, changed_at, source
                FROM app_setting_audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def _public_row(self, row: dict[str, object]) -> dict[str, object]:
        if not int(row["is_secret"]):
            return row
        try:
            plain_value = decrypt_secret(str(row["value"]), self._encryption_key)
        except ValueError:
            plain_value = ""
        row["value"] = mask_secret(plain_value)
        row["is_set"] = bool(plain_value)
        return row


class LoanApplicationRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(self, application: LoanApplication) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO loan_applications (
                    applicant_name,
                    requested_amount,
                    annual_income
                ) VALUES (?, ?, ?)
                """,
                (
                    application.applicant_name,
                    application.requested_amount,
                    application.annual_income,
                ),
            )
            return int(cursor.lastrowid)


class BotRunRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def start(self, dry_run: bool) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_runs (status, dry_run, message)
                VALUES (?, ?, ?)
                """,
                ("running", int(dry_run), ""),
            )
            return int(cursor.lastrowid)

    def finish(self, bot_run_id: int, status: str, message: str = "") -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE bot_runs
                SET finished_at = CURRENT_TIMESTAMP,
                    status = ?,
                    message = ?
                WHERE id = ?
                """,
                (status, message, bot_run_id),
            )

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM bot_runs").fetchone()
            return int(row["count"])

    def latest(self) -> dict[str, object] | None:
        with connect(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT id, started_at, finished_at, status, dry_run, message
                FROM bot_runs
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                return None

            return dict(row)

    def fail_running(self, message: str) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                UPDATE bot_runs
                SET finished_at = CURRENT_TIMESTAMP,
                    status = 'failed',
                    message = ?
                WHERE status = 'running'
                """,
                (message,),
            )
            return int(cursor.rowcount)

    def recent(self, limit: int = 10) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, started_at, finished_at, status, dry_run, message
                FROM bot_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_dry_run_records(self) -> dict[str, int]:
        with connect(self._database_url) as connection:
            dry_run_ids = [
                int(row["id"])
                for row in connection.execute("SELECT id FROM bot_runs WHERE dry_run = 1").fetchall()
            ]
            offer_cursor = connection.execute("DELETE FROM loan_offers WHERE dry_run = 1")
            history_cursor = connection.execute("DELETE FROM lending_history WHERE dry_run = 1")
            if not dry_run_ids:
                return {
                    "deleted_dry_run_offers": int(offer_cursor.rowcount),
                    "deleted_dry_run_lending_history": int(history_cursor.rowcount),
                    "deleted_runs": 0,
                    "deleted_decisions": 0,
                    "deleted_steps": 0,
                }

            placeholders = ",".join("?" for _ in dry_run_ids)
            step_cursor = connection.execute(
                f"DELETE FROM bot_run_steps WHERE bot_run_id IN ({placeholders})",
                dry_run_ids,
            )
            decision_cursor = connection.execute(
                f"DELETE FROM bot_run_decisions WHERE bot_run_id IN ({placeholders})",
                dry_run_ids,
            )
            run_cursor = connection.execute(
                f"DELETE FROM bot_runs WHERE id IN ({placeholders})",
                dry_run_ids,
            )
            return {
                "deleted_dry_run_offers": int(offer_cursor.rowcount),
                "deleted_dry_run_lending_history": int(history_cursor.rowcount),
                "deleted_runs": int(run_cursor.rowcount),
                "deleted_decisions": int(decision_cursor.rowcount),
                "deleted_steps": int(step_cursor.rowcount),
            }


class BotRunDecisionRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(self, decision: dict[str, object]) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_run_decisions (
                    bot_run_id,
                    currency,
                    balance,
                    active_amount,
                    open_offer_amount,
                    best_market_rate,
                    configured_min_daily_rate,
                    suggested_min_daily_rate,
                    effective_min_daily_rate,
                    max_daily_rate,
                    max_to_lend,
                    max_percent_to_lend,
                    max_active_amount,
                    offer_count,
                    offers_json,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision["bot_run_id"],
                    decision["currency"],
                    decision["balance"],
                    decision["active_amount"],
                    decision["open_offer_amount"],
                    decision["best_market_rate"],
                    decision["configured_min_daily_rate"],
                    decision["suggested_min_daily_rate"],
                    decision["effective_min_daily_rate"],
                    decision["max_daily_rate"],
                    decision["max_to_lend"],
                    decision["max_percent_to_lend"],
                    decision["max_active_amount"],
                    decision["offer_count"],
                    json.dumps(decision["offers"], separators=(",", ":")),
                    decision["reason"],
                ),
            )
            return int(cursor.lastrowid)

    def for_run(self, bot_run_id: int) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    bot_run_id,
                    currency,
                    balance,
                    active_amount,
                    open_offer_amount,
                    best_market_rate,
                    configured_min_daily_rate,
                    suggested_min_daily_rate,
                    effective_min_daily_rate,
                    max_daily_rate,
                    max_to_lend,
                    max_percent_to_lend,
                    max_active_amount,
                    offer_count,
                    offers_json,
                    reason,
                    created_at
                FROM bot_run_decisions
                WHERE bot_run_id = ?
                ORDER BY currency
                """,
                (bot_run_id,),
            ).fetchall()
            decisions = []
            for row in rows:
                decision = dict(row)
                decision["offers"] = json.loads(str(decision.pop("offers_json")))
                decisions.append(decision)
            return decisions


class BotRunStepRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def start(self, bot_run_id: int, step_key: str, label: str) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_run_steps (bot_run_id, step_key, label, status, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (bot_run_id, step_key, label, "running", ""),
            )
            return int(cursor.lastrowid)

    def finish(self, step_id: int, status: str = "completed", message: str = "") -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE bot_run_steps
                SET status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    message = ?
                WHERE id = ?
                """,
                (status, message, step_id),
            )

    def record_completed(self, bot_run_id: int, step_key: str, label: str, message: str = "") -> int:
        step_id = self.start(bot_run_id, step_key, label)
        self.finish(step_id, message=message)
        return step_id

    def for_run(self, bot_run_id: int) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, bot_run_id, step_key, label, status, started_at, finished_at, message
                FROM bot_run_steps
                WHERE bot_run_id = ?
                ORDER BY id
                """,
                (bot_run_id,),
            ).fetchall()
            return [dict(row) for row in rows]


class NotificationStateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def get_float(self, key: str) -> float | None:
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT value FROM notification_state WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None

            return float(row["value"])

    def set_float(self, key: str, value: float) -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                INSERT INTO notification_state (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, str(value)),
            )


class LoanOfferRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(self, bot_run_id: int, offer: LoanOffer, status: str, dry_run: bool) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO loan_offers (
                    bot_run_id,
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    status,
                    dry_run,
                    external_offer_id,
                    message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bot_run_id,
                    offer.currency,
                    offer.amount,
                    offer.daily_rate,
                    offer.duration_days,
                    status,
                    int(dry_run),
                    None,
                    "",
                ),
            )
            return int(cursor.lastrowid)

    def update_status(
        self,
        loan_offer_id: int,
        status: str,
        external_offer_id: str | None = None,
        message: str = "",
    ) -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE loan_offers
                SET status = ?,
                    external_offer_id = ?,
                    message = ?
                WHERE id = ?
                """,
                (status, external_offer_id, message, loan_offer_id),
            )

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM loan_offers").fetchone()
            return int(row["count"])

    def count_by_status(self, status: str) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM loan_offers WHERE status = ?",
                (status,),
            ).fetchone()
            return int(row["count"])

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, bot_run_id, currency, amount, daily_rate, duration_days,
                       status, dry_run, external_offer_id, message, created_at
                FROM loan_offers
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

class MarketRateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(self, order: LoanOrder) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO market_rates (currency, daily_rate, available_amount)
                VALUES (?, ?, ?)
                """,
                (order.currency, order.daily_rate, order.amount),
            )
            return int(cursor.lastrowid)

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM market_rates").fetchone()
            return int(row["count"])

    def delete_older_than_days(self, days: int) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                DELETE FROM market_rates
                WHERE captured_at < datetime('now', ?)
                """,
                (f"-{days} days",),
            )
            return int(cursor.rowcount)

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, currency, daily_rate, available_amount, captured_at
                FROM market_rates
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]


class MarketAnalysisRateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add_many(self, orders: list[LoanOrder]) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.executemany(
                """
                INSERT INTO market_analysis_rates (
                    currency,
                    level,
                    daily_rate,
                    available_amount
                ) VALUES (?, ?, ?, ?)
                """,
                [
                    (order.currency, index, order.daily_rate, order.amount)
                    for index, order in enumerate(orders)
                ],
            )
            return int(cursor.rowcount)

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM market_analysis_rates"
            ).fetchone()
            return int(row["count"])

    def delete_older_than_days(self, days: int) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                DELETE FROM market_analysis_rates
                WHERE captured_at < datetime('now', ?)
                """,
                (f"-{days} days",),
            )
            return int(cursor.rowcount)

    def recent(self, limit: int = 50) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, currency, level, daily_rate, available_amount, captured_at
                FROM market_analysis_rates
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def stats_by_currency(self, max_age_seconds: int = 0) -> dict[str, dict[str, object]]:
        stale_expression = "0"
        stale_params: tuple[str, ...] = ()
        if max_age_seconds > 0:
            stale_expression = "MAX(captured_at) < datetime('now', ?)"
            stale_params = (f"-{int(max_age_seconds)} seconds",)

        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    currency,
                    COUNT(*) AS sample_count,
                    SUM(CASE WHEN level = 0 THEN 1 ELSE 0 END) AS top_level_sample_count,
                    MAX(captured_at) AS latest_captured_at,
                    {stale_expression} AS is_stale
                FROM market_analysis_rates
                GROUP BY currency
                ORDER BY currency
                """,
                stale_params,
            ).fetchall()
            return {str(row["currency"]): dict(row) for row in rows}

    def percentile_rate(
        self,
        currency: str,
        percentile: float,
        min_samples: int = 0,
        max_age_seconds: int = 0,
    ) -> float | None:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT daily_rate
                FROM market_analysis_rates
                WHERE currency = ?
                  {_max_age_filter(max_age_seconds)}
                ORDER BY daily_rate
                """,
                (currency.upper(),),
            ).fetchall()
            rates = [float(row["daily_rate"]) for row in rows]
            if len(rates) < max(min_samples, 1):
                return None

            bounded_percentile = min(max(percentile, 0), 100)
            index = round((bounded_percentile / 100) * (len(rates) - 1))
            return rates[index]

    def macd_rate(
        self,
        currency: str,
        short_samples: int,
        long_samples: int,
        multiplier: float = 1.0,
        min_samples: int = 0,
        max_age_seconds: int = 0,
    ) -> float | None:
        sample_count = max(short_samples, long_samples, min_samples, 1)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT daily_rate
                FROM market_analysis_rates
                WHERE currency = ? AND level = 0
                  {_max_age_filter(max_age_seconds)}
                ORDER BY id DESC
                LIMIT ?
                """,
                (currency.upper(), sample_count),
            ).fetchall()
            rates = [float(row["daily_rate"]) for row in rows]
            if len(rates) < sample_count:
                return None

            short_window = rates[: max(short_samples, 1)]
            long_window = rates[: max(long_samples, 1)]
            short_average = sum(short_window) / len(short_window)
            long_average = sum(long_window) / len(long_window)
            return max(short_average, long_average) * multiplier

    def macd_rate_by_seconds(
        self,
        currency: str,
        short_seconds: int,
        long_seconds: int,
        multiplier: float = 1.0,
        min_samples: int = 0,
        max_age_seconds: int = 0,
    ) -> float | None:
        if short_seconds <= 0 or long_seconds <= 0:
            return None

        with connect(self._database_url) as connection:
            short_rates = self._rates_since_seconds(
                connection,
                currency,
                _bounded_seconds(short_seconds, max_age_seconds),
            )
            long_rates = self._rates_since_seconds(
                connection,
                currency,
                _bounded_seconds(long_seconds, max_age_seconds),
            )
            if len(short_rates) < max(min_samples, 1) or len(long_rates) < max(min_samples, 1):
                return None

            short_average = sum(short_rates) / len(short_rates)
            long_average = sum(long_rates) / len(long_rates)
            return max(short_average, long_average) * multiplier

    def recent_top_level_rates(
        self,
        currency: str,
        limit: int,
        max_age_seconds: int = 0,
    ) -> list[float]:
        if limit <= 0:
            return []

        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT daily_rate
                FROM market_analysis_rates
                WHERE currency = ? AND level = 0
                  {_max_age_filter(max_age_seconds)}
                ORDER BY id DESC
                LIMIT ?
                """,
                (currency.upper(), limit),
            ).fetchall()
            return [float(row["daily_rate"]) for row in rows]

    @staticmethod
    def _rates_since_seconds(connection, currency: str, seconds: int) -> list[float]:
        rows = connection.execute(
            """
            SELECT daily_rate
            FROM market_analysis_rates
            WHERE currency = ?
              AND level = 0
              AND captured_at >= datetime('now', ?)
            ORDER BY id DESC
            """,
            (currency.upper(), f"-{seconds} seconds"),
        ).fetchall()
        return [float(row["daily_rate"]) for row in rows]


def _max_age_filter(max_age_seconds: int) -> str:
    if max_age_seconds <= 0:
        return ""

    return f"AND captured_at >= datetime('now', '-{int(max_age_seconds)} seconds')"


def _bounded_seconds(seconds: int, max_age_seconds: int) -> int:
    if max_age_seconds <= 0:
        return seconds

    return min(seconds, max_age_seconds)


class ActiveLoanRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def replace_all(self, active_loans: list[ActiveLoan]) -> None:
        with connect(self._database_url) as connection:
            connection.execute("DELETE FROM active_loans")
            connection.executemany(
                """
                INSERT INTO active_loans (
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    external_loan_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        active_loan.currency,
                        active_loan.amount,
                        active_loan.daily_rate,
                        active_loan.duration_days,
                        active_loan.external_loan_id,
                    )
                    for active_loan in active_loans
                ],
            )

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM active_loans").fetchone()
            return int(row["count"])

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, currency, amount, daily_rate, duration_days,
                       external_loan_id, captured_at
                FROM active_loans
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]


class LendingHistoryRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def upsert_many(self, entries: list[LendingHistoryEntry], dry_run: bool = False, source: str = "exchange") -> int:
        with connect(self._database_url) as connection:
            cursor = connection.executemany(
                """
                INSERT OR REPLACE INTO lending_history (
                    external_entry_id,
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    interest,
                    fee,
                    earned,
                    opened_at,
                    closed_at,
                    dry_run,
                    source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        entry.external_entry_id,
                        entry.currency,
                        entry.amount,
                        entry.daily_rate,
                        entry.duration_days,
                        entry.interest,
                        entry.fee,
                        entry.earned,
                        entry.opened_at,
                        entry.closed_at,
                        int(dry_run),
                        source,
                    )
                    for entry in entries
                ],
            )
            return int(cursor.rowcount)

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM lending_history").fetchone()
            return int(row["count"])

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, external_entry_id, currency, amount, daily_rate, duration_days,
                       interest, fee, earned, opened_at, closed_at, dry_run, source, synced_at
                FROM lending_history
                ORDER BY closed_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def earnings_summary_by_currency(self) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT
                    currency,
                    COALESCE(SUM(CASE WHEN date(closed_at) = date('now') THEN earned END), 0)
                        AS today_earned,
                    COALESCE(SUM(CASE WHEN date(closed_at) = date('now', '-1 day') THEN earned END), 0)
                        AS yesterday_earned,
                    COALESCE(SUM(earned), 0) AS total_earned,
                    dry_run,
                    source
                FROM lending_history
                GROUP BY currency, dry_run, source
                ORDER BY dry_run, currency, source
                """
            ).fetchall()
            return [dict(row) for row in rows]


class OpenLoanOfferRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def replace_all(self, offers: list[LoanOffer]) -> None:
        with connect(self._database_url) as connection:
            connection.execute("DELETE FROM open_loan_offers")
            connection.executemany(
                """
                INSERT INTO open_loan_offers (
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    external_offer_id
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        offer.currency,
                        offer.amount,
                        offer.daily_rate,
                        offer.duration_days,
                        offer.external_offer_id,
                    )
                    for offer in offers
                ],
            )

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM open_loan_offers").fetchone()
            return int(row["count"])

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, currency, amount, daily_rate, duration_days,
                       external_offer_id, captured_at
                FROM open_loan_offers
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
