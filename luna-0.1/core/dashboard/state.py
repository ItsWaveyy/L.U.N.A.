from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4


VALID_STATES = {
    "starting",
    "idle",
    "listening",
    "thinking",
    "speaking",
    "working",
    "updating",
    "researching",
    "error",
}

VALID_SEVERITIES = {
    "info",
    "warning",
    "critical",
}

VALID_TRANSITIONS = {
    "replace",
    "fade",
    "slide",
    "scale",
    "none",
}


@dataclass
class DashboardAlert:
    severity: str
    message: str
    timestamp: str


class DashboardStateManager:
    """
    Owns the presentation state of the L.U.N.A. dashboard.

    Core owns system truth.
    DashboardStateManager owns what L.U.N.A. wants the interface
    to communicate right now.

    The frontend is responsible for rendering this state.
    """

    def __init__(self) -> None:
        self._lock = Lock()

        now = self._timestamp()

        self.state = "starting"
        self.status_message = "Initializing L.U.N.A."

        self.presentation: dict[str, Any] = {
            "type": "idle",
            "data": {},
            "transition": "replace",
        }

        self.boot: dict[str, str] = {
            "boot_id": uuid4().hex,
            "started_at": now,
        }

        self.last_updated = now
        self.alerts: list[DashboardAlert] = []

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self.state,
                "status": {
                    "state": self.state,
                    "message": self.status_message,
                },
                "presentation": {
                    "type": self.presentation["type"],
                    "data": dict(self.presentation["data"]),
                    "transition": self.presentation["transition"],
                },
                "boot": dict(self.boot),
                "alerts": [
                    asdict(alert)
                    for alert in self.alerts
                ],
                "last_updated": self.last_updated,
            }

    def apply_command(
        self,
        *,
        command: dict[str, Any],
        timestamp: str | None = None,
    ) -> None:
        action = str(command.get("action", "")).strip().lower()

        if not action:
            raise ValueError(
                "Dashboard command requires an action."
            )

        if action == "set_state":
            self._set_state(command)

        elif action == "set_presentation":
            self._set_presentation(command)

        elif action == "clear_presentation":
            self._clear_presentation()

        elif action == "show_alert":
            self._show_alert(command)

        elif action == "clear_alert":
            self._clear_alert(command)

        elif action == "begin_boot":
            self._begin_boot()

        elif action == "complete_boot":
            self._complete_boot()

        else:
            raise ValueError(
                f"Unknown dashboard action: {action}"
            )

        if timestamp is not None:
            with self._lock:
                self.last_updated = timestamp

    def _set_state(
        self,
        command: dict[str, Any],
    ) -> None:
        state = (
            str(command.get("state", ""))
            .strip()
            .lower()
        )

        if state not in VALID_STATES:
            raise ValueError(
                f"Invalid dashboard state: {state}"
            )

        message = command.get("message")

        with self._lock:
            self.state = state

            if message is not None:
                self.status_message = str(message).strip()

            self._touch()

    def _set_presentation(
        self,
        command: dict[str, Any],
    ) -> None:
        presentation_type = (
            str(command.get("type", ""))
            .strip()
            .lower()
        )

        if not presentation_type:
            raise ValueError(
                "set_presentation requires a type."
            )

        data = command.get("data", {})

        if not isinstance(data, dict):
            raise ValueError(
                "set_presentation data must be an object."
            )

        transition = (
            str(command.get("transition", "replace"))
            .strip()
            .lower()
        )

        if transition not in VALID_TRANSITIONS:
            raise ValueError(
                f"Invalid presentation transition: {transition}"
            )

        with self._lock:
            self.presentation = {
                "type": presentation_type,
                "data": dict(data),
                "transition": transition,
            }

            self._touch()

    def _clear_presentation(self) -> None:
        with self._lock:
            self.presentation = {
                "type": "idle",
                "data": {},
                "transition": "fade",
            }

            self._touch()

    def add_alert(
        self,
        *,
        severity: str,
        message: str,
        timestamp: str | None = None,
    ) -> None:
        severity = severity.strip().lower()
        message = message.strip()

        if severity not in VALID_SEVERITIES:
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

    def _show_alert(
        self,
        command: dict[str, Any],
    ) -> None:
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

    def _clear_alert(
        self,
        command: dict[str, Any],
    ) -> None:
        message = str(command.get("message", "")).strip()

        self.clear_alert(
            message=message or None,
        )

    def _begin_boot(self) -> None:
        now = self._timestamp()

        with self._lock:
            self.boot = {
                "boot_id": uuid4().hex,
                "started_at": now,
            }

            self.state = "starting"
            self.status_message = "Initializing L.U.N.A."

            self.presentation = {
                "type": "boot",
                "data": {},
                "transition": "replace",
            }

            self._touch()

    def _complete_boot(self) -> None:
        with self._lock:
            self.state = "idle"
            self.status_message = "L.U.N.A. online."

            self.presentation = {
                "type": "idle",
                "data": {},
                "transition": "fade",
            }

            self._touch()

    def _touch(self) -> None:
        self.last_updated = self._timestamp()

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()