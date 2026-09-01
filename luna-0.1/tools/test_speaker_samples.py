import sys
from pathlib import Path

import numpy as np


# ---------------------------------------------------------
# PROJECT ROOT
# ---------------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from core.identity.speaker import SpeakerIdentity


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

PROFILE_PATH = (
    ROOT
    / "data"
    / "speakers"
    / "profiles.json"
)

TEST_DIR = (
    ROOT
    / "data"
    / "speakers"
    / "test"
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def cosine(first, second):
    first = np.asarray(
        first,
        dtype=np.float32,
    )

    second = np.asarray(
        second,
        dtype=np.float32,
    )

    first /= np.linalg.norm(first)
    second /= np.linalg.norm(second)

    return float(
        np.dot(first, second)
    )


def main():
    print("=" * 60)
    print("L.U.N.A. LIVE SPEAKER SAMPLE TEST")
    print("=" * 60)

    if not TEST_DIR.exists():
        print(
            f"\nERROR: Test directory does not exist:\n"
            f"{TEST_DIR}\n"
        )

        print(
            "Create it with:"
        )

        print(
            "  mkdir -p "
            "data/speakers/test"
        )

        sys.exit(1)

    samples = sorted(
        TEST_DIR.glob("*.wav")
    )

    if not samples:
        print(
            f"\nERROR: No WAV files found in:\n"
            f"{TEST_DIR}\n"
        )

        print(
            "\nPut fresh recordings of your voice "
            "in that directory."
        )

        sys.exit(1)

    print(
        f"\nFound {len(samples)} test recordings:"
    )

    for sample in samples:
        print(
            f"  - {sample.name}"
        )

    # -----------------------------------------------------
    # LOAD IDENTITY SYSTEM
    # -----------------------------------------------------

    identity = SpeakerIdentity(
        profile_path=PROFILE_PATH
    )

    print(
        "\nLoading speaker identity model..."
    )

    embedder = identity._get_embedder()

    print(
        "Model loaded."
    )

    # -----------------------------------------------------
    # LOAD REECE PROFILE
    # -----------------------------------------------------

    profiles = identity._profiles

    profile = profiles.get("Reece")

    if not profile:
        print(
            "\nERROR: No 'Reece' profile found."
        )

        sys.exit(1)

    enrollment_embeddings = (
        profile.get(
            "embeddings",
            [],
        )
    )

    if not enrollment_embeddings:
        print(
            "\nERROR: Reece profile contains "
            "no embeddings."
        )

        sys.exit(1)

    centroid = identity._profile_embedding(
        enrollment_embeddings
    )

    if centroid is None:
        print(
            "\nERROR: Could not construct "
            "Reece profile centroid."
        )

        sys.exit(1)

    print(
        f"\nLoaded Reece profile with "
        f"{len(enrollment_embeddings)} "
        f"enrollment embeddings."
    )

    # -----------------------------------------------------
    # TEST EACH SAMPLE
    # -----------------------------------------------------

    results = []

    print(
        "\n" + "-" * 60
    )

    for sample in samples:
        print(
            f"\nEmbedding: {sample.name}"
        )

        embedding = embedder.embed(
            str(sample)
        )

        embedding = (
            identity._normalize_embedding(
                embedding
            )
        )

        score = cosine(
            embedding,
            centroid,
        )

        results.append(
            (
                sample.name,
                score,
            )
        )

        print(
            f"  centroid similarity: "
            f"{score:.4f}"
        )

    # -----------------------------------------------------
    # SUMMARY
    # -----------------------------------------------------

    scores = [
        score
        for _, score in results
    ]

    print(
        "\n" + "=" * 60
    )

    print(
        "RESULTS"
    )

    print(
        "=" * 60
    )

    for name, score in results:
        print(
            f"{name:<30} "
            f"{score:.4f}"
        )

    print(
        "\nStatistics:"
    )

    print(
        f"  minimum: "
        f"{min(scores):.4f}"
    )

    print(
        f"  maximum: "
        f"{max(scores):.4f}"
    )

    print(
        f"  mean:    "
        f"{np.mean(scores):.4f}"
    )

    print(
        f"  median:  "
        f"{np.median(scores):.4f}"
    )

    print(
        f"  std:     "
        f"{np.std(scores):.4f}"
    )

    print(
        "\n" + "=" * 60
    )
    print(
        "CALIBRATION DATA ONLY"
    )
    print(
        "=" * 60
    )

    print(
        "\nThese scores should NOT be used to "
        "change the production threshold yet."
    )

    print(
        "We need both authorized and "
        "unauthorized samples before selecting "
        "a threshold."
    )


if __name__ == "__main__":
    main()