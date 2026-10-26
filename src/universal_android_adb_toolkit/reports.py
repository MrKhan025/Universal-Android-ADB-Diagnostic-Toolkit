from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .cli import device_report, list_packages


def build_report_snapshot(serial: str) -> Dict[str, Any]:
    """Collect a comprehensive diagnostic snapshot for a connected device."""
    report = device_report(serial)
    battery = report.get("battery", {})
    packages = list_packages(serial, third_party_only=False)
    return {
        "serial": serial,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "device": report,
        "battery": battery,
        "packages": packages,
    }


def export_report_json(path: str | Path, payload: Dict[str, Any]) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(output_path)


def export_report_html(path: str | Path, payload: Dict[str, Any]) -> str:
    """Export a styled, XSS-safe HTML diagnostic report."""
    device = payload.get("device", {}) if isinstance(payload.get("device"), dict) else {}
    battery = payload.get("battery", {}) if isinstance(payload.get("battery"), dict) else {}
    packages = payload.get("packages", []) if isinstance(payload.get("packages"), list) else []
    candidates = device.get("safe_bloatware_candidates", []) if isinstance(device, dict) else []

    serial_str = html.escape(str(payload.get("serial") or device.get("serial") or "unknown"))
    model_str = html.escape(str(device.get("model", "unknown")))
    brand_str = html.escape(str(device.get("brand", "unknown")))
    android_str = html.escape(str(device.get("android_version", "unknown")))
    patch_str = html.escape(str(device.get("security_patch", "unknown")))
    batt_pct = html.escape(str(battery.get("percentage", battery.get("level", "N/A"))))
    batt_temp = html.escape(str(battery.get("temperature_c", battery.get("temperature", "N/A"))))
    escaped_json = html.escape(json.dumps(payload, indent=2))

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Android Diagnostic Report - {serial_str}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 24px; color: #1e293b; background: #f8fafc; }}
    h1, h2 {{ color: #0f172a; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-bottom: 24px; }}
    .card {{ background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; box-shadow: 0 1px 2px rgba(0,0,0,0.04); }}
    .label {{ font-size: 12px; text-transform: uppercase; color: #64748b; margin-bottom: 4px; }}
    .value {{ font-size: 18px; font-weight: 600; color: #0f172a; }}
    pre {{ background: #0f172a; color: #f8fafc; padding: 16px; border-radius: 8px; white-space: pre-wrap; word-wrap: break-word; overflow-x: auto; }}
  </style>
</head>
<body>
  <h1>Android Diagnostic Report</h1>
  <div class="grid">
    <div class="card"><div class="label">Serial</div><div class="value">{serial_str}</div></div>
    <div class="card"><div class="label">Device</div><div class="value">{brand_str} {model_str}</div></div>
    <div class="card"><div class="label">Android / Patch</div><div class="value">Android {android_str} ({patch_str})</div></div>
    <div class="card"><div class="label">Battery</div><div class="value">{batt_pct}% ({batt_temp} &deg;C)</div></div>
    <div class="card"><div class="label">Installed Packages</div><div class="value">{len(packages)}</div></div>
    <div class="card"><div class="label">Bloatware Candidates</div><div class="value">{len(candidates)}</div></div>
  </div>
  <h2>Raw Diagnostic Payload</h2>
  <pre>{escaped_json}</pre>
</body>
</html>
"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(doc, encoding="utf-8")
    return str(output_path)


def export_report_csv(path: str | Path, payload: Dict[str, Any]) -> str:
    rows = payload.get("packages", [])
    device = payload.get("device", {}) if isinstance(payload.get("device"), dict) else {}
    bloatware_set = set(device.get("safe_bloatware_candidates", [])) if isinstance(device, dict) else set()
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["package", "is_bloatware_candidate"])
        for item in rows:
            writer.writerow([item, "true" if item in bloatware_set else "false"])
    return str(output_path)
