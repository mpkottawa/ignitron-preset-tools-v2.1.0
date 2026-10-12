# Ignitron Preset Tools v2.1.01

## Fixes in v2.1.01 - 2026-10-12

This maintenance release follows v2.1.00 with the Linux testing fixes. The application, native archives and bundled current firmware are labelled **2.1.01**. The original v2.1.00 release remains available. Download the archive for your platform and its matching SHA256SUMS.txt.

- Fixed Linux VLC discovery and a PipeWire crash when changing volume before playback. Added a real-audio-backend self-test.
- Added KDE Places folder selection, remembered music locations, and SMB access through the desktop credential/mount services.
- Fixed CP2102 serial control-line resets and kept a verified connection open for Pedal Remote. Orange preset highlighting now means selected only.
- Moved Capture connection work off the GUI thread and wait for the previous USB task to finish. Firmware tasks and app serial tools cannot share the port concurrently.
- Capture now decodes nested and inline preset JSON and preserves different presets with the same name. Routine keepalive messages no longer flood the log.
- Backups reuse the verified port, report interrupted or incomplete transfers, and use unique folders. **Pull listed presets** describes all filenames in PresetList.txt, rather than implying just the active bank.
- Linux upgrades and normal uninstalls preserve working projects, presets, captures and backups. Bundled firmware templates update separately. Settings writes are atomic.
- Both firmware and filesystem must build before an optional erase. Builder exports back up replaced preset JSON and reject ambiguous selected filenames.
- Added the revised **Linux-Install-Guide.pdf**, also available as a separate release download. Published filenames and checksum entries now match.

Close IPT before installing. Use the v2.1.01 installer. The guide's clean-install checklist remains a separate end-to-end test; native CI packaging does not replace testing each amp or Linux distribution.

IPT v2.1.01 is the desktop control center for building Ignitron preset banks, installing IPT firmware support, flashing firmware/filesystem data, controlling presets over USB, backing up a pedal, capturing presets from the Spark app, and playing backing tracks.

## Native downloads

### Linux: installer included

1. Download **Linux-x64.tar.gz** for an Intel/AMD PC, or **Linux-arm64.tar.gz** for an ARM64 computer.
2. Extract the whole archive, open its folder, and double-click **Install Ignitron**. Choose Execute/Trust/Allow Launching if your desktop asks.
3. Enter your Linux password in the setup window and wait for **SETUP COMPLETE**. IPT opens automatically.

Keep the pedal unplugged during setup. The included all-in-one installer verifies the bundle and installs or locates native VLC/Python requirements, PlatformIO Core, USB permissions, and KDE Places/NAS helpers. It checks VLC playback and builds firmware/filesystem without flashing the pedal. It preserves existing projects and presets. Internet is needed for dependencies. Supports Fedora with dnf and Ubuntu/Debian with apt; VS Code is not required.

If the launcher opens as text, use **Open Terminal Here** inside the extracted folder and run `bash ./launch_linux_setup.sh`. Some desktops require marking the launcher executable or trusted first. See **START-HERE-Linux.txt** and the bundled **Linux-Install-Guide.pdf**.

**Linux packaging refresh:** these two Linux archives now contain the installer, launcher and revised guide. The application and firmware payloads are unchanged from v2.1.01. Use the updated **SHA256SUMS.txt**. Windows/macOS archives and the release tag are unchanged.

The separate [Install-IPT-Linux.sh](https://github.com/mpkottawa/ignitron-preset-tools-v2.1.0/releases/download/v2.1.01/Install-IPT-Linux.sh) remains available: download it into Downloads and run `bash "$HOME/Downloads/Install-IPT-Linux.sh"` for online setup.

### Individual platform packages

Choose the archive matching the operating system and CPU:

- `Ignitron.Preset.Tools.v2.1.01.Windows-x64.zip`
- `Ignitron.Preset.Tools.v2.1.01.macOS-arm64.zip` for Apple Silicon
- `Ignitron.Preset.Tools.v2.1.01.macOS-x64.zip` for Intel Macs
- `Ignitron.Preset.Tools.v2.1.01.Linux-x64.tar.gz`
- `Ignitron.Preset.Tools.v2.1.01.Linux-arm64.tar.gz`

Windows users extract the ZIP and run the EXE. Mac users extract the ZIP and move the app to Applications. Linux users use **Install Ignitron** inside the extracted folder. The `install_linux.sh` script remains an app-only/manual alternative after separately installing prerequisites.

The release workflow builds each application natively. It does not relabel a Windows executable for another operating system.

## Included firmware

- `ignitron firmware` is the ready-to-build IPT v2.1.01 project with the current feature set and prepared preset library.
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
