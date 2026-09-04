from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

import httpx
from icalendar import Calendar
from dateutil import tz
from dateutil.rrule import rrulestr

from config import CANVAS_CALENDAR_URL
from core.canvas.models import CanvasEvent


class CanvasCalendar:
    """Read and normalize events from a Canvas iCalendar feed."""

    def __init__(
        self,
        feed_url: str | None = None,
    ):
        self.feed_url = (
            feed_url or CANVAS_CALENDAR_URL
        ).strip()

    async def fetch_events(
        self,
        *,
        start: datetime | date | None = None,
        end: datetime | date | None = None,
    ) -> list[CanvasEvent]:
        """
        Fetch Canvas calendar events.

        If start/end are omitted, returns events from the
        feed's available window without expanding indefinitely.
        """

        if not self.feed_url:
            raise RuntimeError(
                "Canvas calendar URL is not configured."
            )

        start_dt = self._as_datetime(start)
        end_dt = self._as_datetime(end)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=5.0,
                read=15.0,
                write=10.0,
                pool=5.0,
            )
        ) as client:
            response = await client.get(
                self.feed_url,
                headers={
                    "User-Agent": "L.U.N.A./CanvasCalendar",
                    "Accept": "text/calendar, text/plain, */*",
                },
            )

            response.raise_for_status()

        calendar = Calendar.from_ical(
            response.content
        )

        events: list[CanvasEvent] = []

        for component in calendar.walk("VEVENT"):
            events.extend(
                self._parse_event(
                    component,
                    start_dt=start_dt,
                    end_dt=end_dt,
                )
            )

        events.sort(key=lambda event: event.start)

        return events

    def _parse_event(
        self,
        component: Any,
        *,
        start_dt: datetime | None,
        end_dt: datetime | None,
    ) -> list[CanvasEvent]:
        uid = self._text(component.get("UID"))
        title = self._text(
            component.get("SUMMARY")
        ) or "Untitled Canvas event"

        dtstart = component.get("DTSTART")

        if dtstart is None:
            return []

        raw_start = dtstart.dt

        if isinstance(raw_start, datetime):
            event_start = self._normalize_datetime(
                raw_start
            )
            event_end = self._parse_end(
                component.get("DTEND")
            )
        else:
            event_start = datetime.combine(
                raw_start,
                time.min,
            ).replace(
                tzinfo=tz.tzlocal()
            )
            event_end = None

        location = self._text(
            component.get("LOCATION")
        )

        description = self._text(
            component.get("DESCRIPTION")
        )

        url = self._text(
            component.get("URL")
        )

        recurrence = component.get("RRULE")

        if recurrence is None:
            if self._overlaps_range(
                event_start,
                event_end,
                start_dt,
                end_dt,
            ):
                return [
                    CanvasEvent(
                        uid=uid,
                        title=title,
                        start=event_start,
                        end=event_end,
                        location=location,
                        description=description,
                        url=url,
                    )
                ]

            return []

        return self._expand_recurrence(
            uid=uid,
            title=title,
            start=event_start,
            end=event_end,
            location=location,
            description=description,
            url=url,
            recurrence=recurrence,
            start_dt=start_dt,
            end_dt=end_dt,
        )

    def _expand_recurrence(
        self,
        *,
        uid: str,
        title: str,
        start: datetime,
        end: datetime | None,
        location: str | None,
        description: str | None,
        url: str | None,
        recurrence: Any,
        start_dt: datetime | None,
        end_dt: datetime | None,
    ) -> list[CanvasEvent]:
        """
        Expand recurring events only inside the requested window.
        """

        if start_dt is None:
            start_dt = start

        if end_dt is None:
            end_dt = start_dt + timedelta(days=30)

        duration = (
            end - start
            if end is not None
            else None
        )

        rule = rrulestr(
            recurrence.to_ical().decode(),
            dtstart=start,
        )

        occurrences = rule.between(
            start_dt,
            end_dt,
            inc=True,
        )

        result = []

        for occurrence in occurrences:
            occurrence_end = (
                occurrence + duration
                if duration is not None
                else None
            )

            result.append(
                CanvasEvent(
                    uid=uid,
                    title=title,
                    start=occurrence,
                    end=occurrence_end,
                    location=location,
                    description=description,
                    url=url,
                )
            )

        return result

    @staticmethod
    def _parse_end(
        value: Any,
    ) -> datetime | None:
        if value is None:
            return None

        raw = value.dt

        if isinstance(raw, datetime):
            return CanvasCalendar._normalize_datetime(
                raw
            )

        return datetime.combine(
            raw,
            time.min,
        ).replace(
            tzinfo=tz.tzlocal()
        )

    @staticmethod
    def _normalize_datetime(
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            return value.replace(
                tzinfo=tz.tzlocal()
            )

        return value.astimezone(
            tz.tzlocal()
        )

    @staticmethod
    def _as_datetime(
        value: datetime | date | None,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return CanvasCalendar._normalize_datetime(
                value
            )

        return datetime.combine(
            value,
            time.min,
        ).replace(
            tzinfo=tz.tzlocal()
        )

    @staticmethod
    def _overlaps_range(
        start: datetime,
        end: datetime | None,
        range_start: datetime | None,
        range_end: datetime | None,
    ) -> bool:
        if range_start is not None and start < range_start:
            if end is None or end <= range_start:
                return False

        if range_end is not None and start >= range_end:
            return False

        return True

    @staticmethod
    def _text(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        try:
            return str(value)
        except Exception:
            return None