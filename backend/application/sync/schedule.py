"""Manual and scheduled sync orchestration."""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timedelta
from typing import Callable

from backend.application.interfaces import DATA_SYNC_SCOPES, SyncTaskSubmitter
from backend.domain.models import SyncSchedule
from backend.domain.ports import SyncScheduleRepository

logger = logging.getLogger(__name__)

RUN_TIME_PATTERN = re.compile(r"^\d{2}:\d{2}$")
UNSET = object()


class SyncScheduleService:
    """Manage the default local stock data sync schedule."""

    DEFAULT_SCHEDULE_ID = "default"
    DEFAULT_NAME = "默认数据同步"
    DEFAULT_SCOPE = "all"
    DEFAULT_RUN_TIME = "18:30"
    DEFAULT_LOOKBACK_DAYS = 7

    def __init__(
        self,
        schedule_repository: SyncScheduleRepository,
        job_service: SyncTaskSubmitter,
        clock: Callable[[], datetime] | None = None,
    ):
        self.schedule_repository = schedule_repository
        self.job_service = job_service
        self.clock = clock or datetime.now

    def get_default_schedule(self) -> dict:
        schedule = self._ensure_default_schedule()
        return schedule.to_dict()

    def update_default_schedule(
        self,
        enabled: bool | None = None,
        scope: str | None = None,
        run_time: str | None = None,
        lookback_days: int | None = None,
        stock_codes=UNSET,
    ) -> dict:
        schedule = self._ensure_default_schedule()
        updated = SyncSchedule(
            schedule_id=schedule.schedule_id,
            name=schedule.name,
            enabled=schedule.enabled if enabled is None else enabled,
            scope=schedule.scope if scope is None else self._validate_scope(scope),
            run_time=schedule.run_time if run_time is None else self._validate_run_time(run_time),
            lookback_days=(
                schedule.lookback_days
                if lookback_days is None
                else self._validate_lookback_days(lookback_days)
            ),
            stock_codes=(
                schedule.stock_codes
                if stock_codes is UNSET
                else self._normalize_stock_codes(stock_codes)
            ),
            last_job_id=schedule.last_job_id,
            last_run_at=schedule.last_run_at,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
        updated.next_run_at = self._calculate_next_run_at(updated, self.clock())
        self.schedule_repository.save_sync_schedule(updated)
        return self.schedule_repository.get_sync_schedule(updated.schedule_id).to_dict()

    def run_default_now(self) -> dict:
        schedule = self._ensure_default_schedule()
        logger.info("手动触发默认定时同步: schedule_id=%s", schedule.schedule_id)
        return self._submit_schedule(schedule, self.clock())

    def tick(self) -> dict | None:
        now = self.clock()
        schedule = self._ensure_default_schedule(now=now)
        if not schedule.enabled:
            return None
        if not self._is_due(schedule, now):
            return None
        logger.info("定时同步到期: schedule_id=%s run_time=%s", schedule.schedule_id, schedule.run_time)
        return self._submit_schedule(schedule, now)

    def _ensure_default_schedule(self, now: datetime | None = None) -> SyncSchedule:
        schedule = self.schedule_repository.get_sync_schedule(self.DEFAULT_SCHEDULE_ID)
        if schedule is not None:
            return schedule

        created = SyncSchedule(
            schedule_id=self.DEFAULT_SCHEDULE_ID,
            name=self.DEFAULT_NAME,
            enabled=False,
            scope=self.DEFAULT_SCOPE,
            run_time=self.DEFAULT_RUN_TIME,
            lookback_days=self.DEFAULT_LOOKBACK_DAYS,
            next_run_at=self._calculate_next_run_at(
                SyncSchedule(
                    schedule_id=self.DEFAULT_SCHEDULE_ID,
                    name=self.DEFAULT_NAME,
                    enabled=False,
                    scope=self.DEFAULT_SCOPE,
                    run_time=self.DEFAULT_RUN_TIME,
                    lookback_days=self.DEFAULT_LOOKBACK_DAYS,
                ),
                now or self.clock(),
            ),
        )
        self.schedule_repository.save_sync_schedule(created)
        return self.schedule_repository.get_sync_schedule(self.DEFAULT_SCHEDULE_ID)

    def _submit_schedule(self, schedule: SyncSchedule, now: datetime) -> dict:
        start_date, end_date = self._sync_date_range(schedule, now)
        job = self.job_service.submit_sync(
            scope=schedule.scope,
            start_date=start_date,
            end_date=end_date,
            stock_codes=schedule.stock_codes,
        )
        logger.info(
            "定时同步任务已提交: schedule_id=%s job_id=%s scope=%s start_date=%s end_date=%s",
            schedule.schedule_id,
            job["job_id"],
            schedule.scope,
            start_date,
            end_date,
        )
        updated = SyncSchedule(
            schedule_id=schedule.schedule_id,
            name=schedule.name,
            enabled=schedule.enabled,
            scope=schedule.scope,
            run_time=schedule.run_time,
            lookback_days=schedule.lookback_days,
            stock_codes=schedule.stock_codes,
            last_job_id=job["job_id"],
            last_run_at=now.isoformat(),
            next_run_at=None,
            created_at=schedule.created_at,
            updated_at=schedule.updated_at,
        )
        updated.next_run_at = self._calculate_next_run_at(updated, now)
        self.schedule_repository.save_sync_schedule(updated)
        return job

    def _sync_date_range(self, schedule: SyncSchedule, now: datetime) -> tuple[str | None, str | None]:
        if schedule.scope == "stocks":
            return None, None
        end_date = now.strftime("%Y%m%d")
        start_date = (now - timedelta(days=schedule.lookback_days)).strftime("%Y%m%d")
        return start_date, end_date

    def _is_due(self, schedule: SyncSchedule, now: datetime) -> bool:
        if schedule.last_run_at:
            last_run_date = datetime.fromisoformat(schedule.last_run_at).date()
            if last_run_date == now.date():
                return False

        run_hour, run_minute = self._parse_run_time(schedule.run_time)
        due_time = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
        return now >= due_time

    def _calculate_next_run_at(self, schedule: SyncSchedule, now: datetime) -> str | None:
        if not schedule.enabled:
            return None

        run_hour, run_minute = self._parse_run_time(schedule.run_time)
        candidate = now.replace(hour=run_hour, minute=run_minute, second=0, microsecond=0)
        if now >= candidate or self._ran_today(schedule, now):
            candidate += timedelta(days=1)
        return candidate.isoformat()

    def _ran_today(self, schedule: SyncSchedule, now: datetime) -> bool:
        if not schedule.last_run_at:
            return False
        return datetime.fromisoformat(schedule.last_run_at).date() == now.date()

    def _validate_scope(self, scope: str) -> str:
        if scope not in DATA_SYNC_SCOPES:
            raise ValueError(f"不支持的数据同步范围: {scope}")
        return scope

    def _validate_run_time(self, run_time: str) -> str:
        if not RUN_TIME_PATTERN.match(run_time):
            raise ValueError("run_time 必须使用 HH:MM 格式")
        self._parse_run_time(run_time)
        return run_time

    def _parse_run_time(self, run_time: str) -> tuple[int, int]:
        hour_text, minute_text = run_time.split(":")
        hour = int(hour_text)
        minute = int(minute_text)
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("run_time 必须是有效的 24 小时时间")
        return hour, minute

    def _validate_lookback_days(self, lookback_days: int) -> int:
        if lookback_days < 1 or lookback_days > 365:
            raise ValueError("lookback_days 必须在 1 到 365 之间")
        return lookback_days

    def _normalize_stock_codes(self, stock_codes: list[str] | None) -> list[str] | None:
        if not stock_codes:
            return None
        normalized = [code.strip() for code in stock_codes if code and code.strip()]
        return normalized or None


class InProcessSyncScheduler:
    """Small in-process scheduler for single-machine local deployments."""

    def __init__(
        self,
        schedule_service: SyncScheduleService,
        poll_interval_seconds: int = 60,
    ):
        self.schedule_service = schedule_service
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="sync-scheduler",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.schedule_service.tick()
            except Exception:
                logger.exception("定时同步检查失败")
            time.sleep(self.poll_interval_seconds)
