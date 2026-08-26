from collections import deque
import asyncio
import time

import numpy as np
from livekit import rtc

from core.identity.speaker import SpeakerIdentity, SpeakerMatch


class SpeakerAudioBuffer:
    """
    Rolling raw microphone buffer used exclusively by the
    speaker-identity gate.
    """

    def __init__(
        self,
        max_seconds: float = 8.0,
    ):
        self.max_seconds = max_seconds
        self._frames = deque()

        self.sample_rate: int | None = None
        self.num_channels: int | None = None

    def push(
        self,
        frame: rtc.AudioFrame,
    ) -> None:
        sample_rate = frame.sample_rate
        num_channels = frame.num_channels

        if (
            self.sample_rate is not None
            and (
                sample_rate != self.sample_rate
                or num_channels != self.num_channels
            )
        ):
            self.clear()

        self.sample_rate = sample_rate
        self.num_channels = num_channels

        data = bytes(frame.data)

        duration = (
            frame.samples_per_channel
            / sample_rate
        )

        self._frames.append(
            (
                data,
                duration,
            )
        )

        total_duration = sum(
            duration
            for _, duration in self._frames
        )

        while (
            self._frames
            and total_duration > self.max_seconds
        ):
            _, removed_duration = (
                self._frames.popleft()
            )

            total_duration -= removed_duration

    def duration(self) -> float:
        return sum(
            duration
            for _, duration in self._frames
        )

    def get_audio(
        self,
        max_seconds: float | None = None,
    ) -> tuple[
        bytes,
        int | None,
        int | None,
    ]:
        if not self._frames:
            return (
                b"",
                self.sample_rate,
                self.num_channels,
            )

        if max_seconds is None:
            selected = list(self._frames)
        else:
            selected = []
            duration = 0.0

            for data, frame_duration in reversed(
                self._frames
            ):
                selected.append(
                    (data, frame_duration)
                )

                duration += frame_duration

                if duration >= max_seconds:
                    break

            selected.reverse()

        pcm = b"".join(
            data
            for data, _ in selected
        )

        return (
            pcm,
            self.sample_rate,
            self.num_channels,
        )

    def stats(self) -> dict:
        if not self._frames:
            return {
                "frames": 0,
                "buffered_bytes": 0,
                "duration": 0.0,
                "peak_rms": 0.0,
            }

        pcm = b"".join(
            data
            for data, _ in self._frames
        )

        duration = self.duration()

        try:
            samples = np.frombuffer(
                pcm,
                dtype=np.int16,
            ).astype(np.float32)

            if samples.size:
                rms = float(
                    np.sqrt(
                        np.mean(
                            np.square(samples)
                        )
                    )
                )

                peak_rms = rms / 32768.0
            else:
                peak_rms = 0.0

        except Exception:
            peak_rms = 0.0

        return {
            "frames": len(self._frames),
            "buffered_bytes": len(pcm),
            "duration": duration,
            "peak_rms": peak_rms,
        }

    def clear(self) -> None:
        self._frames.clear()
        self.sample_rate = None
        self.num_channels = None


class SpeakerIdentityProcessor(
    rtc.FrameProcessor[rtc.AudioFrame]
):
    """
    HARD SPEAKER GATE.

    Raw microphone audio enters here first.

    Unauthorized audio NEVER reaches the downstream processor.

    Authorized audio is released only after speaker identity
    has passed authorization.

    Pipeline:

        microphone
            ↓
        SpeakerIdentityProcessor
            ↓
        authorization
            ↓
        ai-coustics
            ↓
        Silero VAD
            ↓
        Groq STT
            ↓
        L.U.N.A.
    """

    REQUIRED_AUDIO_SECONDS = 1.25

    # RMS threshold used ONLY to determine whether meaningful
    # speech/audio has started. This is not the AgentSession VAD.
    SPEECH_RMS_THRESHOLD = 0.008

    # How long silence must persist before a denied/unfinished
    # attempt is considered a new attempt.
    RESET_SILENCE_SECONDS = 0.9

    def __init__(
        self,
        buffer: SpeakerAudioBuffer,
        speaker_identity: SpeakerIdentity,
        downstream: rtc.FrameProcessor[rtc.AudioFrame],
    ):
        self.buffer = buffer
        self.speaker_identity = speaker_identity
        self.downstream = downstream

        self._enabled = True

        self._state = "locked"

        self._identity_task: asyncio.Task | None = None

        self._last_audio_time = 0.0
        self._speech_started_at: float | None = None

        self.last_match: SpeakerMatch | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(
        self,
        value: bool,
    ) -> None:
        self._enabled = bool(value)

    # ---------------------------------------------------------
    # AUDIO ANALYSIS
    # ---------------------------------------------------------

    @staticmethod
    def _rms(
        frame: rtc.AudioFrame,
    ) -> float:
        try:
            samples = np.frombuffer(
                bytes(frame.data),
                dtype=np.int16,
            ).astype(np.float32)

            if samples.size == 0:
                return 0.0

            return float(
                np.sqrt(
                    np.mean(
                        np.square(samples)
                    )
                )
                / 32768.0
            )

        except Exception:
            return 0.0

    # ---------------------------------------------------------
    # SILENCE FRAME
    # ---------------------------------------------------------

    @staticmethod
    def _silence_like(
        frame: rtc.AudioFrame,
    ) -> rtc.AudioFrame:
        return rtc.AudioFrame(
            data=bytes(
                len(frame.data)
            ),
            sample_rate=frame.sample_rate,
            num_channels=frame.num_channels,
            samples_per_channel=frame.samples_per_channel,
        )

    # ---------------------------------------------------------
    # RELEASE BUFFER
    # ---------------------------------------------------------

    def _release_buffer(
        self,
        current_frame: rtc.AudioFrame,
    ) -> rtc.AudioFrame:
        """
        Combine the buffered pre-auth audio with the current frame.

        This lets the first ~1.25 seconds of speech reach ai-coustics
        after authorization instead of being permanently lost.
        """

        pcm_data, sample_rate, num_channels = (
            self.buffer.get_audio()
        )

        current_data = bytes(
            current_frame.data
        )

        combined = (
            pcm_data
            + current_data
        )

        self.buffer.clear()

        sample_rate = (
            sample_rate
            or current_frame.sample_rate
        )

        num_channels = (
            num_channels
            or current_frame.num_channels
        )

        samples_per_channel = (
            len(combined)
            // (num_channels * 2)
        )

        return rtc.AudioFrame(
            data=combined,
            sample_rate=sample_rate,
            num_channels=num_channels,
            samples_per_channel=samples_per_channel,
        )

    # ---------------------------------------------------------
    # IDENTITY
    # ---------------------------------------------------------

    def _start_identity_check(self) -> None:
        if self._identity_task is not None:
            return

        pcm_data, sample_rate, num_channels = (
            self.buffer.get_audio()
        )

        if not pcm_data:
            return

        if (
            sample_rate is None
            or num_channels is None
        ):
            return

        print(
            "[L.U.N.A.] Speaker gate: "
            f"checking identity from "
            f"{self.buffer.duration():.2f}s of raw audio"
        )

        self._state = "checking"

        self._identity_task = asyncio.create_task(
            self._identify(
                pcm_data,
                sample_rate,
                num_channels,
            )
        )

    async def _identify(
        self,
        pcm_data: bytes,
        sample_rate: int,
        num_channels: int,
    ) -> None:
        try:
            match = await (
                self.speaker_identity.identify_pcm(
                    pcm_data=pcm_data,
                    sample_rate=sample_rate,
                    num_channels=num_channels,
                )
            )

            self.last_match = match

            print(
                "[L.U.N.A.] Speaker gate: "
                f"{match.name or 'unknown'} "
                f"({match.confidence:.2f}) "
                f"authorized={match.authorized}"
            )

            if match.authorized:
                self._state = "authorized"

                print(
                    "[L.U.N.A.] Speaker gate: "
                    "AUTHORIZED — releasing buffered audio."
                )

            else:
                self._state = "locked"

                print(
                    "[L.U.N.A.] Speaker gate: "
                    "UNAUTHORIZED — dropping audio."
                )

                self.buffer.clear()

        except Exception as exc:
            print(
                "[L.U.N.A.] Speaker gate error: "
                f"{exc}"
            )

            self.last_match = None
            self._state = "locked"
            self.buffer.clear()

        finally:
            self._identity_task = None

    # ---------------------------------------------------------
    # RESET
    # ---------------------------------------------------------

    def reset(self) -> None:
        """
        Lock the gate for the next speaker attempt.
        """

        if (
            self._identity_task is not None
            and not self._identity_task.done()
        ):
            self._identity_task.cancel()

        self._identity_task = None

        self._state = "locked"

        self.last_match = None

        self._speech_started_at = None
        self._last_audio_time = 0.0

        self.buffer.clear()

    # ---------------------------------------------------------
    # PROCESS
    # ---------------------------------------------------------

    def _process(
        self,
        frame: rtc.AudioFrame,
    ) -> rtc.AudioFrame:

        print(
            "[L.U.N.A.] GATE FRAME:",
            frame.sample_rate,
            frame.num_channels,
            frame.samples_per_channel,
        )

        if not self.enabled:
            return self.downstream._process(frame)

        # ---------------------------------------------------------
        # AUTHORIZED
        # ---------------------------------------------------------

        if self._state == "authorized":

            if is_speech_like:
                self._last_audio_time = now

            # If we still have buffered pre-auth audio,
            # release it BEFORE continuing with live audio.
            if self.buffer.duration() > 0:
                released = self._release_buffer(frame)

                return self.downstream._process(
                    released
                )

            # If the speaker stops talking, lock again.
            if (
                self._last_audio_time
                and (
                    now - self._last_audio_time
                    > self.RESET_SILENCE_SECONDS
                )
            ):
                print(
                    "[L.U.N.A.] Speaker gate: "
                    "speech ended — locking."
                )

                self.reset()

                return self._silence_like(frame)

            # Authorized live audio passes normally.
            return self.downstream._process(frame)

        # ---------------------------------------------------------
        # LOCKED / CHECKING
        # ---------------------------------------------------------

        if is_speech_like:
            self._last_audio_time = now

            if self._speech_started_at is None:
                self._speech_started_at = now

                print(
                    "[L.U.N.A.] Speaker gate: "
                    "speech detected — buffering."
                )

        # EVERYTHING BEFORE AUTHORIZATION STAYS HERE.
        self.buffer.push(frame)

        # ---------------------------------------------------------
        # IDENTITY CHECK
        # ---------------------------------------------------------

        if (
            self._state == "locked"
            and self._speech_started_at is not None
            and self.buffer.duration()
            >= self.REQUIRED_AUDIO_SECONDS
        ):
            self._start_identity_check()

        # ---------------------------------------------------------
        # UNAUTHORIZED / CHECKING
        # ---------------------------------------------------------

        if (
            self._last_audio_time
            and (
                now - self._last_audio_time
                > self.RESET_SILENCE_SECONDS
            )
        ):
            self.reset()

        # HARD GATE:
        # NOTHING REACHES AI-COUSTICS UNTIL AUTHORIZED.
        return self._silence_like(frame)

    def _close(self) -> None:
        if (
            self._identity_task is not None
            and not self._identity_task.done()
        ):
            self._identity_task.cancel()

        self._identity_task = None

        try:
            self.downstream._close()
        except Exception:
            pass