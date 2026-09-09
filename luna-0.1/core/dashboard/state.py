from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


VALID_MODES = {
    "default",
    "monitoring",
    "diagnostics",
    "inference",
    "improvement",
    "network",
    "memory",
    "security",
    "idle",
    "alert",
}

VALID_PRIORITIES = {
    "low": 0,
    "normal": 0,
    "high": 1,
    "critical": 2,
}

DEFAULT_PANELS = (
    "system",
    "providers",
    "routing",
    "memory",
    "activity",
    "network",
    "improvement",
    "wakeword",
)


@dataclass
class DashboardPanel:
    id: str
    visible: bool = True
    priority: int = 0


@dataclass
class DashboardAlert:
    severity: str
    message: str
    timestamp: str


class DashboardStateManager:
    """
    Owns the presentation state of the L.U.N.A. dashboard.

    Core owns system truth.
    DashboardStateManager owns how that truth should be presented.

    L.U.N.A. can eventually manipulate this same state through
    validated dashboard commands.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self.mode = "default"
        self.focused_panel: str | None = None
        self.last_updated = self._timestamp()

        self.panels: dict[str, DashboardPanel] = {
            panel_id: DashboardPanel(id=panel_id)
            for panel_id in DEFAULT_PANELS
        }

        self.alerts: list[DashboardAlert] = []

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "mode": self.mode,
                "focused_panel": self.focused_panel,
                "last_updated": self.last_updated,
                "panels": {
                    panel_id: asdict(panel)
                    for panel_id, panel in self.panels.items()
                },
                "alerts": [
                    asdict(alert)
                    for alert in self.alerts
                ],
            }

    def apply_command(
        self,
        *,
        command: dict[str, Any],
        timestamp: str | None = None,
    ) -> None:
        action = str(command.get("action", "")).strip().lower()

        if not action:
            raise ValueError("Dashboard command requires an action.")

        if action == "set_dashboard":
            self._set_dashboard(command)

        elif action == "show_panel":
            self._set_panel_visibility(command, visible=True)

        elif action == "hide_panel":
            self._set_panel_visibility(command, visible=False)

        elif action == "focus_panel":
            self._focus_panel(command)

        elif action == "clear_focus":
            with self._lock:
                self.focused_panel = None
                self._touch()

        elif action == "set_priority":
            self._set_priority(command)

        elif action == "show_alert":
            self._show_alert(command)

        elif action == "clear_alert":
            self._clear_alert(command)

        else:
            raise ValueError(f"Unknown dashboard action: {action}")

        if timestamp is not None:
            with self._lock:
                self.last_updated = timestamp

    def _set_dashboard(self, command: dict[str, Any]) -> None:
        layout = str(command.get("layout", "")).strip().lower()
        panels = command.get("panels")

        if layout not in VALID_MODES:
            raise ValueError(
                f"Invalid dashboard layout: {layout}"
            )

        if not isinstance(panels, list) or not panels:
            raise ValueError(
                "set_dashboard requires a non-empty panels list."
            )

        requested_panels = {
            str(panel).strip().lower()
            for panel in panels
            if str(panel).strip()
        }

        unknown = requested_panels - self.panels.keys()

        if unknown:
            raise ValueError(
                f"Unknown dashboard panels: {sorted(unknown)}"
            )

        with self._lock:
            self.mode = layout

            for panel_id, panel in self.panels.items():
                panel.visible = panel_id in requested_panels

            if (
                self.focused_panel is not None
                and self.focused_panel not in requested_panels
            ):
                self.focused_panel = None

            self._touch()

    def _set_panel_visibility(
        self,
        command: dict[str, Any],
        *,
        visible: bool,
    ) -> None:
        panel = self._require_panel(command)

        with self._lock:
            self.panels[panel].visible = visible

            if not visible and self.focused_panel == panel:
                self.focused_panel = None

            self._touch()

    def _focus_panel(self, command: dict[str, Any]) -> None:
        panel = self._require_panel(command)

        with self._lock:
            self.panels[panel].visible = True
            self.focused_panel = panel
            self._touch()

    def _set_priority(self, command: dict[str, Any]) -> None:
        panel = self._require_panel(command)

        priority_name = (
            str(command.get("priority", "normal"))
            .strip()
            .lower()
        )

        if priority_name not in VALID_PRIORITIES:
            raise ValueError(
                f"Invalid panel priority: {priority_name}"
            )

        with self._lock:
            self.panels[panel].priority = VALID_PRIORITIES[
                priority_name
            ]
            self._touch()

    def add_alert(
        self,
        *,
        severity: str,
        message: str,
        timestamp: str | None = None,
    ) -> None:
        """
        Add an alert from an internal L.U.N.A. Core component.

        This is the programmatic interface used by Core runtime monitoring.
        Dashboard commands use the validated show_alert action below.
        """
        severity = severity.strip().lower()
        message = message.strip()

        if severity not in {"info", "warning", "critical"}:
            raise ValueError(
                f"Invalid alert severity: {severity}"
            )

        if not message:
            raise ValueError(
                "Alert message cannot be empty."
            )

        with self._lock:
            self.alerts.append(
                DashboardAlert(
                    severity=severity,
                    message=message,
                    timestamp=timestamp or self._timestamp(),
                )
            )

            self.alerts = self.alerts[-20:]
            self._touch()

    def clear_alert(
        self,
        *,
        message: str | None = None,
    ) -> None:
        """
        Clear dashboard alerts from an internal L.U.N.A. Core component.

        If message is provided, only matching alerts are removed.
        Otherwise all alerts are cleared.
        """
        message = message.strip() if message else None

        with self._lock:
            if message:
                self.alerts = [
                    alert
                    for alert in self.alerts
                    if alert.message != message
                ]
            else:
                self.alerts.clear()

            self._touch()

    def _show_alert(self, command: dict[str, Any]) -> None:
        severity = (
            str(command.get("severity", "info"))
            .strip()
            .lower()
        )

        message = str(command.get("message", "")).strip()

        self.add_alert(
            severity=severity,
            message=message,
        )

    def _clear_alert(self, command: dict[str, Any]) -> None:
        message = str(command.get("message", "")).strip()

        self.clear_alert(
            message=message or None,
        )


    def _require_panel(self, command: dict[str, Any]) -> str:
        panel = str(command.get("panel", "")).strip().lower()

        if not panel:
            raise ValueError(
                "Dashboard command requires a panel."
            )

        if panel not in self.panels:
            raise ValueError(
                f"Unknown dashboard panel: {panel}"
            )

        return panel

    def _touch(self) -> None:
        self.last_updated = self._timestamp()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()