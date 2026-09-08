"""Tool exports.

Only the memory tooling is required at app startup. The optional tools are
loaded lazily so the app does not import every tool and trigger their full
initialization chain during module import.
"""

__all__ = [
    "get_weather",
    "send_email",
    "remember",
    "recall",
    "delegate_task",
]

def __getattr__(name):
    if name == "get_weather":
        from .weather import get_weather
        return get_weather
    if name == "send_email":
        from .email import send_email
        return send_email
    if name in {"remember", "recall"}:
        from .memory import remember, recall
        return remember if name == "remember" else recall
    if name == "delegate_task":
        from .delegate import delegate_task
        return delegate_task
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")