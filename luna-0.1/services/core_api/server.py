from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path

from fastapi.responses import FileResponse

from config import LUNA_MODE

class AskRequest(BaseModel):
    prompt: str
    task: str | None = None
    system_prompt: str | None = None


def create_core_api(runtime=None) -> FastAPI:
    """
    Create the permanent L.U.N.A. Core API.

    The API belongs to Core Runtime rather than to a LiveKit session.
    """

    app = FastAPI(
        title="L.U.N.A. Core API",
        version="1.0",
        description=(
            "Persistent local control and status API "
            "for L.U.N.A. Core."
        ),
    )

    app.state.runtime = runtime

    def get_runtime():
        current_runtime = app.state.runtime

        if current_runtime is None:
            raise HTTPException(
                status_code=503,
                detail="L.U.N.A. Core runtime is unavailable.",
            )

        return current_runtime

    dashboard_dir = (
        Path(__file__).resolve().parent / "dashboard"
    )

    @app.get("/dashboard")
    async def dashboard_page() -> FileResponse:
        return FileResponse(
            dashboard_dir / "index.html"
        )

    @app.get("/dashboard/{filename}")
    async def dashboard_asset(filename: str) -> FileResponse:
        allowed_files = {
            "app.js",
            "style.css",
        }

        if filename not in allowed_files:
            raise HTTPException(
                status_code=404,
                detail="Dashboard asset not found.",
            )

        return FileResponse(
            dashboard_dir / filename
        )


    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "luna-core",
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        runtime = get_runtime()
        core = runtime.core

        provider_health = await core.health_status()

        providers = []

        for provider in core.router.providers:
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
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),

            "mode": LUNA_MODE,

            "listening": core.listening,

            "providers": providers,

            "conversation": {
                "active": (
                    core.conversations.session_id
                    is not None
                ),
                "session_id": (
                    core.conversations.session_id
                ),
            },

            "improvement": {
                "available": (
                    core.improvement is not None
                ),
            },

            "dashboard": runtime.dashboard.snapshot(),
        }

    @app.get("/api/system")
    async def system() -> dict[str, Any]:
        runtime = get_runtime()

        return runtime.system_monitor.as_dict()

    @app.get("/api/dashboard")
    async def dashboard() -> dict[str, Any]:
        runtime = get_runtime()

        return runtime.dashboard.snapshot()

    @app.get("/api/dashboard/state")
    async def dashboard_state() -> dict[str, Any]:
        runtime = get_runtime()

        return runtime.dashboard.snapshot()

    @app.get("/api/telemetry")
    async def telemetry() -> dict[str, Any]:
        runtime = get_runtime()
        return await runtime.telemetry.snapshot()

    @app.get("/api/activity")
    async def activity() -> dict[str, Any]:
        runtime = get_runtime()
        return runtime.activity.snapshot()

    @app.post("/api/ask")
    async def ask(request: AskRequest) -> dict[str, Any]:
        runtime = get_runtime()

        prompt = request.prompt.strip()

        if not prompt:
            raise HTTPException(
                status_code=400,
                detail="Prompt cannot be empty.",
            )

        response = await runtime.core.ask(
            prompt=prompt,
            task=request.task,
            system_prompt=request.system_prompt,
        )

        return {
            "text": response.text,
            "provider": response.provider,
            "model": response.model,
            "metadata": response.metadata,
        }

    @app.post("/api/dashboard/command")
    async def dashboard_command(
        command: dict[str, Any],
    ) -> dict[str, Any]:
        runtime = get_runtime()

        try:
            runtime.dashboard.apply_command(
                command=command,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        return runtime.dashboard.snapshot()

    return app