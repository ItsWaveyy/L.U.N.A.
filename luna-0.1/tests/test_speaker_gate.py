from core.identity.audio import SpeakerAudioBuffer, SpeakerIdentityProcessor


class EchoDownstream:
    def __init__(self):
        self.frames = []

    def _process(self, frame):
        self.frames.append(frame)
        return frame


def _frame(data: bytes):
    from livekit import rtc

    return rtc.AudioFrame(
        data=data,
        sample_rate=16000,
        num_channels=1,
        samples_per_channel=len(data) // 2,
    )


def test_authorized_gate_releases_buffered_opening_audio_once():
    downstream = EchoDownstream()
    buffer = SpeakerAudioBuffer()
    opening = _frame(b"\x01\x00" * 160)
    current = _frame(b"\x02\x00" * 160)
    buffer.push(opening)

    processor = SpeakerIdentityProcessor(
        buffer=buffer,
        speaker_identity=object(),
        downstream=downstream,
    )
    processor._state = "authorized"

    released = processor._process(current)

    assert bytes(released.data) == bytes(opening.data) + bytes(current.data)
    assert buffer.duration() == 0
    assert downstream.frames == [released]

    next_frame = _frame(b"\x03\x00" * 160)
    processor._process(next_frame)

    assert bytes(downstream.frames[-1].data) == bytes(next_frame.data)
