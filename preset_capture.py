"""Decode serial preset messages and save captures without overwriting tones."""

import json
import re
from pathlib import Path


class PresetCaptureDecoder:
    def __init__(self):
        self.buffer = None

    def feed(self, line):
        line = line.strip()
        if not line or line == "OK CAPTUREKEEPALIVE" or line.startswith("IGNITRON_FLASHER "):
            return None
        if line.startswith("received from app:"):
            self.buffer = ""
            line = line.partition(":")[2].strip()
        elif line.startswith("JSON STRING:"):
            self.buffer = ""
            line = line.partition(":")[2].strip()
        if self.buffer is None or not line:
            return None
        self.buffer += line + "\n"
        if len(self.buffer) > 2 * 1024 * 1024:
            self.buffer = None
            raise ValueError("Preset message exceeded the 2 MB capture limit")
        try:
            preset, end = json.JSONDecoder().raw_decode(self.buffer.lstrip())
        except json.JSONDecodeError:
            return None  # A nested object ending is not the end of the preset.
        trailing = self.buffer.lstrip()[end:].strip()
        self.buffer = None
        if trailing or not isinstance(preset, dict) or not isinstance(preset.get("Pedals"), list):
            raise ValueError("Received data is not a complete Spark preset")
        return preset


def save_captured_preset(folder, preset):
    """Return (path, created); preserve different presets with the same name."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = re.sub(r"[^A-Za-z0-9_-]+", "", str(preset.get("Name", "preset")))[:120] or "preset"
    suffix = 1
    while True:
        path = folder / (f"{name}.json" if suffix == 1 else f"{name}_{suffix}.json")
        try:
            with path.open("x", encoding="utf-8") as output:
                json.dump(preset, output, indent=2)
            return path, True
        except FileExistsError:
            try:
                if json.loads(path.read_text(encoding="utf-8")) == preset:
                    return path, False
            except (OSError, ValueError):
                pass
        suffix += 1
