import time
from datetime import datetime, timezone

from fastapi import FastAPI

from core.orchestrator import LunaCore


app = FastAPI(
    title="L.U.N.A. Core API",
    version="1.0",
)


STARTED_AT = time.time()


def get_core() -> LunaCore:
    """
    Return the active L.U.N.A. Core instance.

    The API server will eventually be started alongside the
    primary Core process, so this function will be replaced
    by the shared Core instance wiring.
    """
    return LunaCore()


@app.get("/api/health")
async def health():
    """
    Basic API health endpoint.

    This intentionally does not require provider/network health.
    It answers one question:

        Is the Core API process alive?
    """

    return {
        "status": "ok",
        "service": "luna-core-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/status")
async def status():
    """
    Return the current L.U.N.A. Core status.
    """

    core = get_core()

    provider_health = await core.health_status()

    return {
        "service": "luna-core",
        "status": "online",
        "listening": core.listening,
        "providers": provider_health,
        "uptime_seconds": round(
            time.time() - STARTED_AT,
            2,
        ),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
