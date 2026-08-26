import argparse
import sys
import time
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    
from core.identity.speaker import SpeakerIdentity


SAMPLE_RATE = 16000
CHANNELS = 1


def record_clip(
    path: Path,
    seconds: float,
) -> None:
    print()
    print(
        f"Recording for {seconds:.1f} seconds..."
    )
    print("Speak normally.")

    recording = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )

    sd.wait()

    recording = np.asarray(
        recording,
        dtype=np.int16,
    )

    with wave.open(
        str(path),
        "wb",
    ) as wav:
        wav.setnchannels(
            CHANNELS
        )
        wav.setsampwidth(2)
        wav.setframerate(
            SAMPLE_RATE
        )
        wav.writeframes(
            recording.tobytes()
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Enroll a L.U.N.A. speaker profile."
        )
    )

    parser.add_argument(
        "--name",
        required=True,
        help="Speaker profile name.",
    )

    parser.add_argument(
        "--clips",
        type=int,
        default=3,
        help="Number of enrollment clips.",
    )

    parser.add_argument(
        "--seconds",
        type=float,
        default=5.0,
        help="Length of each recording.",
    )

    parser.add_argument(
        "--unauthorized",
        action="store_true",
        help=(
            "Create the profile but do not "
            "authorize it."
        ),
    )

    args = parser.parse_args()

    if args.clips < 1:
        raise ValueError(
            "--clips must be at least 1."
        )

    if args.seconds < 1.0:
        raise ValueError(
            "--seconds must be at least 1."
        )

    recordings_dir = (
        Path("data")
        / "speakers"
        / "enrollment"
        / args.name.lower().replace(" ", "_")
    )

    recordings_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    recordings = []

    print()
    print(
        f"=== L.U.N.A. Speaker Enrollment: "
        f"{args.name} ==="
    )

    for index in range(args.clips):
        path = (
            recordings_dir
            / f"clip_{index + 1}.wav"
        )

        input(
            f"\nPress ENTER for recording "
            f"{index + 1}/{args.clips}..."
        )

        record_clip(
            path,
            args.seconds,
        )

        recordings.append(path)

        print(
            f"Saved: {path}"
        )

        time.sleep(0.5)

    identity = SpeakerIdentity()

    identity.enroll(
        name=args.name,
        wav_paths=recordings,
        authorized=not args.unauthorized,
    )

    print()
    print(
        f"[L.U.N.A.] Enrollment complete for "
        f"{args.name}."
    )

    if args.unauthorized:
        print(
            "[L.U.N.A.] Profile status: "
            "UNAUTHORIZED"
        )
    else:
        print(
            "[L.U.N.A.] Profile status: "
            "AUTHORIZED"
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nEnrollment cancelled.")
        sys.exit(1)