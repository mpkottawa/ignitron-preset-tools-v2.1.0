$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$ReleaseVersion = "2.1.04"
$AppName = "Ignitron Preset Tools v$ReleaseVersion"
$Entry = Join-Path $Root "ignitron_preset_tools_v2.1.py"
$Icon = Join-Path $Root "IPT.ico"
$AsciiLogo = Join-Path $Root "Ignitron preset tools logo ASCII 120x60.txt"
$BuildRoot = Join-Path $Root "build"
$DistRoot = Join-Path $Root "release"
$DistApp = Join-Path $DistRoot $AppName
$Architecture = [System.Runtime.InteropServices.RuntimeInformation]::OSArchitecture.ToString().ToLowerInvariant()
$ZipPath = Join-Path $DistRoot "$AppName Windows-$Architecture.zip"
$FirmwareSource = Join-Path $Root "Ignitron"
$FirmwareRelease = Join-Path $DistApp "ignitron firmware"
$LegacyFirmwareSource = Join-Path $Root "Ignitron 1.9.0"
$LegacyFirmwareRelease = Join-Path $DistApp "Ignitron 1.9.0"
$ReleaseTools = Join-Path $Root "release_tools.py"
$ProgrammingSetupSource = Join-Path $Root "windows_programming_setup.ps1"
$ProgrammingSetupRelease = Join-Path $DistApp "windows_programming_setup.ps1"
$InnoScript = Join-Path $Root "windows_installer.iss"
$SetupPath = Join-Path $DistRoot "Ignitron.Preset.Tools.v$ReleaseVersion.Windows-$Architecture-Setup.exe"

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq "Core") {
  throw "build_release.ps1 creates the Windows package and must run on Windows."
}
if (-not (Test-Path -LiteralPath $Entry)) {
  throw "Missing entry point: $Entry"
}
foreach ($required in @($ProgrammingSetupSource, $InnoScript)) {
  if (-not (Test-Path -LiteralPath $required)) {
    throw "Missing Windows installer source: $required"
  }
}

$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
  throw "Python 3 was not found. Install Python 3.10 or newer and try again."
}

New-Item -ItemType Directory -Force -Path $BuildRoot, $DistRoot | Out-Null
$VenvRoot = Join-Path $BuildRoot "venv-windows-$Architecture"
$BuildPython = Join-Path $VenvRoot "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $BuildPython)) {
  & $Python.Source -m venv $VenvRoot
}
& $BuildPython -m pip install --upgrade pip
& $BuildPython -m pip install -r (Join-Path $Root "requirements-build.txt")

$addData = @()
if (Test-Path -LiteralPath (Join-Path $Root "reference")) {
  $addData += "--add-data"
  $addData += "$(Join-Path $Root 'reference');reference"
}
if (Test-Path -LiteralPath $Icon) {
  $addData += "--add-data"
  $addData += "$Icon;."
}
if (Test-Path -LiteralPath $AsciiLogo) {
  $addData += "--add-data"
  $addData += "$AsciiLogo;."
}

$iconArgs = @()
if (Test-Path -LiteralPath $Icon) {
  $iconArgs += "--icon"
  $iconArgs += $Icon
}

& $BuildPython -m PyInstaller `
  --noconfirm `
  --clean `
  --windowed `
  --name $AppName `
  --distpath $DistRoot `
  --workpath (Join-Path $BuildRoot "pyinstaller-windows-$Architecture") `
  --specpath $BuildRoot `
  @iconArgs `
  @addData `
  --add-data "$(Join-Path $Root 'preset_puller.py');." `
  --add-data "$(Join-Path $Root 'preset_chart.py');." `
  --add-data "$(Join-Path $Root 'preset_converter.py');." `
  $Entry

foreach ($document in @("README.md", "WINDOWS-INSTALL-GUIDE.md", "FIRMWARE.md", "RELEASE_NOTES.md", "GITHUB_RELEASE.md", "LICENSE")) {
  $source = Join-Path $Root $document
  if (Test-Path -LiteralPath $source) {
    Copy-Item -LiteralPath $source -Destination (Join-Path $DistApp $document) -Force
  }
}

if (Test-Path -LiteralPath $FirmwareSource) {
  & $BuildPython $ReleaseTools stage-firmware $FirmwareSource $FirmwareRelease
}
if (Test-Path -LiteralPath $LegacyFirmwareSource) {
  & $BuildPython $ReleaseTools stage-firmware $LegacyFirmwareSource $LegacyFirmwareRelease
}

Copy-Item -LiteralPath $ProgrammingSetupSource -Destination $ProgrammingSetupRelease -Force
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ProgrammingSetupRelease -SelfTest -NonInteractive
if ($LASTEXITCODE -ne 0) {
  throw "Windows programming setup self-test failed with code $LASTEXITCODE."
}

& $BuildPython $ReleaseTools verify $DistApp

if (Test-Path -LiteralPath $ZipPath) {
  Remove-Item -LiteralPath $ZipPath -Force
}
Compress-Archive -Path (Join-Path $DistApp "*") -DestinationPath $ZipPath

$Iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if (-not $Iscc) {
  foreach ($candidate in @(
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
  )) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) {
      $Iscc = [pscustomobject]@{ Source = $candidate }
      break
    }
  }
}
if (-not $Iscc) {
  throw "Inno Setup 6 was not found. Install it from https://jrsoftware.org/isinfo.php to build the Windows Setup executable."
}

$versionParts = @($ReleaseVersion.Split(".") | ForEach-Object { [int]$_ })
while ($versionParts.Count -lt 4) { $versionParts += 0 }
$VersionInfoVersion = ($versionParts[0..3] -join ".")
if (Test-Path -LiteralPath $SetupPath) {
  Remove-Item -LiteralPath $SetupPath -Force
}
& $Iscc.Source `
  "/DAppVersion=$ReleaseVersion" `
  "/DAppVersionNumeric=$VersionInfoVersion" `
  "/DSourceDir=$DistApp" `
  "/DOutputDir=$DistRoot" `
  "/DSetupIcon=$Icon" `
  $InnoScript
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $SetupPath)) {
  throw "Inno Setup failed to create $SetupPath"
}

Write-Host "Built $AppName for Windows $Architecture"
Write-Host "Folder: $DistApp"
Write-Host "Zip:    $ZipPath"
Write-Host "Setup:  $SetupPath"
