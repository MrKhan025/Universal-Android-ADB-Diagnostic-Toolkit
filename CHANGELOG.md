# Changelog

## 0.4.0 — 2026-10-27

### Added
- **Expanded OEM bloatware catalog** (~430 packages) covering Google, Samsung, Xiaomi/MIUI, Huawei, OnePlus, Oppo/Realme/ColorOS, Vivo, Motorola, and carrier/preload apps.
- New CLI commands:
  - `version` — print toolkit version
  - `props` — dump key system properties
  - `cpu` — CPU online cores, load average, thermal zones
  - `network` — Wi-Fi / IP summary
  - `screenshot` — capture PNG via `screencap`
  - `install` — install APK (`-r` by default)
  - `clear` — force-stop + cache-only clear (safe, non-destructive)
  - `reboot` — system / recovery / bootloader
  - `tcpip` / `connect` / `disconnect` — wireless ADB helpers
- Enriched `device_report` with fingerprint, hardware, board, baseband, package count, CPU/thermal, and network snapshots.
- Stronger `PROTECTED_PACKAGES` list (launcher, NFC, Bluetooth, keychain, etc.).
- CI matrix for Python 3.10–3.13 with package install + flake8 + pytest.

### Fixed
- `list_packages` no longer applies a redundant system-package filter on top of `pm list packages -3`.
- CI workflow now installs the package properly and matches the documented Python matrix.
- README architecture references aligned with actual workflow filenames.

### Safety
- Default package action remains `pm disable-user` (reversible).
- Cache clear never falls back to full `pm clear` (data wipe).
