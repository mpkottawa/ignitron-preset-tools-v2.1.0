#!/usr/bin/env python3
"""Shared release staging and privacy checks for every supported OS."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


IGNORED_DIRECTORIES = {
    ".git",
    ".github",
    ".pio",
    ".vscode",
    "__pycache__",
    "backups",
    "captures",
    "doxygen",
    "html",
    "latex",
    "logs",
    "output",
    "preview_cache",
    "tmp",
}
IGNORED_FILES = {"doxyfile"}
FORBIDDEN_RELEASE_DIRECTORIES = {
    ".pio",
    "__pycache__",
    "backups",
    "captures",
    "doxygen",
    "logs",
    "preview_cache",
    "tmp",
}
IGNORED_SUFFIXES = {".bak", ".log", ".pyc", ".pyo", ".tmp"}
TEXT_SUFFIXES = {
    ".bat", ".cfg", ".command", ".cpp", ".css", ".desktop", ".h",
    ".html", ".ini", ".ino", ".json", ".md", ".ps1", ".py",
    ".sh", ".toml", ".txt", ".xml", ".yaml", ".yml",
}
PRIVATE_PATTERNS = (
    ("Windows user directory", re.compile(r"(?i)[a-z]:[\\/]+users[\\/]+[^\\/\s]+")),
    ("Unix user directory", re.compile(r"(?i)/(?:users|home)/[^/\s]+")),
    ("Windows working-drive path", re.compile(r"(?i)(?<!%)\b[defghijklmnopqrstuvwxyz]:\\")),
    ("private IPv4/UNC path", re.compile(r"(?i)(?:\\\\|//)(?:10\.|172\.(?:1[6-9]|2\d|3[01])\.|192\.168\.)")),
    ("OneDrive path", re.compile(r"(?i)onedrive[\\/]")),
)
SOURCE_FILES = (
    ".gitattributes",
    ".gitignore",
    "GITHUB_RELEASE.md",
    "FIRMWARE.md",
    "Ignitron preset tools logo ASCII 120x60.txt",
    "IPT.ico",
    "LICENSE",
    "Linux-Install-Guide.pdf",
    "README.md",
    "RELEASE_NOTES.md",
    "Run IPT 2.1.bat",
    "Run IPT 2.1.command",
    "build_release.ps1",
    "build_release_linux.sh",
    "build_release_mac.sh",
    "ignitron_preset_tools_v2.1.py",
    "install_linux.sh",
    "preset_app_scraper.py",
    "preset_chart.py",
    "preset_converter.py",
    "preset_capture.py",
    "preset_puller.py",
    "release_tools.py",
    "requirements-build.txt",
    "requirements.txt",
    "run_ipt_2.1.sh",
    "test_firmware_injector.py",
    "test_linux_workflows.py",
    "uninstall_linux.sh",
)
SOURCE_DIRECTORIES = (".github", "reference", "docs")
FIRMWARE_PROJECTS = (
    ("Ignitron", "Ignitron"),
    ("Ignitron 1.9.0", "Ignitron 1.9.0"),
)


def _firmware_ignore(source: str, names: list[str]) -> set[str]:
    source_path = Path(source)
    ignored: set[str] = set()
    for name in names:
        path = source_path / name
        if (
            name in IGNORED_DIRECTORIES
            or name.lower() in IGNORED_FILES
            or path.suffix.lower() in IGNORED_SUFFIXES
        ):
            ignored.add(name)
    return ignored


def _sanitize_platformio(path: Path) -> None:
    if not path.exists():
        return
    clean_lines: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if re.match(r"^\s*(?:upload_port|monitor_port)\s*=", line, flags=re.IGNORECASE):
            continue
        clean_lines.append(line)
    clean_lines.extend(
        [
            "",
            "; Serial ports are intentionally not stored in release packages.",
            "; Ignitron Preset Tools writes the selected port before upload.",
        ]
    )
    path.write_text("\n".join(clean_lines) + "\n", encoding="utf-8")


def stage_firmware(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    if not (source / "platformio.ini").exists():
        raise SystemExit(f"Not an Ignitron PlatformIO project: {source}")
    if destination == source or source in destination.parents:
        raise SystemExit("Release firmware destination must be outside the source project.")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, ignore=_firmware_ignore)
    _sanitize_platformio(destination / "platformio.ini")

    # Always ship the pedal in its normal APP/BLE defaults. Presets and their
    # generated lists are intentionally preserved as release content.
    data_dir = destination / "data"
    config_dir = data_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "BTMode.config").write_text("1\n", encoding="ascii")
    (config_dir / "SparkMode.config").write_text("1\n", encoding="ascii")
    print(f"Staged sanitized firmware: {destination}")


def stage_source(source: Path, destination: Path) -> None:
    """Create a clean, reviewable GitHub source tree from a working tree."""
    source = source.resolve()
    destination = destination.resolve()
    if destination == source or source in destination.parents:
        raise SystemExit("Release source destination must be outside the working tree.")
    if destination.exists() and any(destination.iterdir()):
        raise SystemExit(
            f"Release source destination is not empty: {destination}\n"
            "Use an empty folder so existing release work is never overwritten."
        )
    destination.mkdir(parents=True, exist_ok=True)

    missing: list[str] = []
    for name in SOURCE_FILES:
        source_file = source / name
        if not source_file.exists():
            missing.append(name)
            continue
        shutil.copy2(source_file, destination / name)
    for name in SOURCE_DIRECTORIES:
        source_dir = source / name
        if source_dir.exists():
            shutil.copytree(source_dir, destination / name, ignore=_firmware_ignore)
        else:
            missing.append(name)
    if missing:
        raise SystemExit("Required release-source items are missing: " + ", ".join(missing))

    for source_name, destination_name in FIRMWARE_PROJECTS:
        firmware_source = source / source_name
        if not firmware_source.exists():
            raise SystemExit(f"Required firmware project is missing: {firmware_source}")
        stage_firmware(firmware_source, destination / destination_name)
    verify_release(destination)
    print(f"Staged clean GitHub source: {destination}")


def _read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        if path.stat().st_size > 4 * 1024 * 1024:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def verify_release(root: Path) -> None:
    root = root.resolve()
    if not root.exists():
        raise SystemExit(f"Release path does not exist: {root}")
    problems: list[str] = []
    forbidden_names = {"settings.json", "setlists.json"}
    for path in root.rglob("*"):
        if path.is_dir() and path.name in FORBIDDEN_RELEASE_DIRECTORIES:
            relative = path.relative_to(root).as_posix()
            problems.append(f"generated/private directory: {relative}")
            continue
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.name.lower() in forbidden_names:
            problems.append(f"local settings file: {relative}")
        text = _read_text(path)
        if text is None:
            continue
        for label, pattern in PRIVATE_PATTERNS:
            match = pattern.search(text)
            if match:
                problems.append(f"{label}: {relative}: {match.group(0)!r}")
    if problems:
        rendered = "\n".join(f"  - {item}" for item in problems)
        raise SystemExit(f"Release privacy check failed:\n{rendered}")
    print(f"Release privacy check passed: {root}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage = subparsers.add_parser("stage-firmware", help="copy a sanitized firmware project")
    stage.add_argument("source", type=Path)
    stage.add_argument("destination", type=Path)

    verify = subparsers.add_parser("verify", help="reject personal data in a staged release")
    verify.add_argument("root", type=Path)

    source = subparsers.add_parser("stage-source", help="create a clean GitHub release source tree")
    source.add_argument("source", type=Path)
    source.add_argument("destination", type=Path)

    args = parser.parse_args()
    if args.command == "stage-firmware":
        stage_firmware(args.source, args.destination)
    elif args.command == "stage-source":
        stage_source(args.source, args.destination)
    else:
        verify_release(args.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
