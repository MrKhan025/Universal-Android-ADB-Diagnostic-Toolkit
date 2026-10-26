from __future__ import annotations

import queue
import subprocess
import threading
from typing import Optional


class LogStreamer:
    def __init__(
        self,
        serial: str,
        filter_text: str = "",
        max_queue_size: int = 2000,
    ) -> None:
        self.serial = serial
        self.filter_text = filter_text.strip()
        self.queue: queue.Queue[str] = queue.Queue(maxsize=max_queue_size)
        self.process: Optional[subprocess.Popen[str]] = None
        self.reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _enqueue(self, message: str) -> None:
        try:
            self.queue.put_nowait(message)
        except queue.Full:
            try:
                self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(message)
            except queue.Full:
                pass

    def start(self) -> None:
        if self.process is not None:
            return
        self._stop_event.clear()
        try:
            self.process = subprocess.Popen(
                ["adb", "-s", self.serial, "logcat", "-v", "brief"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            self._enqueue("Error: 'adb' binary was not found in PATH.")
            self.process = None
            return
        except OSError as exc:
            self._enqueue(f"Error starting logcat stream: {exc}")
            self.process = None
            return

        proc = self.process

        def _reader() -> None:
            if proc.stdout is None:
                return
            try:
                for line in proc.stdout:
                    if self._stop_event.is_set():
                        break
                    text = line.rstrip()
                    if not text:
                        continue
                    if self.filter_text and self.filter_text.lower() not in text.lower():
                        continue
                    self._enqueue(text)
            except ValueError:
                # Stream closed during shutdown
                pass
            finally:
                try:
                    proc.stdout.close()
                except Exception:
                    pass

        self.reader_thread = threading.Thread(target=_reader, daemon=True)
        self.reader_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        proc = self.process
        self.process = None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except OSError:
                    pass
            except OSError:
                pass
        if self.reader_thread and self.reader_thread.is_alive():
            self.reader_thread.join(timeout=1.0)
        self.reader_thread = None
