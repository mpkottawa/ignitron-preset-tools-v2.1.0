import argparse
import serial
import re
import json
import os
import time
from preset_capture import PresetCaptureDecoder, save_captured_preset

BAUD = 115200

def normalize_number(val):
    if isinstance(val, float):
        if val.is_integer():
            return int(val)
        return round(val, 4)
    return val

def normalize_json(obj):
    if isinstance(obj, dict):
        return {k: normalize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [normalize_json(v) for v in obj]
    else:
        return normalize_number(obj)

def connect(port, baud):
    return serial.Serial(port, baud, timeout=0.5)

def main():
    parser = argparse.ArgumentParser(description="Capture Ignitron preset JSON from a serial port.")
    parser.add_argument("port", help="Serial device, for example COM7 or /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=BAUD)
    args = parser.parse_args()
    print("Ignitron Spark App Tool (App Preset Capture)")
    ser = connect(args.port, args.baud)
    print(f"Connected on {args.port} at {args.baud}")

    # make timestamped session folder
    session_folder = time.strftime("presets_%Y%m%d_%H%M%S")
    os.makedirs(session_folder, exist_ok=True)
    print(f"📂 Saving captured presets into: {session_folder}")

    decoder = PresetCaptureDecoder()

    while True:
        try:
            line = ser.readline().decode(errors="ignore").rstrip()
            if not line:
                continue

            print(line)

            try:
                preset = decoder.feed(line)
                if preset is not None:
                    output, created = save_captured_preset(session_folder, normalize_json(preset))
                    if created:
                        print(f"Saved preset: {output}")
            except (ValueError, OSError) as exc:
                print(f"Could not save preset: {exc}")

        except KeyboardInterrupt:
            print("Exiting...")
            ser.close()
            break

if __name__ == "__main__":
    main()
