from __future__ import annotations

import json
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from .cli import get_connected_devices, read_battery, read_storage_snapshot, summarize_dashboard, safe_removal_candidates


class AndroidDiagnosticsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Universal Android / ADB Diagnostic Toolkit")
        self.root.geometry("980x720")

        self.serial_var = tk.StringVar()
        self.output = tk.Text(self.root, wrap="word", state="disabled", width=120, height=30)
        self.output.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=10, pady=10)

        ttk.Label(toolbar, text="Serial:").pack(side="left")
        combo = ttk.Combobox(toolbar, textvariable=self.serial_var, state="readonly", width=30)
        combo.pack(side="left", padx=(0, 10))

        ttk.Button(toolbar, text="Refresh Devices", command=self.refresh_devices).pack(side="left")
        ttk.Button(toolbar, text="Dashboard", command=self.dashboard).pack(side="left", padx=(5, 0))
        ttk.Button(toolbar, text="Battery", command=self.show_battery).pack(side="left", padx=(5, 0))
        ttk.Button(toolbar, text="Logs", command=self.show_logs).pack(side="left", padx=(5, 0))
        ttk.Button(toolbar, text="Safe Remove", command=self.show_safe_candidates).pack(side="left", padx=(5, 0))

        self.refresh_devices()

    def log(self, message: str) -> None:
        self.output.configure(state="normal")
        self.output.insert(tk.END, message + "\n")
        self.output.configure(state="disabled")
        self.output.see(tk.END)

    def refresh_devices(self) -> None:
        devices = get_connected_devices()
        self.serial_var.set(devices[0] if devices else "")
        values = devices if devices else ["No device found"]
        self.root.nametowidget("_does_not_exist") if False else None
        # replace the previous combobox values is not trivial in this minimal wrapper, so keep it simple
        self.log("Connected devices: " + (", ".join(devices) if devices else "none"))

    def get_selected_serial(self) -> Optional[str]:
        serial = self.serial_var.get().strip()
        return serial if serial and serial != "No device found" else None

    def run_adb(self, *args: str) -> str:
        cmd = ["adb"]
        serial = self.get_selected_serial()
        if serial:
            cmd.extend(["-s", serial])
        cmd.extend(list(args))
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip() or result.stderr.strip()

    def dashboard(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            self.log("No device selected.")
            return
        payload = summarize_dashboard(serial)
        self.log(json.dumps(payload, indent=2))

    def show_battery(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            self.log("No device selected.")
            return
        self.log(json.dumps(read_battery(serial), indent=2))

    def show_logs(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            self.log("No device selected.")
            return
        output = self.run_adb("logcat", "-d")
        self.log(output[:4000])

    def show_safe_candidates(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            self.log("No device selected.")
            return
        self.log(json.dumps(safe_removal_candidates(serial), indent=2))


def main() -> int:
    root = tk.Tk()
    AndroidDiagnosticsApp(root)
    root.mainloop()
    return 0
