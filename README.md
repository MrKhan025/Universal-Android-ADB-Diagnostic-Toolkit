# Universal Android / ADB Diagnostic Toolkit

A lightweight yet advanced Android device diagnostics and safe debloating toolkit built in Python. It integrates CLI tooling, a lightweight desktop wrapper, OEM-safe package detection, battery diagnostics, storage snapshotting, and secure package removal workflows.

## Features

- ADB and Fastboot installation checks
- Connected-device detection and serial selection
- Android version, model, build, and security patch reporting
- Battery health, temperature, voltage, and level analysis
- Storage and memory snapshot reporting
- Logcat filtering by priority, tag, text, and PID
- Third-party package discovery and app inventory
- Curated OEM-safe bloatware detection list
- Safe `pm disable-user --user 0` disable workflow by default
- Optional package removal and restoration
- JSON output for automation and CI
- Desktop Tkinter wrapper for quick diagnostics
- GitHub Actions testing on Python 3.10 through 3.13
- Windows packaging helper for PyInstaller build automation

## Project layout

- `src/universal_android_adb_toolkit/cli.py` – command-line toolkit
- `src/universal_android_adb_toolkit/gui.py` – lightweight desktop interface
- `src/universal_android_adb_toolkit/bloatware.py` – curated OEM safe-debloat package list
- `scripts/build_windows_installer.py` – Windows build automation
- `tests/test_cli.py` – automated regression tests
- `.github/workflows/ci.yml` – CI pipeline
- `pyproject.toml` – Python packaging metadata

## Quick start

### Install locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### CLI usage

```bash
android-adb-toolkit doctor
android-adb-toolkit devices
android-adb-toolkit report --serial <SERIAL>
android-adb-toolkit battery --serial <SERIAL>
android-adb-toolkit logcat --serial <SERIAL> --tag ActivityManager --priority W --pattern crash
android-adb-toolkit packages --serial <SERIAL> --third-party
android-adb-toolkit remove com.example.app --serial <SERIAL> --dry-run
android-adb-toolkit dashboard --serial <SERIAL>
android-adb-toolkit desktop
```

### Desktop UI

Launch the lightweight desktop wrapper:

```bash
android-adb-desktop
```

This opens a Tkinter-based dashboard for:
- device selection
- battery health summary
- storage snapshot
- package inventory
- OEM-safe bloatware suggestions
- logcat output preview

## Safety guidance

- Default removal is `pm disable-user --user 0` for safety.
- Use `--dry-run` before any package changes.
- Use `--remove` only when you understand the consequences.
- Always validate package names before disabling system apps.
- Recommended to review OEM-curated suggestions before executing removal.

## Curated safe-removal candidates

The toolkit compares installed packages against a curated package list covering common OEM and carrier bloatware patterns such as:

- `com.android.chrome` (optional)
- `com.google.android.apps.messaging` (optional, if replacing app)
- `com.samsung.android.app.watchmanager` (device-specific)
- `com.huawei.android.hsf` (device-specific)
- `com.oneplus.mms`
- `com.miui.cleanmaster`
- carrier-specific diagnostic apps

These are suggestions only. Always review device-specific package names before removing anything.

## Windows installer packaging

To build a Windows executable using PyInstaller:

```bash
python scripts/build_windows_installer.py
```

This script creates a bundled executable in a `dist/` directory.

## License

MIT
