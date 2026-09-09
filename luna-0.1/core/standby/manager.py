import asyncio
import time

from core.identity.access import AccessController
from core.identity.speaker import SpeakerIdentity
from core.standby.wake_detector import WakeDetector


SPEAKER_SAMPLE_DURATION = 1.5
SPEAKER_SAMPLE_RATE = 16000
SPEAKER_SAMPLE_CHANNELS = 1


class StandbyManager:
    """
    Controls L.U.N.A.'s standby lifecycle.

    Awake:
        LiveKit owns the microphone and handles normal STT.

    Standby:
        LiveKit's audio input is detached completely.
        The dedicated local ONNX wake detector owns the microphone.

    Wake:
        A wake word is detected.
        A short local speaker sample is captured.
        Speaker identity is checked.
        Only an authorized speaker may wake L.U.N.A.
    """

    def __init__(
        self,
        luna_core,
        session,
    ):
        self.luna_core = luna_core
        self.session = session

        self.wake_detector = WakeDetector()

        self.speaker_identity = SpeakerIdentity()
        self.access_controller = AccessController()

        self._wake_task = None
        self._stop_event = asyncio.Event()
        self._wake_detector_active = False

        # Speaker authorization state used during wake.
        self.awaiting_speaker_authorization = False

        # Preserve LiveKit's original audio input so it can be restored.
        self._livekit_audio_input = None

    # ---------------------------------------------------------
    # STATE
    # ---------------------------------------------------------

    @property
    def in_standby(self) -> bool:
        return not self.luna_core.listening

    @property
    def wake_detector_active(self) -> bool:
        return self._wake_detector_active

    # ---------------------------------------------------------
    # LIVEKIT AUDIO
    # ---------------------------------------------------------

    def _disable_livekit_audio(self) -> None:
        """
        Completely detach LiveKit's audio input.

        This prevents normal STT from receiving microphone audio
        while the local wake detector owns the microphone.
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

    # ---------------------------------------------------------
    # SPEAKER CAPTURE
    # ---------------------------------------------------------

    async def _capture_speaker_sample(
        self,
        duration: float = SPEAKER_SAMPLE_DURATION,
    ) -> bytes:
        """
        Capture a short local microphone sample for speaker
        identification.

        The wake detector must have released the microphone
        before this is called.
        """

        return await asyncio.to_thread(
            self._capture_speaker_sample_sync,
            duration,
        )

    @staticmethod
    def _capture_speaker_sample_sync(
        duration: float,
    ) -> bytes:
        """
        Synchronous PyAudio microphone capture.

        Returns raw 16-bit mono PCM at 16 kHz.
        """

        import pyaudio

        audio = pyaudio.PyAudio()

        stream = None

        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=SPEAKER_SAMPLE_CHANNELS,
                rate=SPEAKER_SAMPLE_RATE,
                input=True,
                frames_per_buffer=1024,
            )

            frames = []

            deadline = (
                time.monotonic()
                + duration
            )

            while time.monotonic() < deadline:
                frames.append(
                    stream.read(
                        1024,
                        exception_on_overflow=False,
                    )
                )

            return b"".join(frames)

        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()

            audio.terminate()

    # ---------------------------------------------------------
    # SPEAKER AUTHORIZATION
    # ---------------------------------------------------------

    async def _authorize_wake(self) -> bool:
        """
        Capture the speaker immediately after the wake word
        and determine whether they are authorized to wake L.U.N.A.
        """

        print(
            "[L.U.N.A.] Identifying wake speaker..."
        )

        try:
            pcm_data = await self._capture_speaker_sample()

            match = await self.speaker_identity.identify_pcm(
                pcm_data=pcm_data,
                sample_rate=SPEAKER_SAMPLE_RATE,
                num_channels=SPEAKER_SAMPLE_CHANNELS,
            )

            decision = self.access_controller.can_wake(
                match
            )

            print(
                "[L.U.N.A.] Speaker identity: "
                f"{self.access_controller.describe(match)}"
            )

            print(
                "[L.U.N.A.] Wake authorization: "
                f"{'GRANTED' if decision.allowed else 'DENIED'}"
            )

            if not decision.allowed:
                print(
                    f"[L.U.N.A.] {decision.reason}"
                )

            return decision.allowed

        except Exception as exc:
            print(
                "[L.U.N.A.] Speaker authorization failed: "
                f"{exc}"
            )

            return False

    # ---------------------------------------------------------
    # STANDBY
    # ---------------------------------------------------------

    async def enter_standby(self) -> None:
        if self.in_standby:
            return

        print(
            "[L.U.N.A.] Entering standby..."
        )

        await self.luna_core.set_listening(False)

        self._disable_livekit_audio()

        # Give CoreAudio time to release the microphone.
        await asyncio.sleep(0.25)

        self._stop_event.clear()
        self._wake_detector_active = True

        self._wake_task = asyncio.create_task(
            self._wait_for_wake()
        )

        print(
            "[L.U.N.A.] Standby mode active."
        )

        print(
            "[L.U.N.A.] Wake detection available."
        )

    # ---------------------------------------------------------
    # WAKE DETECTION
    # ---------------------------------------------------------

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

            self.begin_wake_authorization()

            authorized = await self._authorize_wake()

            if authorized:
                self.complete_wake_authorization()
                await self.wake()
            else:
                await self.reject_wake()

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            print(
                f"[L.U.N.A.] Wake detector error: {exc}"
            )

        finally:
            self._wake_detector_active = False

    # ---------------------------------------------------------
    # WAKE
    # ---------------------------------------------------------

    async def wake(self) -> None:
        if not self.in_standby:
            return

        print(
            "[L.U.N.A.] Waking..."
        )

        self._stop_event.set()
        self._wake_detector_active = False

        if self._wake_task:
            current_task = asyncio.current_task()

            if self._wake_task is not current_task:
                self._wake_task.cancel()

                try:
                    await self._wake_task

                except asyncio.CancelledError:
                    pass

            self._wake_task = None

        # Give CoreAudio time to release the wake detector.
        await asyncio.sleep(0.25)

        self._enable_livekit_audio()

        await self.luna_core.set_listening(True)

        print(
            "[L.U.N.A.] Wake authorized."
        )

    def begin_wake_authorization(self) -> None:
        """
        Mark the standby manager as waiting for speaker
        authorization after the wake word is detected.
        """
        self.awaiting_speaker_authorization = True

        print(
            "[L.U.N.A.] Awaiting speaker authorization..."
        )

    def complete_wake_authorization(self) -> None:
        """
        Accept the currently detected speaker and clear
        the pending authorization state.
        """
        self.awaiting_speaker_authorization = False

        print(
            "[L.U.N.A.] Speaker authorization complete."
        )

    async def reject_wake(self) -> None:
        """
        Reject an unauthorized wake attempt and return
        L.U.N.A. to standby.
        """
        print(
            "[L.U.N.A.] Unauthorized wake rejected."
        )

        self.awaiting_speaker_authorization = False

        # Make sure the wake detector remains active.
        if not self.in_standby:
            await self.luna_core.set_listening(False)

        if not self._wake_detector_active:
            self._stop_event.clear()
            self._wake_detector_active = True

            self._wake_task = asyncio.create_task(
                self._wait_for_wake()
            )

    # ---------------------------------------------------------
    # REMINDER NOTIFICATIONS
    # ---------------------------------------------------------

    async def notify(self, message: str) -> None:
        """
        Temporarily wake L.U.N.A. to deliver an internal
        notification, then return to standby when appropriate.

        Reminder notifications bypass wake-word and speaker
        authorization because they originate from L.U.N.A.
        herself.
        """

        message = (message or "").strip()

        if not message:
            return

        was_in_standby = self.in_standby

        if was_in_standby:
            print(
                "[L.U.N.A.] Reminder notification: "
                "temporarily waking..."
            )

            await self.wake()

        try:
            await self.session.say(message)

        finally:
            if was_in_standby:
                print(
                    "[L.U.N.A.] Reminder notification complete. "
                    "Returning to standby..."
                )

                await self.enter_standby()
                
    # ---------------------------------------------------------
    # SHUTDOWN
    # ---------------------------------------------------------

    async def shutdown(self) -> None:
        self.awaiting_speaker_authorization = False
        self._stop_event.set()
        self._wake_detector_active = False

        if self._wake_task:
            current_task = asyncio.current_task()

            if self._wake_task is not current_task:
                self._wake_task.cancel()

                try:
                    await self._wake_task

                except asyncio.CancelledError:
                    pass

            self._wake_task = None

        self._enable_livekit_audio()
