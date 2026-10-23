from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def generate_inno_setup_script() -> Path:
    repo_root = _repo_root()
    installer_dir = repo_root / "installer"
    installer_dir.mkdir(exist_ok=True)

    content = """[Setup]
AppName=Universal Android ADB Diagnostic Toolkit
AppVersion=0.2.0
DefaultDirName={userpf}\\Universal Android ADB Diagnostic Toolkit
DefaultGroupName=Universal Android ADB Diagnostic Toolkit
OutputDir=.\\output
OutputBaseFilename=UniversalAndroidADBToolkit-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: \"..\\dist\\UniversalAndroidADBToolkit.exe\"; DestDir: \"{app}\";

[Icons]
Name: \"{group}\\Universal Android ADB Diagnostic Toolkit\"; Filename: \"{app}\\UniversalAndroidADBToolkit.exe\"
Name: \"{commondesktop}\\Universal Android ADB Diagnostic Toolkit\"; Filename: \"{app}\\UniversalAndroidADBToolkit.exe\"; Tasks: desktopicon

[Tasks]
Name: \"desktopicon\"; Description: \"Create a desktop icon\"; GroupDescription: \"Additional icons:\"

[Run]
Filename: \"{app}\\UniversalAndroidADBToolkit.exe\"; Description: \"Launch Universal Android ADB Diagnostic Toolkit\"; Flags: nowait postinstall skipifsilent
"""
    script_path = installer_dir / "installer.iss"
    script_path.write_text(content, encoding="utf-8")
    return script_path


def build_windows_installer() -> None:
    repo_root = _repo_root()
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(exist_ok=True)

    try:
        import PyInstaller  # type: ignore
    except ImportError:
        print("PyInstaller is not installed. Install with: pip install pyinstaller")
        raise SystemExit(1)

    gui_entry = repo_root / "src" / "universal_android_adb_toolkit" / "gui.py"
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "UniversalAndroidADBToolkit",
        "--distpath",
        str(dist_dir),
        str(gui_entry),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    exe_path = dist_dir / "UniversalAndroidADBToolkit.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Executable not found at {exe_path}")

    installer_script = generate_inno_setup_script()
    iscc = shutil.which("iscc")
    if iscc:
        output_dir = repo_root / "installer" / "output"
        output_dir.mkdir(exist_ok=True)
        subprocess.run([iscc, str(installer_script)], check=True)
        print(f"Inno Setup installer created at {output_dir}")
    else:
        print("Inno Setup not found. Installer script generated at:", installer_script)
        print("You can build it manually with: iscc installer/installer.iss")


if __name__ == "__main__":
    build_windows_installer()
