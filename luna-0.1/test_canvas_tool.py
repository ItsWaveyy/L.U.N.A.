import asyncio

from tools.canvas import get_canvas_calendar


async def main():
    print(await get_canvas_calendar(scope="today"))


if __name__ == "__main__":
    asyncio.run(main())