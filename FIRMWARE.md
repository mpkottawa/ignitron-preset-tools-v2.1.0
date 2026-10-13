# Firmware included with IPT v2.1.02

Every IPT v2.1.02 desktop package includes two complete PlatformIO projects. They are source projects that IPT builds for the connected pedal; no separate Arduino IDE setup is required.

## Which folder should I use?

### `ignitron firmware` (native packages) or `Ignitron` (source release)

This is the ready-to-build IPT v2.1.02 firmware and the normal choice for this release. It includes the serial protocol used by Pedal Remote and Spark Capture, software-controlled capture mode, the multi-amp blocklist, Spark 2 battery support, the dedicated-preset-LED flicker fix, the prepared preset library, and all current fixes.

The release default is the SH1106 1.3-inch OLED. Before flashing, review the Firmware and Hardware tabs if your pedal uses a different display, GPIO mapping, or battery wiring. **Build + Flash FW + FS** saves and verifies the values shown in IPT before compiling.

### `Ignitron 1.9.0`

This is the Ignitron 1.9.0 fallback project. Its firmware source is retained for users who want the earlier release or need a clean recovery point. Release staging removes saved computer-specific serial ports and resets its runtime mode files to normal APP/BLE startup; it does not add IPT v2.1 support.

Keep this folder unchanged if you want it available as a fallback. If you select it in IPT and apply **IPT 2.1 Setup**, IPT upgrades that selected copy and creates backups inside the project.

## Recommended flash procedure

1. Connect the Ignitron pedal by USB and open IPT.
2. Select the current `ignitron firmware`/`Ignitron` project.
3. Confirm the detected pedal in the top-right **Pedal USB** selector.
4. In **Firmware**, check the OLED, battery, and Hardware-tab GPIO values.
5. Keep **Required IPT 2.1 changes** selected. Select only the optional features you want.
6. Click **Build + Flash FW + FS**. The combined action saves the displayed settings, verifies them, builds both firmware and filesystem, then performs any requested erase and uploads both images.
7. Let the pedal restart. If the first upload is interrupted by USB enumeration, leave it connected and run the same action again.

PlatformIO Core is required for building and flashing. The default upload speed is `460800`; IPT serial-control features use `115200`.

## Linux first build

The IPT user installer does not install PlatformIO Core. Install it with PlatformIO's official per-user installer, restart IPT, and select `~/.platformio/penv/bin/platformio` in **Firmware > Show setup**. The normal installed firmware project is `~/.local/share/ignitron-preset-tools/ignitron firmware`; do not accidentally select the neighboring 1.9.0 fallback.

For optional build-only diagnostics, compile both images from a terminal:

```bash
cd "$HOME/.local/share/ignitron-preset-tools/ignitron firmware"
"$HOME/.platformio/penv/bin/platformio" run -e esp32dev
"$HOME/.platformio/penv/bin/platformio" run -e esp32dev -t buildfs
```

If you run these diagnostics, both commands must report `SUCCESS`. The combined app action runs these builds automatically; separate terminal builds are not required. Complete Fedora and Ubuntu/Debian package installation, udev rules, serial-group checks, and troubleshooting are in [README.md](README.md#linux).

## Important recovery notes

- A firmware-only upload does not replace presets in the pedal filesystem.
- A filesystem upload replaces the on-pedal preset data with the selected project's `data` folder.
- Back up a custom preset library before replacing it.
- Do not use another pedal's battery-divider or GPIO values without checking the hardware.
- If a display is blank after flashing, select the correct OLED driver and flash the firmware again.

