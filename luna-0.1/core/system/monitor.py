from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import psutil


@dataclass
class SystemSnapshot:
    timestamp: str
    uptime_seconds: float

    cpu_percent: float
    cpu_count: int
    cpu_frequency_mhz: float | None

    memory_total_bytes: int
    memory_used_bytes: int
    memory_available_bytes: int
    memory_percent: float

    storage_path: str
    storage_total_bytes: int
    storage_used_bytes: int
    storage_free_bytes: int
    storage_percent: float

    temperature_celsius: float | None

    hostname: str
    network_interface_online: bool


class SystemMonitor:
    def __init__(self, storage_path: str | None = None) -> None:
        self.storage_path = storage_path or self._default_storage_path()
        self.started_at = time.monotonic()

    @staticmethod
    def _default_storage_path() -> str:
        """
        Select the primary storage location for the current host.

        Raspberry Pi deployment:
            /mnt/luna

        Development machines:
            The filesystem containing the running L.U.N.A. application.
        """

        pi_storage = Path("/mnt/luna")

        if pi_storage.exists():
            return str(pi_storage)

        return str(Path(__file__).resolve().parents[2])

    def snapshot(self) -> SystemSnapshot:
        cpu_frequency = psutil.cpu_freq()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage(self.storage_path)

        return SystemSnapshot(
            timestamp=datetime.now(timezone.utc).isoformat(),
            uptime_seconds=time.monotonic() - self.started_at,

            cpu_percent=psutil.cpu_percent(interval=None),
            cpu_count=psutil.cpu_count(logical=True) or 0,
            cpu_frequency_mhz=(
                cpu_frequency.current
                if cpu_frequency is not None
                else None
            ),

            memory_total_bytes=memory.total,
            memory_used_bytes=memory.used,
            memory_available_bytes=memory.available,
            memory_percent=memory.percent,

            storage_path=self.storage_path,
            storage_total_bytes=disk.total,
            storage_used_bytes=disk.used,
            storage_free_bytes=disk.free,
            storage_percent=disk.percent,

            temperature_celsius=self._temperature(),

            hostname=socket.gethostname(),
            network_interface_online=self._network_interface_online(),
        )

    def _temperature(self) -> float | None:
        try:
            temperatures = psutil.sensors_temperatures()

            if not temperatures:
                return None

            preferred_names = (
                "cpu_thermal",
                "cpu-thermal",
                "coretemp",
                "k10temp",
                "thermal_zone0",
            )

            for preferred in preferred_names:
                entries = temperatures.get(preferred)

                if entries:
                    for entry in entries:
                        if entry.current is not None:
                            return float(entry.current)

            for entries in temperatures.values():
                for entry in entries:
                    if entry.current is not None:
                        return float(entry.current)

        except Exception:
            pass

        return None

    @staticmethod
    def _network_interface_online() -> bool:
        """
        Determine whether the host has an active non-loopback
        IPv4 interface.

        This intentionally represents interface availability,
        not guaranteed internet reachability.
        """

        try:
            interfaces = psutil.net_if_addrs()
            stats = psutil.net_if_stats()

            for interface, addresses in interfaces.items():
                if interface == "lo":
                    continue

                interface_stats = stats.get(interface)

                if interface_stats is None or not interface_stats.isup:
                    continue

                for address in addresses:
                    if address.family == socket.AF_INET:
                        return True

        except Exception:
            pass

        return False

    def as_dict(self) -> dict:
        snapshot = self.snapshot()

        return {
            "timestamp": snapshot.timestamp,
            "uptime_seconds": snapshot.uptime_seconds,

            "cpu": {
                "percent": snapshot.cpu_percent,
                "count": snapshot.cpu_count,
                "frequency_mhz": snapshot.cpu_frequency_mhz,
            },

            "memory": {
                "total_bytes": snapshot.memory_total_bytes,
                "used_bytes": snapshot.memory_used_bytes,
                "available_bytes": snapshot.memory_available_bytes,
                "percent": snapshot.memory_percent,
            },

            "storage": {
                "path": snapshot.storage_path,
                "total_bytes": snapshot.storage_total_bytes,
                "used_bytes": snapshot.storage_used_bytes,
                "free_bytes": snapshot.storage_free_bytes,
                "percent": snapshot.storage_percent,
            },

            "temperature": {
                "celsius": snapshot.temperature_celsius,
            },

            "network": {
                "interface_online": snapshot.network_interface_online,
            },

            "host": {
                "hostname": snapshot.hostname,
            },
        }