from collections import deque
import asyncio
import time
import wave

import numpy as np
from livekit import rtc

from pathlib import Path

from core.identity.speaker import SpeakerIdentity, SpeakerMatch
from core.timing import luna_log


class SpeakerAudioBuffer:
    """
    Rolling raw microphone buffer used by the asynchronous
    speaker-identity system.

    This buffer is NOT an authorization gate.

    It exists only to provide enough recent speech for speaker
    identification without interrupting the normal audio pipeline.
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
    ASYNCHRONOUS SPEAKER IDENTITY PROCESSOR.

    Speaker identity is treated as an informational signal rather
    than a hard audio authorization gate.

    Active-mode pipeline:

        microphone
            ↓
        SpeakerIdentityProcessor
            ├──→ background speaker identification
            │
            └──→ downstream audio immediately
                    ↓
                ai-coustics
                    ↓
                Silero VAD
                    ↓
                STT
                    ↓
                L.U.N.A.

    IMPORTANT:

    This processor NEVER blocks active-mode audio while waiting for
    speaker identification.

    Speaker authorization remains the responsibility of the
    standby/wake system.
    """

    REQUIRED_AUDIO_SECONDS = 2.5

    SPEECH_RMS_THRESHOLD = 0.008

    RESET_SILENCE_SECONDS = 0.9

    # Minimum amount of fresh speech that must accumulate before
    # another identity check is allowed.
    IDENTITY_RECHECK_SECONDS = 2.5

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

        self._identity_task: asyncio.Task | None = None

        self._last_audio_time = 0.0
        self._speech_started_at: float | None = None

        self._last_identity_check_at = 0.0

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
    # DEBUG AUDIO
    # ---------------------------------------------------------

    def _save_debug_audio(self) -> None:
        """
        Save the exact raw microphone audio used for a speaker
        identity check.

        These recordings are calibration samples only. They are
        intentionally captured before ai-coustics / VAD processing
        so they represent the same raw audio that reaches the
        identity system.
        """

        pcm_data, sample_rate, num_channels = (
            self.buffer.get_audio(
                max_seconds=self.REQUIRED_AUDIO_SECONDS
            )
        )

        if (
            not pcm_data
            or sample_rate is None
            or num_channels is None
        ):
            return

        output_dir = (
            Path(__file__).resolve().parents[2]
            / "data"
            / "speakers"
            / "test"
        )

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        existing = sorted(
            output_dir.glob(
                "live_*.wav"
            )
        )

        next_number = len(existing) + 1

        while (
            output_dir
            / f"live_{next_number:03d}.wav"
        ).exists():
            next_number += 1

        output_path = (
            output_dir
            / f"live_{next_number:03d}.wav"
        )

        with wave.open(
            str(output_path),
            "wb",
        ) as wav:
            wav.setnchannels(num_channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm_data)

        luna_log(
            "IDENTITY CALIBRATION SAMPLE SAVED:",
            str(output_path),
            f"({sample_rate}Hz, {num_channels}ch, "
            f"{len(pcm_data)} bytes)"
        )

    # ---------------------------------------------------------
    # IDENTITY
    # ---------------------------------------------------------

    def _start_identity_check(self) -> None:
        """
        Start speaker identification in the background.

        Audio processing continues normally while the embedding
        model runs in another task/thread.
        """

        if (
            self._identity_task is not None
            and not self._identity_task.done()
        ):
            return

        pcm_data, sample_rate, num_channels = (
            self.buffer.get_audio(
                max_seconds=self.REQUIRED_AUDIO_SECONDS
            )
        )

        if not pcm_data:
            return

        if (
            sample_rate is None
            or num_channels is None
        ):
            return

        self._last_identity_check_at = time.monotonic()

        self._save_debug_audio()

        luna_log(
            "Speaker identity: "
            f"checking {self.buffer.duration():.2f}s "
            "of recent audio..."
        )

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

            luna_log(
                "Speaker identity: "
                f"{match.name or 'unknown'} "
                f"({match.confidence:.2f}) "
                f"authorized={match.authorized}"
            )

        except asyncio.CancelledError:
            raise

        except Exception as exc:
            luna_log(
                "Speaker identity error: "
                f"{exc}"
            )

        finally:
            self._identity_task = None

    # ---------------------------------------------------------
    # RESET
    # ---------------------------------------------------------

    def reset(self) -> None:
        """
        Reset the rolling identity state.

        This does NOT affect downstream audio authorization because
        this processor is not an authorization gate.
        """

        if (
            self._identity_task is not None
            and not self._identity_task.done()
        ):
            self._identity_task.cancel()

        self._identity_task = None

        self._speech_started_at = None
        self._last_audio_time = 0.0
        self._last_identity_check_at = 0.0

        self.buffer.clear()

    # ---------------------------------------------------------
    # PROCESS
    # ---------------------------------------------------------

    def _process(
        self,
        frame: rtc.AudioFrame,
    ) -> rtc.AudioFrame:

        now = time.monotonic()

        # ---------------------------------------------------------
        # DISABLED
        # ---------------------------------------------------------

        if not self.enabled:
            return self.downstream._process(frame)

        rms = self._rms(frame)

        is_speech_like = (
            rms >= self.SPEECH_RMS_THRESHOLD
        )

        # ---------------------------------------------------------
        # ALWAYS FORWARD ACTIVE AUDIO
        # ---------------------------------------------------------

        # Speaker identity NEVER blocks or modifies active-mode
        # microphone audio.

        downstream_result = (
            self.downstream._process(frame)
        )

        # ---------------------------------------------------------
        # TRACK SPEECH
        # ---------------------------------------------------------

        if is_speech_like:

            self._last_audio_time = now

            if self._speech_started_at is None:
                self._speech_started_at = now

                luna_log(
                    "Speaker identity: "
                    "speech detected."
                )

            self.buffer.push(frame)

        # ---------------------------------------------------------
        # BACKGROUND IDENTITY CHECK
        # ---------------------------------------------------------

        if (
            self._speech_started_at is not None
            and self.buffer.duration()
            >= self.REQUIRED_AUDIO_SECONDS
            and (
                self._last_identity_check_at == 0.0
                or (
                    now - self._last_identity_check_at
                    >= self.IDENTITY_RECHECK_SECONDS
                )
            )
        ):
            self._start_identity_check()

        # ---------------------------------------------------------
        # SPEECH END
        # ---------------------------------------------------------

        if (
            self._last_audio_time
            and (
                now - self._last_audio_time
                > self.RESET_SILENCE_SECONDS
            )
        ):
            self._speech_started_at = None
            self._last_audio_time = 0.0

            # Keep the most recent identity result available to the
            # rest of L.U.N.A. rather than destroying it at the end
            # of every utterance.

            self.buffer.clear()

        return downstream_result

    # ---------------------------------------------------------
    # DOWNSTREAM LIFECYCLE / AUTH PROPAGATION
    # ---------------------------------------------------------

    def _on_stream_info_updated(
        self,
        *,
        room_name: str,
        participant_identity: str,
        publication_sid: str,
    ) -> None:
        self.downstream._on_stream_info_updated(
            room_name=room_name,
            participant_identity=participant_identity,
            publication_sid=publication_sid,
        )

    def _on_stream_info_cleared(self) -> None:
        self.downstream._on_stream_info_cleared()

    def _on_credentials_updated(
        self,
        *,
        token: str,
        url: str,
    ) -> None:
        self.downstream._on_credentials_updated(
            token=token,
            url=url,
        )

    def _on_credentials_cleared(self) -> None:
        self.downstream._on_credentials_cleared()

    # ---------------------------------------------------------
    # CLOSE
    # ---------------------------------------------------------

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

    