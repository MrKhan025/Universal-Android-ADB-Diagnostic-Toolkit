# 📱 Universal Android / ADB Diagnostic Toolkit







> **Diagnose, inspect, monitor, and safely debloat any Android device over ADB & Fastboot—from a scriptable CLI or a lightweight desktop dashboard.**

**Universal Android / ADB Diagnostic Toolkit** is a zero-bloat Python toolkit engineered for developers, QA engineers, repair technicians, and Android power users. It combines deep hardware/OS telemetry, real-time logcat filtering, multi-format diagnostic reporting, and a safety-first OEM debloating workflow that protects critical system components from accidental removal.

## ✨ Why Use This Toolkit?

| Pillar | What You Get |
| :--- | :--- |
| **🩺 Instant Device Health** | One-command hardware, OS, security patch, battery (`°C`, `mV`, health/charge states), storage mount (`df -h`), and RAM/Swap (`/proc/meminfo`) snapshots. |
| **🛡️ Guarded OEM Debloating** | Curated bloatware catalogs for **Google, Samsung, Xiaomi, Huawei, OnePlus, and Carrier** apps paired with a strict `PROTECTED_PACKAGES` blocklist and `pm disable-user --user 0` defaults. |
| **📡 Smart Logcat Engine** | Filter device logs by priority (`V`–`A`), tag, regex/substring pattern, and PID—or stream live logs in a bounded background ring buffer without freezing your UI. |
| **📊 Audit-Ready Reports** | Export complete device snapshots to **JSON** (for CI/automation), **styled XSS-safe HTML** (for sharing), or **CSV** (with per-package bloatware flags). |
| **🖥️ Dual Experience** | Use `android-adb-toolkit` in headless terminals/CI pipelines or launch `android-adb-desktop` for an interactive 5-tab Tkinter desktop dashboard. |

## 🚀 Quick Start

### 1. Prerequisites

Ensure Android Platform Tools (`adb` and `fastboot`) are installed and available in your system `PATH`, and enable **USB Debugging** inside your Android device's **Developer Options**.

### 2. Installation

```bash
# Clone or extract the repository
cd Universal-Android-ADB-Diagnostic-Toolkit-main

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows PowerShell / CMD

# Install the toolkit and development/test extras
pip install -U pip
pip install -e ".[dev]"
```

### 3. Verify Your Environment

```bash
# Check ADB/Fastboot availability and connected devices
android-adb-toolkit doctor

# Launch the interactive desktop GUI
android-adb-desktop
```

## ⌨️ CLI Command Reference

Every CLI subcommand supports `--json` for machine-readable output in CI/CD pipelines and automated scripts. When `--serial` is omitted, the toolkit automatically selects the first authorized online device.

| Subcommand | Key Flags | Description | Example Command |
| :--- | :--- | :--- | :--- |
| `doctor` | `--serial`, `--json` | Verifies `adb` and `fastboot` binaries in `PATH` and runs a quick device check. | `android-adb-toolkit doctor --json` |
| `devices` | `--detailed`, `--json` | Lists connected ADB devices with optional connection state and model metadata. | `android-adb-toolkit devices --detailed` |
| `dashboard` | `--serial`, `--json` | Prints an executive summary of device model, battery, storage, RAM, and bloatware. | `android-adb-toolkit dashboard` |
| `report` | `--serial`, `--json` | Collects full system properties, battery telemetry, mounts, memory, and bloatware list. | `android-adb-toolkit report --serial R58M123` |
| `battery` | `--serial`, `--json` | Reads battery percentage, temperature (`°C`), voltage (`mV`), status, and health labels. | `android-adb-toolkit battery` |
| `packages` | `--third-party`, `--json` | Lists all installed packages or filters strictly to user-installed third-party apps. | `android-adb-toolkit packages --third-party` |
| `bloatware` | `--by-category`, `--json` | Scans installed apps against the curated OEM bloatware catalog. | `android-adb-toolkit bloatware --by-category` |
| `remove` | `--dry-run`, `--remove`, `--user` | Disables (`pm disable-user --user 0`) or uninstalls a package after safety validation. | `android-adb-toolkit remove com.miui.cleanmaster --dry-run` |
| `restore` | `--user`, `--json` | Re-enables a previously disabled package (`pm enable --user 0`). | `android-adb-toolkit restore com.miui.cleanmaster` |
| `logcat` | `--tag`, `--priority`, `--pattern`, `--pid`, `--limit` | Captures and filters recent `logcat` entries by tag, severity, PID, or keyword. | `android-adb-toolkit logcat --priority E --pattern crash` |
| `fastboot` | `--json` | Lists devices currently connected in Fastboot bootloader mode. | `android-adb-toolkit fastboot` |
| `export` | `--format`, `--output`, `--serial` | Exports a full diagnostic snapshot to `json`, `html`, or `csv`. | `android-adb-toolkit export --format html --output report.html` |
| `desktop` | `--json` | Opens the Tkinter desktop diagnostic application. | `android-adb-toolkit desktop` |

### Common CLI Workflows

```bash
# 1. Inspect detailed device connection states
android-adb-toolkit devices --detailed

# 2. Preview safe bloatware candidates grouped by OEM
android-adb-toolkit bloatware --by-category

# 3. Safely dry-run disabling an unwanted OEM package
android-adb-toolkit remove com.samsung.android.game.gamehome --dry-run

# 4. Disable the package for User 0 (non-destructive & reversible)
android-adb-toolkit remove com.samsung.android.game.gamehome

# 5. Re-enable a disabled package at any time
android-adb-toolkit restore com.samsung.android.game.gamehome

# 6. Capture the last 500 log lines filtered to ActivityManager warnings
android-adb-toolkit logcat --tag ActivityManager --priority W --limit 500

# 7. Generate a styled HTML diagnostic report for a client or ticket
android-adb-toolkit export --format html --output device_audit.html
```

## 🖥️ Desktop GUI Walkthrough

Launch the desktop interface with `android-adb-desktop` or `android-adb-toolkit desktop`. The interface is organized into five focused workspaces:

| Workspace Tab | Capabilities |
| :--- | :--- |
| **1. Overview** | Select active device serials, refresh connection state, and inspect formatted **Dashboard** and **Battery** JSON telemetry. |
| **2. Logs** | Stream live `adb logcat` output via a background worker thread, filter by keyword in real time, capture instant 200-line snapshots, or clear the buffer. |
| **3. Packages** | Browse all installed packages, filter in real time with the search bar, toggle **Third-party only**, or click **Load Safe Bloatware Suggestions** to isolate removable OEM apps. |
| **4. Safety** | Review a side-by-side **Staging Queue (Unapproved)** and **Approved Manifest**. Approve or unapprove packages individually and opt in to on-device `pm disable-user` execution. |
| **5. Reports** | Preview complete diagnostic payloads and export one-click **JSON**, **HTML**, or **CSV** reports via native file dialogs. |

## 🛡️ Multi-Layer Debloat Safety Architecture

Removing the wrong system package on Android can cause bootloops, broken notifications, or loss of Google Play services. This toolkit enforces four layers of protection:

1. **Non-Destructive Default (`disable-user`)**: By default, `remove` executes `adb shell pm disable-user --user 0 <package>` rather than uninstalling APK payloads, making changes trivially reversible via `android-adb-toolkit restore <package>`.
2. **Hardcoded Core Package Blocklist (`PROTECTED_PACKAGES`)**: Critical packages are strictly blocked from approval, disabling, or removal—even if passed manually on the CLI:
   - **Android Core & System UI**: `android`, `com.android.systemui`, `com.android.settings`, `com.android.shell`
   - **Telephony & Providers**: `com.android.phone`, `com.android.providers.telephony`, `com.android.providers.settings`, `com.android.providers.contacts`, `com.android.providers.media`
   - **Google Play & HMS Core**: `com.android.vending` (Play Store), `com.google.android.gms` (Play Services), `com.google.android.gsf`, `com.google.android.packageinstaller`, `com.google.android.permissioncontroller`, `com.huawei.hwid` (HMS Core)
3. **Strict Package Name Validation**: All package identifiers are validated against `^[a-zA-Z][a-zA-Z0-9_]*(?:\.[a-zA-Z0-9_]+)+$` before any shell command is constructed.
4. **Two-Step Staging & Approval Manifest**: In the desktop UI, packages must be staged and explicitly approved into `.adb_toolkit_approvals.json` before batch actions can run.

### Curated OEM Bloatware Categories

| Category | Example Safe-Removal Candidates Detected |
| :--- | :--- |
| **Google** | `com.google.android.apps.translate`, `com.google.android.apps.wellbeing`, `com.google.android.apps.tachyon`, `com.google.android.videos`, `com.google.android.music` |
| **Samsung** | `com.samsung.android.app.watchmanager`, `com.samsung.android.oneconnect`, `com.samsung.android.bixby.agent`, `com.samsung.android.app.spage`, `com.samsung.android.game.gamehome` |
| **Xiaomi / MIUI** | `com.miui.cleanmaster`, `com.xiaomi.mipicks`, `com.miui.miservice`, `com.miui.analytics`, `com.miui.msa.global`, `com.miui.videoplayer` |
| **Huawei / EMUI** | `com.huawei.android.hsf`, `com.huawei.android.thememanager`, `com.huawei.himovie.overseas`, `com.huawei.health`, `com.huawei.appmarket` |
| **OnePlus / OxygenOS** | `com.oneplus.mms`, `com.oneplus.opbugreport`, `com.oneplus.LogKit`, `com.oneplus.brickmode`, `net.oneplus.forums` |
| **Carrier & Preloads** | `com.google.android.apps.nbu.files`, `com.facebook.system`, `com.facebook.appmanager`, `com.facebook.services`, `com.Netflix.mediaclient`, `com.spotify.music` |

## 🗂️ Project Architecture

```text
Universal-Android-ADB-Diagnostic-Toolkit-main/
├── .github/workflows/
│   └── ci.yml                          # GitHub Actions matrix (Python 3.10 – 3.13)
├── installer/
│   └── installer.iss                   # Inno Setup Windows installer configuration
├── scripts/
│   └── build_windows_installer.py      # Automated PyInstaller + Inno Setup builder
├── src/universal_android_adb_toolkit/
│   ├── __init__.py                     # Lazy package exports & version metadata
│   ├── __main__.py                     # `python -m universal_android_adb_toolkit` entry
│   ├── bloatware.py                    # OEM bloatware catalog & PROTECTED_PACKAGES guard
│   ├── cli.py                          # CLI parser, ADB/Fastboot runners & telemetry parsers
│   ├── gui.py                          # 5-tab Tkinter desktop diagnostic application
│   ├── logstream.py                    # Threaded bounded-queue live logcat streamer
│   ├── reports.py                      # JSON, styled XSS-safe HTML & CSV report exporters
│   └── safety.py                       # Approval manifest persistence & batch execution
├── tests/
│   └── test_cli.py                     # 15+ unit & regression tests (pytest + unittest)
├── LICENSE                             # MIT License
├── pyproject.toml                      # PEP 621 package metadata & entry points
└── README.md                           # Project documentation
```

## 🧪 Testing & Windows Packaging

### Run the Automated Test Suite

The test suite runs cleanly without requiring a physical Android device attached (all ADB/Fastboot calls are deterministically mocked):

```bash
# Run with pytest
pytest -v

# Or run with Python's built-in unittest runner (zero external packages needed)
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

### Build a Standalone Windows Installer

Bundle the desktop GUI into a single-file `.exe` (`dist/UniversalAndroidADBToolkit.exe`) and optionally compile a Windows Setup wizard via Inno Setup (`iscc`):

```bash
pip install pyinstaller
python scripts/build_windows_installer.py
```

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for full license text.
