from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import datetime, timezone

import uvicorn

from core.dashboard.state import DashboardStateManager
from core.dashboard.telemetry import DashboardTelemetry
from core.dashboard.activity import ActivityManager
from core.dashboard.runtime_state import CoreRuntimeState
from core.orchestrator import LunaCore
from core.reminders import ReminderScheduler
from core.system.monitor import SystemMonitor
from services.core_api.server import create_core_api


logger = logging.getLogger("luna.core")


class LunaCoreRuntime:
    API_HOST = "0.0.0.0"
    API_PORT = 8090

    MONITOR_INTERVAL = 5.0

    def __init__(self) -> None:
        self.core = LunaCore()

        self.system_monitor = SystemMonitor()

        self.dashboard = DashboardStateManager()

        self.activity = ActivityManager()

        self.runtime_state = CoreRuntimeState()

        self.core.set_runtime_state(self.runtime_state)

        self.core.set_activity_manager(
            self.activity
        )

        self.telemetry = DashboardTelemetry(
            core=self.core,
            system_monitor=self.system_monitor,
            dashboard=self.dashboard,
            activity=self.activity,
            runtime_state=self.runtime_state,
        )

        self.reminder_scheduler = ReminderScheduler(
            conversations=self.core.conversations,
            on_reminder=self._handle_reminder,
        )

        self.api = create_core_api(runtime=self)

        self._api_server: uvicorn.Server | None = None
        self._monitor_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        # Tracks whether a monitored condition is currently active.
        #
        # This prevents the dashboard alert list from being flooded
        # with the same alert every monitoring cycle.
        self._condition_state: dict[str, bool] = {}

    async def start(self) -> None:
        logger.info("[L.U.N.A.] Core runtime starting...")

        self.core.conversations.start_session()

        self.dashboard.add_alert(
            severity="info",
            message="L.U.N.A. Core started.",
            timestamp=self._timestamp(),
        )

        self.reminder_scheduler.start()

        self._monitor_task = asyncio.create_task(
            self._monitor_loop(),
            name="luna-core-monitor",
        )

        await self._serve_api()

    async def shutdown(self) -> None:
        logger.info("[L.U.N.A.] Core runtime shutting down...")

        self._shutdown_event.set()

        if self._monitor_task is not None:
            self._monitor_task.cancel()

            with suppress(asyncio.CancelledError):
                await self._monitor_task

            self._monitor_task = None

        await self.reminder_scheduler.shutdown()

        self.core.conversations.end_session()

        logger.info("[L.U.N.A.] Core runtime stopped.")

    async def _serve_api(self) -> None:
        config = uvicorn.Config(
            self.api,
            host=self.API_HOST,
            port=self.API_PORT,
            log_level="info",
            access_log=True,
        )

        self._api_server = uvicorn.Server(config)

        logger.info(
            "[L.U.N.A.] Core API listening on "
            f"{self.API_HOST}:{self.API_PORT}"
        )

        try:
            await self._api_server.serve()
        finally:
            self._api_server = None

    async def _monitor_loop(self) -> None:
        while not self._shutdown_event.is_set():
            try:
                snapshot = self.system_monitor.snapshot()

                self._evaluate_temperature(snapshot.temperature_celsius)
                self._evaluate_memory(snapshot.memory_percent)
                self._evaluate_storage(snapshot.storage_percent)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "[L.U.N.A.] Core monitoring error."
                )

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self.MONITOR_INTERVAL,
                )

            except asyncio.TimeoutError:
                pass

    def _evaluate_temperature(
        self,
        temperature_celsius: float | None,
    ) -> None:
        if temperature_celsius is None:
            self._set_condition(
                "temperature",
                False,
                None,
            )
            return

        if temperature_celsius >= 80:
            self._set_condition(
                "temperature",
                True,
                (
                    "Core temperature is above 80°C "
                    f"({temperature_celsius:.1f}°C)."
                ),
                severity="critical",
            )

        elif temperature_celsius >= 70:
            self._set_condition(
                "temperature",
                True,
                (
                    "Core temperature is elevated "
                    f"({temperature_celsius:.1f}°C)."
                ),
                severity="warning",
            )

        else:
            self._set_condition(
                "temperature",
                False,
                None,
            )

    def _evaluate_memory(self, memory_percent: float) -> None:
        if memory_percent >= 90:
            self._set_condition(
                "memory",
                True,
                f"System memory usage is above 90% ({memory_percent:.1f}%).",
                severity="warning",
            )
        else:
            self._set_condition(
                "memory",
                False,
                None,
            )

    def _evaluate_storage(self, storage_percent: float) -> None:
        if storage_percent >= 95:
            self._set_condition(
                "storage",
                True,
                (
                    "L.U.N.A. storage usage is critical "
                    f"({storage_percent:.1f}%)."
                ),
                severity="critical",
            )

        elif storage_percent >= 90:
            self._set_condition(
                "storage",
                True,
                (
                    "L.U.N.A. storage usage is above 90% "
                    f"({storage_percent:.1f}%)."
                ),
                severity="warning",
            )

        else:
            self._set_condition(
                "storage",
                False,
                None,
            )

    def _set_condition(
        self,
        condition_id: str,
        active: bool,
        message: str | None,
        severity: str = "warning",
    ) -> None:
        previous = self._condition_state.get(
            condition_id,
            False,
        )

        self._condition_state[condition_id] = active

        # No state change → don't create another alert.
        if active == previous:
            return

        timestamp = self._timestamp()

        if active and message:
            logger.warning(
                "[L.U.N.A.] %s",
                message,
            )

            self.dashboard.add_alert(
                severity=severity,
                message=message,
                timestamp=timestamp,
            )

        elif not active and previous:
            clear_message = (
                f"{condition_id.replace('_', ' ').title()} "
                "condition cleared."
            )

            logger.info(
                "[L.U.N.A.] %s",
                clear_message,
            )

            self.dashboard.add_alert(
                severity="info",
                message=clear_message,
                timestamp=timestamp,
            )

    async def _handle_reminder(self, message: str) -> None:
        logger.info(
            "[L.U.N.A.] Reminder event: %s",
            message,
        )

        self.dashboard.add_alert(
            severity="info",
            message=f"Reminder: {message}",
            timestamp=self._timestamp(),
        )

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()


async def main() -> None:
    runtime = LunaCoreRuntime()

    try:
        await runtime.start()

    except (KeyboardInterrupt, asyncio.CancelledError):
        pass

    finally:
        await runtime.shutdown()


if __name__ == "__main__":
    asyncio.run(main())