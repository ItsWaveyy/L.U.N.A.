import asyncio

from core.standby.wake_detector import WakeDetector


class StandbyManager:
    """
    Controls L.U.N.A.'s standby lifecycle.

    Awake:
        LiveKit owns the microphone and handles normal STT.

    Standby:
        LiveKit's audio input is detached completely.
        The dedicated local ONNX wake detector owns the microphone.

    Wake:
        LiveKit audio input is restored.
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

        # Preserve LiveKit's original audio input so we can restore it.
        self._livekit_audio_input = None

    @property
    def in_standby(self) -> bool:
        return not self.luna_core.listening

    @property
    def wake_detector_active(self) -> bool:
        return self._wake_detector_active

    def _disable_livekit_audio(self) -> None:
        """
        Completely detach LiveKit's audio input.

        This is stronger than set_audio_enabled(False).
        It prevents the AgentSession from continuing to feed
        microphone audio into the STT pipeline.
        """

        if self.session.input.audio is None:
            return

        self._livekit_audio_input = self.session.input.audio

        self.session.input.audio = None

        print(
            "[L.U.N.A.] LiveKit audio input: detached."
        )

    def _enable_livekit_audio(self) -> None:
        """
        Restore LiveKit's original audio input.
        """

        if self._livekit_audio_input is None:
            return

        self.session.input.audio = (
            self._livekit_audio_input
        )

        self.session.input.set_audio_enabled(True)

        print(
            "[L.U.N.A.] LiveKit audio input: restored."
        )

        self._livekit_audio_input = None

    async def enter_standby(self) -> None:
        if self.in_standby:
            return

        print("[L.U.N.A.] Entering standby...")

        # Stop L.U.N.A.'s normal listening state first.
        self.luna_core.set_listening(False)

        # Completely detach LiveKit from the microphone.
        self._disable_livekit_audio()

        # Start dedicated wake detection.
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

        # Give the microphone back to LiveKit.
        self._enable_livekit_audio()

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

        # Make sure LiveKit gets its microphone back if
        # shutdown happens while L.U.N.A. is asleep.
        self._enable_livekit_audio()