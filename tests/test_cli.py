from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from universal_android_adb_toolkit.bloatware import (
    categorize_bloatware_candidates,
    is_protected_package,
    safe_removal_candidates,
)
from universal_android_adb_toolkit.cli import (
    build_package_command,
    filter_logcat_output,
    get_connected_devices,
    get_connected_devices_detailed,
    log_priority_matches,
    main,
    read_battery,
    read_memory_snapshot,
    read_storage_snapshot,
    run_command,
    shutil_which,
    summarize_dashboard,
    validate_package_name,
)
from universal_android_adb_toolkit.reports import (
    build_report_snapshot,
    export_report_csv,
    export_report_html,
    export_report_json,
)
from universal_android_adb_toolkit.safety import (
    approve_package,
    clear_approvals,
    execute_approved_packages_detailed,
    load_approvals,
    remove_approved_packages,
    unapprove_package,
)


def test_log_priority_matches():
    line = "11-20 12:34:56.789 12345 6789 I/ActivityManager: Displayed com.example.app/12345"
    assert log_priority_matches(line, "I") is True
    assert log_priority_matches(line, "W") is False


def test_filter_logcat_output():
    lines = [
        "11-20 12:34:56.789 12345 6789 I/ActivityManager: foo",
        "11-20 12:35:40.123 12345 6789 W/WindowManager: bar",
        "11-20 12:36:00.000 9876 4321 E/Example: crash detected",
    ]
    filtered = filter_logcat_output(lines, pattern="crash", priority="E")
    assert filtered == ["11-20 12:36:00.000 9876 4321 E/Example: crash detected"]


def test_build_package_command_uses_disable_user_by_default():
    cmd = build_package_command("SERIAL-123", "com.example.app")
    assert cmd == ["adb", "-s", "SERIAL-123", "shell", "pm", "disable-user", "--user", "0", "com.example.app"]


def test_build_package_command_for_uninstall():
    cmd = build_package_command("SERIAL-123", "com.example.app", remove=True)
    assert cmd == ["adb", "-s", "SERIAL-123", "shell", "pm", "uninstall", "--user", "0", "com.example.app"]


def test_safe_removal_candidates():
    packages = ["com.samsung.android.messaging", "com.google.android.apps.translate", "com.example.app"]
    assert safe_removal_candidates(package_list=packages) == [
        "com.google.android.apps.translate",
        "com.samsung.android.messaging",
    ]


def test_protected_packages_never_marked_as_bloatware():
    assert is_protected_package("com.android.vending") is True
    assert is_protected_package("com.android.systemui") is True
    assert is_protected_package("com.huawei.hwid") is True
    candidates = safe_removal_candidates(
        package_list=["com.android.vending", "com.huawei.hwid", "com.miui.cleanmaster"]
    )
    assert candidates == ["com.miui.cleanmaster"]


def test_safe_removal_candidates_queries_serial_when_package_list_omitted():
    with patch(
        "universal_android_adb_toolkit.cli.list_packages",
        return_value=["com.miui.cleanmaster", "com.example.custom"],
    ) as mock_list:
        result = safe_removal_candidates(serial="DEVICE-001")
        mock_list.assert_called_once_with("DEVICE-001", third_party_only=False)
        assert result == ["com.miui.cleanmaster"]


def test_categorize_bloatware_candidates():
    grouped = categorize_bloatware_candidates(
        package_list=["com.miui.cleanmaster", "com.samsung.android.oneconnect", "com.example.app"]
    )
    assert grouped == {
        "samsung": ["com.samsung.android.oneconnect"],
        "xiaomi": ["com.miui.cleanmaster"],
    }


def test_package_validation_and_protection():
    assert validate_package_name("com.example.app_1") is True
    assert validate_package_name("invalid_pkg_without_dot") is False
    assert validate_package_name("com.example;rm -rf /") is False

    try:
        build_package_command("SERIAL-1", "com.android.vending")
        raise AssertionError("Expected ValueError for protected package")
    except ValueError as exc:
        assert "protected" in str(exc).lower()

    try:
        build_package_command("SERIAL-1", "bad package name")
        raise AssertionError("Expected ValueError for invalid package name")
    except ValueError as exc:
        assert "invalid" in str(exc).lower()


def test_run_command_handles_missing_binary_gracefully():
    res = run_command(["definitely_nonexistent_adb_binary_xyz123"])
    assert res.returncode == 127
    assert "Command not found" in res.stderr


def test_shutil_which_cross_platform():
    # Python's executable or 'python3'/'sh' should be resolvable without invoking 'which' subprocess
    assert shutil_which("definitely_missing_binary_9999") is None


def test_read_battery_parses_temperature_and_labels():
    sample_dumpsys = """Current Battery Service state:
  AC powered: false
  USB powered: true
  status: 2
  health: 2
  present: true
  level: 84
  scale: 100
  voltage: 4150
  temperature: 315
  technology: Li-poly
"""
    fake_proc = subprocess.CompletedProcess(args=["adb"], returncode=0, stdout=sample_dumpsys, stderr="")
    with patch("universal_android_adb_toolkit.cli.shell", return_value=fake_proc):
        data = read_battery("SER-1")
        assert data["level"] == 84
        assert data["scale"] == 100
        assert data["percentage"] == 84.0
        assert data["temperature"] == 315
        assert data["temperature_c"] == 31.5
        assert data["status_label"] == "charging"
        assert data["health_label"] == "good"


def test_read_storage_and_memory_snapshots():
    df_out = """Filesystem      Size  Used Avail Use% Mounted on
/dev/block/dm-5 110G   45G   65G  41% /data
"""
    mem_out = """MemTotal:        8000000 kB
MemFree:         1200000 kB
MemAvailable:    4000000 kB
SwapTotal:       2000000 kB
SwapFree:        1500000 kB
"""
    with patch(
        "universal_android_adb_toolkit.cli.shell",
        return_value=subprocess.CompletedProcess(["adb"], 0, df_out, ""),
    ):
        storage = read_storage_snapshot("SER-1")
        assert "/dev/block/dm-5" in storage["raw"]
        assert len(storage["mounts"]) == 1
        assert storage["mounts"][0]["mounted_on"] == "/data"
        assert storage["mounts"][0]["use_percent"] == "41%"

    with patch(
        "universal_android_adb_toolkit.cli.shell",
        return_value=subprocess.CompletedProcess(["adb"], 0, mem_out, ""),
    ):
        mem = read_memory_snapshot("SER-1")
        assert mem["memtotal_kb"] == 8000000
        assert mem["memavailable_kb"] == 4000000
        assert mem["used_percent"] == 50.0


def test_get_connected_devices_and_detailed():
    adb_out = """List of devices attached
SER12345               device usb:1-1 product:husky model:Pixel_8_Pro device:husky transport_id:1
SER99999               unauthorized usb:1-2 transport_id:2
"""
    with patch(
        "universal_android_adb_toolkit.cli.run_command",
        return_value=subprocess.CompletedProcess(["adb"], 0, adb_out, ""),
    ):
        assert get_connected_devices() == ["SER12345", "SER99999"]
        assert get_connected_devices(only_authorized=True) == ["SER12345"]
        detailed = get_connected_devices_detailed()
        assert detailed[0]["serial"] == "SER12345"
        assert detailed[0]["model"] == "Pixel_8_Pro"
        assert detailed[1]["state"] == "unauthorized"


def test_summarize_dashboard_does_not_duplicate_device_report():
    with patch("universal_android_adb_toolkit.cli.device_report") as mock_report:
        mock_report.return_value = {
            "serial": "SER-1",
            "model": "Pixel 8",
            "android_version": "15",
            "battery": {"percentage": 90.0},
            "storage": {"raw": "ok"},
            "memory": {"used_percent": 42.0},
            "safe_bloatware_candidates": ["com.google.android.apps.translate"],
        }
        summary = summarize_dashboard("SER-1")
        assert mock_report.call_count == 1
        assert summary["model"] == "Pixel 8"
        assert summary["safe_bloatware_candidates"] == ["com.google.android.apps.translate"]


def test_safety_workflow_and_protected_guard():
    with tempfile.TemporaryDirectory() as tmpdir:
        manifest = Path(tmpdir) / "approvals.json"
        approve_package("com.miui.cleanmaster", path=manifest)
        approve_package("com.samsung.android.oneconnect", path=manifest)
        assert load_approvals(manifest) == ["com.miui.cleanmaster", "com.samsung.android.oneconnect"]

        unapprove_package("com.miui.cleanmaster", path=manifest)
        assert load_approvals(manifest) == ["com.samsung.android.oneconnect"]

        try:
            approve_package("com.android.vending", path=manifest)
            raise AssertionError("Should reject protected package")
        except ValueError:
            pass

        dry_outcomes = execute_approved_packages_detailed(
            "SER-1",
            load_approvals(manifest),
            dry_run=True,
            path=manifest,
        )
        assert len(dry_outcomes) == 1
        assert dry_outcomes[0]["status"] == "dry_run"

        executed = remove_approved_packages("SER-1", path=manifest)
        assert executed == ["com.samsung.android.oneconnect"]
        assert load_approvals(manifest) == []
        clear_approvals(manifest)


def test_reports_export_escapes_html_and_writes_csv_and_json():
    payload = {
        "serial": "SER<script>alert(1)</script>",
        "device": {
            "serial": "SER<script>alert(1)</script>",
            "brand": "Google",
            "model": "Pixel <8>",
            "android_version": "15",
            "security_patch": "2026-10-05",
            "safe_bloatware_candidates": ["com.google.android.apps.translate"],
        },
        "battery": {"percentage": 88.0, "temperature_c": 29.5},
        "packages": ["com.google.android.apps.translate", "com.example.safe"],
    }
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "report.html"
        json_path = Path(tmpdir) / "report.json"
        csv_path = Path(tmpdir) / "report.csv"

        export_report_html(html_path, payload)
        html_text = html_path.read_text(encoding="utf-8")
        assert "<script>alert(1)</script>" not in html_text
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html_text

        export_report_json(json_path, payload)
        loaded = json.loads(json_path.read_text(encoding="utf-8"))
        assert loaded["serial"] == "SER<script>alert(1)</script>"

        export_report_csv(csv_path, payload)
        csv_lines = csv_path.read_text(encoding="utf-8").splitlines()
        assert csv_lines[0] == "package,is_bloatware_candidate"
        assert "com.google.android.apps.translate,true" in csv_lines
        assert "com.example.safe,false" in csv_lines


def test_build_report_snapshot_avoids_duplicate_battery_call():
    with patch("universal_android_adb_toolkit.reports.device_report") as mock_dev, patch(
        "universal_android_adb_toolkit.reports.list_packages", return_value=["com.example.app"]
    ):
        mock_dev.return_value = {"serial": "SER-1", "battery": {"percentage": 75.0}}
        snap = build_report_snapshot("SER-1")
        assert snap["battery"] == {"percentage": 75.0}
        assert snap["packages"] == ["com.example.app"]
        mock_dev.assert_called_once_with("SER-1")


def test_cli_remove_dry_run_json(capsys=None):
    rc = main(["remove", "com.example.app", "--serial", "SER-100", "--dry-run", "--json"])
    assert rc == 0


def test_windows_installer_repo_root_points_to_project_root():
    import importlib.util

    script_file = Path(__file__).resolve().parents[1] / "scripts" / "build_windows_installer.py"
    spec = importlib.util.spec_from_file_location("build_windows_installer", script_file)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    repo_root = mod._repo_root()
    assert (repo_root / "pyproject.toml").exists()
    assert (repo_root / "src" / "universal_android_adb_toolkit" / "gui.py").exists()




def test_version_command():
    from universal_android_adb_toolkit.cli import main
    import io
    from contextlib import redirect_stdout
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(["version"])
    assert rc == 0
    assert "0.4.0" in buf.getvalue()


def test_expanded_bloatware_catalog():
    from universal_android_adb_toolkit.bloatware import OEM_BLOATWARE, get_safe_bloatware_packages
    cats = get_safe_bloatware_packages()
    assert "oppo_realme" in cats
    assert "vivo" in cats
    assert "motorola" in cats
    total = sum(len(v) for v in cats.values())
    assert total >= 200


def test_read_cpu_thermal_handles_missing(monkeypatch=None):
    from universal_android_adb_toolkit import cli
    with patch("universal_android_adb_toolkit.cli.shell") as mock_shell:
        mock_shell.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        data = cli.read_cpu_thermal("SERIAL")
        assert "status" in data or data == {"status": "unavailable"} or isinstance(data, dict)


def test_validate_package_rejects_bad_names():
    assert validate_package_name("com.example.app") is True
    assert validate_package_name("not a package") is False
    assert validate_package_name("") is False
    assert validate_package_name("com") is False


def test_package_info_invalid_name():
    from universal_android_adb_toolkit.cli import package_info
    result = package_info(None, "not a valid package")
    assert result.get("ok") is False


def test_approvals_list_empty(tmp_path, monkeypatch):
    from universal_android_adb_toolkit import safety
    monkeypatch.setattr(safety, "APPROVALS_PATH", tmp_path / "approvals.json")
    assert safety.load_approvals() == []

class ToolkitTestSuite(unittest.TestCase):
    """Unittest wrapper so `python3 -m unittest` runs every test function."""

    def test_all(self):
        test_log_priority_matches()
        test_filter_logcat_output()
        test_build_package_command_uses_disable_user_by_default()
        test_build_package_command_for_uninstall()
        test_safe_removal_candidates()
        test_protected_packages_never_marked_as_bloatware()
        test_safe_removal_candidates_queries_serial_when_package_list_omitted()
        test_categorize_bloatware_candidates()
        test_package_validation_and_protection()
        test_run_command_handles_missing_binary_gracefully()
        test_shutil_which_cross_platform()
        test_read_battery_parses_temperature_and_labels()
        test_read_storage_and_memory_snapshots()
        test_get_connected_devices_and_detailed()
        test_summarize_dashboard_does_not_duplicate_device_report()
        test_safety_workflow_and_protected_guard()
        test_reports_export_escapes_html_and_writes_csv_and_json()
        test_build_report_snapshot_avoids_duplicate_battery_call()
        test_cli_remove_dry_run_json()
        test_windows_installer_repo_root_points_to_project_root()


if __name__ == "__main__":
    unittest.main()
