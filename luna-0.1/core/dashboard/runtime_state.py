from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any


@dataclass
class RoutingState:
    """
    Live state describing what L.U.N.A. Core is currently doing.

    This is runtime state only. It is not persisted to SQLite.
    """

    active: bool = False
    task: str | None = None
    provider: str | None = None
    model: str | None = None
    started_at: str | None = None

    fallback_used: bool = False
    fallback_from: str | None = None

    last_completed_at: str | None = None
    last_latency_seconds: float | None = None


class CoreRuntimeState:
    """
    Live runtime state exposed to the dashboard.

    This represents the current operational state of L.U.N.A. Core,
    not historical conversation data.
    """

    def __init__(self) -> None:
        self._lock = Lock()

        self.routing = RoutingState()

        self.last_request: dict[str, Any] | None = None
        self.last_response: dict[str, Any] | None = None

    def begin_routing(
        self,
        *,
        task: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        with self._lock:
            self.routing.active = True
            self.routing.task = task
            self.routing.provider = provider
            self.routing.model = model
            self.routing.started_at = self._timestamp()

            self.routing.fallback_used = False
            self.routing.fallback_from = None

    def complete_routing(
        self,
        *,
        task: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        latency_seconds: float | None = None,
        fallback_used: bool = False,
        fallback_from: str | None = None,
    ) -> None:
        completed_at = self._timestamp()

        with self._lock:
            self.routing.active = False

            if task is not None:
                self.routing.task = task

            if provider is not None:
                self.routing.provider = provider

            if model is not None:
                self.routing.model = model

            self.routing.fallback_used = fallback_used
            self.routing.fallback_from = fallback_from

            self.routing.last_completed_at = completed_at
            self.routing.last_latency_seconds = latency_seconds

    def record_request(
        self,
        *,
        prompt: str,
        task: str | None = None,
    ) -> None:
        with self._lock:
            self.last_request = {
                "timestamp": self._timestamp(),
                "prompt": prompt,
                "task": task,
            }

    def record_response(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        latency_seconds: float | None = None,
    ) -> None:
        with self._lock:
            self.last_response = {
                "timestamp": self._timestamp(),
                "provider": provider,
                "model": model,
                "latency_seconds": latency_seconds,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "routing": asdict(self.routing),
                "last_request": (
                    dict(self.last_request)
                    if self.last_request is not None
                    else None
                ),
                "last_response": (
                    dict(self.last_response)
                    if self.last_response is not None
                    else None
                ),
            }

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat()