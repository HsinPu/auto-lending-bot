from typing import Protocol

from auto_lending_bot.bot.factory import RunnerRepositories, create_bot_runner
from auto_lending_bot.config import Settings
from auto_lending_bot.persistence.factory import RepositoryBundle
from auto_lending_bot.profiles import DEFAULT_PROFILE_CONTEXT, BotProfileContext
from auto_lending_bot.settings_snapshot import settings_snapshot_json


class LoopController(Protocol):
    def status(self) -> dict[str, object]:
        ...

    def start(self, bot_job_id: int) -> dict[str, object]:
        ...

    def stop(self) -> dict[str, object]:
        ...

    def stop_job(self, bot_job_id: int) -> dict[str, object]:
        ...


class BotActionService:
    def __init__(
        self,
        settings: Settings,
        repositories: RepositoryBundle,
        loop_controller: LoopController,
        profile_context: BotProfileContext = DEFAULT_PROFILE_CONTEXT,
    ) -> None:
        self._settings = settings
        self._repositories = repositories
        self._loop_controller = loop_controller
        self._profile_context = profile_context

    def reset_dry_run_records(self) -> dict[str, object]:
        deleted_counts = self._repositories.bot_runs.delete_dry_run_records(self._profile_context)
        return {
            "action": "reset-dry-run-records",
            "ok": True,
            "deleted_count": sum(deleted_counts.values()),
            **deleted_counts,
        }

    def run_once(self) -> dict[str, object]:
        offers_before = self._repositories.loan_offers.count(self._profile_context)
        runner = create_bot_runner(
            self._settings,
            RunnerRepositories(
                bot_runs=self._repositories.bot_runs,
                loan_offers=self._repositories.loan_offers,
                active_loans=self._repositories.active_loans,
                open_offers=self._repositories.open_offers,
                lending_history=self._repositories.lending_history,
                notification_state=self._repositories.notification_state,
                market_analysis_rates=self._repositories.market_analysis_rates,
                market_rates=self._repositories.market_rates,
                decision_snapshots=self._repositories.bot_run_decisions,
                run_steps=self._repositories.bot_run_steps,
            ),
            profile_context=self._profile_context,
        )
        runner.run_once()
        offers_after = self._repositories.loan_offers.count(self._profile_context)
        latest_run = self._repositories.bot_runs.latest(self._profile_context) or {}
        bot_run_id = latest_run.get("id")
        return {
            "action": "run-once",
            "ok": True,
            "dry_run": self._settings.dry_run,
            "created_count": offers_after - offers_before,
            "bot_run_id": bot_run_id,
            "status": latest_run.get("status"),
            "message": latest_run.get("message", ""),
            "started_at": latest_run.get("started_at"),
            "finished_at": latest_run.get("finished_at"),
            "decisions": self._repositories.bot_run_decisions.for_run(
                int(bot_run_id),
                self._profile_context,
            )
            if bot_run_id
            else [],
            "steps": self._repositories.bot_run_steps.for_run(
                int(bot_run_id),
                self._profile_context,
            )
            if bot_run_id
            else [],
            "latest_run": latest_run,
        }

    def start_loop(self) -> dict[str, object]:
        current_status = self._loop_controller.status()
        if current_status.get("running"):
            return {"action": "start-loop", "ok": True, **current_status}

        bot_job_id = self._repositories.bot_jobs.create(
            self._profile_context,
            settings_snapshot_json=settings_snapshot_json(self._settings),
        )
        return {
            "action": "start-loop",
            "ok": True,
            "bot_job_id": bot_job_id,
            **self._loop_controller.start(bot_job_id),
        }

    def stop_loop(self) -> dict[str, object]:
        return {"action": "stop-loop", "ok": True, **self._loop_controller.stop()}

    def stop_job(self, bot_job_id: int) -> dict[str, object]:
        return {"action": "stop-job", "ok": True, **self._loop_controller.stop_job(bot_job_id)}

    def loop_status(self) -> dict[str, object]:
        return self._loop_controller.status()
