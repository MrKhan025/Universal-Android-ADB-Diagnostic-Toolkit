from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Optional

from .bloatware import get_safe_bloatware_packages, safe_removal_candidates


DEFAULT_PRIORITY = {"V": "verbose", "D": "debug", "I": "info", "W": "warning", "E": "error", "F": "fatal", "A": "assert"}


def run_command(command: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def adb_prefix(serial: Optional[str] = None) -> List[str]:
    prefix = ["adb"]
    if serial:
        prefix.extend(["-s", serial])
    return prefix


def get_connected_devices() -> List[str]:
    proc = run_command(["adb", "devices", "-l"])
    if proc.returncode != 0:
        return []
    devices: List[str] = []
    for line in proc.stdout.splitlines():
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] in {"device", "unauthorized", "offline"}:
            devices.append(parts[0])
    return devices


def fastboot_devices() -> List[str]:
    proc = run_command(["fastboot", "devices"])
    if proc.returncode != 0:
        return []
    return [line.split()[0] for line in proc.stdout.splitlines() if line.strip()]


def shell(serial: Optional[str], *command: str) -> subprocess.CompletedProcess[str]:
    return run_command(adb_prefix(serial) + ["shell", *command])


def get_android_property(serial: Optional[str], key: str) -> str:
    proc = shell(serial, "getprop", key)
    return proc.stdout.strip()


def read_battery(serial: Optional[str]) -> Dict[str, Any]:
    result = shell(serial, "dumpsys", "battery")
    if result.returncode != 0:
        return {"status": "unavailable", "details": result.stderr.strip() or result.stdout.strip()}

    data: Dict[str, Any] = {}
    for line in result.stdout.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        cleaned_key = key.strip().lower().replace(" ", "_")
        cleaned_value = value.strip()
        if cleaned_key in {"health", "status", "technology", "present"}:
            data[cleaned_key] = cleaned_value
        elif cleaned_key in {"level", "scale", "temperature", "voltage", "current_now"}:
            try:
                data[cleaned_key] = int(cleaned_value)
            except ValueError:
                data[cleaned_key] = cleaned_value

    if "level" in data and "scale" in data and data["scale"]:
        data["percentage"] = round((data["level"] / data["scale"]) * 100, 2)
    return data


def device_report(serial: Optional[str]) -> Dict[str, Any]:
    props = {
        "brand": "ro.product.brand",
        "model": "ro.product.model",
        "device": "ro.product.device",
        "manufacturer": "ro.product.manufacturer",
        "build_id": "ro.build.id",
        "android_version": "ro.build.version.release",
        "sdk": "ro.build.version.sdk",
        "security_patch": "ro.build.version.security_patch",
    }
    report: Dict[str, Any] = {"serial": serial}
    for name, key in props.items():
        report[name] = get_android_property(serial, key) or "unknown"

    battery = read_battery(serial)
    report["battery"] = battery
    report["storage"] = read_storage_snapshot(serial)
    report["safe_bloatware_candidates"] = safe_removal_candidates(serial)
    return report


def read_storage_snapshot(serial: Optional[str]) -> Dict[str, str]:
    proc = shell(serial, "df", "-h")
    if proc.returncode != 0:
        return {"status": "unavailable", "details": proc.stderr.strip() or proc.stdout.strip()}
    return {"raw": proc.stdout.strip()}


def list_packages(serial: Optional[str], third_party_only: bool = False) -> List[str]:
    proc = shell(serial, "pm", "list", "packages")
    if proc.returncode != 0:
        return []
    packages: List[str] = []
    for line in proc.stdout.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("package:"):
            package = cleaned.split(":", 1)[1]
            if third_party_only and is_system_package(package):
                continue
            packages.append(package)
    return sorted(packages)


def is_system_package(package: str) -> bool:
    blocked_prefixes = (
        "android.",
        "com.android.",
        "com.google.android.",
        "com.google.",
        "androidx.",
    )
    return package.startswith(blocked_prefixes)


def build_package_command(serial: Optional[str], package: str, *, remove: bool = False, user: int = 0) -> List[str]:
    prefix = adb_prefix(serial)
    if remove:
        return prefix + ["shell", "pm", "uninstall", "--user", str(user), package]
    return prefix + ["shell", "pm", "disable-user", "--user", str(user), package]


def restore_package(serial: Optional[str], package: str) -> subprocess.CompletedProcess[str]:
    cmd = adb_prefix(serial) + ["shell", "pm", "enable", package]
    return run_command(cmd)


def filter_logcat_output(log_lines: Iterable[str], pattern: Optional[str] = None, tag: Optional[str] = None, priority: Optional[str] = None, pid: Optional[str] = None) -> List[str]:
    filtered: List[str] = []
    for line in log_lines:
        if not line.strip():
            continue
        if pattern and pattern.lower() not in line.lower():
            continue
        if tag and tag.lower() not in line.lower():
            continue
        if priority and not log_priority_matches(line, priority):
            continue
        if pid and not re.search(rf"\b{re.escape(pid)}\b", line):
            continue
        filtered.append(line)
    return filtered


def log_priority_matches(line: str, target: str) -> bool:
    token = target.upper()
    match = re.search(r"\s([A-Z])/(?:[^:]+):", line)
    if match:
        return match.group(1).upper() == token
    return False


def read_logcat(serial: Optional[str], limit: int = 200) -> List[str]:
    proc = run_command(adb_prefix(serial) + ["logcat", "-d"])
    if proc.returncode != 0:
        return []
    lines = proc.stdout.splitlines()
    return lines[-limit:] if limit else lines


def run_doctor(serial: Optional[str] = None, json_output: bool = False) -> Dict[str, Any]:
    adb_ok = shutil_which("adb")
    fastboot_ok = shutil_which("fastboot")
    devices = get_connected_devices()
    report = {
        "adb_available": bool(adb_ok),
        "fastboot_available": bool(fastboot_ok),
        "connected_devices": devices,
    }
    if serial:
        report["selected_device"] = serial
        report["device_report"] = device_report(serial)
    elif devices:
        report["selected_device"] = devices[0]
        report["device_report"] = device_report(devices[0])
    if json_output:
        print(json.dumps(report, indent=2))
    return report


def shutil_which(binary_name: str) -> Optional[str]:
    return subprocess.run(["which", binary_name], capture_output=True, text=True).stdout.strip() or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Universal Android / ADB Diagnostic Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check ADB and Fastboot availability")
    doctor.add_argument("--serial")
    doctor.add_argument("--json", action="store_true")

    devices = subparsers.add_parser("devices", help="List connected devices")
    devices.add_argument("--json", action="store_true")

    report = subparsers.add_parser("report", help="Collect a device status report")
    report.add_argument("--serial")
    report.add_argument("--json", action="store_true")

    battery = subparsers.add_parser("battery", help="Read battery diagnostics")
    battery.add_argument("--serial")
    battery.add_argument("--json", action="store_true")

    packages = subparsers.add_parser("packages", help="List installed packages")
    packages.add_argument("--serial")
    packages.add_argument("--third-party", action="store_true")
    packages.add_argument("--json", action="store_true")

    remove = subparsers.add_parser("remove", help="Disable or remove a package")
    remove.add_argument("package")
    remove.add_argument("--serial")
    remove.add_argument("--remove", action="store_true")
    remove.add_argument("--dry-run", action="store_true")
    remove.add_argument("--user", type=int, default=0)
    remove.add_argument("--json", action="store_true")

    restore = subparsers.add_parser("restore", help="Restore a disabled package")
    restore.add_argument("package")
    restore.add_argument("--serial")
    restore.add_argument("--json", action="store_true")

    logcat = subparsers.add_parser("logcat", help="Capture and filter logcat output")
    logcat.add_argument("--serial")
    logcat.add_argument("--pattern")
    logcat.add_argument("--tag")
    logcat.add_argument("--priority", choices=["V", "D", "I", "W", "E", "F", "A"])
    logcat.add_argument("--pid")
    logcat.add_argument("--limit", type=int, default=200)
    logcat.add_argument("--json", action="store_true")

    fastboot = subparsers.add_parser("fastboot", help="Inspect connected Fastboot devices")
    fastboot.add_argument("--json", action="store_true")

    dashboard = subparsers.add_parser("dashboard", help="Print a battery + storage + bloatware summary")
    dashboard.add_argument("--serial")
    dashboard.add_argument("--json", action="store_true")

    desktop = subparsers.add_parser("desktop", help="Launch the desktop diagnostic GUI")
    desktop.add_argument("--json", action="store_true")

    return parser


def summarize_dashboard(serial: Optional[str]) -> Dict[str, Any]:
    data = {} if serial is None else device_report(serial)
    if serial is None:
        serial = get_connected_devices()[0] if get_connected_devices() else None
    if not serial:
        return {"serial": None, "battery": None, "storage": None, "safe_bloatware_candidates": []}
    data = device_report(serial)
    return {
        "serial": serial,
        "battery": data.get("battery", {}),
        "storage": data.get("storage", {}),
        "safe_bloatware_candidates": data.get("safe_bloatware_candidates", []),
        "android_version": data.get("android_version"),
        "model": data.get("model"),
    }


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "doctor":
        report = run_doctor(args.serial, json_output=args.json)
        if not args.json:
            print(f"ADB available: {report['adb_available']}")
            print(f"Fastboot available: {report['fastboot_available']}")
            print(f"Devices: {', '.join(report['connected_devices']) if report['connected_devices'] else 'none'}")
        return 0

    if args.command == "devices":
        devices = get_connected_devices()
        payload = {"devices": devices}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not devices:
                print("No connected devices detected.")
            else:
                for device in devices:
                    print(device)
        return 0

    if args.command == "report":
        serial = args.serial or (get_connected_devices()[0] if get_connected_devices() else None)
        payload = {"serial": serial, "report": device_report(serial) if serial else {}} if serial else {"serial": None, "report": {}}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not serial:
                print("No device available.")
                return 1
            for key, value in payload["report"].items():
                print(f"{key}: {value}")
        return 0

    if args.command == "battery":
        serial = args.serial or (get_connected_devices()[0] if get_connected_devices() else None)
        if not serial:
            print("No connected device available.")
            return 1
        payload = {"serial": serial, "battery": read_battery(serial)}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for key, value in payload["battery"].items():
                print(f"{key}: {value}")
        return 0

    if args.command == "packages":
        serial = args.serial or (get_connected_devices()[0] if get_connected_devices() else None)
        if not serial:
            print("No connected device available.")
            return 1
        packages = list_packages(serial, third_party_only=args.third_party)
        payload = {"serial": serial, "packages": packages}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for package in packages:
                print(package)
        return 0

    if args.command == "remove":
        serial = args.serial or (get_connected_devices()[0] if get_connected_devices() else None)
        if not serial:
            print("No connected device available.")
            return 1
        command = build_package_command(serial, args.package, remove=args.remove, user=args.user)
        payload = {"serial": serial, "dry_run": args.dry_run, "command": command}
        if args.dry_run:
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Dry-run command:")
                print(" ".join(command))
            return 0
        result = run_command(command)
        if args.json:
            print(json.dumps({"serial": serial, "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}, indent=2))
        else:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        return result.returncode

    if args.command == "restore":
        serial = args.serial or (get_connected_devices()[0] if get_connected_devices() else None)
        if not serial:
            print("No connected device available.")
            return 1
        result = restore_package(serial, args.package)
        payload = {"serial": serial, "return_code": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        return result.returncode

    if args.command == "logcat":
        serial = args.serial or (get_connected_devices()[0] if get_connected_devices() else None)
        if not serial:
            print("No connected device available.")
            return 1
        lines = read_logcat(serial, limit=args.limit)
        filtered = filter_logcat_output(lines, pattern=args.pattern, tag=args.tag, priority=args.priority, pid=args.pid)
        payload = {"serial": serial, "lines": filtered}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for line in filtered:
                print(line)
        return 0

    if args.command == "fastboot":
        devices = fastboot_devices()
        payload = {"fastboot_devices": devices}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            if not devices:
                print("No devices detected in Fastboot mode.")
            else:
                for device in devices:
                    print(device)
        return 0

    if args.command == "dashboard":
        payload = summarize_dashboard(args.serial)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            serial = payload.get("serial")
            if not serial:
                print("No connected device available.")
                return 1
            print(f"Device: {serial}")
            print(f"Model: {payload.get('model', 'unknown')}")
            print(f"Android: {payload.get('android_version', 'unknown')}")
            print(f"Battery: {payload.get('battery', {})}")
            print(f"Storage: {payload.get('storage', {})}")
            print(f"Safe removal candidates: {payload.get('safe_bloatware_candidates', [])}")
        return 0

    if args.command == "desktop":
        from .gui import main as gui_main
        return gui_main()

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
