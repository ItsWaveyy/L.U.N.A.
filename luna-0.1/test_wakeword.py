import asyncio

from core.standby.wake_detector import WakeDetector


async def main():
    detector = WakeDetector()

    print("L.U.N.A. wake detector online.")
    print("Say: HEY LUNA")

    detection = await detector.wait_for_wake()

    print(
        f"WAKE DETECTED: "
        f"{detection.name} "
        f"confidence={detection.confidence:.2f}"
    )


if __name__ == "__main__":
    asyncio.run(main())