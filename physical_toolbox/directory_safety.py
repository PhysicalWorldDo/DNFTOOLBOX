from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


ALLOWED_DIRECTORY_NAMES = {
    "_internal",
    "cache",
    "config",
    "downloads",
    "logs",
    "self-update",
    "tools",
}
ALLOWED_FILE_NAMES = {
    "LICENSE",
    "LICENSE.txt",
    "PhysicalWorldToolbox.exe",
    "README.md",
    "README.txt",
    "toolbox.py",
}
EXTRA_FOLDER_WARNING_THRESHOLD = 2
EXTRA_FILE_WARNING_THRESHOLD = 5
EXTRA_ENTRY_WARNING_THRESHOLD = 8
SAFE_PATH_PATTERN = re.compile(r"^[A-Za-z0-9:._\\/\-]+$")
GAME_DIRECTORY_MARKERS = {
    "dnf.exe",
    "imagepacks2",
    "soundpacks",
    "script.pvf",
    "tcls",
}


@dataclass(frozen=True)
class DirectorySafetyIssue:
    code: str
    message: str


@dataclass(frozen=True)
class DirectorySafetyReport:
    path: Path
    issues: tuple[DirectorySafetyIssue, ...]
    extra_folders: tuple[str, ...]
    extra_files: tuple[str, ...]

    @property
    def is_risky(self) -> bool:
        return bool(self.issues)

    @property
    def issue_codes(self) -> tuple[str, ...]:
        return tuple(issue.code for issue in self.issues)


def inspect_toolbox_directory(
    path: Path,
    *,
    personal_directories: tuple[Path, ...] | None = None,
) -> DirectorySafetyReport:
    workspace = path.resolve()
    issues: list[DirectorySafetyIssue] = []

    if not _uses_safe_english_path(workspace):
        issues.append(
            DirectorySafetyIssue(
                "non_english_path",
                "当前路径包含中文、空格或特殊符号，建议改为英文、数字、下划线或短横线。",
            )
        )

    if _is_personal_directory(workspace, personal_directories):
        issues.append(
            DirectorySafetyIssue(
                "personal_directory",
                "当前目录像是桌面、下载或文档目录，不建议直接作为工具箱目录。",
            )
        )

    extra_folders, extra_files = _extra_entries(workspace)
    if _looks_like_game_directory(workspace):
        issues.append(
            DirectorySafetyIssue(
                "game_directory",
                "当前目录像是游戏目录，不建议与工具箱安装、更新文件混放。",
            )
        )
    if len(extra_folders) >= EXTRA_FOLDER_WARNING_THRESHOLD:
        issues.append(
            DirectorySafetyIssue(
                "extra_folders",
                "当前目录包含多个非工具箱文件夹，建议把工具箱放到独立目录。",
            )
        )
    if len(extra_files) >= EXTRA_FILE_WARNING_THRESHOLD:
        issues.append(
            DirectorySafetyIssue(
                "extra_files",
                "当前目录包含较多非工具箱文件，建议避免与个人文件混放。",
            )
        )
    if len(extra_folders) + len(extra_files) >= EXTRA_ENTRY_WARNING_THRESHOLD:
        issues.append(
            DirectorySafetyIssue(
                "extra_entries",
                "当前目录包含较多额外内容，工具箱应放在独立文件夹中。",
            )
        )

    return DirectorySafetyReport(
        path=workspace,
        issues=tuple(issues),
        extra_folders=extra_folders,
        extra_files=extra_files,
    )


def _uses_safe_english_path(path: Path) -> bool:
    return bool(SAFE_PATH_PATTERN.fullmatch(str(path)))


def _is_personal_directory(path: Path, personal_directories: tuple[Path, ...] | None) -> bool:
    directories = personal_directories or _default_personal_directories()
    normalized = _normalize_path(path)
    return any(normalized == _normalize_path(directory) for directory in directories)


def _default_personal_directories() -> tuple[Path, ...]:
    home = Path.home()
    return (
        home / "Desktop",
        home / "Downloads",
        home / "Documents",
    )


def _extra_entries(path: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not path.exists() or not path.is_dir():
        return (), ()

    extra_folders: list[str] = []
    extra_files: list[str] = []
    for entry in path.iterdir():
        name = entry.name
        if entry.is_dir():
            if name not in ALLOWED_DIRECTORY_NAMES:
                extra_folders.append(name)
            continue
        if entry.is_file() and not _is_allowed_file(name):
            extra_files.append(name)

    return tuple(sorted(extra_folders)), tuple(sorted(extra_files))


def _looks_like_game_directory(path: Path) -> bool:
    if not path.exists() or not path.is_dir():
        return False
    names = {entry.name.casefold() for entry in path.iterdir()}
    return len(names.intersection(GAME_DIRECTORY_MARKERS)) >= 2


def _is_allowed_file(name: str) -> bool:
    if name in ALLOWED_FILE_NAMES:
        return True
    lowered = name.lower()
    return lowered.endswith(".log") or lowered.startswith("physicalworldtoolbox-") and lowered.endswith(".zip")


def _normalize_path(path: Path) -> str:
    return str(path.resolve()).casefold()
