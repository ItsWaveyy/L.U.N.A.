from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class CanvasEvent:
    """Normalized calendar event from the Canvas iCalendar feed."""

    uid: str
    title: str
    start: datetime
    end: datetime | None = None
    location: str | None = None
    description: str | None = None
    url: str | None = None

    @property
    def is_all_day(self) -> bool:
        return self.start.hour == 0 and self.start.minute == 0

    def summary(self) -> str:
        parts = [self.title]

        if self.location:
            parts.append(f"at {self.location}")

        return " ".join(parts)