from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import subprocess
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import asyncio
import platform

from fastapi.responses import FileResponse

from config import LUNA_MODE

LUNA_SERVICES = {
    "luna-core": "luna-core.service",
    "luna-agent": "luna-agent.service",
    "kokoro": "kokoro.service",
    "ollama": "ollama.service",
}


def control_luna_service(service: str, action: str) -> dict:
    if service not in LUNA_SERVICES:
        raise ValueError(f"Unknown LUNA service: {service}")

    if action not in {"start", "stop", "restart"}:
        raise ValueError(f"Unsupported service action: {action}")

    unit = LUNA_SERVICES[service]

    result = subprocess.run(
        ["sudo", "systemctl", action, unit],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or f"systemctl {action} failed for {unit}"
        )

    return {
        "service": service,
        "action": action,
        "status": "accepted",
    }

class AskRequest(BaseModel):
    prompt: str
    task: str | None = None
    system_prompt: str | None = None

class ConversationMessageRequest(BaseModel):
    role: str
    content: str


class ListeningRequest(BaseModel):
    listening: bool

class VoiceStateRequest(BaseModel):
    state: str
    message: str | None = None

class SpeakerRequest(BaseModel):
    speaker: dict[str, Any] | None = None

class ServiceControlRequest(BaseModel):
    service: str
    action: str

class ControlRequest(BaseModel):
    action: str
    payload: dict[str, Any] = {}
    
class ServiceControlResponse(BaseModel):
    service: str
    action: str
    status: str

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

    @app.get("/api/data")
    async def data_status() -> dict[str, Any]:
        runtime = get_runtime()

        database_path = (
            runtime.core.conversations.database_path
        )

        if not database_path.exists():
            return {
                "status": "unavailable",
                "memories": 0,
                "sessions": 0,
                "messages": 0,
                "reminders": 0,
            }

        import sqlite3

        connection = sqlite3.connect(
            database_path
        )

        try:
            memories = connection.execute(
                "SELECT COUNT(*) FROM memories"
            ).fetchone()[0]

            sessions = connection.execute(
                "SELECT COUNT(*) FROM conversation_sessions"
            ).fetchone()[0]

            messages = connection.execute(
                "SELECT COUNT(*) FROM conversation_messages"
            ).fetchone()[0]

            reminders = connection.execute(
                "SELECT COUNT(*) FROM reminders"
            ).fetchone()[0]

            return {
                "status": "online",
                "memories": memories,
                "sessions": sessions,
                "messages": messages,
                "reminders": reminders,
            }

        finally:
            connection.close()

    @app.get("/api/dashboard")
    async def dashboard() -> dict[str, Any]:
        runtime = get_runtime()

        return runtime.dashboard.snapshot()

    @app.get("/api/update")
    async def update_status() -> dict[str, Any]:
        def run_command(
            command: list[str],
            timeout: int = 5,
        ) -> str:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                )
                return result.stdout.strip()
            except Exception:
                return ""

        def format_timestamp(value: str) -> str:
            if not value:
                return "—"

            try:
                parts = value.split()

                # systemd format:
                # "Sun 2026-09-28 20:41:12 EDT"
                if len(parts) >= 4:
                    date = parts[1]
                    time = parts[2]
                    zone = parts[3]

                    from datetime import datetime

                    parsed = datetime.strptime(
                        f"{date} {time}",
                        "%Y-%m-%d %H:%M:%S",
                    )

                    return (
                        f"{parsed.strftime('%b %-d, %-I:%M %p')} "
                        f"{zone}"
                    )
            except Exception:
                pass

            return value

        current_platform = platform.system()

        # ---------------------------------------------------------
        # Development environment (macOS)
        # ---------------------------------------------------------
        if current_platform == "Darwin":
            repo_path = Path(__file__).resolve().parents[3]

            branch = run_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "branch",
                    "--show-current",
                ]
            )

            commit = run_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "rev-parse",
                    "--short",
                    "HEAD",
                ]
            )

            remote = run_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "rev-parse",
                    "--short",
                    f"origin/{branch}",
                ]
            ) if branch else ""

            status = run_command(
                [
                    "git",
                    "-C",
                    str(repo_path),
                    "status",
                    "--porcelain",
                ]
            )

            return {
                "status": "development",
                "environment": "macos",
                "branch": branch or "—",
                "commit": commit or "—",
                "remote": remote or "—",
                "current": bool(
                    commit
                    and remote
                    and commit == remote
                ),
                "local_changes": bool(status),
                "last_result": "—",
                "last_update": "—",
                "next_run": "—",
                "schedule": "Pi updater only",
            }

        # ---------------------------------------------------------
        # Raspberry Pi deployment environment
        # ---------------------------------------------------------
        repo_path = Path("/mnt/luna")

        branch = run_command(
            [
                "git",
                "-C",
                str(repo_path),
                "branch",
                "--show-current",
            ]
        )

        commit = run_command(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-parse",
                "--short",
                "HEAD",
            ]
        )

        remote = run_command(
            [
                "git",
                "-C",
                str(repo_path),
                "rev-parse",
                "--short",
                "origin/main",
            ]
        )

        status = run_command(
            [
                "git",
                "-C",
                str(repo_path),
                "status",
                "--porcelain",
            ]
        )

        timer = run_command(
            [
                "systemctl",
                "--user",
                "show",
                "luna-updater.timer",
                "--property=NextElapseUSecRealtime",
                "--value",
            ]
        )

        service_status = run_command(
            [
                "systemctl",
                "--user",
                "show",
                "luna-updater.service",
                "--property=Result",
                "--value",
            ]
        )

        service_time = run_command(
            [
                "systemctl",
                "--user",
                "show",
                "luna-updater.service",
                "--property=ExecMainExitTimestamp",
                "--value",
            ]
        )

        # If the deployment repo/updater does not exist,
        # report the updater as unavailable rather than returning
        # misleading placeholder Git information.
        if not repo_path.exists() or not branch or not commit:
            return {
                "status": "unavailable",
                "environment": "linux",
                "branch": "—",
                "commit": "—",
                "remote": "—",
                "current": False,
                "local_changes": False,
                "last_result": "unknown",
                "last_update": "—",
                "next_run": "—",
                "schedule": "Every 15 min",
            }

        return {
            "status": "online",
            "environment": "linux",
            "branch": branch or "—",
            "commit": commit or "—",
            "remote": remote or "—",
            "current": bool(
                commit
                and remote
                and commit == remote
            ),
            "local_changes": bool(status),
            "last_result": service_status or "unknown",
            "last_update": format_timestamp(service_time),
            "next_run": format_timestamp(timer),
            "schedule": "Every 15 min",
        }

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

    @app.post("/api/service")
    async def service_control(
        request: ServiceControlRequest,
    ) -> dict[str, Any]:
        try:
            return control_luna_service(
                service=request.service,
                action=request.action,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc
        except RuntimeError as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            ) from exc

    def set_microphone_enabled(enabled: bool) -> dict[str, Any]:
        """
        Enable or mute L.U.N.A.'s physical microphone.

        The Raspberry Pi resolves the physical PCM2902 source dynamically
        so the PipeWire node ID can change across reboots.
        """

        if platform.system() != "Linux":
            return {
                "status": "unavailable",
                "action": "mic",
                "enabled": enabled,
                "reason": "Hardware microphone control is Pi-only.",
            }

        try:
            result = subprocess.run(
                ["wpctl", "status"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "action": "mic",
                    "enabled": enabled,
                    "reason": result.stderr.strip() or "wpctl status failed.",
                }

            mic_node = None

            for line in result.stdout.splitlines():
                if "PCM2902 Audio Codec Analog Mono" in line:
                    parts = line.strip().split(".", 1)
                    if parts and parts[0].isdigit():
                        mic_node = parts[0]
                        break

            if mic_node is None:
                return {
                    "status": "error",
                    "action": "mic",
                    "enabled": enabled,
                    "reason": "Physical PCM2902 microphone source not found.",
                }

            mute = "0" if enabled else "1"

            mute_result = subprocess.run(
                ["wpctl", "set-mute", mic_node, mute],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if mute_result.returncode != 0:
                return {
                    "status": "error",
                    "action": "mic",
                    "enabled": enabled,
                    "reason": (
                        mute_result.stderr.strip()
                        or "wpctl set-mute failed."
                    ),
                }

            return {
                "status": "ready",
                "action": "mic",
                "enabled": enabled,
                "node": mic_node,
            }

        except (OSError, subprocess.TimeoutExpired) as exc:
            return {
                "status": "error",
                "action": "mic",
                "enabled": enabled,
                "reason": str(exc),
            }

    def set_speaker_volume(volume: int) -> dict[str, Any]:
        """
        Set L.U.N.A.'s physical speaker volume.

        The Raspberry Pi resolves the current luna-echo-sink
        dynamically so PipeWire node IDs can change across reboots.
        """

        if platform.system() != "Linux":
            return {
                "status": "unavailable",
                "action": "volume",
                "volume": volume,
                "reason": "Hardware volume control is Pi-only.",
            }

        volume = max(0, min(100, int(volume)))

        try:
            result = subprocess.run(
                ["wpctl", "status"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "action": "volume",
                    "volume": volume,
                    "reason": result.stderr.strip()
                    or "wpctl status failed.",
                }

            speaker_node = None

            for line in result.stdout.splitlines():
                if "luna-echo-sink" in line:
                    parts = line.strip().split(".", 1)

                    if parts and parts[0].isdigit():
                        speaker_node = parts[0]
                        break

            if speaker_node is None:
                return {
                    "status": "error",
                    "action": "volume",
                    "volume": volume,
                    "reason": "L.U.N.A. speaker sink not found.",
                }

            level = volume / 100

            volume_result = subprocess.run(
                [
                    "wpctl",
                    "set-volume",
                    speaker_node,
                    str(level),
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            if volume_result.returncode != 0:
                return {
                    "status": "error",
                    "action": "volume",
                    "volume": volume,
                    "reason": volume_result.stderr.strip()
                    or "wpctl set-volume failed.",
                }

            return {
                "status": "ready",
                "action": "volume",
                "volume": volume,
                "node": speaker_node,
            }

        except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
            return {
                "status": "error",
                "action": "volume",
                "volume": volume,
                "reason": str(exc),
            }

    @app.post("/api/control")
    async def control_runtime(
        request: ControlRequest,
    ) -> dict[str, Any]:

        action = request.action.strip().lower()
        payload = request.payload or {}

        if action == "reboot":
            result = subprocess.run(
                ["sudo", "systemctl", "reboot"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=(
                        result.stderr.strip()
                        or "Reboot request failed."
                    ),
                )

            return {
                "status": "accepted",
                "action": "reboot",
            }

        if action == "stop":

            control_path = Path(
                "/tmp/luna-agent-control.json"
            )

            import json
            from uuid import uuid4

            control_path.write_text(
                json.dumps(
                    {
                        "id": uuid4().hex,
                        "action": "stop",
                    }
                )
            )

            return {
                "status": "accepted",
                "action": "stop",
            }

        if action == "listen":
            control_path = Path(
                "/tmp/luna-agent-control.json"
            )

            import json
            from uuid import uuid4

            control_path.write_text(
                json.dumps(
                    {
                        "id": uuid4().hex,
                        "action": "listen",
                        "enabled": bool(
                            request.payload.get(
                                "enabled",
                                True,
                            )
                        ),
                    }
                )
            )

            return {
                "status": "accepted",
                "action": "listen",
                "enabled": bool(
                    request.payload.get(
                        "enabled",
                        True,
                    )
                ),
            }

        if action == "mic":
            enabled = bool(payload.get("enabled", True))

            result = set_microphone_enabled(enabled)

            if result["status"] == "ready":
                runtime.voice_state.set_mic_muted(
                    not enabled
                )

            return result

        if action in {
            "start_service",
            "stop_service",
            "restart_service",
        }:

            service = str(
                payload.get("service", "")
            ).strip()

            if not service:
                raise HTTPException(
                    status_code=400,
                    detail="Missing service.",
                )

            system_action = action.replace(
                "_service",
                "",
            )

            try:
                result = control_luna_service(
                    service,
                    system_action,
                )

                return {
                    "status": "accepted",
                    "action": action,
                    "result": result,
                }

            except (
                ValueError,
                RuntimeError,
            ) as exc:

                raise HTTPException(
                    status_code=400,
                    detail=str(exc),
                ) from exc

        if action == "volume":
            volume = int(
                payload.get(
                    "volume",
                    100,
                )
            )

            return set_speaker_volume(volume)

        if action == "set_listening":

            runtime = get_runtime()

            enabled = bool(
                payload.get(
                    "enabled",
                    True,
                )
            )

            runtime.core.set_listening(
                enabled
            )

            return {
                "status": "accepted",
                "action": action,
                "enabled": enabled,
            }

        raise HTTPException(
        status_code=400,
        detail=(
            f"Unknown control action: {action}"
        ),
    )


    LUNA_SERVICE_NAMES = {
        "luna-core": "luna-core.service",
        "luna-agent": "luna-agent.service",
        "kokoro": "kokoro.service",
        "ollama": "ollama.service",
    }


    def get_service_status(service: str) -> dict[str, Any]:
        if service not in LUNA_SERVICE_NAMES:
            raise ValueError(
                f"Unknown L.U.N.A. service: {service}"
            )

        unit = LUNA_SERVICE_NAMES[service]

        try:
            result = subprocess.run(
                [
                    "systemctl",
                    "is-active",
                    unit,
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )

            state = result.stdout.strip()

            return {
                "name": service,
                "unit": unit,
                "state": state or "unknown",
                "active": state == "active",
            }

        except FileNotFoundError:
            # Mac/dev environment.
            return {
                "name": service,
                "unit": unit,
                "state": "development",
                "active": False,
            }

        except Exception as exc:
            return {
                "name": service,
                "unit": unit,
                "state": "unknown",
                "active": False,
                "error": str(exc),
            }


    @app.get("/api/services")
    async def service_statuses() -> dict[str, Any]:
        return {
            "services": [
                get_service_status(name)
                for name in LUNA_SERVICE_NAMES
            ]
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

    @app.post("/api/conversation/message")
    async def conversation_message(
        request: ConversationMessageRequest,
    ) -> dict[str, Any]:
        runtime = get_runtime()

        role = request.role.strip().lower()
        content = request.content.strip()

        if role not in {"user", "assistant"}:
            raise HTTPException(
                status_code=400,
                detail="Conversation role must be user or assistant.",
            )

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Conversation message cannot be empty.",
            )

        if role == "user":
            runtime.core.record_user_message(content)
        else:
            runtime.core.record_assistant_message(content)

        return {
            "status": "recorded",
            "role": role,
        }


    @app.post("/api/listening")
    async def set_listening(
        request: ListeningRequest,
    ) -> dict[str, Any]:
        runtime = get_runtime()

        runtime.core.set_listening(
            request.listening
        )

        return {
            "listening": runtime.core.listening,
        }

    @app.post("/api/voice/state")
    async def set_voice_state(
        request: VoiceStateRequest,
    ) -> dict[str, Any]:
        runtime = get_runtime()

        state = request.state.strip().lower()

        try:
            runtime.dashboard.apply_command(
                command={
                    "action": "set_state",
                    "state": state,
                    "message": request.message,
                },
                timestamp=datetime.now(
                    timezone.utc
                ).isoformat(),
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        return {
            "status": "updated",
            "state": runtime.dashboard.snapshot()["state"],
        }


    @app.post("/api/speaker")
    async def set_speaker(
        request: SpeakerRequest,
    ) -> dict[str, Any]:
        runtime = get_runtime()

        speaker = request.speaker

        if speaker is None:
            runtime.core.set_speaker(None)

            return {
                "status": "updated",
                "speaker": None,
            }

        from core.identity.speaker import SpeakerMatch

        name = speaker.get("name")
        confidence = speaker.get("confidence")

        if confidence is None:
            raise HTTPException(
                status_code=400,
                detail="Speaker confidence is required.",
            )

        authorized = speaker.get("authorized", False)
        reason = speaker.get("reason", "")

        match = SpeakerMatch(
            name=name,
            confidence=float(confidence),
            authorized=bool(authorized),
            reason=str(reason),
        )

        runtime.core.set_speaker(match)

        return {
            "status": "updated",
            "speaker": {
                "name": match.name,
                "confidence": match.confidence,
                "authorized": match.authorized,
                "reason": match.reason,
            },
        }

    return app