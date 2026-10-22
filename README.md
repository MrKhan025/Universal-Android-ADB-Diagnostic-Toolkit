# Universal Android / ADB Diagnostic Toolkit

A lightweight Python command-line toolkit for Android device diagnostics, ADB/Fastboot health checks, log collection, and safe package debloating.

## Features

- ADB and Fastboot environment validation
- Connected device detection and serial selection
- Android build, model, SDK, and security-patch reporting
- Battery health, voltage, temperature, and level checks
- Logcat filtering by keyword, tag, priority, and PID
- Discovered app package listings, including third-party packages
- Safe debloating with `pm disable-user --user 0` by default
- Optional package removal and restore commands
- JSON output for automation and scripting
- CI coverage on Python 3.10–3.13

## Project layout

- `src/universal_android_adb_toolkit/cli.py` – main CLI implementation
- `tests/test_cli.py` – automated tests
- `.github/workflows/ci.yml` – GitHub Actions CI
- `pyproject.toml` – packaging and script metadata

## Quick start

### 1) Install locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

### 2) Verify ADB/Fastboot

```bash
android-adb-toolkit doctor
```

### 3) View connected devices

```bash
android-adb-toolkit devices
```

### 4) Collect a device report

```bash
android-adb-toolkit report --serial <SERIAL>
```

### 5) Read battery health

```bash
android-adb-toolkit battery --serial <SERIAL>
```

### 6) Filter logcat output

```bash
android-adb-toolkit logcat --serial <SERIAL> --tag ActivityManager --priority W --pattern crash
```

### 7) List third-party applications

```bash
android-adb-toolkit packages --serial <SERIAL> --third-party
```

### 8) Safely disable a package

```bash
android-adb-toolkit remove com.example.app --serial <SERIAL> --dry-run
android-adb-toolkit remove com.example.app --serial <SERIAL>
```

### 9) Restore a disabled package

```bash
android-adb-toolkit restore com.example.app --serial <SERIAL>
```

## Safety guidance

- The default removal mode is `disable-user` for user 0, which is safer than uninstalling system apps.
- Use `--dry-run` before applying changes.
- Use `--remove` only when you are sure the application should be removed.
- Always confirm package names and device selection before running removal commands.

## JSON output example

```bash
android-adb-toolkit report --serial <SERIAL> --json
```

## License

This project is licensed under the MIT License.
