import asyncio
import sys
from pathlib import Path

# Add the L.U.N.A. project root to Python's import path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path.cwd()))

from core.standby.wake_detector import WakeDetector


async def main():
    print()
    print("========================================")
    print("        L.U.N.A. WAKE WORD TEST")
    print("========================================")
    print()
    print('Listening for "Hey Luna"...')
    print("Press Ctrl+C to stop.")
    print()

    detector = WakeDetector(
        threshold=0.5,
        debounce=2.0,
    )

    while True:
        detection = await detector.wait_for_wake()

        print()
        print(
            f"🔥 WAKE DETECTED: {detection.name} "
            f"confidence={detection.confidence:.3f}"
        )
        print()
        print('Listening again for "Hey Luna"...')


if __name__ == "__main__":
    asyncio.run(main())
