#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef AppVersionNumeric
  #define AppVersionNumeric "0.0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "."
#endif
#ifndef OutputDir
  #define OutputDir "."
#endif
#ifndef SetupIcon
  #define SetupIcon "IPT.ico"
#endif

#define MyAppName "Ignitron Preset Tools"
#define MyAppExeName "Ignitron Preset Tools v" + AppVersion + ".exe"

[Setup]
AppId=IgnitronPresetTools-{#AppVersion}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} v{#AppVersion}
AppPublisher=Ignitron Preset Tools
AppPublisherURL=https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0
AppSupportURL=https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0/issues
DefaultDirName={localappdata}\Programs\Ignitron Preset Tools v{#AppVersion}
DefaultGroupName=Ignitron Preset Tools v{#AppVersion}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=Ignitron.Preset.Tools.v{#AppVersion}.Windows-x64-Setup
SetupIconFile={#SetupIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersionNumeric}
VersionInfoDescription=Ignitron Preset Tools Windows installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Ignitron Preset Tools v{#AppVersion}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Windows Programming Setup"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows_programming_setup.ps1"" -ProjectDir ""{app}\ignitron firmware"""
Name: "{autodesktop}\Ignitron Preset Tools v{#AppVersion}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows_programming_setup.ps1"" -ProjectDir ""{app}\ignitron firmware"""; Description: "Check and install pedal programming requirements"; Flags: postinstall skipifsilent waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Ignitron Preset Tools"; Flags: postinstall nowait skipifsilent unchecked
