from auto_lending_bot.domain.models import LoanApplication, LoanOffer, LoanOrder
from auto_lending_bot.persistence.database import connect


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
                    external_offer_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
                ),
            )
            return int(cursor.lastrowid)

    def update_status(
        self,
        loan_offer_id: int,
        status: str,
        external_offer_id: str | None = None,
    ) -> None:
        with connect(self._database_url) as connection:
            connection.execute(
                """
                UPDATE loan_offers
                SET status = ?,
                    external_offer_id = ?
                WHERE id = ?
                """,
                (status, external_offer_id, loan_offer_id),
            )

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM loan_offers").fetchone()
            return int(row["count"])

    def recent(self, limit: int = 20) -> list[dict[str, object]]:
        with connect(self._database_url) as connection:
            rows = connection.execute(
                """
                SELECT id, bot_run_id, currency, amount, daily_rate, duration_days,
                       status, dry_run, external_offer_id, created_at
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
