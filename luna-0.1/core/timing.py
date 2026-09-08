from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


def luna_log(
    message: str,
    *,
    debug: bool = False,
) -> None:
    """Write an immediately visible L.U.N.A. log line."""

    if debug:
        from config import LUNA_DEBUG

        if not LUNA_DEBUG:
            return

        message = f"[DEBUG] {message}"

    print(
        f"[L.U.N.A.] {message}",
        flush=True,
    )


@dataclass
class TurnTiming:
    """High-resolution timings for one L.U.N.A. response turn."""

    started_at: float = field(
        default_factory=time.perf_counter
    )

    durations: dict[str, float] = field(
        default_factory=dict
    )

    def measure(
        self,
        name: str,
    ):
        return _Timer(self, name)

    def add(
        self,
        name: str,
        seconds: float | None,
    ) -> None:
        if seconds is not None:
            self.durations[name] = max(
                0.0,
                float(seconds),
            )


class _Timer:
    def __init__(
        self,
        owner: TurnTiming,
        name: str,
    ):
        self.owner = owner
        self.name = name
        self.started = 0.0

    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        self.owner.durations[self.name] = (
            time.perf_counter()
            - self.started
        )


def format_seconds(
    value: float | None,
) -> str:
    if value is None:
        return "n/a"

    return f"{value:.3f}s"


def log_turn_timing(
    timing: TurnTiming,
) -> None:
    luna_log(
        "── TURN TIMING ─────────────────────────"
    )

    for name, seconds in timing.durations.items():
        label = (
            name
            .replace("_", " ")
            .title()
        )

        luna_log(
            f"{label:<28} "
            f"{format_seconds(seconds)}"
        )

    luna_log(
        "────────────────────────────────────────"
    )