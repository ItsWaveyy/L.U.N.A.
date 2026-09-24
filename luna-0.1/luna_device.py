import asyncio
import os
import signal
import subprocess
import re

from dotenv import load_dotenv
from livekit import api, rtc


load_dotenv()


# ─────────────────────────────────────────────────────────────
# L.U.N.A. DEVICE CONFIGURATION
# ─────────────────────────────────────────────────────────────

LIVEKIT_URL = os.environ["LIVEKIT_URL"]
LIVEKIT_API_KEY = os.environ["LIVEKIT_API_KEY"]
LIVEKIT_API_SECRET = os.environ["LIVEKIT_API_SECRET"]

SAMPLE_RATE = 48000
CHANNELS = 1
FRAME_SAMPLES = 480

# These are stable hardware identifiers/descriptions.
# PipeWire runtime node IDs are discovered dynamically.
SPEAKER_DEVICE = "luna-echo-sink"
MIC_DEVICE = "luna-echo-source"


# ─────────────────────────────────────────────────────────────
# PIPEWIRE DEVICE DISCOVERY
# ─────────────────────────────────────────────────────────────

def discover_pipewire_node(
        device_name: str,
        node_type: str,
    ) -> str:
        """Resolve the current PipeWire node ID from wpctl status."""

        section_map = {
            "sink": "Sinks:",
            "source": "Sources:",
        }

        if node_type not in section_map:
            raise ValueError(
                f"Unsupported PipeWire node type: {node_type}"
            )

        result = subprocess.run(
            ["wpctl", "status"],
            capture_output=True,
            text=True,
            check=True,
        )

        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()

            if device_name.lower() not in line.lower():
                continue

            match = re.search(
                r"(\d+)\.\s+",
                line,
            )

            if match:
                return match.group(1)

        raise RuntimeError(
            f"L.U.N.A. could not find the required PipeWire "
            f"{node_type}: {device_name!r}"
        )

def discover_audio_devices():
    """
    Discover both required physical audio devices.

    Returns:
        (speaker_node_id, mic_node_id)
    """

    print("[DEVICE] Discovering PipeWire audio hardware...")

    speaker_node = discover_pipewire_node(
        SPEAKER_DEVICE,
        "sink",
    )

    mic_node = discover_pipewire_node(
        MIC_DEVICE,
        "source",
    )

    print(
        f"[DEVICE] Speaker: {SPEAKER_DEVICE} "
        f"(PipeWire node {speaker_node})"
    )

    print(
        f"[DEVICE] Microphone: {MIC_DEVICE} "
        f"(PipeWire node {mic_node})"
    )

    return speaker_node, mic_node


# ─────────────────────────────────────────────────────────────
# REMOTE AUDIO → USB SPEAKERS
# ─────────────────────────────────────────────────────────────

async def play_remote_audio(
    track: rtc.RemoteAudioTrack,
    speaker_node: str,
):
    loop = asyncio.get_running_loop()

    print(
        f"[DEVICE] AUDIO TRACK RECEIVED @ "
        f"{loop.time():.3f}: {track.sid}"
    )

    process = await asyncio.create_subprocess_exec(
        "pw-cat",
        "--playback",
        "--raw",
        "--format=s16",
        f"--rate={SAMPLE_RATE}",
        f"--channels={CHANNELS}",
        f"--target={speaker_node}",
        "--latency=250ms",
        "-",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )

    print(
        f"[DEVICE] SPEAKER STREAM STARTED @ "
        f"{loop.time():.3f}: PID {process.pid}"
    )

    stream = rtc.AudioStream(
        track,
        sample_rate=SAMPLE_RATE,
        num_channels=CHANNELS,
    )

    first_frame = True
    frames = 0
    total_bytes = 0
    start_time = loop.time()

    try:
        async for event in stream:
            frame = event.frame
            data = bytes(frame.data)

            if first_frame:
                first_frame = False

                print(
                    f"[DEVICE] FIRST AUDIO FRAME @ "
                    f"{loop.time():.3f}"
                )

            if process.stdin is None:
                print(
                    "[DEVICE] Speaker process has no stdin."
                )
                break

            try:
                process.stdin.write(data)
                await process.stdin.drain()

            except (
                BrokenPipeError,
                ConnectionResetError,
            ):
                print(
                    "[DEVICE] Speaker output closed."
                )
                break

            frames += 1
            total_bytes += len(data)

            if frames % 100 == 0:
                elapsed = loop.time() - start_time
                audio_seconds = (
                    total_bytes
                    / (SAMPLE_RATE * CHANNELS * 2)
                )

                print(
                    f"[DEVICE AUDIO] "
                    f"frames={frames} "
                    f"bytes={total_bytes} "
                    f"elapsed={elapsed:.2f}s "
                    f"audio={audio_seconds:.2f}s"
                )

    except asyncio.CancelledError:
        print(
            "[DEVICE] Audio playback task cancelled."
        )
        raise

    finally:
        await stream.aclose()

        if process.stdin is not None:
            try:
                process.stdin.close()
            except Exception:
                pass

        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=2.0,
            )

        except asyncio.TimeoutError:
            print(
                f"[DEVICE] Speaker process did not exit; "
                f"killing PID {process.pid}"
            )

            try:
                process.kill()
            except ProcessLookupError:
                pass

            try:
                await process.wait()
            except Exception:
                pass

        print(
            f"[DEVICE] AUDIO TRACK ENDED @ "
            f"{loop.time():.3f}"
        )


# ─────────────────────────────────────────────────────────────
# LIVEKIT TOKEN
# ─────────────────────────────────────────────────────────────

def make_token(room_name: str) -> str:
    return (
        api.AccessToken(
            api_key=LIVEKIT_API_KEY,
            api_secret=LIVEKIT_API_SECRET,
        )
        .with_identity("luna-device")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
            )
        )
        .to_jwt()
    )


# ─────────────────────────────────────────────────────────────
# MAIN DEVICE
# ─────────────────────────────────────────────────────────────

async def main():

    room_name = "luna-device-test"

    # Discover hardware BEFORE connecting to LiveKit.
    #
    # If the expected devices are missing, LUNA stops here
    # rather than connecting to the wrong audio hardware.
    speaker_node, mic_node = discover_audio_devices()

    room = rtc.Room()

    audio_tasks = set()
    pw_record = None
    disconnect_reason = None

    def on_disconnected(reason):
        nonlocal disconnect_reason

        print(
            f"[DEVICE] LIVEKIT DISCONNECTED: {reason}"
        )

        disconnect_reason = reason

        if (
            pw_record is not None
            and pw_record.poll() is None
        ):
            pw_record.send_signal(signal.SIGTERM)

    room.on(
        "disconnected",
        on_disconnected,
    )

    def on_track_subscribed(
        track,
        publication,
        participant,
    ):
        if not isinstance(
            track,
            rtc.RemoteAudioTrack,
        ):
            return

        print(
            f"[DEVICE] REMOTE AUDIO SUBSCRIBED @ "
            f"{asyncio.get_running_loop().time():.3f}: "
            f"{participant.identity} / "
            f"{publication.sid}"
        )

        task = asyncio.create_task(
            play_remote_audio(
                track,
                speaker_node,
            )
        )

        audio_tasks.add(task)

        def remove_task(done_task):
            audio_tasks.discard(done_task)

            try:
                done_task.result()

            except asyncio.CancelledError:
                pass

            except Exception as exc:
                print(
                    f"[DEVICE] Audio task error: "
                    f"{type(exc).__name__}: {exc}"
                )

        task.add_done_callback(remove_task)

    room.on(
        "track_subscribed",
        on_track_subscribed,
    )

    token = make_token(room_name)

    print(
        f"Connecting to LiveKit room: "
        f"{room_name}"
    )

    await room.connect(
        LIVEKIT_URL,
        token,
    )

    print(
        f"CONNECTED as: "
        f"{room.local_participant.identity}"
    )

    # Explicitly dispatch L.U.N.A.
    lk = api.LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )

    try:
        dispatch = (
            await lk.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name="L.U.N.A.",
                    room=room_name,
                )
            )
        )

        print(
            f"LUNA DISPATCHED: {dispatch.id}"
        )

    finally:
        await lk.aclose()

    # ─────────────────────────────────────────────
    # USB MICROPHONE → LIVEKIT
    # ─────────────────────────────────────────────

    audio_source = rtc.AudioSource(
        SAMPLE_RATE,
        CHANNELS,
    )

    audio_track = (
        rtc.LocalAudioTrack.create_audio_track(
            "luna-mic",
            audio_source,
        )
    )

    await room.local_participant.publish_track(
        audio_track,
        rtc.TrackPublishOptions(
            source=rtc.TrackSource.SOURCE_MICROPHONE,
        ),
    )

    print(
        "[DEVICE] MIC TRACK PUBLISHED"
    )

    pw_record = subprocess.Popen(
        [
            "pw-record",
            f"--target={mic_node}",
            "--media-category",
            "Record",
            "--raw",
            "--format=s16",
            f"--rate={SAMPLE_RATE}",
            f"--channels={CHANNELS}",
            "-",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        bufsize=0,
    )

    frame_bytes = (
        FRAME_SAMPLES * 2
    )

    def read_exact(
        stream,
        size,
    ):
        chunks = []
        remaining = size

        while remaining:
            chunk = stream.read(
                remaining
            )

            if not chunk:
                return b""

            chunks.append(chunk)
            remaining -= len(chunk)

        return b"".join(chunks)

    print(
        f"[DEVICE] USB MIC ACTIVE @ "
        f"{asyncio.get_running_loop().time():.3f}"
    )

    print(
        f"[DEVICE] READY @ "
        f"{asyncio.get_running_loop().time():.3f}"
    )

    try:

        while True:

            data = await asyncio.to_thread(
                read_exact,
                pw_record.stdout,
                frame_bytes,
            )

            if not data:
                print(
                    "[DEVICE] USB microphone "
                    "stream ended."
                )
                break

            frame = rtc.AudioFrame(
                data=data,
                sample_rate=SAMPLE_RATE,
                num_channels=CHANNELS,
                samples_per_channel=FRAME_SAMPLES,
            )

            await audio_source.capture_frame(
                frame
            )

    except asyncio.CancelledError:
        raise

    finally:

        print(
            "[DEVICE] Shutting down audio..."
        )

        # Stop microphone process.
        if pw_record.poll() is None:

            pw_record.send_signal(
                signal.SIGTERM
            )

            try:
                await asyncio.to_thread(
                    pw_record.wait,
                    2,
                )

            except subprocess.TimeoutExpired:

                pw_record.kill()

                await asyncio.to_thread(
                    pw_record.wait,
                )

        # Stop speaker streams belonging to LUNA.
        for task in list(audio_tasks):
            task.cancel()

        if audio_tasks:
            await asyncio.gather(
                *audio_tasks,
                return_exceptions=True,
            )

        try:
            await room.disconnect()
        except Exception:
            pass

        print(
            "[DEVICE] DISCONNECTED"
        )

        if disconnect_reason is not None:
            raise RuntimeError(
                f"LiveKit disconnected: {disconnect_reason}"
            )


# ─────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        print(
            "\n[DEVICE] Stopped."
        )