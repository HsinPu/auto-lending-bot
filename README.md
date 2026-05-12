# auto-lending-bot

Python starter project for an auto lending bot.

## Requirements

- Python 3.11+
- uv

## Setup

```powershell
uv sync
```

Optional local configuration:

```powershell
Copy-Item .env.example .env
```

## Run

```powershell
uv run auto-lending-bot
```

Phase one uses a mock exchange by default and runs in dry-run mode. It records bot runs,
generated loan offers, and captured mock market rates into SQLite.

## Test And Lint

```powershell
uv run pytest
uv run ruff check .
```

## Project Structure

```text
src/auto_lending_bot/
├─ bot/                 # Bot runner and orchestration
├─ main.py              # Application entry point
├─ config.py            # Environment-based settings
├─ logging.py           # Logging setup
├─ domain/              # Core business rules and models
├─ integrations/        # External service clients
├─ market/              # Market data recording
├─ notifications/       # Notification adapters
├─ persistence/         # SQLite and repository code
└─ utils/               # Shared utilities
```

## Phase One Scope

- Mock exchange only
- Dry-run enabled by default
- Simple lending strategy based on minimum daily rate, minimum loan size, and split count
- SQLite tables for bot runs, loan offers, and market rates
- No real exchange API calls yet
