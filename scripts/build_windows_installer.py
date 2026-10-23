from __future__ import annotations

import os
import subprocess
import sys


def build_windows_installer() -> None:
    try:
        import PyInstaller  # type: ignore
    except ImportError:
        print("PyInstaller is not installed. Run: pip install pyinstaller")
        raise SystemExit(1)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    output_dir = os.path.join(repo_root, "dist")
    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--windowed",
        "--name",
        "UniversalAndroidADBToolkit",
        "--distpath",
        output_dir,
        os.path.join(repo_root, "src", "universal_android_adb_toolkit", "gui.py"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)
    print(f"Windows installer built in: {output_dir}")


if __name__ == "__main__":
    build_windows_installer()
