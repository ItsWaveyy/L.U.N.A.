import asyncio

from core.canvas.calendar import CanvasCalendar


async def main():
    calendar = CanvasCalendar()

    events = await calendar.fetch_events()

    print(
        f"[TEST] Canvas events loaded: {len(events)}"
    )

    for event in events[:10]:
        print(
            "[TEST]",
            event.start,
            "->",
            event.title,
        )


if __name__ == "__main__":
    asyncio.run(main())