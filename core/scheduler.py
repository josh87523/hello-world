"""Scheduler for automated daily content generation."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Callable

logger = logging.getLogger(__name__)


class Scheduler:
    """Simple scheduler for running content workflows on a schedule.

    For production use, consider replacing with APScheduler or Celery Beat.

    Usage:
        scheduler = Scheduler()
        scheduler.add_job("daily_content", workflow.run, cron="08:00", kwargs={...})
        scheduler.start()  # blocking
    """

    def __init__(self):
        self._jobs: dict[str, dict[str, Any]] = {}
        self._running = False

    def add_job(
        self,
        name: str,
        func: Callable,
        cron: str = "08:00",
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Add a scheduled job.

        Args:
            name: Unique job name.
            func: Callable to execute.
            cron: Time in HH:MM format.
            kwargs: Keyword arguments to pass to func.
        """
        hour, minute = map(int, cron.split(":"))
        self._jobs[name] = {
            "func": func,
            "hour": hour,
            "minute": minute,
            "kwargs": kwargs or {},
            "last_run": None,
        }
        logger.info("Job '%s' scheduled at %02d:%02d", name, hour, minute)

    def start(self) -> None:
        """Start the scheduler loop (blocking)."""
        self._running = True
        logger.info("Scheduler started with %d jobs", len(self._jobs))

        while self._running:
            now = datetime.now()
            for name, job in self._jobs.items():
                if self._should_run(job, now):
                    self._run_job(name, job, now)
            time.sleep(30)  # check every 30 seconds

    def stop(self) -> None:
        self._running = False
        logger.info("Scheduler stopped")

    def run_now(self, name: str) -> Any:
        """Manually trigger a job immediately."""
        job = self._jobs.get(name)
        if not job:
            raise ValueError(f"Job '{name}' not found")
        return self._run_job(name, job, datetime.now())

    def _should_run(self, job: dict, now: datetime) -> bool:
        if now.hour != job["hour"] or now.minute != job["minute"]:
            return False
        last_run = job.get("last_run")
        if last_run and (now - last_run) < timedelta(hours=1):
            return False
        return True

    def _run_job(self, name: str, job: dict, now: datetime) -> Any:
        logger.info("Running job: %s", name)
        try:
            result = job["func"](**job["kwargs"])
            job["last_run"] = now
            logger.info("Job '%s' completed successfully", name)
            return result
        except Exception as e:
            logger.error("Job '%s' failed: %s", name, e, exc_info=True)
            return None
