#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ignitron Preset Puller v1.1
--------------------------------
Connects to the Ignitron pedal over serial, fetches either:
 - Only presets listed in the pedal's active PresetList
 - OR all presets stored on the pedal

Each preset is saved as JSON into presets_TIMESTAMP inside the chosen backup folder.

Usage:
    python puller.py
    python puller.py --fast   # skip splash delays
"""

import os
import re
import sys
import time
import json
import queue
import serial
import subprocess
import threading
import tempfile
import serial.tools.list_ports
from pathlib import Path
from datetime import datetime

# ==========================================================
# ------------------ Regex Patterns ------------------------
# ==========================================================
LISTBANKS_START_RE   = re.compile(r"^LISTBANKS_START", re.I)
LISTBANKS_DONE_RE    = re.compile(r"^LISTBANKS_DONE", re.I)
BANK_HEADER_RE       = re.compile(r"^--\s*Bank\b", re.I)

LISTPRESETS_START_RE = re.compile(r"^LISTPRESETS_START", re.I)
LISTPRESETS_DONE_RE  = re.compile(r"^LISTPRESETS_DONE", re.I)

# ==========================================================
# ------------------ Serial Reader -------------------------
# ==========================================================
class SerialReader(threading.Thread):
    """Line-buffered serial reader on a background thread."""
    def __init__(self, port: str, baud: int = 115200, timeout: float = 0.1,
                 capture_keepalive: bool = False, connection=None):
        super().__init__(daemon=True)
        self.port_name = port
        self.baud = baud
        self.timeout = timeout
        self.capture_keepalive = capture_keepalive
        self._stop_event = threading.Event()
        self.ready = threading.Event()
        self.q = queue.Queue()
        self.ser = connection
        self.owns_connection = connection is None

    def run(self):
        try:
            if self.ser is None:
                self.ser = serial.Serial(self.port_name, self.baud, timeout=self.timeout, write_timeout=1)
            self.ser.timeout = self.timeout
        except Exception as e:
            self.q.put(("__ERROR__", f"Serial open failed: {e}"))
            self.ready.set()
            return

        self.ready.set()

        buf = bytearray()
        next_keepalive = 0.0
        try:
            while not self._stop_event.is_set():
                if self.capture_keepalive and time.monotonic() >= next_keepalive:
                    self.ser.write(b"CAPTUREKEEPALIVE\n")
                    next_keepalive = time.monotonic() + 2.0
                chunk = self.ser.read(1024)
                if not chunk:
                    continue
                for b in chunk:
                    if b == 10:  # LF
                        line = buf.decode(errors="ignore").rstrip("\r")
                        buf.clear()
                        if line != "OK CAPTUREKEEPALIVE":
                            self.q.put(("line", line))
                    elif b != 13:
                        buf.append(b)
        except Exception as e:
            self.q.put(("__ERROR__", f"Serial read error: {e}"))
        finally:
            try:
                if self.owns_connection and self.ser and self.ser.is_open:
                    self.ser.close()
            except Exception:
                pass

    def stop(self):
        self._stop_event.set()

    def write_line(self, s: str):
        if not self.ser or not self.ser.is_open:
            raise RuntimeError("The pedal USB connection is not open")
        self.ser.write((s + "\n").encode())

# ==========================================================
# ------------------ Utilities -----------------------------
# ==========================================================
def safe_mkdir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def timestamp_now():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def resolve_out_paths(base_dir=None):
    ts = timestamp_now()
    root = Path(base_dir).expanduser().resolve() if base_dir else Path.cwd()
    root.mkdir(parents=True, exist_ok=True)
    out_dir = Path(tempfile.mkdtemp(prefix=f"presets_{ts}_", dir=root))
    return out_dir, ts

def print_divider(title=""):
    print("\n" + "="*60)
    if title:
        print(title)
        print("="*60)

def print_summary(stats, out_dir, ts):
    print("\n✅ Preset pull complete.")
    print(f"   Scanned:   {stats['scanned']}")
    print(f"   Saved:     {stats['saved']}")
    print(f"   Skipped:   {stats['skipped']}")
    print(f"   Duplicate: {stats['duplicate']}")
    print(f"   Folder:    {out_dir.resolve()}")

def open_folder(path: Path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass

def _basename(name: str) -> str:
    return Path(name.strip().lstrip("/")).name

def _clean_json_text(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end >= start:
        return text[start:end+1]
    return text

# ==========================================================
# ------------------ Preset Handling -----------------------
# ==========================================================
def parse_presetlist_from_lines(lines):
    in_section = False
    keep = []
    for ln in lines:
        if LISTBANKS_START_RE.match(ln):
            in_section = True
            continue
        if LISTBANKS_DONE_RE.match(ln):
            break
        if in_section:
            if BANK_HEADER_RE.match(ln):
                continue
            candidate = ln.strip()
            if candidate.lower().endswith(".json"):
                keep.append(_basename(candidate))
    return keep

def _normalize_for_ignitron(preset: dict) -> dict:
    # Strip Spark-only fields
    preset.pop("PresetNumber", None)

    # Ensure required Ignitron fields
    preset.setdefault("Version", "0.7")
    preset.setdefault("Description", "")
    preset.setdefault("Icon", "icon.png")
    preset.setdefault("BPM", 120.0)

    if "UUID" in preset:
        preset["UUID"] = str(preset["UUID"]).upper()

    return preset

def _write_preset_file(filename, buffer, out_dir, include_only):
    json_text = "\n".join(buffer)
    json_text = _clean_json_text(json_text)

    try:
        preset = json.loads(json_text)
        if not isinstance(preset, dict) or not isinstance(preset.get("Pedals"), list):
            raise ValueError("Not a Spark preset object")
        preset = _normalize_for_ignitron(preset)
        uuid_up = preset.get("UUID", "")

        base = _basename(filename)
        if (include_only is None) or (base in include_only):
            with open(out_dir / base, "w", encoding="utf-8") as f:
                json.dump(preset, f, indent=2)
            return True, uuid_up
        return False, uuid_up

    except Exception as e:
        print(f"⚠️ Failed to process preset {filename}: {e}")
        return False, ""

def _extract_lines_to_files(lines, out_dir: Path, include_only=None):
    safe_mkdir(out_dir)
    scanned, saved, skipped, duplicate = 0, 0, 0, 0
    seen_files = set()

    filename, buffer = None, []
    collecting = False

    for ln in lines:
        low = ln.lower()

        if low.startswith("reading preset filename:"):
            if filename:
                scanned += 1
                base = _basename(filename)
                if base in seen_files:
                    duplicate += 1
                else:
                    ok, _ = _write_preset_file(filename, buffer, out_dir, include_only)
                    if ok:
                        saved += 1
                    else:
                        skipped += 1
                    seen_files.add(base)

            filename = ln.split(":", 1)[-1].strip()
            buffer = []
            collecting = False
            continue

        if ("JSON STRING" in ln and "{" in ln):
            collecting = True
            buffer.append(ln[ln.index("{"):])
            continue

        if ln.lstrip().startswith("{"):
            collecting = True
            buffer.append(ln)
            continue

        if collecting:
            buffer.append(ln)

    if filename:
        scanned += 1
        base = _basename(filename)
        if base in seen_files:
            duplicate += 1
        else:
            ok, _ = _write_preset_file(filename, buffer, out_dir, include_only)
            if ok:
                saved += 1
            else:
                skipped += 1
            seen_files.add(base)

    return {"scanned": scanned, "saved": saved, "skipped": skipped, "duplicate": duplicate}

# ==========================================================
# ------------------ Preset Pull ---------------------------
# ==========================================================
def pull_presets(port: str,
                 baud: int = 115200,
                 include_only_active: bool = True,
                 open_folder_after: bool = True,
                 output_root=None,
                 stop_event=None,
                 capture_keepalive: bool = False,
                 connection=None):
    out_dir, ts = resolve_out_paths(output_root)
    safe_mkdir(out_dir)
    print_divider("Serial Preset Pull")
    print(f"Opening {port} @ {baud} ...")
    reader = SerialReader(port, baud, capture_keepalive=capture_keepalive, connection=connection)
    reader.start()

    def cancelled():
        return stop_event is not None and stop_event.is_set()

    def request_lines(command, start_pattern, done_pattern, timeout):
        if cancelled():
            raise InterruptedError("Preset backup cancelled")
        print(f"→ Requesting {command} ...")
        reader.write_line(command)
        lines = []
        started = False
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancelled():
                raise InterruptedError("Preset backup cancelled")
            try:
                kind, payload = reader.q.get(timeout=0.1)
            except queue.Empty:
                continue
            if kind == "__ERROR__":
                raise RuntimeError(payload)
            if kind != "line":
                continue
            if start_pattern.match(payload):
                started = True
            if started:
                lines.append(payload)
                if done_pattern.match(payload):
                    return lines
        raise TimeoutError(f"{command} did not finish; the backup is incomplete")

    try:
        if not reader.ready.wait(5):
            raise TimeoutError("Timed out opening the pedal USB connection")
        # Surface an open failure immediately, rather than reporting an empty
        # backup as successful after waiting for commands that were never sent.
        if not reader.ser or not reader.ser.is_open:
            try:
                _kind, error = reader.q.get_nowait()
            except queue.Empty:
                error = "The pedal USB connection is not open"
            raise RuntimeError(error)
        include_only = None
        if include_only_active:
            banks_lines = request_lines("LISTBANKS", LISTBANKS_START_RE, LISTBANKS_DONE_RE, 5)
            include_only = set(parse_presetlist_from_lines(banks_lines))
            if not include_only:
                raise RuntimeError("The pedal PresetList contains no preset filenames; no backup was saved")
            print(f"Pedal PresetList detected: {len(include_only)} filenames to keep.")
        presets_lines = request_lines("LISTPRESETS", LISTPRESETS_START_RE, LISTPRESETS_DONE_RE, 120)
        stats = _extract_lines_to_files(presets_lines, out_dir, include_only)
        if not stats["saved"]:
            raise RuntimeError("No valid presets were received; no backup was saved")
        if include_only is None and stats["skipped"]:
            raise RuntimeError(f"Incomplete backup: {stats['skipped']} preset(s) could not be saved")
        if include_only:
            missing = sorted(name for name in include_only if not (out_dir / name).is_file())
            if missing:
                raise RuntimeError(f"Incomplete backup: {len(missing)} listed preset(s) missing: " + ", ".join(missing[:8]))
        print_summary(stats, out_dir, ts)
        if open_folder_after:
            open_folder(out_dir)
        return stats
    finally:
        reader.stop()
        reader.join(timeout=2.0)
        if reader.is_alive():
            raise RuntimeError("The preset backup reader did not stop")

# ==========================================================
# ------------------ Splash Screen -------------------------
# ==========================================================
def splash_screen(fast=False):
    print("="*60)
    print("    🎸  Ignitron Preset Puller  🎛️")
    print("    \"Because tone should be saved, not lost.\"")
    print("="*60, "\n")

    steps = [
        "Plugging in the cable... 🎤",
        "Warming up the tubes... 🔥",
        "Tuning the strings... 🎵",
        "Ready to rock! 🤘"
    ]
    for step in steps:
        print("   " + step)
        if not fast:
            time.sleep(0.8)
    print()

# ==========================================================
# ------------------ Entry Point ---------------------------
# ==========================================================
def choose_serial_port():
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        print("❌ No serial ports found.")
        sys.exit(1)

    print("\nAvailable serial ports:")
    for i, p in enumerate(ports, 1):
        print(f"  {i}. {p.device} ({p.description})")

    while True:
        try:
            choice = int(input("\nSelect COM port number: ").strip())
            if 1 <= choice <= len(ports):
                return ports[choice - 1].device
        except ValueError:
            pass
        print("Invalid choice. Try again.")

if __name__ == "__main__":
    fast_mode = "--fast" in sys.argv
    splash_screen(fast=fast_mode)
    print_divider("Ignitron Preset Puller")

    print("Pull mode:")
    print("  1. Only presets in pedal’s PresetList.txt")
    print("  2. All presets on the pedal")
    while True:
        choice = input("Choose [1/2]: ").strip()
        if choice in ("1", "2"):
            include_only_active = (choice == "1")
            break
        print("Invalid choice. Please enter 1 or 2.")

    port = choose_serial_port()
    print("\n⚠️  Before connecting: HOLD PRESET 1 on the pedal.")
    input(f"Selected {port}. Press Enter when ready to continue...")

    pull_presets(
        port=port,
        baud=115200,
        include_only_active=include_only_active,
        open_folder_after=True
    )

    input("\nPress Enter to exit...")
