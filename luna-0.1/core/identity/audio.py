from __future__ import annotations

from collections import deque

import numpy as np
from livekit import rtc


class SpeakerAudioBuffer(rtc.FrameProcessor[rtc.AudioFrame]):
    """
    LiveKit audio frame processor used for speaker identification.

    Every frame continues through the normal LiveKit audio pipeline
    while a temporary copy is retained for speaker identification.

    Only speech-bearing frames are retained. Obvious silence is
    discarded before the embedding model sees the audio.
    """

    def __init__(
        self,
        max_seconds: float = 8.0,
        min_rms: float = 0.008,
    ):
        super().__init__()

        self.max_seconds = max_seconds
        self.min_rms = min_rms

        self._frames = deque()

        self.sample_rate: int | None = None
        self.num_channels: int | None = None

    # ---------------------------------------------------------
    # AUDIO ANALYSIS
    # ---------------------------------------------------------

    @staticmethod
    def _calculate_rms(
        pcm_data: bytes,
    ) -> float:
        if not pcm_data:
            return 0.0

        samples = np.frombuffer(
            pcm_data,
            dtype=np.int16,
        ).astype(np.float32)

        if samples.size == 0:
            return 0.0

        samples /= 32768.0

        return float(
            np.sqrt(
                np.mean(
                    samples * samples
                )
            )
        )

    # ---------------------------------------------------------
    # FRAME PROCESSING
    # ---------------------------------------------------------

    async def process_frame(
        self,
        frame: rtc.AudioFrame,
    ) -> rtc.AudioFrame:
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

        if data:
            duration = (
                frame.samples_per_channel
                / sample_rate
            )

            rms = self._calculate_rms(data)

            # Keep only frames containing meaningful audio.
            if rms >= self.min_rms:
                self._frames.append(
                    (
                        data,
                        duration,
                    )
                )

                total_duration = sum(
                    item[1]
                    for item in self._frames
                )

                while (
                    self._frames
                    and total_duration > self.max_seconds
                ):
                    _, removed_duration = (
                        self._frames.popleft()
                    )

                    total_duration -= (
                        removed_duration
                    )

        # IMPORTANT:
        # Return the original frame so LiveKit continues
        # processing it normally.
        return frame

    # ---------------------------------------------------------
    # EXTRACTION
    # ---------------------------------------------------------

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

    # ---------------------------------------------------------
    # STATE
    # ---------------------------------------------------------

    @property
    def duration(self) -> float:
        return sum(
            duration
            for _, duration in self._frames
        )

    @property
    def has_audio(self) -> bool:
        return bool(self._frames)

    def clear(self) -> None:
        self._frames.clear()

        self.sample_rate = None
        self.num_channels = None