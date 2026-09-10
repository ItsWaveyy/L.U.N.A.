from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class ActivityEvent:
    timestamp: str
    event_type: str
    message: str

    task: str | None = None
    provider: str | None = None
    model: str | None = None

    latency_seconds: float | None = None
    fallback_used: bool = False
    fallback_from: str | None = None


class ActivityManager:
    """
    Persistent-runtime activity feed for the dashboard.

    This is intentionally separate from the conversation archive.

    Conversation archive:
        What L.U.N.A. and the user actually said.

    Activity feed:
        What L.U.N.A. Core was doing internally.
    """

    MAX_EVENTS = 50

    def __init__(self) -> None:
        self._lock = Lock()
        self._events: list[ActivityEvent] = []

    def record(
        self,
        event_type: str,
        message: str,
        *,
        task: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        latency_seconds: float | None = None,
        fallback_used: bool = False,
        fallback_from: str | None = None,
    ) -> None:
        event = ActivityEvent(
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            message=message,
            task=task,
            provider=provider,
            model=model,
            latency_seconds=latency_seconds,
            fallback_used=fallback_used,
            fallback_from=fallback_from,
        )

        with self._lock:
            self._events.append(event)

            if len(self._events) > self.MAX_EVENTS:
                self._events = self._events[-self.MAX_EVENTS :]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            events = [
                asdict(event)
                for event in reversed(self._events)
            ]

        return {
            "count": len(events),
            "events": events,
        }

    def clear(self) -> None:
        with self._lock:
            self._events.clear()