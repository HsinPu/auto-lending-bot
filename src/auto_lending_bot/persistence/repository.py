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
                INSERT INTO bot_runs (status, dry_run)
                VALUES (?, ?)
                """,
                ("running", int(dry_run)),
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
                    dry_run
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bot_run_id,
                    offer.currency,
                    offer.amount,
                    offer.daily_rate,
                    offer.duration_days,
                    status,
                    int(dry_run),
                ),
            )
            return int(cursor.lastrowid)

    def count(self) -> int:
        with connect(self._database_url) as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM loan_offers").fetchone()
            return int(row["count"])


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
