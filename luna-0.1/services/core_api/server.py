from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI

from config import LUNA_MODE
from core.orchestrator import LunaCore


def create_core_api() -> FastAPI:
    """
    Create the L.U.N.A. Core API.

    The API server itself is independent from a specific LiveKit session,
    while the active LunaCore instance is supplied by the agent runtime.
    """

    app = FastAPI(
        title="L.U.N.A. Core API",
        version="1.0",
        description="Local control and status API for L.U.N.A. Core.",
    )

    current_core: LunaCore | None = None

    def set_core(core: LunaCore) -> None:
        nonlocal current_core
        current_core = core

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "luna-core",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        if current_core is None:
            return {
                "service": "luna-core",
                "status": "starting",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        provider_health = await current_core.health_status()

        providers = []

        for provider in current_core.router.providers:
            providers.append(
                {
                    "name": provider.name,
                    "model": getattr(
                        provider,
                        "model",
                        None,
                    ),
                    "healthy": provider_health.get(
                        provider.name,
                        False,
                    ),
                    "capabilities": sorted(
                        provider.capabilities
                    ),
                }
            )

        return {
            "service": "luna-core",
            "status": "online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "mode": LUNA_MODE,
            "listening": current_core.listening,
            "providers": providers,
            "conversation": {
                "active": (
                    current_core.conversations.session_id
                    is not None
                ),
                "session_id": (
                    current_core.conversations.session_id
                ),
            },
            "improvement": {
                "available": (
                    current_core.improvement
                    is not None
                ),
            },
        }

    app.state.set_core = set_core

    return app
