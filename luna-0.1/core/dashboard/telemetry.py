from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.orchestrator import LunaCore
from core.system.monitor import SystemMonitor
from core.dashboard.state import DashboardStateManager
from core.dashboard.activity import ActivityManager
from core.dashboard.runtime_state import CoreRuntimeState


class DashboardTelemetry:
    """
    Aggregates L.U.N.A. Core state into one dashboard-facing snapshot.

    Core remains the source of truth.
    The dashboard consumes this aggregated state and does not
    independently determine system or assistant state.
    """

    def __init__(
        self,
        core: LunaCore,
        system_monitor: SystemMonitor,
        dashboard: DashboardStateManager,
        activity: ActivityManager,
        runtime_state: CoreRuntimeState,
    ) -> None:
        self.core = core
        self.system_monitor = system_monitor
        self.dashboard = dashboard
        self.activity = activity
        self.runtime_state = runtime_state

    async def snapshot(self) -> dict[str, Any]:
        system = self.system_monitor.as_dict()
        status = await self._core_status()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),

            "system": system,

            "core": status,

            "activity": self.activity.snapshot(),

            "runtime_state": self.runtime_state.snapshot(),

            "dashboard": self.dashboard.snapshot(),
        }

    async def _core_status(self) -> dict[str, Any]:
        provider_health = await self.core.health_status()

        providers = []

        for provider in self.core.router.providers:
            providers.append(
                {
                    "name": provider.name,
                    "model": getattr(provider, "model", None),
                    "healthy": provider_health.get(
                        provider.name,
                        False,
                    ),
                    "capabilities": sorted(
                        provider.capabilities,
                    ),
                }
            )

        return {
            "status": "online",

            "mode": self._get_mode(),

            "listening": self.core.listening,

            "providers": providers,

            "conversation": {
                "active": (
                    self.core.conversations.session_id
                    is not None
                ),
                "session_id": (
                    self.core.conversations.session_id
                ),
            },

            "memory": self._memory_status(),

            "improvement": {
                "available": (
                    self.core.improvement is not None
                ),
            },
        }

    def _get_mode(self) -> str:
        """
        Return the currently configured L.U.N.A. operating mode.
        """

        from config import LUNA_MODE

        return LUNA_MODE

    def _memory_status(self) -> dict[str, Any]:
        """
        Return the current memory subsystem state.

        Memory remains intentionally lightweight here.
        Detailed memory telemetry will be added when the
        Memory 2.0 architecture is implemented.
        """

        return {
            "available": True,
            "conversation_archive": True,
        }