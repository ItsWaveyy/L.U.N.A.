"""Canvas calendar integration for L.U.N.A."""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta

import httpx
from dotenv import load_dotenv
from icalendar import Calendar

load_dotenv()


CANVAS_CALENDAR_URL = os.getenv("CANVAS_CALENDAR_URL", "").strip().strip("'\"")


async def _fetch_calendar() -> Calendar:
    """Fetch and parse the user's Canvas calendar feed."""
    if not CANVAS_CALENDAR_URL:
        raise RuntimeError("CANVAS_CALENDAR_URL is not configured.")

    async with httpx.AsyncClient(
        timeout=httpx.Timeout(
            connect=5.0,
            read=15.0,
            write=10.0,
            pool=5.0,
        ),
        follow_redirects=True,
        headers={"User-Agent": "L.U.N.A./0.05"},
    ) as client:
        response = await client.get(CANVAS_CALENDAR_URL)
        response.raise_for_status()

    return Calendar.from_ical(response.content)


def _event_datetime(event) -> datetime:
    """Return an event's start time as a timezone-aware datetime."""
    value = event.decoded("DTSTART")

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.astimezone()

        return value

    if isinstance(value, date):
        return datetime.combine(
            value,
            datetime.min.time(),
        ).astimezone()

    raise ValueError("Canvas event has an invalid DTSTART value.")


def _event_matches_query(event, query: str) -> bool:
    """Check whether an event matches a natural-language search query."""
    if not query:
        return True

    query = query.lower().strip()

    searchable = " ".join(
        [
            str(event.get("SUMMARY", "")),
            str(event.get("DESCRIPTION", "")),
            str(event.get("LOCATION", "")),
            str(event.get("CATEGORIES", "")),
        ]
    ).lower()

    return query in searchable


def _friendly_course_name(event) -> str:
    """Extract a human-friendly course name from Canvas event metadata."""
    import re

    summary = str(event.get("SUMMARY", "")).strip()

    # Canvas commonly appends course metadata in brackets:
    # [CHEM_1035_CRN 82924 (...)_FALL 2026]
    match = re.search(r"\[([^\]]+)\]", summary)

    if not match:
        return ""

    course_metadata = match.group(1).strip()

    # The course subject is the first token before "_" or whitespace.
    subject = re.split(r"[_\s]", course_metadata, maxsplit=1)[0]
    subject = subject.strip().upper()

    subject_names = {
        "MATH": "Math",
        "CHEM": "Chemistry",
        "ENGE": "Engineering",
        "ENGL": "English",
        "PHYS": "Physics",
        "BIOL": "Biology",
        "CS": "Computer Science",
    }

    return subject_names.get(subject, subject.title())

def _event_type(event) -> str:
    """Classify a Canvas event using its title first."""
    summary = str(event.get("SUMMARY", "")).lower().strip()

    if any(
        word in summary
        for word in ("assignment", "homework", "problem set", "topic memo", "extra credit", "lab report", "project", "paper", "essay", "presentation", "oral report")
    ):
        return "assignment"

    if any(
        word in summary
        for word in ("quiz", "test", "exam")
    ):
        return "assessment"

    if any(
        word in summary
        for word in ("lecture", "class", "lesson", "learning session")
    ):
        return "class"

    return "event"

def _format_event(event) -> str:
    """Format one Canvas event into clean data for L.U.N.A."""
    start = _event_datetime(event)

    summary = str(
        event.get("SUMMARY", "Untitled event")
    ).strip()

    course = _friendly_course_name(event)
    event_type = _event_type(event)

    # Remove Canvas course IDs and other internal metadata

    summary = re.sub(
        r"\s*\[[^\]]+\]",
        "",
        summary,
    )

    summary = re.sub(
        r"\s*\([^)]*(?:_\d{4,}|CRN|fall|FALL)[^)]*\)",
        "",
        summary,
        flags=re.IGNORECASE,
    )

    summary = summary.strip()

    parts = [
        start.strftime("%Y-%m-%d"),
        event_type,
    ]

    if course:
        parts.append(course)

    parts.append(summary)

    return " | ".join(parts)


async def get_canvas_calendar(
    scope: str = "today",
    query: str = "",
    days: int = 7,
) -> str:
    """
    Get events from the user's Canvas calendar.

    Args:
        scope:
            today, tomorrow, week, or upcoming.
        query:
            Optional text to search for in event details.
        days:
            Number of days to search when scope is upcoming.

    Returns:
        A readable list of matching Canvas events.
    """
    calendar = await _fetch_calendar()

    now = datetime.now().astimezone()
    today = now.date()

    scope = scope.lower().strip()

    if scope == "today":
        start_date = today
        end_date = today + timedelta(days=1)

    elif scope == "tomorrow":
        start_date = today + timedelta(days=1)
        end_date = today + timedelta(days=2)

    elif scope == "week":
        start_date = today
        end_date = today + timedelta(days=7)

    elif scope == "upcoming":
        days = max(1, min(days, 30))
        start_date = today
        end_date = today + timedelta(days=days)

    else:
        return (
            "Invalid Canvas calendar scope. "
            "Use today, tomorrow, week, or upcoming."
        )

    events = []

    for event in calendar.walk("VEVENT"):
        try:
            event_start = _event_datetime(event)
        except (ValueError, TypeError):
            continue

        event_date = event_start.date()

        if not (start_date <= event_date < end_date):
            continue

        if not _event_matches_query(event, query):
            continue

        events.append((event_start, event))

    events.sort(key=lambda item: item[0])

    if not events:
        if query:
            return (
                f"No Canvas events found for {scope} "
                f"matching '{query}'."
            )

        return f"No Canvas events found for {scope}."

    lines = [
        f"Canvas calendar events ({scope}):",
    ]

    for _, event in events:
        lines.append(f"- {_format_event(event)}")

    return "\n".join(lines)