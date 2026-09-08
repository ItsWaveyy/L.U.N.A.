#!/usr/bin/env python3

import sys
import wave
from pathlib import Path

import numpy as np


# ---------------------------------------------------------
# PROJECT PATH
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from core.identity.speaker import (  # noqa: E402
    DEFAULT_THRESHOLD,
    SpeakerIdentity,
)


# ---------------------------------------------------------
# PATHS
# ---------------------------------------------------------

ENROLLMENT_DIR = (
    PROJECT_ROOT
    / "data"
    / "speakers"
    / "enrollment"
    / "reece"
)

TEST_DIR = (
    PROJECT_ROOT
    / "data"
    / "speakers"
    / "test"
)


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def wav_duration(path: Path) -> float:
    with wave.open(
        str(path),
        "rb",
    ) as wav:
        frames = wav.getnframes()
        sample_rate = wav.getframerate()

        if sample_rate <= 0:
            return 0.0

        return frames / sample_rate


def classification(
    score: float,
    threshold: float,
) -> str:
    """
    Diagnostic classification only.

    ACCEPT = production would authorize.
    REVIEW = close enough that it may be a useful
             owner-learning candidate later.
    REJECT = too far below the current threshold
             to trust automatically.
    """

    if score >= threshold:
        return "ACCEPT"

    if score >= threshold - 0.08:
        return "REVIEW"

    return "REJECT"


def print_header(
    title: str,
) -> None:
    print()
    print("=" * 76)
    print(title)
    print("=" * 76)


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def main() -> None:

    identity = SpeakerIdentity()

    threshold = identity.threshold

    print_header(
        "L.U.N.A. SPEAKER IDENTITY CALIBRATION"
    )

    print(
        f"\nProduction threshold: "
        f"{threshold:.4f}"
    )

    print(
        "\nProduction scoring rule:"
    )

    print(
        "  max("
        "best enrollment-anchor match, "
        "profile centroid match"
        ")"
    )

    # -----------------------------------------------------
    # LOAD ENROLLMENT ANCHORS
    # -----------------------------------------------------

    enrollment_files = sorted(
        ENROLLMENT_DIR.glob("*.wav")
    )

    if not enrollment_files:
        raise RuntimeError(
            "No enrollment WAV files found in "
            f"{ENROLLMENT_DIR}"
        )

    print_header(
        "ENROLLMENT ANCHORS"
    )

    anchor_embeddings: list[np.ndarray] = []

    for path in enrollment_files:

        embedding = identity._embed_wav(
            str(path)
        )

        anchor_embeddings.append(
            embedding
        )

        print(
            f"{path.name:<24} "
            f"{wav_duration(path):>6.2f}s"
        )

    # -----------------------------------------------------
    # ENROLLMENT ↔ ENROLLMENT
    # -----------------------------------------------------

    print_header(
        "ANCHOR ↔ ANCHOR SIMILARITY"
    )

    print()

    print(
        f"{'':<18}",
        end="",
    )

    for path in enrollment_files:
        print(
            f"{path.stem:>14}",
            end="",
        )

    print()

    for i, path_a in enumerate(
        enrollment_files
    ):
        print(
            f"{path_a.stem:<18}",
            end="",
        )

        for j in range(
            len(enrollment_files)
        ):
            score = identity.cosine_similarity(
                anchor_embeddings[i],
                anchor_embeddings[j],
            )

            print(
                f"{score:>14.4f}",
                end="",
            )

        print()

    # -----------------------------------------------------
    # BUILD CENTROID EXACTLY LIKE PRODUCTION
    # -----------------------------------------------------

    centroid = identity._profile_embedding(
        [
            embedding.tolist()
            for embedding in anchor_embeddings
        ]
    )

    if centroid is None:
        raise RuntimeError(
            "Unable to calculate profile centroid."
        )

    print_header(
        "ANCHOR → CENTROID"
    )

    anchor_centroid_scores = []

    for path, embedding in zip(
        enrollment_files,
        anchor_embeddings,
    ):
        score = identity.cosine_similarity(
            embedding,
            centroid,
        )

        anchor_centroid_scores.append(
            score
        )

        print(
            f"{path.name:<24} "
            f"{score:.4f}"
        )

    print(
        "\nAnchor centroid statistics:"
    )

    print(
        f"  minimum: "
        f"{min(anchor_centroid_scores):.4f}"
    )

    print(
        f"  maximum: "
        f"{max(anchor_centroid_scores):.4f}"
    )

    print(
        f"  mean:    "
        f"{np.mean(anchor_centroid_scores):.4f}"
    )

    # -----------------------------------------------------
    # LIVE SAMPLES
    # -----------------------------------------------------

    test_files = sorted(
        TEST_DIR.glob("*.wav")
    )

    if not test_files:
        raise RuntimeError(
            "No live speaker samples found in "
            f"{TEST_DIR}"
        )

    print_header(
        "LIVE SAMPLE PRODUCTION-MATCH ANALYSIS"
    )

    results = []

    for path in test_files:

        embedding = identity._embed_wav(
            str(path)
        )

        individual_scores = [
            identity.cosine_similarity(
                embedding,
                anchor,
            )
            for anchor in anchor_embeddings
        ]

        best_anchor_index = int(
            np.argmax(individual_scores)
        )

        best_anchor_score = (
            individual_scores[
                best_anchor_index
            ]
        )

        centroid_score = (
            identity.cosine_similarity(
                embedding,
                centroid,
            )
        )

        # Exact same rule as SpeakerIdentity._identify_wav().
        production_score = max(
            best_anchor_score,
            centroid_score,
        )

        result_class = classification(
            production_score,
            threshold,
        )

        results.append(
            {
                "path": path,
                "duration": wav_duration(path),
                "embedding": embedding,
                "individual_scores": individual_scores,
                "best_anchor_index": best_anchor_index,
                "best_anchor_score": best_anchor_score,
                "centroid_score": centroid_score,
                "production_score": production_score,
                "classification": result_class,
            }
        )

        print()
        print(
            f"{path.name} "
            f"({wav_duration(path):.2f}s)"
        )

        print(
            "-" * 60
        )

        for anchor_path, score in zip(
            enrollment_files,
            individual_scores,
        ):
            print(
                f"  → {anchor_path.name:<20} "
                f"{score:.4f}"
            )

        print(
            f"  → centroid{'':<15} "
            f"{centroid_score:.4f}"
        )

        print()

        print(
            f"  Best anchor:       "
            f"{enrollment_files[best_anchor_index].name}"
        )

        print(
            f"  Best anchor score: "
            f"{best_anchor_score:.4f}"
        )

        print(
            f"  Centroid score:    "
            f"{centroid_score:.4f}"
        )

        print(
            f"  PRODUCTION SCORE:  "
            f"{production_score:.4f}"
        )

        print(
            f"  Current result:    "
            f"{result_class}"
        )

    # -----------------------------------------------------
    # SUMMARY TABLE
    # -----------------------------------------------------

    print_header(
        "SUMMARY"
    )

    print()

    print(
        f"{'Sample':<16}"
        f"{'Time':>8}"
        f"{'Anchor':>11}"
        f"{'Centroid':>12}"
        f"{'Prod':>10}"
        f"{'Result':>11}"
    )

    print(
        "-" * 68
    )

    for result in results:

        print(
            f"{result['path'].name:<16}"
            f"{result['duration']:>7.2f}s"
            f"{result['best_anchor_score']:>11.4f}"
            f"{result['centroid_score']:>12.4f}"
            f"{result['production_score']:>10.4f}"
            f"{result['classification']:>11}"
        )

    production_scores = [
        result["production_score"]
        for result in results
    ]

    print()
    print(
        "Live production-score statistics:"
    )

    print(
        f"  minimum: "
        f"{min(production_scores):.4f}"
    )

    print(
        f"  maximum: "
        f"{max(production_scores):.4f}"
    )

    print(
        f"  mean:    "
        f"{np.mean(production_scores):.4f}"
    )

    print(
        f"  median:  "
        f"{np.median(production_scores):.4f}"
    )

    print(
        f"  std:     "
        f"{np.std(production_scores):.4f}"
    )

    # -----------------------------------------------------
    # LIVE ↔ LIVE
    # -----------------------------------------------------

    print_header(
        "LIVE ↔ LIVE CONSISTENCY"
    )

    live_pair_scores = []

    for i in range(
        len(results)
    ):
        for j in range(
            i + 1,
            len(results),
        ):

            score = identity.cosine_similarity(
                results[i]["embedding"],
                results[j]["embedding"],
            )

            live_pair_scores.append(
                score
            )

            print(
                f"{results[i]['path'].name:<16} "
                f"↔ "
                f"{results[j]['path'].name:<16} "
                f"{score:.4f}"
            )

    if live_pair_scores:
        print()
        print(
            "Live ↔ live statistics:"
        )

        print(
            f"  minimum: "
            f"{min(live_pair_scores):.4f}"
        )

        print(
            f"  maximum: "
            f"{max(live_pair_scores):.4f}"
        )

        print(
            f"  mean:    "
            f"{np.mean(live_pair_scores):.4f}"
        )

        print(
            f"  median:  "
            f"{np.median(live_pair_scores):.4f}"
        )

    # -----------------------------------------------------
    # CANDIDATE BREAKDOWN
    # -----------------------------------------------------

    print_header(
        "LEARNING CANDIDATES — DIAGNOSTIC ONLY"
    )

    accepted = [
        result
        for result in results
        if result["classification"] == "ACCEPT"
    ]

    review = [
        result
        for result in results
        if result["classification"] == "REVIEW"
    ]

    rejected = [
        result
        for result in results
        if result["classification"] == "REJECT"
    ]

    print(
        "\nACCEPT:"
    )

    if accepted:
        for result in accepted:
            print(
                f"  {result['path'].name:<16} "
                f"{result['production_score']:.4f}"
            )
    else:
        print(
            "  none"
        )

    print(
        "\nREVIEW:"
    )

    if review:
        for result in review:
            print(
                f"  {result['path'].name:<16} "
                f"{result['production_score']:.4f}"
            )
    else:
        print(
            "  none"
        )

    print(
        "\nREJECT:"
    )

    if rejected:
        for result in rejected:
            print(
                f"  {result['path'].name:<16} "
                f"{result['production_score']:.4f}"
            )
    else:
        print(
            "  none"
        )

    print()
    print(
        "=" * 76
    )

    print(
        "NO PROFILE DATA WAS MODIFIED."
    )

    print(
        "Do not change the production threshold "
        "from this script alone."
    )

    print(
        "=" * 76
    )


if __name__ == "__main__":
    main()