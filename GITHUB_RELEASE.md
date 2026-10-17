# Ignitron Preset Tools v2.1.04

## Windows setup, clearer flashing, and SSD1309 cold-start fix - 2026-10-16

This maintenance release adds an easy Windows installer and programming-requirement setup, labels the Firmware actions with what each one changes, and fixes unreliable cold starts on 2.42-inch SSD1309 displays.

- Windows users can choose the new `Windows-x64-Setup.exe`, which installs IPT per user, detects an earlier installer release, preserves settings, backs up bundled firmware projects during upgrades, and optionally installs or verifies Python, PlatformIO Core, serial support, firmware builds, and filesystem builds without flashing the pedal. The portable ZIP remains available.
- Firmware action buttons now show concise descriptions: **firmware + banks**, **firmware only**, **checks preset data**, and **updates banks only**.
- SSD1309 startup now uses a real active-low reset pulse on GPIO5, I2C address `0x3C`, and `SSD1306_EXTERNALVCC`. SSD1306, SH1106, and SH1107 keep their previous reset and voltage behavior.
- IPT writes one canonical OLED-driver block and rejects missing or duplicate driver definitions before flashing.

The SSD1309 correction was compiled and flashed to a physical ESP32 pedal, then verified through repeated long power-off cold starts, ordinary resets, and short power cycles without static, vertical bars, flicker, brownouts, or reboot loops.

The application, Windows installer, five native packages, Linux all-in-one installer, and bundled current firmware are labelled **2.1.04**. Releases v2.1.00 through v2.1.03 remain available. Download the package for your platform and the v2.1.04 `SHA256SUMS.txt` together.

This release carries forward the v2.1.02 dedicated-preset-LED stability fix and every v2.1.01 Linux, USB, capture, backup, installer, and VLC improvement.

- Fixed Linux VLC discovery and a PipeWire crash when changing volume before playback. Added a real-audio-backend self-test.
- Added KDE Places folder selection, remembered music locations, and SMB access through the desktop credential/mount services.
- Fixed CP2102 serial control-line resets and kept a verified connection open for Pedal Remote. Orange preset highlighting now means selected only.
- Moved Capture connection work off the GUI thread and wait for the previous USB task to finish. Firmware tasks and app serial tools cannot share the port concurrently.
- Capture now decodes nested and inline preset JSON and preserves different presets with the same name. Routine keepalive messages no longer flood the log.
- Backups reuse the verified port, report interrupted or incomplete transfers, and use unique folders. **Pull listed presets** describes all filenames in PresetList.txt, rather than implying just the active bank.
- Linux upgrades and normal uninstalls preserve working projects, presets, captures and backups. Bundled firmware templates update separately. Settings writes are atomic.
- Both firmware and filesystem must build before an optional erase. Builder exports back up replaced preset JSON and reject ambiguous selected filenames.
- Added the revised **Linux-Install-Guide.pdf**, also available as a separate release download. Published filenames and checksum entries now match.

Close IPT before installing or upgrading. The SSD1309 and Android reconnect corrections have automated coverage and physical pedal validation. The carried-forward dedicated-LED correction still requires confirmation on a pedal fitted with the optional dedicated preset LEDs.

IPT v2.1.04 is the desktop control center for building Ignitron preset banks, installing IPT firmware support, flashing firmware/filesystem data, controlling presets over USB, backing up a pedal, capturing presets from the Spark app, and playing backing tracks.

## Native downloads

### Linux: installer included

1. Download **Linux-x64.tar.gz** for an Intel/AMD PC, or **Linux-arm64.tar.gz** for an ARM64 computer.
2. Extract the whole archive, open its folder, and double-click **Install Ignitron**. Choose Execute/Trust/Allow Launching if your desktop asks.
3. Enter your Linux password in the setup window and wait for **SETUP COMPLETE**. IPT opens automatically.

Keep the pedal unplugged during setup. The included all-in-one installer verifies the bundle and installs or locates native VLC/Python requirements, PlatformIO Core, USB permissions, and KDE Places/NAS helpers. It checks VLC playback and builds firmware/filesystem without flashing the pedal. It preserves existing projects and presets. Internet is needed for dependencies. Supports Fedora with dnf and Ubuntu/Debian with apt; VS Code is not required.

If the launcher opens as text, use **Open Terminal Here** inside the extracted folder and run `bash ./launch_linux_setup.sh`. Some desktops require marking the launcher executable or trusted first. See **START-HERE-Linux.txt** and the bundled **Linux-Install-Guide.pdf**.

Both Linux archives contain the installer, launcher, revised guide, and v2.1.04 application and firmware payloads. Use the v2.1.04 **SHA256SUMS.txt**.

The separate [Install-IPT-Linux.sh](https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0/releases/download/v2.1.04/Install-IPT-Linux.sh) remains available: download it into Downloads and run `bash "$HOME/Downloads/Install-IPT-Linux.sh"` for online setup.

### Individual platform packages

Choose the archive matching the operating system and CPU:

- `Ignitron.Preset.Tools.v2.1.04.Windows-x64-Setup.exe` (recommended Windows installer)
- `Ignitron.Preset.Tools.v2.1.04.Windows-x64.zip` (portable Windows package)
- `Ignitron.Preset.Tools.v2.1.04.macOS-arm64.zip` for Apple Silicon
- `Ignitron.Preset.Tools.v2.1.04.macOS-x64.zip` for Intel Macs
- `Ignitron.Preset.Tools.v2.1.04.Linux-x64.tar.gz`
- `Ignitron.Preset.Tools.v2.1.04.Linux-arm64.tar.gz`

Windows users should normally run the Setup executable; the ZIP remains available for portable use. Mac users extract the ZIP and move the app to Applications. Linux users use **Install Ignitron** inside the extracted folder. The `install_linux.sh` script remains an app-only/manual alternative after separately installing prerequisites.

The release workflow builds each application natively. It does not relabel a Windows executable for another operating system.

## Included firmware

- `ignitron firmware` is the ready-to-build IPT v2.1.04 project with Android reconnect support, the SSD1309 cold-start correction, the current feature set, and the prepared preset library.
- `Ignitron 1.9.0` is included separately as the earlier fallback firmware.

The current project defaults to the SH1106 1.3-inch OLED. Review OLED, battery, and GPIO settings before flashing hardware that differs from that profile. See `FIRMWARE.md` in the download for the short setup and recovery guide.

## Highlights

- Preset Bank Builder with generated preset list, UUID list, and PDF.
- One-button firmware plus filesystem build/flash workflow.
- Required IPT firmware support is offered only when missing.
- Hardware GPIO, OLED, battery, AMP blocklist, LED, and timing configuration.
- Pedal Remote with live preset switching, hardware slots, Spark 2 looper, and tuner display.
- Spark Capture with one-shot software AMP mode and automatic return to APP mode.
- Full-library and PresetList-based JSON backup.
- Backing-track library with VLC playback, search, favorites, and seeking.
- ESP32/Ignitron pin and hardware reference.
- Per-user settings in each operating system's standard configuration directory.

## Requirements

- PlatformIO Core for firmware or filesystem builds/uploads.
- VLC for backing-track playback.
- An operating-system serial driver for the pedal's USB-to-UART adapter when one is not already included.
- Linux serial-device permission through PlatformIO udev rules or the distribution's serial group.

## Firmware setup

1. Open IPT and select the Ignitron PlatformIO project.
2. If the Dashboard reports missing support, open **Firmware > IPT 2.1 Setup** and apply it.
3. Choose the PlatformIO environment and detected serial port.
4. Click **Build + Flash FW + FS**.

The default upload speed is `460800`; app serial controls use `115200`.

## Release hygiene

Every native builder uses the same release staging tool. Generated output, local settings, recent paths, window geometry, user home paths, network shares, backups, captures, logs, and other machine-specific data are excluded and the finished package is checked before archiving. The prepared release preset libraries are retained.

See `README.md` for full Windows, macOS, and Linux setup instructions.

Linux packages use the operating system's matched libVLC core and plugins rather than bundling Ubuntu VLC libraries into every distribution package. If VLC initialization fails, IPT reports the native Fedora and Ubuntu/Debian install commands plus the technical failure detail.
