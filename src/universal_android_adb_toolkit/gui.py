from __future__ import annotations

import json
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from .bloatware import safe_removal_candidates
from .cli import get_connected_devices, list_packages, read_battery, summarize_dashboard
from .logstream import LogStreamer
from .reports import build_report_snapshot, export_report_html, export_report_json
from .safety import approval_manifest_path, approve_package, load_approvals, remove_approved_packages


class AndroidDiagnosticsApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Universal Android / ADB Diagnostic Toolkit")
        self.root.geometry("1100x760")
        self.root.minsize(980, 680)

        self.serial_var = tk.StringVar()
        self.query_var = tk.StringVar(value="")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.log_streamer: Optional[LogStreamer] = None

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.overview_frame = ttk.Frame(self.notebook)
        self.logs_frame = ttk.Frame(self.notebook)
        self.packages_frame = ttk.Frame(self.notebook)
        self.safety_frame = ttk.Frame(self.notebook)
        self.reports_frame = ttk.Frame(self.notebook)

        self.notebook.add(self.overview_frame, text="Overview")
        self.notebook.add(self.logs_frame, text="Logs")
        self.notebook.add(self.packages_frame, text="Packages")
        self.notebook.add(self.safety_frame, text="Safety")
        self.notebook.add(self.reports_frame, text="Reports")

        self._build_overview()
        self._build_logs()
        self._build_packages()
        self._build_safety()
        self._build_reports()

        self.refresh_devices()
        self.root.after(200, self._process_log_queue)

    def _build_overview(self) -> None:
        toolbar = ttk.Frame(self.overview_frame)
        toolbar.pack(fill="x", padx=12, pady=(12, 8))

        ttk.Label(toolbar, text="Serial:").pack(side="left")
        self.device_combo = ttk.Combobox(toolbar, textvariable=self.serial_var, state="readonly", width=32)
        self.device_combo.pack(side="left", padx=(6, 10))

        ttk.Button(toolbar, text="Refresh", command=self.refresh_devices).pack(side="left")
        ttk.Button(toolbar, text="Dashboard", command=self.show_dashboard).pack(side="left", padx=(8, 0))
        ttk.Button(toolbar, text="Battery", command=self.show_battery).pack(side="left", padx=(8, 0))

        self.overview_text = tk.Text(self.overview_frame, wrap="word", state="disabled")
        self.overview_text.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def _build_logs(self) -> None:
        controls = ttk.Frame(self.logs_frame)
        controls.pack(fill="x", padx=10, pady=10)

        ttk.Label(controls, text="Filter:").pack(side="left")
        self.filter_entry = ttk.Entry(controls, textvariable=self.query_var, width=30)
        self.filter_entry.pack(side="left", padx=(4, 10))

        ttk.Button(controls, text="Live Stream", command=self.start_live_log_stream).pack(side="left")
        ttk.Button(controls, text="Stop Stream", command=self.stop_live_log_stream).pack(side="left", padx=(6, 0))
        ttk.Button(controls, text="Snapshot", command=self.show_log_snapshot).pack(side="left", padx=(6, 0))

        self.logs_text = tk.Text(self.logs_frame, wrap="word", state="disabled")
        self.logs_text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def _build_packages(self) -> None:
        self.pkg_listbox = tk.Listbox(self.packages_frame, width=120, height=25)
        self.pkg_listbox.pack(fill="both", expand=True, padx=10, pady=10)

        controls = ttk.Frame(self.packages_frame)
        controls.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(controls, text="Load Packages", command=self.load_packages).pack(side="left")
        ttk.Button(controls, text="Add to Safety Queue", command=self.add_selected_to_safety_queue).pack(side="left", padx=(8, 0))

    def _build_safety(self) -> None:
        self.safety_listbox = tk.Listbox(self.safety_frame, width=120, height=20)
        self.safety_listbox.pack(fill="both", expand=True, padx=10, pady=10)

        controls = ttk.Frame(self.safety_frame)
        controls.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(controls, text="Approve Selected", command=self.approve_selected).pack(side="left")
        ttk.Button(controls, text="Remove Approved", command=self.remove_approved).pack(side="left", padx=(8, 0))

    def _build_reports(self) -> None:
        self.report_text = tk.Text(self.reports_frame, wrap="word", state="disabled")
        self.report_text.pack(fill="both", expand=True, padx=10, pady=10)

        controls = ttk.Frame(self.reports_frame)
        controls.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(controls, text="Generate Snapshot", command=self.generate_report_snapshot).pack(side="left")
        ttk.Button(controls, text="Export JSON", command=self.export_json).pack(side="left", padx=(8, 0))
        ttk.Button(controls, text="Export HTML", command=self.export_html).pack(side="left", padx=(8, 0))

    def _process_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                self.log_message(item)
        except queue.Empty:
            pass
        self.root.after(200, self._process_log_queue)

    def log_message(self, message: str) -> None:
        if not message or not message.strip():
            return
        self.logs_text.configure(state="normal")
        self.logs_text.insert("end", message.strip() + "\n")
        self.logs_text.see("end")
        self.logs_text.configure(state="disabled")

    def refresh_devices(self) -> None:
        devices = get_connected_devices()
        self.device_combo["values"] = devices if devices else ["No device found"]
        if devices:
            self.serial_var.set(devices[0])
        else:
            self.serial_var.set("No device found")
        self.log_message("Connected devices: " + (", ".join(devices) if devices else "none"))

    def get_selected_serial(self) -> Optional[str]:
        serial = self.serial_var.get().strip()
        return serial if serial and serial != "No device found" else None

    def show_dashboard(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            messagebox.showwarning("No device", "No device is selected.")
            return
        payload = summarize_dashboard(serial)
        self.overview_text.configure(state="normal")
        self.overview_text.delete("1.0", "end")
        self.overview_text.insert("end", json.dumps(payload, indent=2))
        self.overview_text.configure(state="disabled")

    def show_battery(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            return
        payload = read_battery(serial)
        self.overview_text.configure(state="normal")
        self.overview_text.delete("1.0", "end")
        self.overview_text.insert("end", json.dumps(payload, indent=2))
        self.overview_text.configure(state="disabled")

    def show_log_snapshot(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            return
        from .cli import read_logcat

        filter_text = self.query_var.get().strip()
        lines = read_logcat(serial, limit=200)
        filtered = []
        for line in lines:
            if filter_text and filter_text.lower() not in line.lower():
                continue
            filtered.append(line)
        self.logs_text.configure(state="normal")
        self.logs_text.delete("1.0", "end")
        for line in filtered:
            self.logs_text.insert("end", line + "\n")
        self.logs_text.configure(state="disabled")

    def load_packages(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            return
        packages = list_packages(serial, third_party_only=False)
        self.pkg_listbox.delete(0, "end")
        for pkg in packages:
            self.pkg_listbox.insert("end", pkg)

    def add_selected_to_safety_queue(self) -> None:
        if not self.pkg_listbox.curselection():
            return
        selected = self.pkg_listbox.get(self.pkg_listbox.curselection()[0])
        items = self.safety_listbox.get(0, "end")
        if selected not in items:
            self.safety_listbox.insert("end", selected)

    def approve_selected(self) -> None:
        selection = self.safety_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        package = self.safety_listbox.get(index)
        self.safety_listbox.delete(index)
        approve_package(package)
        self.log_message(f"Approved for removal: {package}")

    def remove_approved(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            messagebox.showwarning("No device", "A device must be selected before removing packages.")
            return
        approved = load_approvals()
        if not approved:
            self.log_message("No approved applications to remove.")
            return
        remove_approved_packages(serial, approved)
        self.log_message(f"Removal workflow executed for {len(approved)} approved package(s).")
        self.safety_listbox.delete(0, "end")

    def generate_report_snapshot(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            return
        payload = build_report_snapshot(serial)
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("end", json.dumps(payload, indent=2))
        self.report_text.configure(state="disabled")

    def export_json(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            return
        payload = build_report_snapshot(serial)
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON File", "*.json")])
        if not path:
            return
        export_report_json(path, payload)
        self.log_message(f"Report exported to {path}")

    def export_html(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            return
        payload = build_report_snapshot(serial)
        path = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML File", "*.html")])
        if not path:
            return
        export_report_html(path, payload)
        self.log_message(f"HTML report exported to {path}")

    def start_live_log_stream(self) -> None:
        serial = self.get_selected_serial()
        if not serial:
            messagebox.showwarning("No device", "A device must be selected before starting live logs.")
            return
        self.stop_live_log_stream()
        self.log_streamer = LogStreamer(serial, self.query_var.get().strip())
        self.log_streamer.start()
        self.root.after(200, self._consume_log_stream)
        self.log_message(f"Live log stream started for {serial}")

    def stop_live_log_stream(self) -> None:
        if self.log_streamer:
            self.log_streamer.stop()
            self.log_streamer = None
            self.log_message("Live log stream stopped.")

    def _consume_log_stream(self) -> None:
        if self.log_streamer is None:
            return
        while not self.log_streamer.queue.empty():
            line = self.log_streamer.queue.get()
            self.log_message(line)
        self.root.after(200, self._consume_log_stream)


def main() -> int:
    root = tk.Tk()
    app = AndroidDiagnosticsApp(root)
    root.mainloop()
    return 0
