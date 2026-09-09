from __future__ import annotations

from dataclasses import asdict, dataclass
from threading import Lock
from typing import Any


@dataclass
class VoiceComponentState:
    available: bool = False
    active: bool = False
    provider: str | None = None
    model: str | None = None


class VoiceRuntimeState:
    """
    Runtime state for L.U.N.A.'s voice subsystem.

    This is operational state only.
    It is not persistent conversation history.
    """

    def __init__(self) -> None:
        self._lock = Lock()

        self.wakeword = VoiceComponentState()
        self.vad = VoiceComponentState()
        self.stt = VoiceComponentState()
        self.tts = VoiceComponentState()

    def set_component(
        self,
        component: str,
        *,
        available: bool | None = None,
        active: bool | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        with self._lock:
            target = getattr(
                self,
                component,
                None,
            )

            if target is None:
                raise ValueError(
                    f"Unknown voice component: {component}"
                )

            if available is not None:
                target.available = bool(
                    available
                )

            if active is not None:
                target.active = bool(
                    active
                )

            if provider is not None:
                target.provider = provider

            if model is not None:
                target.model = model

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "wakeword": asdict(
                    self.wakeword
                ),
                "vad": asdict(
                    self.vad
                ),
                "stt": asdict(
                    self.stt
                ),
                "tts": asdict(
                    self.tts
                ),
            }