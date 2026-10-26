from __future__ import annotations

from typing import Any

__version__ = "0.3.0"
__all__ = [
    "__version__",
    "main",
    "build_package_command",
    "device_report",
    "filter_logcat_output",
    "get_connected_devices",
    "list_packages",
    "read_battery",
    "safe_removal_candidates",
]


def __getattr__(name: str) -> Any:
    if name == "safe_removal_candidates":
        from .bloatware import safe_removal_candidates

        return safe_removal_candidates
    if name in {
        "main",
        "build_package_command",
        "device_report",
        "filter_logcat_output",
        "get_connected_devices",
        "list_packages",
        "read_battery",
    }:
        from . import cli

        return getattr(cli, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
