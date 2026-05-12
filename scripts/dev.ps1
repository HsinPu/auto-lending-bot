uv sync
if ($?) { uv run pytest }
if ($?) { uv run ruff check . }
