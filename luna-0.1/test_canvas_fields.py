import asyncio

from tools.canvas import _fetch_calendar


async def main():
    calendar = await _fetch_calendar()

    for event in calendar.walk("VEVENT"):
        summary = str(event.get("SUMMARY", "")).strip()

        if "Assignment 1" in summary:
            print("\n=== ASSIGNMENT 1 RAW FIELDS ===")

            for key, value in event.items():
                print(f"{key}: {value!r}")

            break


asyncio.run(main())