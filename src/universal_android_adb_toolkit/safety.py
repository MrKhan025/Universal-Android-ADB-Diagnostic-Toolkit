from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .bloatware import is_protected_package
from .cli import build_package_command, run_command, validate_package_name

APPROVALS_PATH = Path(".adb_toolkit_approvals.json")


def load_approvals(path: str | Path = APPROVALS_PATH) -> List[str]:
    target = Path(path)
    if not target.exists():
        return []
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [str(item).strip() for item in data if str(item).strip()]
    except (ValueError, TypeError, OSError):
        return []
    return []


def save_approvals(packages: List[str], path: str | Path = APPROVALS_PATH) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    cleaned = sorted({pkg.strip() for pkg in packages if pkg and pkg.strip()})
    target.write_text(json.dumps(cleaned, indent=2), encoding="utf-8")


def approve_package(package: str, path: str | Path = APPROVALS_PATH) -> List[str]:
    cleaned = package.strip()
    if not validate_package_name(cleaned):
        raise ValueError(f"Invalid Android package name: {package!r}")
    if is_protected_package(cleaned):
        raise ValueError(f"Cannot approve protected core system package: {cleaned}")
    packages = load_approvals(path)
    if cleaned not in packages:
        packages.append(cleaned)
    save_approvals(packages, path)
    return load_approvals(path)


def unapprove_package(package: str, path: str | Path = APPROVALS_PATH) -> List[str]:
    cleaned = package.strip()
    packages = [pkg for pkg in load_approvals(path) if pkg != cleaned]
    save_approvals(packages, path)
    return packages


def clear_approvals(path: str | Path = APPROVALS_PATH) -> None:
    save_approvals([], path)


def approval_manifest_path() -> str:
    return str(APPROVALS_PATH)


def remove_approved_packages(
    serial: str,
    approved: List[str] | None = None,
    *,
    execute: bool = False,
    remove: bool = False,
    user: int = 0,
    path: str | Path = APPROVALS_PATH,
) -> List[str]:
    """Process approved packages for safe disable/uninstall workflow.

    By default (`execute=False`), operates in safe dry-run/intent mode and clears the
    manifest while returning the processed package list. When `execute=True`, runs
    `pm disable-user --user <user>` (or `pm uninstall` if `remove=True`) for each
    non-protected approved package via ADB.
    """
    packages = approved if approved is not None else load_approvals(path)
    executed: List[str] = []
    for package in packages:
        cleaned = package.strip()
        if not cleaned or not validate_package_name(cleaned) or is_protected_package(cleaned):
            continue
        if execute:
            cmd = build_package_command(serial, cleaned, remove=remove, user=user)
            res = run_command(cmd)
            if res.returncode == 0:
                executed.append(cleaned)
        else:
            executed.append(cleaned)
    save_approvals([], path)
    return executed


def execute_approved_packages_detailed(
    serial: str,
    approved: List[str] | None = None,
    *,
    remove: bool = False,
    user: int = 0,
    dry_run: bool = False,
    path: str | Path = APPROVALS_PATH,
) -> List[Dict[str, Any]]:
    """Execute or dry-run approved packages and return per-package command outcomes."""
    packages = approved if approved is not None else load_approvals(path)
    results: List[Dict[str, Any]] = []
    for package in packages:
        cleaned = package.strip()
        try:
            cmd = build_package_command(serial, cleaned, remove=remove, user=user)
        except ValueError as exc:
            results.append({"package": cleaned, "status": "rejected", "error": str(exc)})
            continue

        if dry_run:
            results.append({"package": cleaned, "status": "dry_run", "command": cmd})
        else:
            proc = run_command(cmd)
            results.append(
                {
                    "package": cleaned,
                    "status": "ok" if proc.returncode == 0 else "failed",
                    "return_code": proc.returncode,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                }
            )
    if not dry_run:
        save_approvals([], path)
    return results
