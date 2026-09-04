"""Reminder tools for L.U.N.A."""

from __future__ import annotations

from datetime import datetime

from core.conversation import ConversationStore


_conversations = ConversationStore()


def create_reminder(
    message: str,
    remind_at: str,
) -> str:
    """
    Create a persistent reminder.

    Args:
        message:
            What L.U.N.A. should remind the user about.
        remind_at:
            ISO-8601 datetime including timezone.

    Returns:
        Confirmation text.
    """
    try:
        reminder_time = datetime.fromisoformat(
            remind_at
        )
    except ValueError as exc:
        return (
            "I couldn't understand that reminder time."
        )

    if reminder_time.tzinfo is None:
        return (
            "The reminder time must include a timezone."
        )

    reminder_id = (
        _conversations.add_reminder(
            message=message,
            remind_at=reminder_time,
        )
    )

    return (
        f"Reminder {reminder_id} created for "
        f"{reminder_time.astimezone().strftime('%Y-%m-%d %I:%M %p')}."
    )