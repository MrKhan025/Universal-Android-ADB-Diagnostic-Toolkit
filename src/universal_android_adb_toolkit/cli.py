from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .bloatware import (
    categorize_bloatware_candidates,
    get_safe_bloatware_packages,
    is_protected_package,
    safe_removal_candidates,
)

DEFAULT_PRIORITY = {
    "V": "verbose",
    "D": "debug",
    "I": "info",
    "W": "warning",
    "E": "error",
    "F": "fatal",
    "A": "assert",
}

BATTERY_STATUS_MAP = {
    "1": "unknown",
    "2": "charging",
    "3": "discharging",
    "4": "not_charging",
    "5": "full",
}

BATTERY_HEALTH_MAP = {
    "1": "unknown",
    "2": "good",
    "3": "overheat",
    "4": "dead",
    "5": "over_voltage",
    "6": "unspecified_failure",
    "7": "cold",
}

PACKAGE_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+$")


def validate_package_name(package: str) -> bool:
    """Validate that a string conforms to standard Android package naming rules."""
    return bool(package and PACKAGE_NAME_RE.match(package.strip()))


def run_command(command: List[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    """Execute an external command safely with timeout and missing-binary handling."""
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        binary = command[0] if command else "command"
        return subprocess.CompletedProcess(
            args=command,
            returncode=127,
            stdout="",
            stderr=f"Command not found: {binary} ({exc})",
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=command,
            returncode=124,
            stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
            stderr=f"Command timed out after {timeout}s: {' '.join(command)}",
        )


def adb_prefix(serial: Optional[str] = None) -> List[str]:
    prefix = ["adb"]
    if serial:
        prefix.extend(["-s", serial])
    return prefix


def get_connected_devices(only_authorized: bool = False) -> List[str]:
    """Return list of connected ADB device serials."""
    proc = run_command(["adb", "devices", "-l"])
    if proc.returncode != 0:
        return []
    devices: List[str] = []
    valid_states = {"device"} if only_authorized else {"device", "unauthorized", "offline"}
    for line in proc.stdout.splitlines():
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] in valid_states:
            devices.append(parts[0])
    return devices


def get_connected_devices_detailed() -> List[Dict[str, str]]:
    """Return detailed connection metadata for each detected ADB device."""
    proc = run_command(["adb", "devices", "-l"])
    if proc.returncode != 0:
        return []
    details: List[Dict[str, str]] = []
    for line in proc.stdout.splitlines():
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2 and parts[1] in {"device", "unauthorized", "offline", "recovery", "sideload"}:
            entry: Dict[str, str] = {"serial": parts[0], "state": parts[1]}
            for token in parts[2:]:
                if ":" in token:
                    k, _, v = token.partition(":")
                    entry[k] = v
            details.append(entry)
    return details


def resolve_serial(serial: Optional[str] = None) -> Optional[str]:
    """Resolve an explicit serial or pick the first connected ADB device (preferring authorized)."""
    if serial and serial.strip():
        return serial.strip()
    authorized = get_connected_devices(only_authorized=True)
    if authorized:
        return authorized[0]
    all_devices = get_connected_devices(only_authorized=False)
    return all_devices[0] if all_devices else None


def fastboot_devices() -> List[str]:
    proc = run_command(["fastboot", "devices"])
    if proc.returncode != 0:
        return []
    return [line.split()[0] for line in proc.stdout.splitlines() if line.strip()]


def shell(serial: Optional[str], *command: str) -> subprocess.CompletedProcess[str]:
    return run_command(adb_prefix(serial) + ["shell", *command])


def get_android_property(serial: Optional[str], key: str) -> str:
    proc = shell(serial, "getprop", key)
    if proc.returncode != 0:
        return ""
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
        if cleaned_key in {"health", "status", "technology", "present", "ac_powered", "usb_powered", "wireless_powered"}:
            data[cleaned_key] = cleaned_value
        elif cleaned_key in {"level", "scale", "temperature", "voltage", "current_now", "charge_counter"}:
            try:
                data[cleaned_key] = int(cleaned_value)
            except ValueError:
                data[cleaned_key] = cleaned_value

    if "level" in data and "scale" in data and isinstance(data["level"], int) and isinstance(data["scale"], int) and data["scale"]:
        data["percentage"] = round((data["level"] / data["scale"]) * 100, 2)
    if "temperature" in data and isinstance(data["temperature"], int):
        data["temperature_c"] = round(data["temperature"] / 10.0, 1)
    if "status" in data and str(data["status"]) in BATTERY_STATUS_MAP:
        data["status_label"] = BATTERY_STATUS_MAP[str(data["status"])]
    if "health" in data and str(data["health"]) in BATTERY_HEALTH_MAP:
        data["health_label"] = BATTERY_HEALTH_MAP[str(data["health"])]
    return data


def read_storage_snapshot(serial: Optional[str]) -> Dict[str, Any]:
    proc = shell(serial, "df", "-h")
    if proc.returncode != 0:
        return {"status": "unavailable", "details": proc.stderr.strip() or proc.stdout.strip()}
    raw_output = proc.stdout.strip()
    mounts: List[Dict[str, str]] = []
    lines = raw_output.splitlines()
    for line in lines[1:]:
        parts = line.split()
        if len(parts) >= 6:
            mounts.append(
                {
                    "filesystem": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "use_percent": parts[4],
                    "mounted_on": parts[5],
                }
            )
    return {"raw": raw_output, "mounts": mounts}


def read_memory_snapshot(serial: Optional[str]) -> Dict[str, Any]:
    """Read device RAM and swap statistics from /proc/meminfo."""
    proc = shell(serial, "cat", "/proc/meminfo")
    if proc.returncode != 0:
        return {"status": "unavailable", "details": proc.stderr.strip() or proc.stdout.strip()}
    mem: Dict[str, Any] = {}
    wanted = {"MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached", "SwapTotal", "SwapFree"}
    for line in proc.stdout.splitlines():
        key, sep, value = line.partition(":")
        if not sep:
            continue
        k = key.strip()
        if k in wanted:
            parts = value.strip().split()
            if parts:
                try:
                    mem[f"{k.lower()}_kb"] = int(parts[0])
                except ValueError:
                    mem[k.lower()] = value.strip()
    if "memtotal_kb" in mem and "memavailable_kb" in mem and mem["memtotal_kb"] > 0:
        used_kb = max(0, mem["memtotal_kb"] - mem["memavailable_kb"])
        mem["used_percent"] = round((used_kb / mem["memtotal_kb"]) * 100, 2)
    return mem


def read_cpu_thermal(serial: Optional[str]) -> Dict[str, Any]:
    """Best-effort CPU and thermal snapshot (varies by kernel/OEM)."""
    data: Dict[str, Any] = {}
    # CPU cores online
    proc = shell(serial, "cat", "/sys/devices/system/cpu/online")
    if proc.returncode == 0 and proc.stdout.strip():
        data["cpu_online"] = proc.stdout.strip()
    # First few thermal zones
    temps: List[Dict[str, str]] = []
    for zone in range(0, 8):
        t_type = shell(serial, "cat", f"/sys/class/thermal/thermal_zone{zone}/type")
        t_temp = shell(serial, "cat", f"/sys/class/thermal/thermal_zone{zone}/temp")
        if t_type.returncode == 0 and t_temp.returncode == 0:
            try:
                milli = int(t_temp.stdout.strip())
                celsius = round(milli / 1000.0, 1) if milli > 200 else float(milli)
            except ValueError:
                celsius = t_temp.stdout.strip()
            temps.append({"zone": f"thermal_zone{zone}", "type": t_type.stdout.strip(), "temp_c": celsius})
        else:
            break
    if temps:
        data["thermal_zones"] = temps
    # Load average
    proc = shell(serial, "cat", "/proc/loadavg")
    if proc.returncode == 0 and proc.stdout.strip():
        parts = proc.stdout.strip().split()
        if len(parts) >= 3:
            data["loadavg"] = {"1m": parts[0], "5m": parts[1], "15m": parts[2]}
    return data or {"status": "unavailable"}


def read_network_info(serial: Optional[str]) -> Dict[str, Any]:
    """Collect basic network / Wi-Fi / IP information."""
    data: Dict[str, Any] = {}
    proc = shell(serial, "ip", "addr", "show")
    if proc.returncode == 0:
        data["ip_addr"] = proc.stdout.strip()[:4000]
    proc = shell(serial, "dumpsys", "wifi")
    if proc.returncode == 0:
        # Keep only first ~80 lines to avoid huge dumps
        lines = proc.stdout.splitlines()[:80]
        data["wifi_summary"] = "\n".join(lines)
    proc = shell(serial, "getprop", "dhcp.wlan0.ipaddress")
    if proc.returncode == 0 and proc.stdout.strip():
        data["wlan0_ip"] = proc.stdout.strip()
    proc = shell(serial, "getprop", "wifi.interface")
    if proc.returncode == 0 and proc.stdout.strip():
        data["wifi_interface"] = proc.stdout.strip()
    return data or {"status": "unavailable"}


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
        "fingerprint": "ro.build.fingerprint",
        "hardware": "ro.hardware",
        "board": "ro.product.board",
        "serialno": "ro.serialno",
        "bootloader": "ro.bootloader",
        "baseband": "gsm.version.baseband",
    }
    report: Dict[str, Any] = {"serial": serial}
    for name, key in props.items():
        report[name] = get_android_property(serial, key) or "unknown"

    report["battery"] = read_battery(serial)
    report["storage"] = read_storage_snapshot(serial)
    report["memory"] = read_memory_snapshot(serial)
    report["cpu_thermal"] = read_cpu_thermal(serial)
    report["network"] = read_network_info(serial)
    installed = list_packages(serial, third_party_only=False)
    report["package_count"] = len(installed)
    report["safe_bloatware_candidates"] = safe_removal_candidates(serial, package_list=installed)
    return report


def list_packages(serial: Optional[str], third_party_only: bool = False) -> List[str]:
    """List installed packages. When third_party_only=True uses `pm list packages -3`."""
    cmd = ["pm", "list", "packages", "-3"] if third_party_only else ["pm", "list", "packages"]
    proc = shell(serial, *cmd)
    if proc.returncode != 0:
        return []
    packages: List[str] = []
    for line in proc.stdout.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if cleaned.startswith("package:"):
            package = cleaned.split(":", 1)[1].strip()
            if package:
                packages.append(package)
    return sorted(set(packages))


def is_system_package(package: str) -> bool:
    """Heuristic: packages that typically ship as system/preloaded."""
    blocked_prefixes = (
        "android.",
        "com.android.",
        "com.google.android.",
        "com.google.",
        "androidx.",
    )
    return package.startswith(blocked_prefixes) or package == "android"


def build_package_command(
    serial: Optional[str],
    package: str,
    *,
    remove: bool = False,
    user: int = 0,
    allow_protected: bool = False,
) -> List[str]:
    cleaned = package.strip()
    if not validate_package_name(cleaned):
        raise ValueError(f"Invalid Android package name: {package!r}")
    if not allow_protected and is_protected_package(cleaned):
        raise ValueError(f"Refusing to modify protected core system package: {cleaned}")
    prefix = adb_prefix(serial)
    if remove:
        return prefix + ["shell", "pm", "uninstall", "--user", str(user), cleaned]
    return prefix + ["shell", "pm", "disable-user", "--user", str(user), cleaned]


def restore_package(serial: Optional[str], package: str, user: int = 0) -> subprocess.CompletedProcess[str]:
    cleaned = package.strip()
    if not validate_package_name(cleaned):
        raise ValueError(f"Invalid Android package name: {package!r}")
    cmd = adb_prefix(serial) + ["shell", "pm", "enable", "--user", str(user), cleaned]
    return run_command(cmd)


def filter_logcat_output(
    log_lines: Iterable[str],
    pattern: Optional[str] = None,
    tag: Optional[str] = None,
    priority: Optional[str] = None,
    pid: Optional[str] = None,
) -> List[str]:
    filtered: List[str] = []
    for line in log_lines:
        if not line.strip():
            continue
        if pattern and pattern.lower() not in line.lower():
            continue
        if tag and not log_tag_matches(line, tag):
            continue
        if priority and not log_priority_matches(line, priority):
            continue
        if pid and not re.search(rf"\b{re.escape(str(pid))}\b", line):
            continue
        filtered.append(line)
    return filtered


def log_tag_matches(line: str, target_tag: str) -> bool:
    target = target_tag.strip().lower()
    if not target:
        return True
    match = re.search(r"\s[VDIWEFA]/([^(:]+)", line)
    if match and target in match.group(1).strip().lower():
        return True
    return target in line.lower()


def log_priority_matches(line: str, target: str) -> bool:
    token = target.strip().upper()
    # Matches standard brief/threadtime formats like ' I/Tag:' or ' 1234 5678 I Tag:'
    match = re.search(r"(?:\s([VDIWEFA])/(?:[^:]+):|\s\d+\s+\d+\s+([VDIWEFA])\s+[^:]+:)", line)
    if match:
        found = (match.group(1) or match.group(2) or "").upper()
        return found == token
    return False


def read_logcat(serial: Optional[str], limit: int = 200) -> List[str]:
    cmd = adb_prefix(serial) + ["logcat", "-d"]
    if limit and limit > 0:
        cmd.extend(["-t", str(limit)])
    proc = run_command(cmd)
    if proc.returncode != 0:
        return []
    lines = proc.stdout.splitlines()
    return lines[-limit:] if limit and limit > 0 else lines


def shutil_which(binary_name: str) -> Optional[str]:
    """Cross-platform binary lookup using standard library shutil.which."""
    return shutil.which(binary_name)


def run_doctor(serial: Optional[str] = None, json_output: bool = False) -> Dict[str, Any]:
    adb_path = shutil_which("adb")
    fastboot_path = shutil_which("fastboot")
    devices = get_connected_devices()
    report: Dict[str, Any] = {
        "adb_available": bool(adb_path),
        "adb_path": adb_path,
        "fastboot_available": bool(fastboot_path),
        "fastboot_path": fastboot_path,
        "connected_devices": devices,
    }
    target_serial = serial or (devices[0] if devices else None)
    if target_serial:
        report["selected_device"] = target_serial
        report["device_report"] = device_report(target_serial)
    if json_output:
        print(json.dumps(report, indent=2))
    return report


def summarize_dashboard(serial: Optional[str]) -> Dict[str, Any]:
    target_serial = resolve_serial(serial)
    if not target_serial:
        return {
            "serial": None,
            "battery": None,
            "storage": None,
            "memory": None,
            "safe_bloatware_candidates": [],
        }
    data = device_report(target_serial)
    return {
        "serial": target_serial,
        "battery": data.get("battery", {}),
        "storage": data.get("storage", {}),
        "memory": data.get("memory", {}),
        "safe_bloatware_candidates": data.get("safe_bloatware_candidates", []),
        "android_version": data.get("android_version"),
        "model": data.get("model"),
    }



def take_screenshot(serial: Optional[str], output: str) -> Dict[str, Any]:
    """Capture a PNG screenshot via `adb exec-out screencap -p`."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No device available"}
    cmd = adb_prefix(target) + ["exec-out", "screencap", "-p"]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=45)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Screenshot timed out"}
    if proc.returncode != 0:
        return {"ok": False, "error": (proc.stderr or b"").decode("utf-8", errors="replace") or "screencap failed"}
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(proc.stdout)
    return {"ok": True, "path": str(out_path), "bytes": len(proc.stdout)}


def install_apk(serial: Optional[str], apk_path: str, replace: bool = True) -> Dict[str, Any]:
    """Install an APK on the device."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No device available"}
    p = Path(apk_path)
    if not p.is_file():
        return {"ok": False, "error": f"APK not found: {apk_path}"}
    cmd = adb_prefix(target) + ["install"]
    if replace:
        cmd.append("-r")
    cmd.append(str(p))
    proc = run_command(cmd, timeout=120)
    return {
        "ok": proc.returncode == 0,
        "return_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def clear_package(serial: Optional[str], package: str, *, clear_cache: bool = True, force_stop: bool = True) -> Dict[str, Any]:
    """Force-stop and/or clear cache for a package (non-destructive)."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No device available"}
    cleaned = package.strip()
    if not validate_package_name(cleaned):
        return {"ok": False, "error": f"Invalid package name: {package!r}"}
    if is_protected_package(cleaned):
        return {"ok": False, "error": f"Refusing to modify protected package: {cleaned}"}
    results: Dict[str, Any] = {"package": cleaned, "actions": []}
    if force_stop:
        proc = shell(target, "am", "force-stop", cleaned)
        results["actions"].append({"action": "force-stop", "return_code": proc.returncode, "stderr": proc.stderr.strip()})
    if clear_cache:
        proc = shell(target, "pm", "clear", "--cache-only", cleaned)
        # Fallback for older Android that may not support --cache-only
        if proc.returncode != 0:
            # Do NOT fall back to full pm clear (data wipe) automatically
            results["actions"].append({"action": "clear-cache", "return_code": proc.returncode, "stderr": proc.stderr.strip() or "cache-only not supported"})
        else:
            results["actions"].append({"action": "clear-cache", "return_code": 0, "stdout": proc.stdout.strip()})
    results["ok"] = all(a.get("return_code", 1) == 0 for a in results["actions"])
    return results


def reboot_device(serial: Optional[str], mode: str = "system") -> Dict[str, Any]:
    """Reboot device into system, recovery, or bootloader."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No device available"}
    mode = (mode or "system").lower()
    if mode not in {"system", "recovery", "bootloader", "fastboot"}:
        return {"ok": False, "error": f"Unsupported reboot mode: {mode}"}
    if mode == "system":
        cmd = adb_prefix(target) + ["reboot"]
    elif mode == "recovery":
        cmd = adb_prefix(target) + ["reboot", "recovery"]
    else:
        cmd = adb_prefix(target) + ["reboot", "bootloader"]
    proc = run_command(cmd, timeout=20)
    return {"ok": proc.returncode == 0, "mode": mode, "return_code": proc.returncode, "stderr": proc.stderr.strip()}


def adb_tcpip(serial: Optional[str], port: int = 5555) -> Dict[str, Any]:
    """Enable ADB over TCP/IP on the given port (device must be USB-connected first)."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No USB device available to enable tcpip"}
    proc = run_command(adb_prefix(target) + ["tcpip", str(port)], timeout=15)
    return {"ok": proc.returncode == 0, "port": port, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def adb_connect(host: str, port: int = 5555) -> Dict[str, Any]:
    """Connect to a device over the network (host:port)."""
    target = f"{host}:{port}" if ":" not in host else host
    proc = run_command(["adb", "connect", target], timeout=15)
    return {"ok": proc.returncode == 0, "target": target, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}


def adb_disconnect(host: Optional[str] = None) -> Dict[str, Any]:
    """Disconnect a specific host or all wireless devices."""
    cmd = ["adb", "disconnect"]
    if host:
        cmd.append(host)
    proc = run_command(cmd, timeout=10)
    return {"ok": proc.returncode == 0, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}



def package_info(serial: Optional[str], package: str) -> Dict[str, Any]:
    """Return version, path, installer and disabled state for a package."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No device available"}
    cleaned = package.strip()
    if not validate_package_name(cleaned):
        return {"ok": False, "error": f"Invalid package name: {package!r}"}
    info: Dict[str, Any] = {"package": cleaned, "ok": True}
    # dumpsys package is heavy; use targeted pm / dumpsys
    proc = shell(target, "dumpsys", "package", cleaned)
    if proc.returncode != 0:
        info["ok"] = False
        info["error"] = proc.stderr.strip() or "dumpsys failed"
        return info
    out = proc.stdout
    # versionName / versionCode
    import re as _re
    m = _re.search(r"versionName=([^\s]+)", out)
    if m:
        info["version_name"] = m.group(1)
    m = _re.search(r"versionCode=(\d+)", out)
    if m:
        info["version_code"] = int(m.group(1))
    m = _re.search(r"codePath=([^\s]+)", out)
    if m:
        info["code_path"] = m.group(1)
    m = _re.search(r"installerPackageName=([^\s]+)", out)
    if m:
        info["installer"] = m.group(1)
    # enabled state
    proc2 = shell(target, "pm", "list", "packages", "-d", cleaned)
    info["disabled"] = proc2.returncode == 0 and cleaned in (proc2.stdout or "")
    # third-party?
    proc3 = shell(target, "pm", "list", "packages", "-3", cleaned)
    info["third_party"] = proc3.returncode == 0 and cleaned in (proc3.stdout or "")
    return info


def collect_bugreport(serial: Optional[str], output: str, timeout: int = 180) -> Dict[str, Any]:
    """Generate a bugreport zip on the device and pull it."""
    target = resolve_serial(serial)
    if not target:
        return {"ok": False, "error": "No device available"}
    out_path = Path(output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Prefer bugreportz if available (Android 7+)
    proc = run_command(adb_prefix(target) + ["bugreport", str(out_path)], timeout=timeout)
    if proc.returncode == 0 and out_path.exists() and out_path.stat().st_size > 0:
        return {"ok": True, "path": str(out_path), "bytes": out_path.stat().st_size}
    return {
        "ok": False,
        "error": proc.stderr.strip() or proc.stdout.strip() or "bugreport failed",
        "return_code": proc.returncode,
    }



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Universal Android / ADB Diagnostic Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="Check ADB and Fastboot availability")
    doctor.add_argument("--serial")
    doctor.add_argument("--json", action="store_true")

    devices = subparsers.add_parser("devices", help="List connected devices")
    devices.add_argument("--detailed", action="store_true", help="Include connection state and model metadata")
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

    bloatware = subparsers.add_parser("bloatware", help="Detect curated OEM safe-removal bloatware candidates")
    bloatware.add_argument("--serial")
    bloatware.add_argument("--by-category", action="store_true", help="Group candidates by OEM category")
    bloatware.add_argument("--json", action="store_true")

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
    restore.add_argument("--user", type=int, default=0)
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

    export = subparsers.add_parser("export", help="Export a full device diagnostic snapshot to JSON, HTML, or CSV")
    export.add_argument("--serial")
    export.add_argument("--format", choices=["json", "html", "csv"], default="json")
    export.add_argument("--output", required=True, help="Output file path")

    desktop = subparsers.add_parser("desktop", help="Launch the desktop diagnostic GUI")
    desktop.add_argument("--json", action="store_true")

    version_p = subparsers.add_parser("version", help="Show toolkit version")
    version_p.add_argument("--json", action="store_true")

    props = subparsers.add_parser("props", help="Dump key system properties")
    props.add_argument("--serial")
    props.add_argument("--json", action="store_true")

    cpu = subparsers.add_parser("cpu", help="CPU online cores, load average and thermal zones")
    cpu.add_argument("--serial")
    cpu.add_argument("--json", action="store_true")

    network = subparsers.add_parser("network", help="Network / Wi-Fi / IP summary")
    network.add_argument("--serial")
    network.add_argument("--json", action="store_true")

    screenshot = subparsers.add_parser("screenshot", help="Capture a PNG screenshot from the device")
    screenshot.add_argument("--serial")
    screenshot.add_argument("--output", "-o", default="screenshot.png", help="Output PNG path")
    screenshot.add_argument("--json", action="store_true")

    install = subparsers.add_parser("install", help="Install an APK on the device")
    install.add_argument("apk")
    install.add_argument("--serial")
    install.add_argument("--no-replace", action="store_true", help="Do not pass -r (replace)")
    install.add_argument("--json", action="store_true")

    clear_cmd = subparsers.add_parser("clear", help="Force-stop and clear cache for a package (safe)")
    clear_cmd.add_argument("package")
    clear_cmd.add_argument("--serial")
    clear_cmd.add_argument("--no-force-stop", action="store_true")
    clear_cmd.add_argument("--no-cache", action="store_true")
    clear_cmd.add_argument("--json", action="store_true")

    reboot_cmd = subparsers.add_parser("reboot", help="Reboot device (system|recovery|bootloader)")
    reboot_cmd.add_argument("--serial")
    reboot_cmd.add_argument("--mode", choices=["system", "recovery", "bootloader", "fastboot"], default="system")
    reboot_cmd.add_argument("--json", action="store_true")

    tcpip = subparsers.add_parser("tcpip", help="Enable ADB over TCP/IP (USB device required)")
    tcpip.add_argument("--serial")
    tcpip.add_argument("--port", type=int, default=5555)
    tcpip.add_argument("--json", action="store_true")

    connect = subparsers.add_parser("connect", help="Connect to a wireless ADB device (host[:port])")
    connect.add_argument("host")
    connect.add_argument("--port", type=int, default=5555)
    connect.add_argument("--json", action="store_true")

    disconnect = subparsers.add_parser("disconnect", help="Disconnect wireless ADB device(s)")
    disconnect.add_argument("host", nargs="?", default=None)
    disconnect.add_argument("--json", action="store_true")

    pkginfo = subparsers.add_parser("package-info", help="Show version, path and state for a package")
    pkginfo.add_argument("package")
    pkginfo.add_argument("--serial")
    pkginfo.add_argument("--json", action="store_true")

    bugreport = subparsers.add_parser("bugreport", help="Capture a full Android bugreport zip")
    bugreport.add_argument("--serial")
    bugreport.add_argument("--output", "-o", default="bugreport.zip")
    bugreport.add_argument("--json", action="store_true")

    approvals = subparsers.add_parser("approvals", help="List or execute staged safety approvals")
    approvals.add_argument("--list", action="store_true", help="List approved packages")
    approvals.add_argument("--execute", action="store_true", help="Execute disable for approved packages")
    approvals.add_argument("--clear", action="store_true", help="Clear approval manifest")
    approvals.add_argument("--serial")
    approvals.add_argument("--dry-run", action="store_true")
    approvals.add_argument("--json", action="store_true")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "doctor":
        report = run_doctor(args.serial, json_output=args.json)
        if not args.json:
            print(f"ADB available: {report['adb_available']}")
            print(f"Fastboot available: {report['fastboot_available']}")
            print(f"Devices: {', '.join(report['connected_devices']) if report['connected_devices'] else 'none'}")
        return 0

    if args.command == "devices":
        if args.detailed:
            detailed = get_connected_devices_detailed()
            payload: Dict[str, Any] = {"devices": detailed}
            if args.json:
                print(json.dumps(payload, indent=2))
            elif not detailed:
                print("No connected devices detected.")
            else:
                for item in detailed:
                    print(f"{item['serial']}\t{item['state']}\t{item.get('model', '')}".rstrip())
            return 0

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
        serial = resolve_serial(args.serial)
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
        serial = resolve_serial(args.serial)
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
        serial = resolve_serial(args.serial)
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

    if args.command == "bloatware":
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        if args.by_category:
            grouped = categorize_bloatware_candidates(serial=serial)
            payload = {"serial": serial, "categories": grouped}
            if args.json:
                print(json.dumps(payload, indent=2))
            elif not grouped:
                print("No safe-removal bloatware candidates detected.")
            else:
                for category, pkgs in grouped.items():
                    print(f"[{category}]")
                    for pkg in pkgs:
                        print(f"  - {pkg}")
        else:
            candidates = safe_removal_candidates(serial=serial)
            payload = {"serial": serial, "candidates": candidates}
            if args.json:
                print(json.dumps(payload, indent=2))
            elif not candidates:
                print("No safe-removal bloatware candidates detected.")
            else:
                for pkg in candidates:
                    print(pkg)
        return 0

    if args.command == "remove":
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        try:
            command = build_package_command(serial, args.package, remove=args.remove, user=args.user)
        except ValueError as exc:
            if args.json:
                print(json.dumps({"serial": serial, "error": str(exc)}, indent=2))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return 2

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
            print(
                json.dumps(
                    {
                        "serial": serial,
                        "return_code": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                    indent=2,
                )
            )
        else:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
        return result.returncode

    if args.command == "restore":
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        try:
            result = restore_package(serial, args.package, user=args.user)
        except ValueError as exc:
            if args.json:
                print(json.dumps({"serial": serial, "error": str(exc)}, indent=2))
            else:
                print(f"Error: {exc}", file=sys.stderr)
            return 2
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
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        lines = read_logcat(serial, limit=args.limit)
        filtered = filter_logcat_output(
            lines,
            pattern=args.pattern,
            tag=args.tag,
            priority=args.priority,
            pid=args.pid,
        )
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
            print(f"Memory: {payload.get('memory', {})}")
            print(f"Safe removal candidates: {payload.get('safe_bloatware_candidates', [])}")
        return 0

    if args.command == "export":
        from .reports import build_report_snapshot, export_report_csv, export_report_html, export_report_json

        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.", file=sys.stderr)
            return 1
        snapshot = build_report_snapshot(serial)
        if args.format == "json":
            out = export_report_json(args.output, snapshot)
        elif args.format == "html":
            out = export_report_html(args.output, snapshot)
        else:
            out = export_report_csv(args.output, snapshot)
        print(f"Exported {args.format.upper()} report to {out}")
        return 0

    if args.command == "desktop":
        from .gui import main as gui_main

        return gui_main()

    if args.command == "version":
        from . import __version__
        payload = {"version": __version__, "name": "universal-android-adb-toolkit"}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(f"universal-android-adb-toolkit {__version__}")
        return 0

    if args.command == "props":
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        keys = [
            "ro.product.brand", "ro.product.model", "ro.product.device",
            "ro.product.manufacturer", "ro.build.id", "ro.build.version.release",
            "ro.build.version.sdk", "ro.build.version.security_patch",
            "ro.build.fingerprint", "ro.hardware", "ro.product.board",
            "ro.serialno", "ro.bootloader", "gsm.version.baseband",
            "ro.build.display.id", "ro.build.version.incremental",
        ]
        props = {k: get_android_property(serial, k) or "" for k in keys}
        payload = {"serial": serial, "properties": props}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for k, v in props.items():
                print(f"{k}={v}")
        return 0

    if args.command == "cpu":
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        data = read_cpu_thermal(serial)
        payload = {"serial": serial, "cpu_thermal": data}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            print(json.dumps(data, indent=2))
        return 0

    if args.command == "network":
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.")
            return 1
        data = read_network_info(serial)
        payload = {"serial": serial, "network": data}
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for k, v in data.items():
                print(f"=== {k} ===")
                print(v)
                print()
        return 0

    if args.command == "screenshot":
        result = take_screenshot(args.serial, args.output)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("ok"):
                print(f"Screenshot saved to {result['path']} ({result.get('bytes', 0)} bytes)")
            else:
                print(f"Error: {result.get('error')}", file=sys.stderr)
                return 1
        return 0 if result.get("ok") else 1

    if args.command == "install":
        result = install_apk(args.serial, args.apk, replace=not args.no_replace)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("ok"):
                print(result.get("stdout") or "Success")
            else:
                print(result.get("stderr") or result.get("error") or "Install failed", file=sys.stderr)
                return 1
        return 0 if result.get("ok") else 1

    if args.command == "clear":
        result = clear_package(
            args.serial,
            args.package,
            clear_cache=not args.no_cache,
            force_stop=not args.no_force_stop,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("ok"):
                print(f"Cleared/stopped {result.get('package')}")
                for a in result.get("actions", []):
                    print(f"  {a.get('action')}: rc={a.get('return_code')}")
            else:
                print(f"Error: {result.get('error')}", file=sys.stderr)
                return 1
        return 0 if result.get("ok") else 1

    if args.command == "reboot":
        result = reboot_device(args.serial, mode=args.mode)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("ok"):
                print(f"Reboot ({result.get('mode')}) issued")
            else:
                print(f"Error: {result.get('error') or result.get('stderr')}", file=sys.stderr)
                return 1
        return 0 if result.get("ok") else 1

    if args.command == "tcpip":
        result = adb_tcpip(args.serial, port=args.port)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("ok"):
                print(f"ADB tcpip mode enabled on port {result.get('port')}")
                print("You can now unplug USB and use: android-adb-toolkit connect <device-ip>")
            else:
                print(result.get("stderr") or result.get("error") or "tcpip failed", file=sys.stderr)
                return 1
        return 0 if result.get("ok") else 1

    if args.command == "connect":
        result = adb_connect(args.host, port=args.port)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result.get("stdout") or result.get("stderr") or ("OK" if result.get("ok") else "Failed"))
        return 0 if result.get("ok") else 1

    if args.command == "disconnect":
        result = adb_disconnect(args.host)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result.get("stdout") or ("Disconnected" if result.get("ok") else result.get("stderr")))
        return 0 if result.get("ok") else 1

    if args.command == "package-info":
        result = package_info(args.serial, args.package)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if not result.get("ok"):
                print(f"Error: {result.get('error')}", file=sys.stderr)
                return 1
            for k, v in result.items():
                if k != "ok":
                    print(f"{k}: {v}")
        return 0 if result.get("ok") else 1

    if args.command == "bugreport":
        result = collect_bugreport(args.serial, args.output)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("ok"):
                print(f"Bugreport saved to {result['path']} ({result.get('bytes', 0)} bytes)")
            else:
                print(f"Error: {result.get('error')}", file=sys.stderr)
                return 1
        return 0 if result.get("ok") else 1

    if args.command == "approvals":
        from .safety import (
            load_approvals,
            clear_approvals,
            execute_approved_packages_detailed,
            approval_manifest_path,
        )
        if args.clear:
            clear_approvals()
            payload = {"cleared": True, "path": approval_manifest_path()}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                print("Approval manifest cleared.")
            return 0
        approved = load_approvals()
        if args.list or not (args.execute):
            payload = {"path": approval_manifest_path(), "packages": approved}
            if args.json:
                print(json.dumps(payload, indent=2))
            else:
                if not approved:
                    print("No packages in approval manifest.")
                else:
                    for pkg in approved:
                        print(pkg)
            return 0
        # execute
        serial = resolve_serial(args.serial)
        if not serial:
            print("No connected device available.", file=sys.stderr)
            return 1
        results = execute_approved_packages_detailed(
            serial, approved=approved, dry_run=args.dry_run
        )
        if args.json:
            print(json.dumps({"serial": serial, "results": results}, indent=2))
        else:
            for r in results:
                print(f"{r.get('package')}: {r.get('status')}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
