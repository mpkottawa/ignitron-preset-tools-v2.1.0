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
; Keep this ID stable so future releases update the existing installation.
; It matches the first installer preview and must not be versioned again.
AppId=IgnitronPresetTools-2.1.03
AppName={#MyAppName}
AppVersion={#AppVersion}
AppVerName={#MyAppName} v{#AppVersion}
AppPublisher=Ignitron Preset Tools
AppPublisherURL=https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0
AppSupportURL=https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0/issues
DefaultDirName={localappdata}\Programs\Ignitron Preset Tools v{#AppVersion}
DefaultGroupName=Ignitron Preset Tools v{#AppVersion}
DisableDirPage=no
DisableProgramGroupPage=yes
UsePreviousAppDir=no
UsePreviousGroup=no
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

[InstallDelete]
; Remove the previous packaged runtime before copying the new release. User data and
; firmware folders are intentionally excluded (firmware is backed up in [Code]).
Type: files; Name: "{app}\Ignitron Preset Tools v*.exe"
Type: filesandordirs; Name: "{app}\_internal"
Type: files; Name: "{autodesktop}\Ignitron Preset Tools v*.lnk"
Type: filesandordirs; Name: "{autoprograms}\Ignitron Preset Tools v*"

[Icons]
Name: "{group}\Ignitron Preset Tools v{#AppVersion}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Windows Programming Setup"; Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows_programming_setup.ps1"" -ProjectDir ""{app}\ignitron firmware"""
Name: "{autodesktop}\Ignitron Preset Tools v{#AppVersion}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\windows_programming_setup.ps1"" -ProjectDir ""{app}\ignitron firmware"""; Description: "Check and install pedal programming requirements"; Flags: postinstall skipifsilent waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Ignitron Preset Tools"; Flags: postinstall nowait skipifsilent unchecked

[Code]
const
  LineBreak = #13#10;

var
  PreviousVersion: String;
  PreviousInstallDir: String;
  SuggestedInstallDir: String;
  PreviousInstallPage: TOutputMsgWizardPage;

function ReadPreviousInstall(): Boolean;
var
  UninstallKey: String;
begin
  UninstallKey := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\IgnitronPresetTools-2.1.03_is1';
  Result :=
    RegQueryStringValue(HKCU, UninstallKey, 'InstallLocation', PreviousInstallDir) and
    (PreviousInstallDir <> '');
  if Result then
  begin
    PreviousInstallDir := RemoveBackslashUnlessRoot(PreviousInstallDir);
    Result := DirExists(PreviousInstallDir);
  end;
  if Result then
  begin
    if not RegQueryStringValue(HKCU, UninstallKey, 'DisplayVersion', PreviousVersion) then
      PreviousVersion := 'an earlier version';
  end;
end;

procedure InitializeWizard();
begin
  if ReadPreviousInstall() then
  begin
    SuggestedInstallDir := AddBackslash(ExtractFileDir(PreviousInstallDir)) +
      'Ignitron Preset Tools v{#AppVersion}';
    WizardForm.DirEdit.Text := SuggestedInstallDir;
    PreviousInstallPage := CreateOutputMsgPage(
      wpSelectDir,
      'Previous version detected',
      'Ignitron Preset Tools ' + PreviousVersion + ' is already installed.',
      'Previous installation:' + LineBreak + PreviousInstallDir + LineBreak + LineBreak +
      'New version folder:' + LineBreak + SuggestedInstallDir + LineBreak + LineBreak +
      'Setup will rename the previous installation folder, then update the application. ' +
      'Your IPT settings are preserved.' +
      LineBreak + LineBreak +
      'To use another location, click Back and choose it on the destination-folder page.'
    );
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  BackupRoot: String;
  SourcePath: String;
  DestinationPath: String;
  CurrentInstallDir: String;
begin
  Result := '';
  if PreviousInstallDir = '' then
    Exit;

  CurrentInstallDir := RemoveBackslashUnlessRoot(ExpandConstant('{app}'));
  if CompareText(PreviousInstallDir, CurrentInstallDir) <> 0 then
  begin
    if DirExists(CurrentInstallDir) then
    begin
      Result := 'Setup cannot rename the previous installation because the new version folder already exists: ' +
        CurrentInstallDir + LineBreak + LineBreak +
        'Choose an empty destination folder or move the existing folder, then run Setup again.';
      Exit;
    end;
    if not ForceDirectories(ExtractFileDir(CurrentInstallDir)) then
    begin
      Result := 'Setup could not create the parent folder for: ' + CurrentInstallDir;
      Exit;
    end;
    if not RenameFile(PreviousInstallDir, CurrentInstallDir) then
    begin
      Result := 'Setup could not rename the previous installation folder. Close IPT and any File Explorer or terminal windows using it, then run Setup again.';
      Exit;
    end;
    PreviousInstallDir := CurrentInstallDir;
  end;

  BackupRoot := AddBackslash(CurrentInstallDir) + 'firmware backups\before-update-' +
    GetDateTimeString('yyyymmdd-hhnnss', '-', ':');

  SourcePath := AddBackslash(CurrentInstallDir) + 'ignitron firmware';
  if DirExists(SourcePath) then
  begin
    if not ForceDirectories(BackupRoot) then
    begin
      Result := 'Setup could not create the firmware backup folder: ' + BackupRoot;
      Exit;
    end;
    DestinationPath := AddBackslash(BackupRoot) + 'ignitron firmware';
    if not RenameFile(SourcePath, DestinationPath) then
    begin
      Result := 'Setup could not back up the existing Ignitron firmware folder. Close programs using it and try again.';
      Exit;
    end;
  end;

  SourcePath := AddBackslash(CurrentInstallDir) + 'Ignitron 1.9.0';
  if DirExists(SourcePath) then
  begin
    if not ForceDirectories(BackupRoot) then
    begin
      Result := 'Setup could not create the firmware backup folder: ' + BackupRoot;
      Exit;
    end;
    DestinationPath := AddBackslash(BackupRoot) + 'Ignitron 1.9.0';
    if not RenameFile(SourcePath, DestinationPath) then
    begin
      Result := 'Setup could not back up the existing Ignitron 1.9.0 folder. Close programs using it and try again.';
      Exit;
    end;
  end;
end;
