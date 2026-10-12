# Ignitron Preset Tools 2.1.00
*Shoutout to stangreg for this great project `https://github.com/stangreg/Ignitron` *
<img width="1024" height="1024" alt="IPT" src="https://github.com/mpkottawa/ignitron-preset-tools/blob/main/Ignitron%20preset%20tools%20logo.png" />

Ignitron Preset Tools (IPT) is a desktop control center for building Ignitron preset banks, flashing firmware and filesystem data, remotely selecting Spark presets, backing up pedal presets, capturing presets from the Spark app, and playing backing tracks. This repository and its native packages are the first public **v2.1.00** release.

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

- **`ignitron firmware`** is the ready-to-build IPT v2.1.00 firmware with the current serial features and prepared preset library. In the GitHub source tree the same project is named **`Ignitron`**.
- **`Ignitron 1.9.0`** is the earlier firmware kept as a clean fallback. It does not have IPT v2.1 support unless you deliberately inject that support into this copy.

Both projects are sanitized for release: saved host serial ports, build caches, backups, logs, captures, and local paths are excluded. See [FIRMWARE.md](FIRMWARE.md) before flashing, especially if the pedal does not use the default SH1106 display.

## Downloads and first launch

### Windows

Download `Ignitron Preset Tools v2.1.00 Windows-x64.zip`, extract it, and run `Ignitron Preset Tools v2.1.00.exe`. If Windows SmartScreen appears on the unsigned build, choose **More info > Run anyway**.

### macOS

Download the package matching the Mac:

- `macOS-arm64.zip` for Apple Silicon (M1 and newer).
- `macOS-x64.zip` for Intel Macs.

Extract it and move `Ignitron Preset Tools v2.1.00.app` to Applications. Unsigned builds may require Control-clicking the app and choosing **Open** once. Signing and notarization with an Apple Developer ID removes that warning for a public Mac distribution.

### Linux

Download the archive matching the computer, extract it, then run:

```bash
chmod +x install_linux.sh
./install_linux.sh
```

This installs only for the current user, adds an application-menu entry, and adds `ignitron-preset-tools` to `~/.local/bin`. `uninstall_linux.sh` removes the application but deliberately keeps user settings.

On Debian or Ubuntu, install the native runtime dependencies with:

```bash
sudo apt update
sudo apt install python3-tk vlc
```

For access to CP210x/CH340 serial adapters, install PlatformIO's udev rules or add the current user to the serial-device group used by the distribution (commonly `dialout`), then sign out and back in:

```bash
sudo usermod -a -G dialout "$USER"
```

Do not run IPT as root.

## Hardware and optional software

- Ignitron pedal connected by USB.
- Spark amp connected to Ignitron for Pedal Remote, Spark Capture, hardware-preset control, or Spark 2 looper features.
- [PlatformIO Core](https://platformio.org/install/cli) for firmware builds and uploads. IPT finds `platformio`/`pio` on `PATH` and also checks the normal per-user PlatformIO virtual environment.
- [VLC](https://www.videolan.org/vlc/) for backing-track playback. Install the native VLC build matching the app architecture.
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

For the normal v2.1.00 setup, select the bundled `ignitron firmware` folder (`Ignitron` when running from source). Select `Ignitron 1.9.0` only when you intentionally want the fallback release.

The persistent **Pedal USB** control in the very top-right of the page header is the single serial-port selector for the whole app. IPT watches for newly connected USB serial devices and asks whether the detected device is the Ignitron pedal. Confirming a port applies it immediately to Firmware, Pedal Remote, Spark Capture, and every other serial tool, then writes `upload_port` to the selected/default PlatformIO environment. The status indicator shows **Disconnected**, **USB ready**, or **Connected**. Use **Scan USB** or choose a different port manually at any time.

The main button first applies the displayed firmware version and every selected **Apply on Save / Flash** settings group, then reads the project configuration back and verifies it before PlatformIO starts. A mismatch stops the flash instead of compiling stale settings. It also writes the selected environment/port/speed to `platformio.ini`, optionally cleans and erases, uploads firmware, builds the filesystem, and uploads filesystem data. The reliable default upload speed is `460800`; serial control features use `115200`.

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
- Pull the active pedal bank or full pedal library.
- Save unique presets as JSON in a timestamped backup folder.

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
- stage both the sanitized IPT v2.1.00 firmware project and the Ignitron 1.9.0 fallback, with preset data but no saved host serial port;
- run a privacy check against the finished package;
- name the archive with its operating system and CPU architecture.

`build_release_mac.sh` creates an `.icns` icon from `IPT.ico`. Set `MACOS_CODESIGN_IDENTITY` to a Developer ID Application identity when building a signed Mac app. Notarization still requires the normal Apple credential submission after signing.

The GitHub Actions workflow builds and tests Windows x64, macOS ARM64, macOS Intel, Linux x64, and Linux ARM64. Tag `v2.1.00` publishes the first release; later fixes can use `v2.1.1`, `v2.1.2`, and so on. Manual workflow runs can build artifacts without publishing.

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
