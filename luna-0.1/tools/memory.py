import sqlite3
from livekit.agents import function_tool, RunContext

DATABASE_PATH = "data/luna.db"


def initialize_database():
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


@function_tool()
async def remember(
    context: RunContext,
    memory: str,
) -> str:
    """
    Store an important piece of information in Luna's long-term memory.
    """

    try:
        connection = sqlite3.connect(DATABASE_PATH)
        cursor = connection.cursor()

        cursor.execute(
            "INSERT INTO memories (memory) VALUES (?)",
            (memory,),
        )

        connection.commit()
        connection.close()

        return f"I'll remember that: {memory}"

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
        connection = sqlite3.connect(DATABASE_PATH)
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT memory
            FROM memories
            WHERE memory LIKE ?
            ORDER BY created_at DESC
            LIMIT 5
            """,
            (f"%{query}%",),
        )

        results = cursor.fetchall()

        connection.close()

        if not results:
            return "I don't have anything stored about that."

        memories = "\n".join(
            f"- {row[0]}"
            for row in results
        )

        return f"Here's what I remember:\n{memories}"

    except Exception as e:
        return f"I couldn't access my memory: {e}"