import json
import sys
from pathlib import Path

import numpy as np


# Add the L.U.N.A. project root to Python's import path.
ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.identity.speaker import SpeakerIdentity

ENROLLMENT_DIR = (
    ROOT
    / "data"
    / "speakers"
    / "enrollment"
    / "reece"
)

PROFILE_PATH = (
    ROOT
    / "data"
    / "speakers"
    / "profiles.json"
)


def cosine(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    a /= np.linalg.norm(a)
    b /= np.linalg.norm(b)

    return float(np.dot(a, b))


def main():
    print("=" * 60)
    print("L.U.N.A. SPEAKER CALIBRATION")
    print("=" * 60)

    recordings = sorted(
        ENROLLMENT_DIR.glob("*.wav")
    )

    if not recordings:
        print(
            f"\nERROR: No WAV files found in:\n"
            f"{ENROLLMENT_DIR}"
        )
        sys.exit(1)

    print(
        f"\nFound {len(recordings)} enrollment recordings:"
    )

    for path in recordings:
        print(f"  - {path.name}")

    identity = SpeakerIdentity(
        profile_path=PROFILE_PATH
    )

    print("\nLoading speaker model...")
    embedder = identity._get_embedder()

    print("Model loaded.\n")

    embeddings = []

    for path in recordings:
        print(
            f"Embedding enrollment sample: "
            f"{path.name}"
        )

        embedding = embedder.embed(
            str(path)
        )

        embedding = identity._normalize_embedding(
            embedding
        )

        embeddings.append(embedding)

    print(
        f"\nGenerated {len(embeddings)} embeddings."
    )

    # ---------------------------------------------------------
    # ENROLLMENT-TO-ENROLLMENT SIMILARITY
    # ---------------------------------------------------------

    print("\nEnrollment similarity matrix:")
    print()

    for i, first in enumerate(embeddings):
        row = []

        for j, second in enumerate(embeddings):
            score = cosine(first, second)
            row.append(f"{score:.3f}")

        print(
            f"{recordings[i].name:<30} "
            + "  ".join(row)
        )

    # ---------------------------------------------------------
    # CENTROID
    # ---------------------------------------------------------

    centroid = identity._profile_embedding(
        [
            embedding.tolist()
            for embedding in embeddings
        ]
    )

    print("\nEnrollment → centroid:")
    print()

    centroid_scores = []

    for path, embedding in zip(
        recordings,
        embeddings,
    ):
        score = cosine(
            embedding,
            centroid,
        )

        centroid_scores.append(score)

        print(
            f"{path.name:<30} "
            f"{score:.4f}"
        )

    print("\nCalibration summary:")
    print(
        f"  min centroid similarity: "
        f"{min(centroid_scores):.4f}"
    )
    print(
        f"  max centroid similarity: "
        f"{max(centroid_scores):.4f}"
    )
    print(
        f"  mean centroid similarity: "
        f"{np.mean(centroid_scores):.4f}"
    )
    print(
        f"  std deviation: "
        f"{np.std(centroid_scores):.4f}"
    )

    # ---------------------------------------------------------
    # CURRENT PROFILE
    # ---------------------------------------------------------

    if PROFILE_PATH.exists():
        try:
            with PROFILE_PATH.open(
                "r",
                encoding="utf-8",
            ) as file:
                profiles = json.load(file)

            reece = profiles.get("Reece")

            if reece:
                stored_embeddings = reece.get(
                    "embeddings",
                    []
                )

                print(
                    "\nExisting profile:"
                )
                print(
                    f"  authorized: "
                    f"{reece.get('authorized')}"
                )
                print(
                    f"  stored embeddings: "
                    f"{len(stored_embeddings)}"
                )

                if stored_embeddings:
                    stored_centroid = (
                        identity._profile_embedding(
                            stored_embeddings
                        )
                    )

                    print(
                        "\nEnrollment → stored "
                        "profile centroid:"
                    )

                    for path, embedding in zip(
                        recordings,
                        embeddings,
                    ):
                        score = cosine(
                            embedding,
                            stored_centroid,
                        )

                        print(
                            f"{path.name:<30} "
                            f"{score:.4f}"
                        )

        except Exception as exc:
            print(
                f"\nCould not inspect existing "
                f"profile: {exc}"
            )

    print("\n" + "=" * 60)
    print("CALIBRATION COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()