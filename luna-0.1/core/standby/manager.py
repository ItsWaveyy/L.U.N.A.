import asyncio

from core.standby.wake_detector import WakeDetector


class StandbyManager:
    """Controls L.U.N.A.'s sleep/standby lifecycle."""

    def __init__(self, luna_core, session):
        self.luna_core = luna_core
        self.session = session
        self.detector = WakeDetector()

        self._standby_task = None
        self._stop_event = asyncio.Event()
        self._wake_detector_active = False

    @property
    def in_standby(self) -> bool:
        return not self.luna_core.listening

    async def enter_standby(self) -> None:
        if self.in_standby:
            return

        print("[L.U.N.A.] Entering standby...")

        self.luna_core.set_listening(False)

        if self.session is not None:
            self.session.input.set_audio_enabled(False)

        self._stop_event.clear()

        self._standby_task = asyncio.create_task(
            self._standby_loop()
        )

    async def _standby_loop(self) -> None:
        print("[L.U.N.A.] Wake detector active.")
        self._wake_detector_active = True

        try:
            while not self._stop_event.is_set():
                detection = await self.detector.wait_for_wake()

                if detection is None:
                    continue

                await self.wake()
                break

        except asyncio.CancelledError:
            pass

        finally:
            self._wake_detector_active = False

    @property
    def wake_detector_active(self) -> bool:
        return self._wake_detector_active

    async def wake(self) -> None:
        if not self.in_standby:
            return

        print("[L.U.N.A.] Waking...")

        self._stop_event.set()

        if self.session is not None:
            self.session.input.set_audio_enabled(True)

        self.luna_core.set_listening(True)

        print("[L.U.N.A.] Standby ended.")

    async def shutdown(self) -> None:
        self._stop_event.set()

        if self._standby_task:
            self._standby_task.cancel()

            try:
                await self._standby_task
            except asyncio.CancelledError:
                pass

            self._standby_task = None