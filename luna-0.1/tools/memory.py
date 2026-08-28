import sqlite3
from pathlib import Path

from livekit.agents import function_tool, RunContext

DATABASE_PATH = Path(__file__).resolve().parent.parent / "data" / "luna.db"


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)

    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


async def store_memory(memory: str) -> str:
    """Store memory without depending on LiveKit's tool context."""

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        connection.execute(
            "INSERT INTO memories (memory) VALUES (?)",
            (memory,),
        )
        connection.commit()
    finally:
        connection.close()

    return f"I'll remember that: {memory}"


async def recall_memories(query: str) -> str:
    """Search memory without depending on LiveKit's tool context."""

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)

    try:
        results = connection.execute(
            """
            SELECT memory
            FROM memories
            WHERE memory LIKE ?
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (f"%{query}%",),
        ).fetchall()
    finally:
        connection.close()

    if not results:
        return "I don't have anything stored about that."

    memories = "\n".join(
        f"- {row[0]}"
        for row in results
    )
    return f"Here's what I remember:\n{memories}"


@function_tool()
async def remember(
    context: RunContext,
    memory: str,
) -> str:
    """
    Store an important piece of information in Luna's long-term memory.
    """

    try:
        return await store_memory(memory)

    except Exception as e:
        return f"I couldn't save that memory: {e}"


@function_tool()
async def recall(
    context: RunContext,
    query: str,
) -> str:
    """
    Search Luna's long-term memory for something relevant.
    """

    try:
        return await recall_memories(query)

    except Exception as e:
        return f"I couldn't access my memory: {e}"
