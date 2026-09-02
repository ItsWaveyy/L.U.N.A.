import asyncio
import json
import os
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

import numpy as np


DEFAULT_MODEL = "wespeaker-resnet34"

# Conservative enough for authorization, but less brittle
# than the original 0.60 on every individual sample.
DEFAULT_THRESHOLD = 0.55

PROFILE_PATH = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "speakers"
    / "profiles.json"
)


@dataclass
class SpeakerMatch:
    name: str | None
    authorized: bool
    confidence: float
    reason: str


class SpeakerIdentity:
    """
    Local speaker identification and authorization system.

    Speaker profiles contain voice embeddings rather than raw recordings.

    Each profile may contain multiple enrollment embeddings. Matching
    compares the incoming voice against the profile centroid and its
    individual enrollment samples, producing a stable confidence score.
    """

    def __init__(
        self,
        profile_path: str | os.PathLike = PROFILE_PATH,
        model: str = DEFAULT_MODEL,
        threshold: float = DEFAULT_THRESHOLD,
    ):
        self.profile_path = Path(profile_path)
        self.model_name = model
        self.threshold = threshold

        self.profile_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._profiles = self._load_profiles()
        self._embedder = None

    # ---------------------------------------------------------
    # MODEL
    # ---------------------------------------------------------

    def _get_embedder(self):
        if self._embedder is None:
            from speakeronnx import SpeakerEmbedder

            print(
                "[L.U.N.A.] Loading speaker identity model: "
                f"{self.model_name}"
            )

            self._embedder = SpeakerEmbedder(
                model=self.model_name
            )

            print(
                "[L.U.N.A.] Speaker identity model ready."
            )

        return self._embedder

    # ---------------------------------------------------------
    # PROFILE STORAGE
    # ---------------------------------------------------------

    def _load_profiles(self) -> dict:
        if not self.profile_path.exists():
            return {}

        try:
            with self.profile_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return {}

            return data

        except Exception as exc:
            print(
                "[L.U.N.A.] Failed to load speaker profiles: "
                f"{exc}"
            )
            return {}

    def _save_profiles(self) -> None:
        self.profile_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_path = self.profile_path.with_suffix(".tmp")

        with temp_path.open(
            "w",
            encoding="utf-8",
        ) as file:
            json.dump(
                self._profiles,
                file,
                indent=2,
            )

        temp_path.replace(self.profile_path)

    # ---------------------------------------------------------
    # EMBEDDINGS
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_embedding(
        embedding,
    ) -> np.ndarray:
        vector = np.asarray(
            embedding,
            dtype=np.float32,
        ).reshape(-1)

        norm = np.linalg.norm(vector)

        if norm <= 1e-8:
            raise ValueError(
                "Speaker embedding has zero magnitude."
            )

        return vector / norm

    @staticmethod
    def cosine_similarity(
        first,
        second,
    ) -> float:
        a = SpeakerIdentity._normalize_embedding(first)
        b = SpeakerIdentity._normalize_embedding(second)

        return float(np.dot(a, b))

    def _embed_wav(
        self,
        wav_path: str | os.PathLike,
    ) -> np.ndarray:
        embedder = self._get_embedder()

        embedding = embedder.embed(
            str(wav_path)
        )

        return self._normalize_embedding(embedding)

    # ---------------------------------------------------------
    # PROFILE REPRESENTATION
    # ---------------------------------------------------------

    def _profile_embedding(
        self,
        embeddings: list,
    ) -> np.ndarray | None:
        """
        Build a normalized centroid from all enrollment embeddings.

        This prevents one unusually good/bad enrollment clip from
        completely determining the match.
        """

        if not embeddings:
            return None

        vectors = [
            self._normalize_embedding(embedding)
            for embedding in embeddings
        ]

        centroid = np.mean(
            np.stack(vectors),
            axis=0,
        )

        return self._normalize_embedding(centroid)

    # ---------------------------------------------------------
    # ENROLLMENT
    # ---------------------------------------------------------

    def enroll(
        self,
        name: str,
        wav_paths: list[str | os.PathLike],
        authorized: bool = True,
        append: bool = False,
    ) -> None:
        if not name.strip():
            raise ValueError(
                "Speaker name cannot be empty."
            )

        if not wav_paths:
            raise ValueError(
                "At least one enrollment recording is required."
            )

        embeddings = []

        for path in wav_paths:
            path = Path(path)

            if not path.exists():
                raise FileNotFoundError(
                    f"Enrollment recording not found: {path}"
                )

            print(
                f"[L.U.N.A.] Enrolling {name} from "
                f"{path.name}..."
            )

            embedding = self._embed_wav(path)

            embeddings.append(
                embedding.tolist()
            )

        existing_profile = self._profiles.get(name)

        if append and existing_profile:
            existing_embeddings = existing_profile.get(
                "embeddings",
                [],
            )

            embeddings = (
                existing_embeddings
                + embeddings
            )

            authorized = existing_profile.get(
                "authorized",
                authorized,
            )

            print(
                f"[L.U.N.A.] Appending {len(wav_paths)} "
                f"new enrollment sample(s) to {name}."
            )

        self._profiles[name] = {
            "authorized": bool(authorized),
            "embeddings": embeddings,
        }

        self._save_profiles()

        print(
            f"[L.U.N.A.] Speaker profile saved: {name}"
        )

    # ---------------------------------------------------------
    # AUDIO → WAV
    # ---------------------------------------------------------

    @staticmethod
    def _resample_pcm_to_16k(
        pcm_data: bytes,
        sample_rate: int,
        num_channels: int,
    ) -> tuple[bytes, int, int]:
        """
        Convert speaker-identification audio to 16 kHz.

        This affects ONLY the audio representation sent to the
        speaker embedding model. The downstream LiveKit audio
        pipeline remains untouched.
        """

        target_sample_rate = 16000

        if sample_rate == target_sample_rate:
            return (
                pcm_data,
                sample_rate,
                num_channels,
            )

        samples = np.frombuffer(
            pcm_data,
            dtype=np.int16,
        ).astype(np.float32)

        if samples.size == 0:
            return (
                b"",
                target_sample_rate,
                num_channels,
            )

        if num_channels > 1:
            samples = samples.reshape(
                -1,
                num_channels,
            ).mean(axis=1)

        source_length = len(samples)

        target_length = int(
            round(
                source_length
                * target_sample_rate
                / sample_rate
            )
        )

        if target_length <= 0:
            return (
                b"",
                target_sample_rate,
                1,
            )

        source_positions = np.linspace(
            0.0,
            1.0,
            source_length,
            endpoint=False,
        )

        target_positions = np.linspace(
            0.0,
            1.0,
            target_length,
            endpoint=False,
        )

        resampled = np.interp(
            target_positions,
            source_positions,
            samples,
        )

        resampled = np.clip(
            np.round(resampled),
            -32768,
            32767,
        ).astype(np.int16)

        return (
            resampled.tobytes(),
            target_sample_rate,
            1,
        )

    @staticmethod
    def _pcm_to_wav(
        pcm_data: bytes,
        sample_rate: int,
        num_channels: int,
    ) -> str:
        temp_file = tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
        )

        temp_path = temp_file.name
        temp_file.close()

        with wave.open(
            temp_path,
            "wb",
        ) as wav:
            wav.setnchannels(num_channels)
            wav.setsampwidth(2)
            wav.setframerate(sample_rate)
            wav.writeframes(pcm_data)

        return temp_path

    # ---------------------------------------------------------
    # IDENTIFICATION
    # ---------------------------------------------------------

    async def identify_pcm(
        self,
        pcm_data: bytes,
        sample_rate: int,
        num_channels: int,
    ) -> SpeakerMatch:

        if not pcm_data:
            return SpeakerMatch(
                name=None,
                authorized=False,
                confidence=0.0,
                reason="No speaker audio available.",
            )

        duration = (
            len(pcm_data)
            / (sample_rate * num_channels * 2)
        )

        if duration < 1.0:
            return SpeakerMatch(
                name=None,
                authorized=False,
                confidence=0.0,
                reason=(
                    f"Speaker sample too short "
                    f"({duration:.2f}s)."
                ),
            )

        identity_pcm, identity_sample_rate, identity_channels = (
            self._resample_pcm_to_16k(
                pcm_data,
                sample_rate,
                num_channels,
            )
        )

        wav_path = self._pcm_to_wav(
            identity_pcm,
            identity_sample_rate,
            identity_channels,
        )

        try:
            return await asyncio.to_thread(
                self._identify_wav,
                wav_path,
            )

        finally:
            try:
                os.unlink(wav_path)
            except FileNotFoundError:
                pass

    def _identify_wav(
        self,
        wav_path: str,
    ) -> SpeakerMatch:

        if not self._profiles:
            return SpeakerMatch(
                name=None,
                authorized=False,
                confidence=0.0,
                reason="No speaker profiles enrolled.",
            )

        embedding = self._embed_wav(wav_path)

        best_name = None
        best_score = -1.0
        best_authorized = False

        for name, profile in self._profiles.items():

            profile_embeddings = profile.get(
                "embeddings",
                [],
            )

            if not profile_embeddings:
                continue

            # Compare against every enrollment sample.
            individual_scores = [
                self.cosine_similarity(
                    embedding,
                    stored_embedding,
                )
                for stored_embedding in profile_embeddings
            ]

            best_individual_score = max(
                individual_scores
            )

            # Compare against the profile centroid.
            centroid = self._profile_embedding(
                profile_embeddings
            )

            centroid_score = (
                self.cosine_similarity(
                    embedding,
                    centroid,
                )
                if centroid is not None
                else -1.0
            )

            # Use the stronger of the centroid and best enrollment
            # match. This keeps the system tolerant of natural
            # variation without throwing away the original samples.
            score = max(
                best_individual_score,
                centroid_score,
            )

            if score > best_score:
                best_score = score
                best_name = name
                best_authorized = bool(
                    profile.get(
                        "authorized",
                        False,
                    )
                )

        if (
            best_name is None
            or best_score < self.threshold
        ):
            return SpeakerMatch(
                name=None,
                authorized=False,
                confidence=max(
                    best_score,
                    0.0,
                ),
                reason=(
                    "No enrolled speaker exceeded "
                    f"the {self.threshold:.2f} threshold."
                ),
            )

        return SpeakerMatch(
            name=best_name,
            authorized=best_authorized,
            confidence=best_score,
            reason="Speaker matched enrolled profile.",
        )

    # ---------------------------------------------------------
    # DEBUGGING
    # ---------------------------------------------------------

    def profile_names(self) -> list[str]:
        return list(self._profiles.keys())

    def has_profiles(self) -> bool:
        return bool(self._profiles)