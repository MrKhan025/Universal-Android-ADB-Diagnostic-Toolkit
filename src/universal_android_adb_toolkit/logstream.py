from __future__ import annotations

import queue
import subprocess
import threading
from typing import Optional


class LogStreamer:
    def __init__(self, serial: str, filter_text: str = "") -> None:
        self.serial = serial
        self.filter_text = filter_text.strip()
        self.queue: queue.Queue[str] = queue.Queue()
        self.process: Optional[subprocess.Popen[str]] = None
        self.reader_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.process is not None:
            return
        self.process = subprocess.Popen(
            ["adb", "-s", self.serial, "logcat", "-v", "brief"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        def _reader() -> None:
            if self.process is None or self.process.stdout is None:
                return
            for line in self.process.stdout:
                text = line.rstrip()
                if self.filter_text and self.filter_text.lower() not in text.lower():
                    continue
                self.queue.put(text)
            if self.process is not None:
                self.process.stdout.close()
                self.process.wait()

        self.reader_thread = threading.Thread(target=_reader, daemon=True)
        self.reader_thread.start()

    def stop(self) -> None:
        if self.process is not None:
            self.process.terminate()
            self.process = None
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1)
            self.reader_thread = None
