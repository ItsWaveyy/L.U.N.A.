from collections import deque

import numpy as np
from livekit import rtc


class SpeakerAudioBuffer:
    """
    Stores a short rolling window of microphone audio.

    This buffer is intentionally separate from the LiveKit audio
    pipeline. The FrameProcessor below copies frames into it while
    returning the original frame unchanged so STT/VAD continue normally.
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

    def get_audio(
        self,
        max_seconds: float = 5.0,
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

        selected = []
        duration = 0.0

        for data, frame_duration in reversed(
            self._frames
        ):
            selected.append(
                (
                    data,
                    frame_duration,
                )
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
        """
        Return useful debugging information about the buffer.
        """

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

        duration = sum(
            frame_duration
            for _, frame_duration in self._frames
        )

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
    LiveKit audio FrameProcessor that copies microphone frames
    into SpeakerAudioBuffer while returning the original frame.

    This is inserted directly into RoomIO's audio pipeline.
    """

    def __init__(
        self,
        buffer: SpeakerAudioBuffer,
    ):
        self.buffer = buffer
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(
        self,
        value: bool,
    ) -> None:
        self._enabled = bool(value)

    def _process(
        self,
        frame: rtc.AudioFrame,
    ) -> rtc.AudioFrame:
        if self.enabled:
            self.buffer.push(frame)

        return frame

    def _close(self) -> None:
        pass