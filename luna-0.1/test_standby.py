import asyncio

from core.orchestrator import LunaCore
from core.standby.manager import StandbyManager


async def main():
    luna_core = LunaCore([])
    standby = StandbyManager(luna_core, None)

    print(f"[TEST] Initial state: {luna_core.listening}")

    await standby.enter_standby()

    print(f"[TEST] Standby state: {luna_core.listening}")
    print("[TEST] Say: HEY LIVEKIT")

    while standby.in_standby:
        await asyncio.sleep(0.1)

    print(f"[TEST] Final state: {luna_core.listening}")

    await standby.shutdown()


if __name__ == "__main__":
    asyncio.run(main())