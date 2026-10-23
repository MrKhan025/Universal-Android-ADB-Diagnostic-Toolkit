from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .cli import device_report, list_packages, read_battery


def build_report_snapshot(serial: str) -> Dict[str, Any]:
    report = device_report(serial)
    battery = read_battery(serial)
    packages = list_packages(serial, third_party_only=False)
    return {
        "serial": serial,
        "device": report,
        "battery": battery,
        "packages": packages,
    }


def export_report_json(path: str, payload: Dict[str, Any]) -> str:
    output_path = Path(path)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(output_path)


def export_report_html(path: str, payload: Dict[str, Any]) -> str:
    html = """<!DOCTYPE html>
<html>
<head>
  <meta charset=\"utf-8\">
  <title>Android Diagnostic Report</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    pre { white-space: pre-wrap; word-wrap: break-word; }
  </style>
</head>
<body>
  <h1>Android Diagnostic Report</h1>
  <pre>{}</pre>
</body>
</html>
""".format(json.dumps(payload, indent=2))
    output_path = Path(path)
    output_path.write_text(html, encoding="utf-8")
    return str(output_path)


def export_report_csv(path: str, payload: Dict[str, Any]) -> str:
    rows = payload.get("packages", [])
    output_path = Path(path)
    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["package"])
        for item in rows:
            writer.writerow([item])
    return str(output_path)
