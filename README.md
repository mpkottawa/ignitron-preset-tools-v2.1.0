# Ignitron Preset Tools 2.1.01
*Shoutout to stangreg for this great project `https://github.com/stangreg/Ignitron` *
**This has not been tested out on mac**

<img width="1024" height="1024" alt="IPT" src="https://github.com/mpkottawa/ignitron-preset-tools/blob/main/Ignitron%20preset%20tools%20logo.png" />

Ignitron Preset Tools (IPT) is a desktop control center for building Ignitron preset banks, flashing firmware and filesystem data, remotely selecting Spark presets, backing up pedal presets, capturing presets from the Spark app, and playing backing tracks. This repository and its native packages provide **v2.1.01**, a maintenance release for Linux playback, USB connections, capture, backups and installation.

## Supported platforms

| Platform | Native release | Serial device example | Status |
|---|---|---|---|
| Windows 10/11 x64 | ZIP containing `.exe` | `COM7` | Primary, tested |
| macOS Apple Silicon | ZIP containing `.app` | `/dev/cu.usbserial-*` | Native CI build |
| macOS Intel | ZIP containing `.app` | `/dev/cu.usbserial-*` | Native CI build |
| Linux x64 | `.tar.gz` with user installer | `/dev/ttyUSB0` | Native CI build |
| Linux ARM64 | `.tar.gz` with user installer | `/dev/ttyUSB0` | Native CI build |

Other Unix-like systems may work from source when Python, Tk, pyserial, VLC, and PlatformIO are available, but the five targets above are the supported release set. PyInstaller packages are built natively on each operating system; they are not cross-compiled.

## What is included

Each native download contains the IPT application, documentation, reference material, and two firmware projects:

- **`ignitron firmware`** is the ready-to-build IPT v2.1.01 firmware with the current serial features and prepared preset library. In the GitHub source tree the same project is named **`Ignitron`**.
- **`Ignitron 1.9.0`** is the earlier firmware kept as a clean fallback. It does not have IPT v2.1 support unless you deliberately inject that support into this copy.

Both projects are sanitized for release: saved host serial ports, build caches, backups, logs, captures, and local paths are excluded. See [FIRMWARE.md](FIRMWARE.md) before flashing, especially if the pedal does not use the default SH1106 display.

## Downloads and first launch

### Windows

Download `Ignitron.Preset.Tools.v2.1.01.Windows-x64.zip`, extract it, and run `Ignitron Preset Tools v2.1.01.exe`. If Windows SmartScreen appears on the unsigned build, choose **More info > Run anyway**.

### macOS

Download the package matching the Mac:

- `macOS-arm64.zip` for Apple Silicon (M1 and newer).
- `macOS-x64.zip` for Intel Macs.

Extract it and move `Ignitron Preset Tools v2.1.01.app` to Applications. Unsigned builds may require Control-clicking the app and choosing **Open** once. Signing and notarization with an Apple Developer ID removes that warning for a public Mac distribution.

### Linux

Follow [the step-by-step Linux installation PDF](Linux-Install-Guide.pdf) for v2.1.01. The guide includes exact download/checksum commands, first-run prerequisites, local music and optional NAS setup, and a recoverable clean-retest procedure.

The IPT installer installs the desktop application and the two firmware projects for the current user. It **does not install PlatformIO Core or VLC**. Install those system prerequisites first.

Fedora:

```bash
sudo dnf install curl python3 vlc
```

Ubuntu/Debian:

```bash
sudo apt update
sudo apt install curl python3 python3-venv vlc
```

`python3-tkinter` (Fedora) or `python3-tk` (Ubuntu/Debian) is additionally required only when running IPT from source; the native package includes its Python/Tk runtime.

Download the archive matching the computer. For an x64 download in the normal Downloads folder, extract and install it with:

```bash
cd "$HOME/Downloads"
tar -xzf "Ignitron.Preset.Tools.v2.1.01.Linux-x64.tar.gz"
cd "Ignitron Preset Tools v2.1.01 Linux-x64"
chmod +x install_linux.sh
./install_linux.sh
```

For ARM64, use `Linux-arm64` in the archive and directory names. The installer copies IPT to `~/.local/share/ignitron-preset-tools`, adds an application-menu entry, and creates `~/.local/bin/ignitron-preset-tools`. Upgrades preserve existing firmware projects, presets, captures and backups. Fresh firmware templates are installed separately for the IPT Setup actions. Close IPT before upgrading. The uninstaller removes the app but keeps working projects and settings; `./uninstall_linux.sh --purge` explicitly deletes the working projects, captures and backups too (settings remain). Do not run IPT or its installer as root.

#### Install PlatformIO Core

Use PlatformIO's official per-user installer; `sudo` is not needed:

```bash
cd "$HOME/Downloads"
curl -fsSL -o get-platformio.py \
  https://raw.githubusercontent.com/platformio/platformio-core-installer/master/get-platformio.py
python3 get-platformio.py
"$HOME/.platformio/penv/bin/platformio" --version
```

The last command must print a PlatformIO Core version. Restart IPT after installation. A desktop app launched from the application menu may not inherit shell `PATH`, so print the executable's absolute path:

```bash
readlink -f "$HOME/.platformio/penv/bin/platformio"
```

In **Firmware > Show setup**, browse to the full path printed by that command. No shell `PATH` change is required after this file is selected in IPT.

#### Give the user USB serial permission

Install PlatformIO's current udev rules on both Fedora and Ubuntu/Debian:

```bash
curl -fsSL \
  https://raw.githubusercontent.com/platformio/platformio-core/develop/platformio/assets/system/99-platformio-udev.rules \
  | sudo tee /etc/udev/rules.d/99-platformio-udev.rules >/dev/null
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Unplug and reconnect the pedal, then confirm that PlatformIO can see it:

```bash
"$HOME/.platformio/penv/bin/platformio" device list
```

If the port is present but permission is denied, inspect the real device and the user's current groups:

```bash
ls -l /dev/ttyUSB0       # use /dev/ttyACM0 instead when that is the reported port
id -nG
```

Only if the device is owned by a normal serial-access group that is not already listed, add the user to that actual group (commonly `dialout`, `plugdev`, or `uucp`), then sign out and back in. Do not add the user to `root`.

```bash
sudo usermod -aG ACTUAL_DEVICE_GROUP "$USER"
```

#### Select and build the firmware before flashing

Open IPT and select the installed current project:

```text
~/.local/share/ignitron-preset-tools/ignitron firmware
```

This is the IPT v2.1.01 firmware. The neighboring `Ignitron 1.9.0` folder is the unmodified fallback and should be selected only when that older baseline is intentional. In **Firmware > Show setup**, select `esp32dev`, the detected `/dev/ttyUSB*` or `/dev/ttyACM*` port, and the PlatformIO executable above.

For optional troubleshooting, build firmware and filesystem without uploading to the pedal:

```bash
cd "$HOME/.local/share/ignitron-preset-tools/ignitron firmware"
"$HOME/.platformio/penv/bin/platformio" run -e esp32dev
"$HOME/.platformio/penv/bin/platformio" run -e esp32dev -t buildfs
```

These terminal checks are optional diagnostics; **Build + Flash FW + FS** runs both builds before any requested erase. If you run the checks separately, both must finish with `SUCCESS`. Then return to IPT, review the OLED/battery/hardware settings, confirm the USB port, and click **Build + Flash FW + FS**. The combined action saves the displayed settings before it builds and uploads.

#### Linux troubleshooting

| Symptom | Action |
|---|---|
| PlatformIO executable not found | Re-run the version command above, restart IPT, and browse to the full `~/.platformio/penv/bin/platformio` path. |
| Permission denied opening the port | Reinstall/reload the udev rules, reconnect USB, inspect the device owner/group, and sign out/in after any group change. Never run IPT as root. |
| No serial port appears | Reconnect the pedal, run `platformio device list`, try another data-capable USB cable/port, and check `dmesg --follow` while reconnecting. |
| Port is busy | Close serial monitors and other IPT instances; use `fuser -v /dev/ttyUSB0` (or the actual port) to identify the process holding it. |
| PlatformIO dependency download fails | Confirm internet/DNS access and retry the build. PlatformIO downloads the ESP32 platform and libraries on the first build. |
| Backing Tracks says VLC could not start | Fedora: `sudo dnf install vlc`; Ubuntu/Debian: `sudo apt install vlc`; then restart IPT. The Linux package uses the distribution's matched libVLC core and plugins. |

## Hardware and optional software

- Ignitron pedal connected by USB.
- Spark amp connected to Ignitron for Pedal Remote, Spark Capture, hardware-preset control, or Spark 2 looper features.
- [PlatformIO Core](https://platformio.org/install/cli) for firmware builds and uploads. IPT finds `platformio`/`pio` on `PATH` and also checks the normal per-user PlatformIO virtual environment.
- [VLC](https://www.videolan.org/vlc/) for backing-track playback. On Linux, install VLC from the same distribution as the operating system; the IPT package intentionally does not bundle another distribution's libVLC core/plugins.
- A Silicon Labs CP210x driver if the operating system does not already expose the pedal as a serial device.

## Running from source

Install Python 3.10 or newer and the requirements:

```bash
python3 -m pip install -r requirements.txt
```

Launch with the platform helper:

```text
Windows:  Run IPT 2.1.bat
macOS:    Run IPT 2.1.command
Linux:    ./run_ipt_2.1.sh
```

Or run `python3 ignitron_preset_tools_v2.1.py` directly. On Windows, `py -3 ignitron_preset_tools_v2.1.py` also works.

## First-time firmware setup

1. Open IPT and select an Ignitron PlatformIO firmware folder on the Dashboard.
2. If required support is missing, open **Firmware > IPT 2.1 Setup** and apply the selected changes.
3. Open **Firmware**, choose the PlatformIO environment and detected serial port.
4. Click **Build + Flash FW + FS**.

For the normal v2.1.01 setup, select the bundled `ignitron firmware` folder (`Ignitron` when running from source). Select `Ignitron 1.9.0` only when you intentionally want the fallback release.

The persistent **Pedal USB** control in the very top-right of the page header is the single serial-port selector for the whole app. IPT watches for newly connected USB serial devices and asks whether the detected device is the Ignitron pedal. Confirming a port applies it immediately to Firmware, Pedal Remote, Spark Capture, and every other serial tool, then writes `upload_port` to the selected/default PlatformIO environment. The status indicator shows **Disconnected**, **USB ready**, or **Connected**. Use **Scan USB** or choose a different port manually at any time.

The main button first applies the displayed firmware version and every selected **Apply on Save / Flash** settings group, then reads the project configuration back and verifies it before PlatformIO starts. A mismatch stops the flash instead of compiling stale settings. It also writes the selected environment/port/speed to `platformio.ini`, optionally cleans, builds both firmware and filesystem, then optionally erases and uploads firmware and filesystem data. The reliable default upload speed is `460800`; serial control features use `115200`.

The release firmware includes its prepared preset library. You can replace or reorganize it in **Preset Builder** before a filesystem upload. The bundled 1.9.0 folder is kept separate so current changes never overwrite the fallback unless you explicitly select and edit it.

## Main sections

### Preset Builder

- Load JSON preset files and arrange them into pedal banks.
- Drag or double-click presets into bank slots.
- Save `PresetList.txt`, `PresetListUUIDs.txt`, preset JSON, and `PresetList.pdf` to the selected firmware project's `data` folder.
- The layout visible in the builder is saved automatically before a combined flash.

### Firmware

- **Build + Flash FW + FS** performs the complete pedal update.
- Firmware-only and filesystem-only actions are also available.
- The PlatformIO terminal opens for build, upload, and monitor tasks.
- **Build + Flash FW + FS** writes and reads back every value currently shown in the Firmware tab before compiling. The lower IPT 2.1 setup selections are also used by **Apply selected changes**; clicking **Save settings** first is not required.
- The Hardware tab includes **Restore stock**, which restores and immediately saves the factory Ignitron GPIO mapping and hardware options, then turns mapping protection back on. Stock defaults are maintained in one registry so future Hardware-tab settings can participate in the same reset.
- IPT only prompts to inject required 2.1 support when it is not already detected.
- OLED, battery, GPIO, blocklist, dedicated LED, and timing options remain independently selectable.
- The Battery section includes an optional **Display Spark 2 battery when connected** setting. It keeps the configured pedal battery as the primary reading, adds Spark 2 telemetry only while a Spark 2 is connected, and automatically retains the normal single-battery layout for other amps.
- AMP blocklist requests use the address from the most recent confirmed connection during the current boot, avoiding false disconnect reports from Spark MINI during the long button hold. Multiple amps can remain blocked together, and block/unblock screens show both the detected Spark model and its Bluetooth address. While disconnected at the Ignitron logo, hold Bank Up + Bank Down for two seconds to open or close the blocked-amp list and use Bank Up/Down to select an entry. Press Preset 4 once to show the `YOU SURE?` confirmation, then press Preset 4 again to unblock it. Moving to another entry or leaving the menu cancels the confirmation. Holding Bank Up + Bank Down during boot still clears the entire list.

### Pedal Remote

- Select presets from the bank grid and see the current preset.
- Select/store Spark hardware presets and use Spark 2 looper controls.
- Display tuner readings when the firmware enters tuner mode.
- Open the serial terminal or Backing Tracks window without losing the preset grid.

### Spark Capture

Spark Capture requests one-shot AMP mode in software. The request is consumed on the capture boot. Ending capture, losing the USB heartbeat, holding the normal reset control, or power-cycling returns the pedal to normal APP mode.

- Capture presets sent by the Spark app.
- Pull the presets referenced by the pedal's PresetList.txt, or its full preset library. **Pull listed presets** includes every listed bank; it is not limited to the four slots currently selected on the pedal.
- Save presets as JSON in a timestamped capture folder. Different presets with the same name receive a filename suffix; edited versions of the same UUID are preserved. Repeated identical captures are skipped.
- Capture startup verifies the pedal in the background. End Connection cancels startup or exits temporary AMP mode. Routine heartbeat replies are hidden from the activity log.

### Backing Tracks

The player understands `Artist > Album > Track` folder layouts and provides collapsed browsing, artist filtering, full-library search, favorites, seeking, transport controls, and volume. Playback uses the native VLC engine.

### Reference

The Reference page contains the ESP32/Ignitron pin mapping, firmware notes, hardware profile, and wiring guidance.

## User data locations

IPT never needs to save settings beside the executable. Existing legacy settings are migrated once.

| Platform | Settings and favorites |
|---|---|
| Windows | `%APPDATA%\Ignitron Preset Tools` |
| macOS | `~/Library/Application Support/Ignitron Preset Tools` |
| Linux | `$XDG_CONFIG_HOME/ignitron-preset-tools` or `~/.config/ignitron-preset-tools` |

Set `IGNITRON_CONFIG_DIR` to use a custom location. Release packages exclude settings, window geometry, recent folders, backups, captured presets, logs, and personal firmware data.

## Building native releases

Install the requirements, then run the native builder on the target OS:

```text
Windows:  .\build_release.ps1
macOS:    ./build_release_mac.sh
Linux:    ./build_release_linux.sh
```

The builders:

- create a native PyInstaller application;
- stage both the sanitized IPT v2.1.01 firmware project and the Ignitron 1.9.0 fallback, with preset data but no saved host serial port;
- run a privacy check against the finished package;
- name the archive with its operating system and CPU architecture.

`build_release_mac.sh` creates an `.icns` icon from `IPT.ico`. Set `MACOS_CODESIGN_IDENTITY` to a Developer ID Application identity when building a signed Mac app. Notarization still requires the normal Apple credential submission after signing.

The GitHub Actions workflow builds and tests Windows x64, macOS ARM64, macOS Intel, Linux x64, and Linux ARM64. Tag `v2.1.01` publishes this maintenance release. Keep previous release tags available when publishing later versions. Manual workflow runs can build artifacts without publishing.

## Release privacy

`release_tools.py` is shared by every native builder. It removes generated folders, settings, backups, captures, documentation build output, and machine-specific state while preserving the release preset libraries. It then rejects staged packages containing Windows, macOS, or Linux user-directory paths, OneDrive paths, private network-share paths, app settings, or favorites.

To audit a staged folder manually:

```bash
python3 release_tools.py verify "path/to/package"
```

To create a clean GitHub source tree in an empty folder:

```bash
python3 release_tools.py stage-source "path/to/working-folder" "path/to/github-release-folder"
```

The command uses an explicit source allowlist and refuses to overwrite a non-empty destination.

## License and repository

IPT is released under the BSD 3-Clause License. Bundled Ignitron firmware retains its own BSD license and copyright notices.

[github.com/mpkottawa/ignitron-preset-tools-v2.1.0](https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0)
