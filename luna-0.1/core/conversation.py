import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DATABASE_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "luna.db"
)


class ConversationStore:
    """
    Persistent archive for L.U.N.A.'s conversations.

    This is intentionally separate from long-term memory.

    Long-term memory:
        Curated facts the user explicitly wants remembered.

    Conversation archive:
        Historical record of actual conversations.
    """

    def __init__(self) -> None:
        self.database_path = DATABASE_PATH
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

        self.session_id: int | None = None

    def _connect(self):
        return sqlite3.connect(
            self.database_path
        )

    def _initialize(self) -> None:
        connection = self._connect()

        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    ended_at TEXT
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (session_id)
                        REFERENCES conversation_sessions(id)
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conversation_messages_session
                ON conversation_messages(session_id)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_conversation_messages_created
                ON conversation_messages(created_at)
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    remind_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_reminders_remind_at
                ON reminders(remind_at)
                """
            )

            connection.commit()

        finally:
            connection.close()

    def start_session(self) -> int:
        now = datetime.now(
            timezone.utc
        ).isoformat()

        connection = self._connect()

        try:
            cursor = connection.execute(
                """
                INSERT INTO conversation_sessions
                (started_at)
                VALUES (?)
                """,
                (now,),
            )

            connection.commit()

            self.session_id = cursor.lastrowid

            return self.session_id

        finally:
            connection.close()

    def add_message(
        self,
        role: str,
        content: str,
    ) -> None:

        content = (content or "").strip()

        if not content:
            return

        if self.session_id is None:
            self.start_session()

        now = datetime.now(
            timezone.utc
        ).isoformat()

        connection = self._connect()

        try:
            connection.execute(
                """
                INSERT INTO conversation_messages
                (session_id, role, content, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    self.session_id,
                    role,
                    content,
                    now,
                ),
            )

            connection.commit()

        finally:
            connection.close()

    def end_session(self) -> None:
        if self.session_id is None:
            return

        now = datetime.now(
            timezone.utc
        ).isoformat()

        connection = self._connect()

        try:
            connection.execute(
                """
                UPDATE conversation_sessions
                SET ended_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    self.session_id,
                ),
            )

            connection.commit()

        finally:
            connection.close()

        self.session_id = None

    def add_reminder(
        self,
        message: str,
        remind_at: datetime,
    ) -> int:
        """Persist a reminder and return its database ID."""
        message = (message or "").strip()

        if not message:
            raise ValueError(
                "Reminder message cannot be empty."
            )

        created_at = datetime.now(
            timezone.utc
        ).isoformat()

        connection = self._connect()

        try:
            cursor = connection.execute(
                """
                INSERT INTO reminders
                (message, remind_at, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    message,
                    remind_at.astimezone(
                        timezone.utc
                    ).isoformat(),
                    created_at,
                ),
            )

            connection.commit()

            return int(cursor.lastrowid)

        finally:
            connection.close()


    def get_due_reminders(
        self,
        now: datetime | None = None,
    ) -> list[dict]:
        """Return all reminders that are due and not completed."""
        if now is None:
            now = datetime.now(timezone.utc)

        now_utc = now.astimezone(
            timezone.utc
        ).isoformat()

        connection = self._connect()

        try:
            rows = connection.execute(
                """
                SELECT id, message, remind_at, created_at
                FROM reminders
                WHERE completed_at IS NULL
                AND remind_at <= ?
                ORDER BY remind_at ASC
                """,
                (now_utc,),
            ).fetchall()

            return [
                {
                    "id": row[0],
                    "message": row[1],
                    "remind_at": datetime.fromisoformat(
                        row[2]
                    ),
                    "created_at": datetime.fromisoformat(
                        row[3]
                    ),
                }
                for row in rows
            ]

        finally:
            connection.close()


    def complete_reminder(
        self,
        reminder_id: int,
    ) -> None:
        """Mark a reminder as completed."""
        completed_at = datetime.now(
            timezone.utc
        ).isoformat()

        connection = self._connect()

        try:
            connection.execute(
                """
                UPDATE reminders
                SET completed_at = ?
                WHERE id = ?
                """,
                (
                    completed_at,
                    reminder_id,
                ),
            )

            connection.commit()

        finally:
            connection.close()