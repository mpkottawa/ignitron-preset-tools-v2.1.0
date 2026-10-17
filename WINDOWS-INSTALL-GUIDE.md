# Windows installation and pedal-programming setup

## Recommended installation

1. Download the release asset ending in `Windows-x64-Setup.exe`.
2. Run it and keep the default per-user install folder.
3. Leave **Check and install pedal programming requirements** selected on the final page.
4. Allow Windows Programming Setup to install Python or PlatformIO Core if either is missing.
5. Wait for both the firmware and filesystem build checks to pass. These checks do not flash the pedal.
6. Open IPT, select the included `ignitron firmware` folder, review its display and hardware settings, and flash only when ready.

The installer does not need administrator access. Python and PlatformIO are installed only for the current Windows user. The Silicon Labs USB driver is a separate, signed hardware driver and may require administrator approval if Windows has not already installed it.

The default folder includes the installed version, for example `Ignitron Preset Tools v2.1.04`. When Setup detects an installer-based earlier release, it displays both paths and proposes a sibling folder carrying the new version number. During the upgrade it renames the previous installation folder, backs up the bundled firmware projects under its timestamped `firmware backups` folder, and installs fresh release copies. Use **Back** to choose another empty destination if needed. IPT settings stored under `%APPDATA%` are preserved.

## What is checked

- Python 3.9 or newer. If missing, setup offers the pinned 64-bit Python runtime from `python.org`.
- PlatformIO Core. If missing, setup runs PlatformIO's pinned official installer script.
- A usable Windows serial/COM subsystem and the status of a connected Silicon Labs CP210x adapter.
- A complete included PlatformIO project.
- A successful `esp32dev` firmware build and LittleFS filesystem build.

Downloads made by the helper use HTTPS and a pinned SHA-256 digest. IPT remembers the verified PlatformIO executable. If IPT already points at another firmware project, setup preserves that selection unless you explicitly approve changing it.

## Portable ZIP

The portable ZIP contains the same application and firmware but does not add Start-menu shortcuts. Extract the entire ZIP, then run `Ignitron Preset Tools v<version>.exe`. To configure programming, right-click `windows_programming_setup.ps1` and choose **Run with PowerShell**.

Do not run IPT or its setup helper from inside Windows Explorer's ZIP preview.

## USB driver troubleshooting

With the pedal connected, Windows should assign it a COM port, commonly through a Silicon Labs CP210x USB-to-UART bridge. Use a data-capable USB cable and try another direct USB port before changing drivers.

If Device Manager shows the CP210x device with an error or no COM port, install the official driver from:

<https://www.silabs.com/software-and-tools/usb-to-uart-bridge-vcp-drivers>

Disconnect and reconnect the pedal after installation, select **Scan USB** in IPT, and confirm the detected port before flashing.

## Rerun or diagnose setup

Use **Start > Ignitron Preset Tools v<version> > Windows Programming Setup** to verify or repair the programming tools later. Logs are stored at:

```text
%LOCALAPPDATA%\Ignitron Preset Tools\Logs
```

The following commands are optional diagnostics from PowerShell:

```powershell
& "$HOME\.platformio\penv\Scripts\platformio.exe" --version
& "$HOME\.platformio\penv\Scripts\platformio.exe" device list
```

To verify requirements without installing anything or changing IPT settings:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\windows_programming_setup.ps1 -CheckOnly -SkipBuild -NonInteractive
```

To include the firmware and filesystem build checks, omit `-SkipBuild`.

## Safety and upgrades

- Setup checks and builds, but never flashes or erases the pedal.
- Flashing remains an explicit action in IPT.
- Setup detects an earlier installer-based release, renames its installation folder for the new version, and updates it; portable copies remain independent.
- Existing IPT settings and custom firmware-folder choices are preserved.
- Uninstalling IPT does not remove the shared settings stored under `%APPDATA%\Ignitron Preset Tools`.
