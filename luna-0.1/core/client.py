from __future__ import annotations

from typing import Any

import httpx


class CoreClient:
    """
    Client-side access point for the persistent L.U.N.A. Core.

    LiveKit and future interfaces use this instead of creating
    their own LunaCore instance.
    """

    WAKE_PHRASES = (
        "luna wake up",
        "wake up luna",
        "hey luna",
        "hi luna",
        "hello luna",
        "luna are you there",
        "luna you there",
        "are you there luna",
        "luna are you awake",
        "are you awake luna",
        "luna wakey wakey",
        "back online luna",
        "luna back online",
        "resume listening luna",
        "luna resume listening",
        "hey, luna",
    )

    SLEEP_PHRASES = (
        "that's all for now",
        "that is all for now",
        "take a break",
        "you can take a break",
        "go to sleep",
        "sleep now",
        "stop listening",
        "pause listening",
        "rest for a bit",
        "that's it for now",
        "that is it for now",
        "you're all done for now",
        "you are all done for now",
    )

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8090",
    ) -> None:
        self.base_url = base_url.rstrip("/")

        self.listening = True

    async def ask(
        self,
        *,
        prompt: str,
        task: str | None = None,
        system_prompt: str | None = None,
    ):
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=3.0,
                read=180.0,
                write=10.0,
                pool=5.0,
            )
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/ask",
                json={
                    "prompt": prompt,
                    "task": task,
                    "system_prompt": system_prompt,
                },
            )

            response.raise_for_status()

        return CoreResponse(
            text=response.json().get("text", ""),
            provider=response.json().get("provider"),
            model=response.json().get("model"),
            metadata=response.json().get("metadata", {}),
        )

    async def record_user_message(
        self,
        content: str,
    ) -> None:
        await self._post_message(
            role="user",
            content=content,
        )

    async def record_assistant_message(
        self,
        content: str,
    ) -> None:
        await self._post_message(
            role="assistant",
            content=content,
        )

    async def _post_message(
        self,
        *,
        role: str,
        content: str,
    ) -> None:
        content = (content or "").strip()

        if not content:
            return

        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/conversation/message",
                json={
                    "role": role,
                    "content": content,
                },
            )

            response.raise_for_status()

    async def set_listening(
        self,
        state: bool,
    ) -> bool:
        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/listening",
                json={
                    "listening": bool(state),
                },
            )

            response.raise_for_status()

            payload = response.json()

        self.listening = bool(
            payload.get(
                "listening",
                state,
            )
        )

        return self.listening

    async def set_speaker(
        self,
        match: Any,
    ) -> None:
        # Speaker identity remains an access-point concern for now.
        # The persistent Core receives the identity information through
        # the Core API without requiring the LiveKit process to own Core.
        payload = None

        if match is not None:
            payload = {
                "name": getattr(
                    match,
                    "name",
                    None,
                ),
                "confidence": getattr(
                    match,
                    "confidence",
                    None,
                ),
            }

        async with httpx.AsyncClient(
            timeout=5.0
        ) as client:
            response = await client.post(
                f"{self.base_url}/api/speaker",
                json={
                    "speaker": payload,
                },
            )

            response.raise_for_status()

    @staticmethod
    def _contains_phrase(
        text: str,
        phrases: tuple[str, ...],
    ) -> bool:
        lowered = (
            text or ""
        ).lower().strip()

        return any(
            phrase in lowered
            for phrase in phrases
        )


class CoreResponse:
    def __init__(
        self,
        *,
        text: str,
        provider: str | None,
        model: str | None,
        metadata: dict[str, Any],
    ) -> None:
        self.text = text
        self.provider = provider
        self.model = model
        self.metadata = metadata