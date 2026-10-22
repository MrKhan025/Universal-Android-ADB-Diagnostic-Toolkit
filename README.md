# Universal-Android-ADB-Diagnostic-Toolkit
Git-ready Universal Android / ADB Diagnostic Toolkit as a lightweight, dependency-free Python command-line application. It includes safety controls for package removal, automated tests, documentation, an MIT licence, and a CI workflow.
Included features
•ADB and Fastboot installation checks
•Connected-device detection and authorisation status
•Android version, model, build and security-patch reporting
•Storage and memory diagnostics
•Battery level, health, temperature and voltage readings
•Logcat filtering by text, tag, priority and PID
•Installed and third-party package listing
•Reversible disable-user debloating by default
•Optional removal for Android user 0
•Package restoration
•Dry-run and interactive confirmation safeguards
•Multiple-device selection using --serial
•JSON output for automation
•GitHub Actions testing on Python 3.10 through 3.13
•Local Git repository with initial commits
The implementation uses the Android Debug Bridge supplied through the Android SDK Platform Tools. ADB provides device communication and access to device shell commands, while Fastboot communicates with devices in bootloader mode. Android Debug Bridge documentation, Flash with Fastboot. 
