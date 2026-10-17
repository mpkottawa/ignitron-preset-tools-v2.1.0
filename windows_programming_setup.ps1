[CmdletBinding()]
param(
  [string]$ProjectDir = "",
  [switch]$CheckOnly,
  [switch]$SkipBuild,
  [switch]$NonInteractive,
  [switch]$InstallMissing,
  [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PythonVersion = "3.13.16"
$PythonUrl = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-amd64.exe"
$PythonSha256 = "fb4f9f5d438b2396da0086dc70b935c530cb578e37adc6d354f7ad2037fee83b"
$PlatformIOInstallerUrl = "https://raw.githubusercontent.com/platformio/platformio-core-installer/7d1203d1a6d075a2cb560295888e23bc43c12abb/get-platformio.py"
$PlatformIOInstallerSha256 = "068d5dca983b22ed36a00dea7d42e58b646f0ac495885892f5746357f39a0470"
$Cp210xDriverUrl = "https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers"

if (-not $ProjectDir) {
  $ProjectDir = Join-Path $PSScriptRoot "ignitron firmware"
}
$ProjectDir = [System.IO.Path]::GetFullPath($ProjectDir)
$LogRoot = Join-Path $env:LOCALAPPDATA "Ignitron Preset Tools\Logs"
New-Item -ItemType Directory -Force -Path $LogRoot | Out-Null
$LogPath = Join-Path $LogRoot ("windows-programming-setup-{0}.log" -f (Get-Date -Format "yyyyMMdd-HHmmss"))

function Write-Setup {
  param([string]$Message, [ValidateSet("INFO", "OK", "WARN", "ERROR")][string]$Level = "INFO")
  $line = "[{0}] {1}" -f $Level, $Message
  Write-Host $line
  Add-Content -LiteralPath $LogPath -Value $line -Encoding UTF8
}

function Confirm-SetupAction {
  param([string]$Prompt)
  if ($NonInteractive) { return [bool]$InstallMissing }
  $answer = Read-Host "$Prompt [Y/n]"
  return -not ($answer -match "^(n|no)$")
}

function Invoke-SetupCommand {
  param([string]$FilePath, [string[]]$ArgumentList)
  Write-Setup ("Running: {0} {1}" -f $FilePath, ($ArgumentList -join " "))
  & $FilePath @ArgumentList 2>&1 | ForEach-Object {
    Write-Host $_
    Add-Content -LiteralPath $LogPath -Value ([string]$_) -Encoding UTF8
  }
  return $LASTEXITCODE
}

function Get-PythonRuntime {
  $candidates = @()
  $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
  if ($launcher) {
    $candidates += [pscustomobject]@{ Exe = $launcher.Source; PrefixArgs = @("-3") }
  }
  $python = Get-Command python.exe -ErrorAction SilentlyContinue
  if ($python) {
    $candidates += [pscustomobject]@{ Exe = $python.Source; PrefixArgs = @() }
  }
  $pythonRoots = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Python"),
    $env:ProgramFiles,
    ${env:ProgramFiles(x86)}
  ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
  foreach ($pythonRoot in $pythonRoots) {
    Get-ChildItem -LiteralPath $pythonRoot -Filter "Python*" -Directory -ErrorAction SilentlyContinue |
      Sort-Object FullName -Descending | ForEach-Object {
        $knownPython = Join-Path $_.FullName "python.exe"
        if (Test-Path -LiteralPath $knownPython) {
          $candidates += [pscustomobject]@{ Exe = $knownPython; PrefixArgs = @() }
        }
      }
  }
  foreach ($candidate in $candidates) {
    try {
      $arguments = @($candidate.PrefixArgs) + @("-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))")
      $versionText = (& $candidate.Exe @arguments 2>$null | Select-Object -Last 1).Trim()
      $version = [version]$versionText
      if ($version -ge [version]"3.9") {
        return [pscustomobject]@{ Exe = $candidate.Exe; PrefixArgs = @($candidate.PrefixArgs); Version = $version }
      }
    } catch { }
  }
  return $null
}

function Get-PlatformIOExecutable {
  $candidates = @()
  $settingsPath = Join-Path $env:APPDATA "Ignitron Preset Tools\settings.json"
  if (Test-Path -LiteralPath $settingsPath) {
    try {
      $savedSettings = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
      if ($savedSettings.platformio_executable) { $candidates += [string]$savedSettings.platformio_executable }
    } catch { }
  }
  if ($env:PLATFORMIO_CORE_DIR) {
    $candidates += Join-Path $env:PLATFORMIO_CORE_DIR "penv\Scripts\platformio.exe"
    $candidates += Join-Path $env:PLATFORMIO_CORE_DIR "penv\Scripts\pio.exe"
  }
  $candidates += @(
    (Join-Path $env:USERPROFILE ".platformio\penv\Scripts\platformio.exe"),
    (Join-Path $env:USERPROFILE ".platformio\penv\Scripts\pio.exe")
  )
  foreach ($name in @("platformio.exe", "pio.exe")) {
    $command = Get-Command $name -ErrorAction SilentlyContinue
    if ($command) { $candidates += $command.Source }
  }
  foreach ($candidate in $candidates | Select-Object -Unique) {
    if (-not (Test-Path -LiteralPath $candidate)) { continue }
    try {
      $versionText = (& $candidate --version 2>$null | Select-Object -Last 1)
      if ($LASTEXITCODE -eq 0 -and $versionText) {
        return [pscustomobject]@{ Exe = [System.IO.Path]::GetFullPath($candidate); Version = $versionText.Trim() }
      }
    } catch { }
  }
  return $null
}

function Get-VerifiedDownload {
  param([string]$Url, [string]$Sha256, [string]$Destination)
  Write-Setup "Downloading $Url"
  Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
  $actual = (Get-FileHash -LiteralPath $Destination -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($actual -ne $Sha256.ToLowerInvariant()) {
    Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
    throw "Downloaded file failed its SHA-256 integrity check. Expected $Sha256; received $actual."
  }
  Write-Setup "Download integrity verified." "OK"
}

function Install-PythonRuntime {
  $temporaryRoot = Join-Path $env:TEMP "ignitron-programming-setup"
  New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null
  $installer = Join-Path $temporaryRoot "python-$PythonVersion-amd64.exe"
  Get-VerifiedDownload $PythonUrl $PythonSha256 $installer
  Write-Setup "Installing Python $PythonVersion for the current Windows user."
  $process = Start-Process -FilePath $installer -ArgumentList @(
    "/passive", "InstallAllUsers=0", "PrependPath=1", "Include_test=0",
    "Include_launcher=1", "InstallLauncherAllUsers=0", "Shortcuts=0"
  ) -Wait -PassThru
  if ($process.ExitCode -notin @(0, 3010)) {
    throw "Python installer exited with code $($process.ExitCode)."
  }
}

function Install-PlatformIOCore {
  param($PythonRuntime)
  $temporaryRoot = Join-Path $env:TEMP "ignitron-programming-setup"
  New-Item -ItemType Directory -Force -Path $temporaryRoot | Out-Null
  $installer = Join-Path $temporaryRoot "get-platformio.py"
  Get-VerifiedDownload $PlatformIOInstallerUrl $PlatformIOInstallerSha256 $installer
  Write-Setup "Installing PlatformIO Core with PlatformIO's official installer."
  $arguments = @($PythonRuntime.PrefixArgs) + @($installer)
  $exitCode = Invoke-SetupCommand $PythonRuntime.Exe $arguments
  if ($exitCode -ne 0) { throw "PlatformIO installer exited with code $exitCode." }
}

function Test-UsbSerialSupport {
  $ports = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object)
  $cp210xDevices = @()
  try {
    $cp210xDevices = @(Get-CimInstance Win32_PnPEntity -ErrorAction Stop | Where-Object {
      $_.PNPDeviceID -match "VID_10C4&PID_EA60" -or $_.Name -match "CP210|Silicon Labs"
    })
  } catch {
    Write-Setup "Windows device status could not be queried: $($_.Exception.Message)" "WARN"
  }

  if ($cp210xDevices.Count -gt 0) {
    $unhealthy = @($cp210xDevices | Where-Object { $_.ConfigManagerErrorCode -notin @(0, $null) })
    if ($unhealthy.Count -gt 0) {
      Write-Setup "A Silicon Labs CP210x device was found, but Windows reports a driver/device error." "WARN"
      if (-not $NonInteractive -and (Confirm-SetupAction "Open the official Silicon Labs CP210x driver page?")) {
        Start-Process $Cp210xDriverUrl
      }
      return $false
    }
    Write-Setup ("Silicon Labs CP210x USB serial support is ready. COM ports: {0}" -f (($ports -join ", ") -replace "^$", "none currently assigned")) "OK"
    return $true
  }

  if ($ports.Count -gt 0) {
    Write-Setup ("Windows serial support is available. Detected ports: {0}. Connect the pedal to confirm its CP210x driver." -f ($ports -join ", ")) "OK"
  } else {
    Write-Setup "No USB serial pedal is currently detected. Driver verification is deferred until the pedal is plugged in." "WARN"
    Write-Setup "If it is not assigned a COM port, install the official Silicon Labs CP210x VCP driver: $Cp210xDriverUrl" "WARN"
  }
  return $true
}

function Save-IptProgrammingSettings {
  param([string]$PlatformIOPath)
  $settingsRoot = Join-Path $env:APPDATA "Ignitron Preset Tools"
  $settingsPath = Join-Path $settingsRoot "settings.json"
  $settings = @{}
  if (Test-Path -LiteralPath $settingsPath) {
    try {
      $parsed = Get-Content -LiteralPath $settingsPath -Raw | ConvertFrom-Json
      foreach ($property in $parsed.PSObject.Properties) { $settings[$property.Name] = $property.Value }
    } catch {
      throw "Existing IPT settings could not be read safely: $settingsPath"
    }
  }
  $settings["platformio_executable"] = $PlatformIOPath
  if (-not $settings.ContainsKey("ignitron_folder") -or -not $settings["ignitron_folder"]) {
    $settings["ignitron_folder"] = $ProjectDir
  } elseif ([System.IO.Path]::GetFullPath([string]$settings["ignitron_folder"]) -ne $ProjectDir) {
    if (-not $NonInteractive -and (Confirm-SetupAction "IPT already uses '$($settings['ignitron_folder'])'. Change it to this release's included firmware?")) {
      $settings["ignitron_folder"] = $ProjectDir
    } else {
      Write-Setup "Preserved the existing IPT firmware project selection." "OK"
    }
  }
  New-Item -ItemType Directory -Force -Path $settingsRoot | Out-Null
  $json = $settings | ConvertTo-Json -Depth 20
  [System.IO.File]::WriteAllText($settingsPath, $json, [System.Text.UTF8Encoding]::new($false))
  Write-Setup "Saved the verified PlatformIO executable for IPT." "OK"
}

function Invoke-ProgrammingBuildCheck {
  param([string]$PlatformIOPath)
  if (-not (Test-Path -LiteralPath (Join-Path $ProjectDir "platformio.ini"))) {
    throw "The selected Ignitron folder is not a PlatformIO project: $ProjectDir"
  }
  Write-Setup "Building Ignitron firmware (no flash will be performed)."
  $exitCode = Invoke-SetupCommand $PlatformIOPath @("run", "--project-dir", $ProjectDir, "-e", "esp32dev")
  if ($exitCode -ne 0) { throw "Firmware build check failed with code $exitCode." }
  Write-Setup "Building the Ignitron filesystem image (no flash will be performed)."
  $exitCode = Invoke-SetupCommand $PlatformIOPath @("run", "--project-dir", $ProjectDir, "-e", "esp32dev", "-t", "buildfs")
  if ($exitCode -ne 0) { throw "Filesystem build check failed with code $exitCode." }
  Write-Setup "Firmware and filesystem build checks passed." "OK"
}

function Invoke-SelfTest {
  foreach ($url in @($PythonUrl, $PlatformIOInstallerUrl, $Cp210xDriverUrl)) {
    $uri = [uri]$url
    if ($uri.Scheme -ne "https") { throw "Setup download URL is not HTTPS: $url" }
  }
  if (([uri]$PythonUrl).Host -ne "www.python.org") { throw "Unexpected Python download host." }
  if (([uri]$PlatformIOInstallerUrl).Host -ne "raw.githubusercontent.com") { throw "Unexpected PlatformIO installer host." }
  foreach ($hash in @($PythonSha256, $PlatformIOInstallerSha256)) {
    if ($hash -notmatch "^[0-9a-f]{64}$") { throw "Invalid pinned SHA-256 value." }
  }
  if ([version]$PythonVersion -lt [version]"3.9") { throw "Pinned Python does not meet PlatformIO's minimum." }
  if (-not [System.IO.Path]::IsPathRooted($ProjectDir)) { throw "Project path was not normalized." }
  Write-Setup "Windows programming setup self-test passed." "OK"
}

try {
  Write-Setup "Ignitron Windows programming setup"
  Write-Setup "Project: $ProjectDir"
  if ($SelfTest) {
    Invoke-SelfTest
    Write-Setup "Log: $LogPath"
    exit 0
  }

  $pythonRuntime = Get-PythonRuntime
  if (-not $pythonRuntime) {
    Write-Setup "Python 3.9 or newer was not found." "WARN"
    if ($CheckOnly -or -not (Confirm-SetupAction "Install the supported per-user Python $PythonVersion runtime?")) {
      throw "Python 3.9 or newer is required. Run this setup again and allow installation."
    }
    Install-PythonRuntime
    $pythonRuntime = Get-PythonRuntime
    if (-not $pythonRuntime) { throw "Python installation completed, but no supported runtime could be verified." }
  }
  Write-Setup ("Python {0}: {1}" -f $pythonRuntime.Version, $pythonRuntime.Exe) "OK"

  $platformIO = Get-PlatformIOExecutable
  if (-not $platformIO) {
    Write-Setup "PlatformIO Core was not found." "WARN"
    if ($CheckOnly -or -not (Confirm-SetupAction "Install PlatformIO Core for the current user?")) {
      throw "PlatformIO Core is required. Run this setup again and allow installation."
    }
    Install-PlatformIOCore $pythonRuntime
    $platformIO = Get-PlatformIOExecutable
    if (-not $platformIO) { throw "PlatformIO installation completed, but its executable could not be verified." }
  }
  Write-Setup ("{0}: {1}" -f $platformIO.Version, $platformIO.Exe) "OK"

  $usbReady = Test-UsbSerialSupport
  if (-not $usbReady) {
    throw "Windows has not finished configuring the connected USB serial device. Install or repair the CP210x driver, reconnect the pedal, and rerun setup."
  }
  if (-not $CheckOnly) { Save-IptProgrammingSettings $platformIO.Exe }
  if (-not $SkipBuild) { Invoke-ProgrammingBuildCheck $platformIO.Exe }

  Write-Setup "Windows programming setup is ready. IPT can now build and flash the pedal." "OK"
  Write-Setup "Log: $LogPath"
  if (-not $NonInteractive) { [void](Read-Host "Press Enter to close") }
  exit 0
} catch {
  Write-Setup $_.Exception.Message "ERROR"
  Write-Setup "Setup did not change or flash pedal firmware. Review the log: $LogPath" "ERROR"
  if (-not $NonInteractive) { [void](Read-Host "Press Enter to close") }
  exit 1
}
