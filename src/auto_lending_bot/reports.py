from html import escape
from pathlib import Path

from auto_lending_bot.config import Settings
from auto_lending_bot.persistence.repository import (
    BotRunRepository,
    LoanOfferRepository,
    MarketRateRepository,
)


def write_dashboard(settings: Settings) -> Path:
    output_path = Path(settings.report_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(_render_dashboard(settings), encoding="utf-8")
    return output_path


def _render_dashboard(settings: Settings) -> str:
    bot_runs = BotRunRepository(settings.database_url)
    loan_offers = LoanOfferRepository(settings.database_url)
    market_rates = MarketRateRepository(settings.database_url)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escape(settings.bot_label)} Dashboard</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; color: #18212f; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 2rem; }}
    th, td {{ border: 1px solid #d5dbe7; padding: 0.5rem; text-align: left; }}
    th {{ background: #eef3fb; }}
    .metric {{ display: inline-block; margin-right: 1rem; padding: 0.75rem; background: #f7f9fc; }}
  </style>
</head>
<body>
  <h1>{escape(settings.bot_label)} Dashboard</h1>
  <p>Exchange: {escape(settings.exchange)} | Dry run: {settings.dry_run}</p>
  <div class="metric">Bot runs: {bot_runs.count()}</div>
  <div class="metric">Loan offers: {loan_offers.count()}</div>
  <div class="metric">Market rates: {market_rates.count()}</div>
  <h2>Recent Bot Runs</h2>
  {_render_table(bot_runs.recent(), ["id", "started_at", "finished_at", "status", "dry_run", "message"])}
  <h2>Recent Loan Offers</h2>
  {_render_table(loan_offers.recent(), ["id", "bot_run_id", "currency", "amount", "daily_rate", "duration_days", "status", "external_offer_id", "created_at"])}
  <h2>Recent Market Rates</h2>
  {_render_table(market_rates.recent(), ["id", "currency", "daily_rate", "available_amount", "captured_at"])}
</body>
</html>
"""


def _render_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    body_rows = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(row.get(column, '')))}</td>" for column in columns)
        body_rows.append(f"<tr>{cells}</tr>")

    if not body_rows:
        body_rows.append(f"<tr><td colspan=\"{len(columns)}\">No data</td></tr>")

    return f"<table><thead><tr>{header}</tr></thead><tbody>{''.join(body_rows)}</tbody></table>"
