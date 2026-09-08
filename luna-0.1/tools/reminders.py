"""Reminder tools for L.U.N.A."""

from __future__ import annotations

from datetime import datetime

from core.conversation import ConversationStore


_conversations = ConversationStore()


def create_reminder(message: str, remind_at: str) -> str:
    """Create a persistent reminder."""

    message = (message or "").strip()

    if not message:
        return "I need something to remind you about."

    try:
        reminder_time = datetime.fromisoformat(remind_at)
    except ValueError:
        return "I couldn't understand that reminder time."

    if reminder_time.tzinfo is None:
        return "The reminder time must include a timezone."

    reminder_id = _conversations.add_reminder(
        message=message,
        remind_at=reminder_time,
    )

    local_time = reminder_time.astimezone().strftime(
        "%A, %B %-d at %-I:%M %p"
    )

    return f"Reminder {reminder_id} created for {local_time}."


def list_active_reminders() -> str:
    """Return all active, incomplete reminders."""

    connection = _conversations._connect()

    try:
        rows = connection.execute(
            """
            SELECT id, message, remind_at
            FROM reminders
            WHERE completed_at IS NULL
            ORDER BY remind_at ASC
            """
        ).fetchall()
    finally:
        connection.close()

    if not rows:
        return "You don't have any active reminders."

    lines = ["Your active reminders are:"]

    for reminder_id, message, remind_at in rows:
        reminder_time = datetime.fromisoformat(remind_at).astimezone()

        formatted_time = reminder_time.strftime(
            "%A, %B %-d at %-I:%M %p"
        )

        lines.append(
            f"{reminder_id}. {message} — {formatted_time}"
        )

    return "\n".join(lines)


def cancel_reminder(reminder_id: int) -> str:
    """Cancel an active reminder."""

    try:
        reminder_id = int(reminder_id)
    except (TypeError, ValueError):
        return "I need a valid reminder ID."

    connection = _conversations._connect()

    try:
        row = connection.execute(
            """
            SELECT id, message
            FROM reminders
            WHERE id = ? AND completed_at IS NULL
            """,
            (reminder_id,),
        ).fetchone()

        if row is None:
            return f"I couldn't find active reminder {reminder_id}."

        connection.execute(
            """
            UPDATE reminders
            SET completed_at = ?
            WHERE id = ?
            """,
            (
                datetime.now().astimezone().isoformat(),
                reminder_id,
            ),
        )

        connection.commit()

        return f"Cancelled reminder {reminder_id}: {row[1]}."

    finally:
        connection.close()