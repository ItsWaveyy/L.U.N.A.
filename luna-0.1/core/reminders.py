"""Persistent reminder scheduling for L.U.N.A."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from core.conversation import ConversationStore


ReminderCallback = Callable[[str], Awaitable[None]]


class ReminderScheduler:
    """Background scheduler that fires due reminders."""

    def __init__(
        self,
        conversations: ConversationStore,
        on_reminder: ReminderCallback,
        poll_interval: float = 1.0,
    ) -> None:
        self.conversations = conversations
        self.on_reminder = on_reminder
        self.poll_interval = poll_interval

        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    def start(self) -> None:
        """Start the background reminder scheduler."""

        if self._task is not None:
            return

        self._stop_event.clear()

        self._task = asyncio.create_task(
            self._run(),
            name="luna-reminder-scheduler",
        )

        print("[L.U.N.A.] Reminder scheduler: ONLINE", flush=True)

    async def _run(self) -> None:
        """Poll for due reminders and dispatch them."""

        while not self._stop_event.is_set():
            try:
                reminders = self.conversations.get_due_reminders()

                for reminder in reminders:
                    try:
                        print(
                            f"[L.U.N.A.] Reminder fired: "
                            f"{reminder['message']}",
                            flush=True,
                        )

                        await self.on_reminder(reminder["message"])

                    finally:
                        self.conversations.complete_reminder(
                            reminder["id"]
                        )

            except asyncio.CancelledError:
                raise

            except Exception as exc:
                print(
                    f"[L.U.N.A.] Reminder scheduler error: {exc}",
                    flush=True,
                )

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.poll_interval,
                )
            except asyncio.TimeoutError:
                pass

    async def shutdown(self) -> None:
        """Stop the background reminder scheduler."""

        self._stop_event.set()

        if self._task is None:
            return

        self._task.cancel()

        try:
            await self._task
        except asyncio.CancelledError:
            pass

        self._task = None

        print("[L.U.N.A.] Reminder scheduler: OFFLINE", flush=True)