from __future__ import annotations

import os
import subprocess
from pathlib import Path


COMMAND_EXTENSIONS = {".bat", ".cmd"}


def launch_creation_flags(entry: Path, platform_name: str | None = None) -> int:
    platform = platform_name or os.name
    if platform != "nt":
        return 0
    if entry.suffix.lower() in COMMAND_EXTENSIONS:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return 0


def launch_entry(entry: Path) -> subprocess.Popen:
    return subprocess.Popen(
        [str(entry)],
        cwd=str(entry.parent),
        creationflags=launch_creation_flags(entry),
    )
