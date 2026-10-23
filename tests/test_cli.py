import json

from universal_android_adb_toolkit.cli import build_package_command, filter_logcat_output, log_priority_matches, safe_removal_candidates


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
    assert safe_removal_candidates(package_list=packages) == ["com.google.android.apps.translate", "com.samsung.android.messaging"]
