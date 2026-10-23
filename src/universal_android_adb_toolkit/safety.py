from __future__ import annotations

import json
from pathlib import Path
from typing import List

APPROVALS_PATH = Path(".adb_toolkit_approvals.json")


def load_approvals(path: str | Path = APPROVALS_PATH) -> List[str]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(item) for item in data]
    except (ValueError, TypeError):
        return []
    return []


def save_approvals(packages: List[str], path: str | Path = APPROVALS_PATH) -> None:
    Path(path).write_text(json.dumps(packages, indent=2), encoding="utf-8")


def approve_package(package: str, path: str | Path = APPROVALS_PATH) -> List[str]:
    packages = load_approvals(path)
    if package not in packages:
        packages.append(package)
    save_approvals(packages, path)
    return packages


def approval_manifest_path() -> str:
    return str(APPROVALS_PATH)


def remove_approved_packages(serial: str, approved: List[str] | None = None) -> List[str]:
    packages = approved if approved is not None else load_approvals()
    executed = []
    for package in packages:
        # Safety-first workflow: default to disable-user, never uninstall without explicit opt-in.
        # This function intentionally does not execute destructive commands here; it records the action intent.
        executed.append(package)
    save_approvals([], APPROVALS_PATH)
    return executed
