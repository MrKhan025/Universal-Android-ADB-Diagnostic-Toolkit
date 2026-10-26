# Universal Android / ADB Diagnostic Toolkit

A lightweight yet comprehensive Android device diagnostics and safe debloating toolkit built in Python. It integrates CLI tooling, a Tkinter desktop interface, OEM-safe package detection with critical system package guards, battery diagnostics, storage and memory snapshotting, live logcat streaming, and structured report exports (JSON, HTML, CSV).

## Features

- Cross-platform ADB and Fastboot installation checks (`shutil.which`) with timeout and missing-binary resilience
- Connected-device detection, detailed connection metadata (`--detailed`), and automatic online-device selection
- Android version, model, build, and security patch reporting
- Battery health, Celsius temperature conversion (`temperature_c`), voltage, charge percentage, and status labels
- Storage (`df -h` mount table parsing) and RAM/Swap (`/proc/meminfo`) snapshot reporting
- Logcat snapshot filtering by priority, tag, substring pattern, and PID, plus bounded live streaming
- Third-party package discovery and full app inventory
- Curated OEM-safe bloatware detection list with strict protection for core Android/Play Services packages (`PROTECTED_PACKAGES`)
- Safe `pm disable-user --user 0` disable workflow by default with package-name validation
- Optional package removal (`--remove`) and restoration (`restore`)
- JSON, XSS-safe styled HTML, and CSV diagnostic report exports via CLI (`export`) and GUI
- Desktop Tkinter wrapper with two-pane Safety staging/approval queue and live logcat stream
- GitHub Actions CI testing on Python 3.10 through 3.13
- Windows packaging helper for PyInstaller + Inno Setup build automation

## Project layout

- `src/universal_android_adb_toolkit/cli.py` – command-line interface and core ADB/Fastboot diagnostics
- `src/universal_android_adb_toolkit/gui.py` – Tkinter desktop dashboard
- `src/universal_android_adb_toolkit/bloatware.py` – curated OEM safe-debloat catalog and protected-package guards
- `src/universal_android_adb_toolkit/logstream.py` – background threaded live `adb logcat` streamer
- `src/universal_android_adb_toolkit/reports.py` – JSON, styled HTML, and CSV report builders
- `src/universal_android_adb_toolkit/safety.py` – staging manifest and safe package removal workflow
- `scripts/build_windows_installer.py` – Windows PyInstaller + Inno Setup build automation
- `installer/installer.iss` – Inno Setup installer configuration
- `tests/test_cli.py` – automated unit and regression test suite
- `.github/workflows/ci.yml` – GitHub Actions CI pipeline
- `pyproject.toml` – Python packaging metadata

## Quick start

### Install locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
```

### CLI usage

```bash
android-adb-toolkit doctor
android-adb-toolkit devices --detailed
android-adb-toolkit report --serial <SERIAL>
android-adb-toolkit battery --serial <SERIAL>
android-adb-toolkit logcat --serial <SERIAL> --tag ActivityManager --priority W --pattern crash
android-adb-toolkit packages --serial <SERIAL> --third-party
android-adb-toolkit bloatware --serial <SERIAL> --by-category
android-adb-toolkit remove com.example.app --serial <SERIAL> --dry-run
android-adb-toolkit restore com.example.app --serial <SERIAL>
android-adb-toolkit export --serial <SERIAL> --format html --output report.html
android-adb-toolkit dashboard --serial <SERIAL>
android-adb-toolkit desktop
```

### Desktop UI

Launch the desktop wrapper:

```bash
android-adb-desktop
```

This opens a Tkinter-based dashboard for:
- Device selection and status refresh
- Battery, storage, and memory health summary
- Searchable package inventory and third-party filtering
- One-click OEM-safe bloatware candidate loading
- Two-pane Safety staging and approval queue with optional on-device `pm disable-user` execution
- Live logcat streaming and snapshot filtering
- JSON, HTML, and CSV diagnostic report export

## Safety guidance

- Default removal uses `pm disable-user --user 0` for non-destructive disabling.
- Core Android and Google Play system packages (`com.android.vending`, `com.google.android.gms`, `com.android.systemui`, `com.android.settings`, `com.huawei.hwid`, etc.) are strictly blocked from removal by `PROTECTED_PACKAGES`.
- Use `--dry-run` before executing any package changes.
- Use `--remove` only when you understand the consequences of uninstalling for the current user.

## Running tests

```bash
pytest -v
# or using standard library unittest:
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Windows installer packaging

To build a Windows executable and Inno Setup installer:

```bash
python scripts/build_windows_installer.py
```

This script builds `dist/UniversalAndroidADBToolkit.exe` via PyInstaller and compiles `installer/installer.iss` if Inno Setup (`iscc`) is installed.

## License

MIT
