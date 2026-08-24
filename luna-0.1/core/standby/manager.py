import asyncio

from core.standby.wake_detector import WakeDetector


class StandbyManager:
    """
    Controls L.U.N.A.'s standby lifecycle.

    Standby keeps the LiveKit session and microphone active.

    The dedicated WakeDetector listens for the "Hey Luna" wake word
    using the local ONNX wake-word model.
    """

    def __init__(
        self,
        luna_core,
        session,
    ):
        self.luna_core = luna_core
        self.session = session

        self.wake_detector = WakeDetector()

        self._wake_task = None
        self._stop_event = asyncio.Event()
        self._wake_detector_active = False

    @property
    def in_standby(self) -> bool:
        return not self.luna_core.listening

    @property
    def wake_detector_active(self) -> bool:
        return self._wake_detector_active

    async def enter_standby(self) -> None:
        if self.in_standby:
            return

        print("[L.U.N.A.] Entering standby...")

        self.luna_core.set_listening(False)

        self._stop_event.clear()
        self._wake_detector_active = True

        self._wake_task = asyncio.create_task(
            self._wait_for_wake()
        )

        print("[L.U.N.A.] Standby mode active.")
        print("[L.U.N.A.] Wake detection available.")

    async def _wait_for_wake(self) -> None:
        try:
            detection = await self.wake_detector.wait_for_wake()

            if self._stop_event.is_set():
                return

            print(
                f"[L.U.N.A.] Wake word detected: "
                f"{detection.name} "
                f"({detection.confidence:.2f})"
            )

            await self.wake()

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[L.U.N.A.] Wake detector error: {exc}"
            )

        finally:
            self._wake_detector_active = False

    async def wake(self) -> None:
        if not self.in_standby:
            return

        print("[L.U.N.A.] Waking...")

        self._stop_event.set()
        self._wake_detector_active = False

        self.luna_core.set_listening(True)

        print("[L.U.N.A.] Standby ended.")

    async def shutdown(self) -> None:
        self._stop_event.set()
        self._wake_detector_active = False

        if self._wake_task:
            self._wake_task.cancel()

            try:
                await self._wake_task

            except asyncio.CancelledError:
                pass

            self._wake_task = None