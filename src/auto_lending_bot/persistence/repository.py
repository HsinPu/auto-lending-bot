import json

from auto_lending_bot.domain.models import (
    ActiveLoan,
    LendingHistoryEntry,
    LoanApplication,
    LoanOffer,
    LoanOrder,
)
from auto_lending_bot.persistence.database import connect
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext, ensure_default_profile
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


class ProfileAppSettingRepository:
    def __init__(self, database_url: str, encryption_key: str = "") -> None:
        self._database_url = database_url
        self._encryption_key = encryption_key

    def get_many(
        self,
        profile_context: BotProfileContext,
    ) -> dict[str, dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT profile_id, key, value, value_type, is_secret, updated_at
                FROM profile_app_settings
                WHERE profile_id = ?
                ORDER BY key
                """,
                (profile_context.id,),
            ).fetchall()
            return {row["key"]: self._public_row(dict(row)) for row in rows}

    def plain_values(self, profile_context: BotProfileContext) -> dict[str, str]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT key, value, is_secret
                FROM profile_app_settings
                WHERE profile_id = ?
                ORDER BY key
                """,
                (profile_context.id,),
            ).fetchall()
            values = {}
            for row in rows:
                value = str(row["value"])
                if int(row["is_secret"]):
                    value = decrypt_secret(value, self._encryption_key)
                values[str(row["key"])] = value
            return values

    def set_many(
        self,
        profile_context: BotProfileContext,
        values: dict[str, str],
        source: str = "api",
    ) -> None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            for key, value in values.items():
                definition = SETTING_DEFINITIONS_BY_KEY.get(key)
                if definition is None:
                    msg = f"Unknown setting: {key}"
                    raise ValueError(msg)

                old_row = connection.execute(
                    """
                    SELECT value
                    FROM profile_app_settings
                    WHERE profile_id = ? AND key = ?
                    """,
                    (profile_context.id, key),
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
                    INSERT INTO profile_app_settings (
                        profile_id, key, value, value_type, is_secret, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(profile_id, key) DO UPDATE SET
                        value = excluded.value,
                        value_type = excluded.value_type,
                        is_secret = excluded.is_secret,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        profile_context.id,
                        key,
                        stored_value,
                        definition.value_type,
                        int(definition.secret),
                    ),
                )
                audit_old_value = (
                    "<secret updated>" if definition.secret and old_value else old_value
                )
                audit_new_value = "<secret updated>" if definition.secret else validated_value
                connection.execute(
                    """
                    INSERT INTO profile_app_setting_audit_log (
                        profile_id, key, old_value, new_value, source
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (profile_context.id, key, audit_old_value, audit_new_value, source),
                )

    def reset(self, profile_context: BotProfileContext, key: str, source: str = "api") -> None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            old_row = connection.execute(
                """
                SELECT value
                FROM profile_app_settings
                WHERE profile_id = ? AND key = ?
                """,
                (profile_context.id, key),
            ).fetchone()
            connection.execute(
                "DELETE FROM profile_app_settings WHERE profile_id = ? AND key = ?",
                (profile_context.id, key),
            )
            connection.execute(
                """
                INSERT INTO profile_app_setting_audit_log (
                    profile_id, key, old_value, new_value, source
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    profile_context.id,
                    key,
                    old_row["value"] if old_row is not None else None,
                    None,
                    source,
                ),
            )

    def reset_all(self, profile_context: BotProfileContext, source: str = "api") -> None:
        for key in list(self.get_many(profile_context)):
            self.reset(profile_context, key, source=source)

    def audit_log(
        self,
        profile_context: BotProfileContext,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, key, old_value, new_value, changed_at, source
                FROM profile_app_setting_audit_log
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
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

    def start(
        self,
        dry_run: bool,
        job_id: int | None = None,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_runs (profile_id, job_id, status, dry_run, message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (profile_context.id, job_id, "running", int(dry_run), ""),
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

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM bot_runs WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def latest(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> dict[str, object] | None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT id, profile_id, job_id, started_at, finished_at, status, dry_run, message
                FROM bot_runs
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (profile_context.id,),
            ).fetchone()

            if row is None:
                return None

            return dict(row)

    def latest_for_job(
        self,
        job_id: int,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> dict[str, object] | None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT id, profile_id, job_id, started_at, finished_at, status, dry_run, message
                FROM bot_runs
                WHERE profile_id = ? AND job_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (profile_context.id, job_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def fail_running(
        self,
        message: str,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                UPDATE bot_runs
                SET finished_at = CURRENT_TIMESTAMP,
                    status = 'failed',
                    message = ?
                WHERE profile_id = ? AND status = 'running'
                """,
                (message, profile_context.id),
            )
            return int(cursor.rowcount)

    def recent(
        self,
        limit: int = 10,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, job_id, started_at, finished_at, status, dry_run, message
                FROM bot_runs
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_dry_run_records(
        self,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> dict[str, int]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            dry_run_ids = [
                int(row["id"])
                for row in connection.execute(
                    "SELECT id FROM bot_runs WHERE profile_id = ? AND dry_run = 1",
                    (profile_context.id,),
                ).fetchall()
            ]
            offer_cursor = connection.execute(
                "DELETE FROM loan_offers WHERE profile_id = ? AND dry_run = 1",
                (profile_context.id,),
            )
            history_cursor = connection.execute(
                "DELETE FROM lending_history WHERE profile_id = ? AND dry_run = 1",
                (profile_context.id,),
            )
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
                f"DELETE FROM bot_run_steps WHERE profile_id = ? AND bot_run_id IN ({placeholders})",
                (profile_context.id, *dry_run_ids),
            )
            decision_cursor = connection.execute(
                f"DELETE FROM bot_run_decisions WHERE profile_id = ? AND bot_run_id IN ({placeholders})",
                (profile_context.id, *dry_run_ids),
            )
            run_cursor = connection.execute(
                f"DELETE FROM bot_runs WHERE profile_id = ? AND id IN ({placeholders})",
                (profile_context.id, *dry_run_ids),
            )
            return {
                "deleted_dry_run_offers": int(offer_cursor.rowcount),
                "deleted_dry_run_lending_history": int(history_cursor.rowcount),
                "deleted_runs": int(run_cursor.rowcount),
                "deleted_decisions": int(decision_cursor.rowcount),
                "deleted_steps": int(step_cursor.rowcount),
            }


class BotJobRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def create(
        self,
        profile_context: BotProfileContext,
        settings_snapshot_json: str,
        mode: str = "loop",
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_jobs (profile_id, status, mode, settings_snapshot_json)
                VALUES (?, ?, ?, ?)
                """,
                (profile_context.id, "running", mode, settings_snapshot_json),
            )
            return int(cursor.lastrowid)

    def get(self, bot_job_id: int) -> dict[str, object] | None:
        with connect(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT id, profile_id, status, mode, settings_snapshot_json,
                       started_at, stopped_at, stop_reason, loops_completed,
                       last_run_id, last_error
                FROM bot_jobs
                WHERE id = ?
                """,
                (bot_job_id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def latest_running(self, profile_context: BotProfileContext) -> dict[str, object] | None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT id, profile_id, status, mode, settings_snapshot_json,
                       started_at, stopped_at, stop_reason, loops_completed,
                       last_run_id, last_error
                FROM bot_jobs
                WHERE profile_id = ? AND status IN ('running', 'stopping')
                ORDER BY id DESC
                LIMIT 1
                """,
                (profile_context.id,),
            ).fetchone()
            return dict(row) if row is not None else None

    def running(self, profile_context: BotProfileContext) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, status, mode, settings_snapshot_json,
                       started_at, stopped_at, stop_reason, loops_completed,
                       last_run_id, last_error
                FROM bot_jobs
                WHERE profile_id = ? AND status = 'running'
                ORDER BY id DESC
                """,
                (profile_context.id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def recent(self, profile_context: BotProfileContext, limit: int = 10) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, status, mode, settings_snapshot_json,
                       started_at, stopped_at, stop_reason, loops_completed,
                       last_run_id, last_error
                FROM bot_jobs
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_stopping(self, bot_job_id: int, stop_reason: str = "stop requested") -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE bot_jobs
                SET status = 'stopping',
                    stop_reason = ?
                WHERE id = ? AND status = 'running'
                """,
                (stop_reason, bot_job_id),
            )

    def mark_stopped(self, bot_job_id: int, stop_reason: str = "stopped") -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE bot_jobs
                SET status = 'stopped',
                    stopped_at = CURRENT_TIMESTAMP,
                    stop_reason = COALESCE(stop_reason, ?)
                WHERE id = ? AND status IN ('running', 'stopping')
                """,
                (stop_reason, bot_job_id),
            )

    def mark_failed(self, bot_job_id: int, error: str) -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE bot_jobs
                SET status = 'failed',
                    stopped_at = CURRENT_TIMESTAMP,
                    last_error = ?
                WHERE id = ?
                """,
                (error, bot_job_id),
            )

    def record_loop(
        self,
        bot_job_id: int,
        loops_completed: int,
        last_run_id: int | None,
        last_error: str | None = None,
    ) -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE bot_jobs
                SET loops_completed = ?,
                    last_run_id = ?,
                    last_error = ?
                WHERE id = ?
                """,
                (loops_completed, last_run_id, last_error, bot_job_id),
            )

    def mark_stopping_jobs_stopped(self, stop_reason: str) -> int:
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                UPDATE bot_jobs
                SET status = 'stopped',
                    stopped_at = CURRENT_TIMESTAMP,
                    stop_reason = COALESCE(stop_reason, ?)
                WHERE status = 'stopping'
                """,
                (stop_reason,),
            )
            return int(cursor.rowcount)


class BotRunDecisionRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(
        self,
        decision: dict[str, object],
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_run_decisions (
                    profile_id,
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
                    rate_candidates_json,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_context.id,
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
                    json.dumps(decision.get("rate_candidates", []), separators=(",", ":")),
                    decision["reason"],
                ),
            )
            return int(cursor.lastrowid)

    def for_run(
        self,
        bot_run_id: int,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT
                    id,
                    profile_id,
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
                    rate_candidates_json,
                    reason,
                    created_at
                FROM bot_run_decisions
                WHERE profile_id = ? AND bot_run_id = ?
                ORDER BY currency
                """,
                (profile_context.id, bot_run_id),
            ).fetchall()
            decisions = []
            for row in rows:
                decision = dict(row)
                decision["offers"] = json.loads(str(decision.pop("offers_json")))
                decision["rate_candidates"] = json.loads(str(decision.pop("rate_candidates_json", "[]")))
                decisions.append(decision)
            return decisions


class BotRunStepRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def start(
        self,
        bot_run_id: int,
        step_key: str,
        label: str,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO bot_run_steps (profile_id, bot_run_id, step_key, label, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (profile_context.id, bot_run_id, step_key, label, "running", ""),
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

    def record_completed(
        self,
        bot_run_id: int,
        step_key: str,
        label: str,
        message: str = "",
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        step_id = self.start(bot_run_id, step_key, label, profile_context=profile_context)
        self.finish(step_id, message=message)
        return step_id

    def for_run(
        self,
        bot_run_id: int,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, bot_run_id, step_key, label, status, started_at, finished_at, message
                FROM bot_run_steps
                WHERE profile_id = ? AND bot_run_id = ?
                ORDER BY id
                """,
                (profile_context.id, bot_run_id),
            ).fetchall()
            return [dict(row) for row in rows]


class NotificationStateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def get_float(
        self,
        key: str,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> float | None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT value FROM notification_state WHERE profile_id = ? AND key = ?",
                (profile_context.id, key),
            ).fetchone()
            if row is None:
                return None

            return float(row["value"])

    def set_float(
        self,
        key: str,
        value: float,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            connection.execute(
                """
                INSERT INTO notification_state (profile_id, key, value, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(profile_id, key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (profile_context.id, key, str(value)),
            )


class LoanOfferRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(
        self,
        bot_run_id: int,
        offer: LoanOffer,
        status: str,
        dry_run: bool,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO loan_offers (
                    profile_id,
                    bot_run_id,
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    status,
                    dry_run,
                    external_offer_id,
                    message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile_context.id,
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

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM loan_offers WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def count_by_status(
        self,
        status: str,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM loan_offers WHERE profile_id = ? AND status = ?",
                (profile_context.id, status),
            ).fetchone()
            return int(row["count"])

    def recent(
        self,
        limit: int = 20,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, bot_run_id, currency, amount, daily_rate, duration_days,
                       status, dry_run, external_offer_id, message, created_at
                FROM loan_offers
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

class MarketRateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add(
        self,
        order: LoanOrder,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                INSERT INTO market_rates (profile_id, currency, daily_rate, available_amount)
                VALUES (?, ?, ?, ?)
                """,
                (profile_context.id, order.currency, order.daily_rate, order.amount),
            )
            return int(cursor.lastrowid)

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM market_rates WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def delete_older_than_days(
        self,
        days: int,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                DELETE FROM market_rates
                WHERE profile_id = ? AND captured_at < datetime('now', ?)
                """,
                (profile_context.id, f"-{days} days"),
            )
            return int(cursor.rowcount)

    def recent(
        self,
        limit: int = 20,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, currency, daily_rate, available_amount, captured_at
                FROM market_rates
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]


class MarketAnalysisRateRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def add_many(
        self,
        orders: list[LoanOrder],
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.executemany(
                """
                INSERT INTO market_analysis_rates (
                    profile_id,
                    currency,
                    level,
                    daily_rate,
                    available_amount
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (profile_context.id, order.currency, index, order.daily_rate, order.amount)
                    for index, order in enumerate(orders)
                ],
            )
            return int(cursor.rowcount)

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM market_analysis_rates WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def delete_older_than_days(
        self,
        days: int,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                """
                DELETE FROM market_analysis_rates
                WHERE profile_id = ? AND captured_at < datetime('now', ?)
                """,
                (profile_context.id, f"-{days} days"),
            )
            return int(cursor.rowcount)

    def recent(
        self,
        limit: int = 50,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, currency, level, daily_rate, available_amount, captured_at
                FROM market_analysis_rates
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def stats_by_currency(
        self,
        max_age_seconds: int = 0,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> dict[str, dict[str, object]]:
        ensure_default_profile(profile_context)
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
                WHERE profile_id = ?
                GROUP BY currency
                ORDER BY currency
                """,
                (profile_context.id, *stale_params),
            ).fetchall()
            return {str(row["currency"]): dict(row) for row in rows}

    def percentile_rate(
        self,
        currency: str,
        percentile: float,
        min_samples: int = 0,
        max_age_seconds: int = 0,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> float | None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT daily_rate
                FROM market_analysis_rates
                WHERE profile_id = ? AND currency = ?
                  {_max_age_filter(max_age_seconds)}
                ORDER BY daily_rate
                """,
                (profile_context.id, currency.upper()),
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
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> float | None:
        ensure_default_profile(profile_context)
        sample_count = max(short_samples, long_samples, min_samples, 1)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT daily_rate
                FROM market_analysis_rates
                WHERE profile_id = ? AND currency = ? AND level = 0
                  {_max_age_filter(max_age_seconds)}
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, currency.upper(), sample_count),
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
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> float | None:
        if short_seconds <= 0 or long_seconds <= 0:
            return None
        ensure_default_profile(profile_context)

        with connect(self._database_url) as connection:
            short_rates = self._rates_since_seconds(
                connection,
                profile_context.id,
                currency,
                _bounded_seconds(short_seconds, max_age_seconds),
            )
            long_rates = self._rates_since_seconds(
                connection,
                profile_context.id,
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
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[float]:
        if limit <= 0:
            return []
        ensure_default_profile(profile_context)

        with connect(self._database_url) as connection:
            rows = connection.execute(
                f"""
                SELECT daily_rate
                FROM market_analysis_rates
                WHERE profile_id = ? AND currency = ? AND level = 0
                  {_max_age_filter(max_age_seconds)}
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, currency.upper(), limit),
            ).fetchall()
            return [float(row["daily_rate"]) for row in rows]

    @staticmethod
    def _rates_since_seconds(connection, profile_id: str, currency: str, seconds: int) -> list[float]:
        rows = connection.execute(
            """
            SELECT daily_rate
            FROM market_analysis_rates
            WHERE profile_id = ?
              AND currency = ?
              AND level = 0
              AND captured_at >= datetime('now', ?)
            ORDER BY id DESC
            """,
            (profile_id, currency.upper(), f"-{seconds} seconds"),
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

    def replace_all(
        self,
        active_loans: list[ActiveLoan],
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            connection.execute("DELETE FROM active_loans WHERE profile_id = ?", (profile_context.id,))
            connection.executemany(
                """
                INSERT INTO active_loans (
                    profile_id,
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    external_loan_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        profile_context.id,
                        active_loan.currency,
                        active_loan.amount,
                        active_loan.daily_rate,
                        active_loan.duration_days,
                        active_loan.external_loan_id,
                    )
                    for active_loan in active_loans
                ],
            )

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM active_loans WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def recent(
        self,
        limit: int = 20,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, currency, amount, daily_rate, duration_days,
                       external_loan_id, captured_at
                FROM active_loans
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]


class LendingHistoryRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def upsert_many(
        self,
        entries: list[LendingHistoryEntry],
        dry_run: bool = False,
        source: str = "exchange",
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.executemany(
                """
                INSERT OR REPLACE INTO lending_history (
                    profile_id,
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        profile_context.id,
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

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM lending_history WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def recent(
        self,
        limit: int = 20,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, external_entry_id, currency, amount, daily_rate, duration_days,
                       interest, fee, earned, opened_at, closed_at, dry_run, source, synced_at
                FROM lending_history
                WHERE profile_id = ?
                ORDER BY closed_at DESC, id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def earnings_summary_by_currency(
        self,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
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
                WHERE profile_id = ?
                GROUP BY currency, dry_run, source
                ORDER BY dry_run, currency, source
                """,
                (profile_context.id,),
            ).fetchall()
            return [dict(row) for row in rows]


class OpenLoanOfferRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def replace_all(
        self,
        offers: list[LoanOffer],
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            connection.execute("DELETE FROM open_loan_offers WHERE profile_id = ?", (profile_context.id,))
            connection.executemany(
                """
                INSERT INTO open_loan_offers (
                    profile_id,
                    currency,
                    amount,
                    daily_rate,
                    duration_days,
                    external_offer_id
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        profile_context.id,
                        offer.currency,
                        offer.amount,
                        offer.daily_rate,
                        offer.duration_days,
                        offer.external_offer_id,
                    )
                    for offer in offers
                ],
            )

    def count(self, profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                "SELECT COUNT(*) AS count FROM open_loan_offers WHERE profile_id = ?",
                (profile_context.id,),
            ).fetchone()
            return int(row["count"])

    def recent(
        self,
        limit: int = 20,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> list[dict[str, object]]:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, profile_id, currency, amount, daily_rate, duration_days,
                       external_offer_id, captured_at
                FROM open_loan_offers
                WHERE profile_id = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_context.id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def find_by_external_offer_id(
        self,
        external_offer_id: str,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> dict[str, object] | None:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT id, profile_id, currency, amount, daily_rate, duration_days,
                       external_offer_id, captured_at
                FROM open_loan_offers
                WHERE profile_id = ? AND external_offer_id = ?
                """,
                (profile_context.id, external_offer_id),
            ).fetchone()
            return dict(row) if row is not None else None

    def delete_by_external_offer_id(
        self,
        external_offer_id: str,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> int:
        ensure_default_profile(profile_context)
        with connect(self._database_url) as connection:
            cursor = connection.execute(
                "DELETE FROM open_loan_offers WHERE profile_id = ? AND external_offer_id = ?",
                (profile_context.id, external_offer_id),
            )
            return int(cursor.rowcount)
