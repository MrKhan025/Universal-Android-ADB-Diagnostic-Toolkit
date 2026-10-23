[Setup]
AppName=Universal Android ADB Diagnostic Toolkit
AppVersion=0.2.0
DefaultDirName={userpf}\Universal Android ADB Diagnostic Toolkit
DefaultGroupName=Universal Android ADB Diagnostic Toolkit
OutputDir=.\output
OutputBaseFilename=UniversalAndroidADBToolkit-Setup
Compression=lzma
SolidCompression=yes

[Files]
Source: "..\dist\UniversalAndroidADBToolkit.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\Universal Android ADB Diagnostic Toolkit"; Filename: "{app}\UniversalAndroidADBToolkit.exe"
Name: "{commondesktop}\Universal Android ADB Diagnostic Toolkit"; Filename: "{app}\UniversalAndroidADBToolkit.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"

[Run]
Filename: "{app}\UniversalAndroidADBToolkit.exe"; Description: "Launch Universal Android ADB Diagnostic Toolkit"; Flags: nowait postinstall skipifsilent
