from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

APP_VERSION = "0.4.0"


def _repo_root() -> Path:
    # scripts/build_windows_installer.py lives at <repo_root>/scripts/build_windows_installer.py
    return Path(__file__).resolve().parents[1]


def generate_inno_setup_script() -> Path:
    repo_root = _repo_root()
    installer_dir = repo_root / "installer"
    installer_dir.mkdir(exist_ok=True)

    content = f"""[Setup]
AppName=Universal Android ADB Diagnostic Toolkit
AppVersion={APP_VERSION}
DefaultDirName={{userpf}}\\Universal Android ADB Diagnostic Toolkit
DefaultGroupName=Universal Android ADB Diagnostic Toolkit
OutputDir=.\\output
OutputBaseFilename=UniversalAndroidADBToolkit-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\\dist\\UniversalAndroidADBToolkit.exe"; DestDir: "{{app}}"

[Icons]
Name: "{{group}}\\Universal Android ADB Diagnostic Toolkit"; Filename: "{{app}}\\UniversalAndroidADBToolkit.exe"
Name: "{{commondesktop}}\\Universal Android ADB Diagnostic Toolkit"; Filename: "{{app}}\\UniversalAndroidADBToolkit.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{{app}}\\UniversalAndroidADBToolkit.exe"; Description: "Launch Universal Android ADB Diagnostic Toolkit"; Flags: nowait postinstall skipifsilent
"""
    script_path = installer_dir / "installer.iss"
    script_path.write_text(content, encoding="utf-8")
    return script_path


def build_windows_installer() -> None:
    repo_root = _repo_root()
    dist_dir = repo_root / "dist"
    src_dir = repo_root / "src"
    dist_dir.mkdir(exist_ok=True)

    try:
        import PyInstaller  # type: ignore  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed. Install with: pip install pyinstaller")
        raise SystemExit(1)

    gui_entry = src_dir / "universal_android_adb_toolkit" / "gui.py"
    if not gui_entry.exists():
        raise FileNotFoundError(f"GUI entry point not found at {gui_entry}")

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--windowed",
        "--name",
        "UniversalAndroidADBToolkit",
        "--paths",
        str(src_dir),
        "--distpath",
        str(dist_dir),
        str(gui_entry),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    exe_name = "UniversalAndroidADBToolkit.exe" if sys.platform == "win32" else "UniversalAndroidADBToolkit"
    exe_path = dist_dir / exe_name
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
