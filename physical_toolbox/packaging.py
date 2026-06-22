from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FileCopy:
    source: Path
    destination: str


@dataclass(frozen=True)
class GeneratedFile:
    destination: str
    content: str


@dataclass(frozen=True)
class ToolPackageSpec:
    id: str
    name: str
    category: str
    description: str
    version: str
    entry: str
    runtime_copies: tuple[FileCopy, ...]
    source_copies: tuple[FileCopy, ...] = ()
    config_copies: tuple[FileCopy, ...] = ()
    runtime_files: tuple[GeneratedFile, ...] = ()
    source_files: tuple[GeneratedFile, ...] = ()
    data_dirs: tuple[str, ...] = ()
    launch_target: str = ""
    config_sync_files: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    permissions: tuple[str, ...] = ()
    need_admin: bool = False
    channel: str = "stable"


@dataclass(frozen=True)
class PackagedTool:
    id: str
    package_path: Path
    manifest_path: Path
    sha256: str
    size: int


def package_tool(spec: ToolPackageSpec, output_root: Path) -> PackagedTool:
    stage_dir = output_root / "staged" / spec.id
    source_dir = output_root / "sources" / spec.id
    package_dir = output_root / "packages"
    manifest_dir = output_root / "index" / "tools"

    _replace_dir(stage_dir)
    _replace_dir(source_dir)
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    for copy in spec.runtime_copies:
        _copy_path(copy.source, stage_dir / copy.destination)
    for copy in spec.config_copies:
        _copy_path(copy.source, stage_dir / "config" / copy.destination)
        _copy_path(copy.source, source_dir / "config" / copy.destination)
    for copy in spec.source_copies:
        _copy_path(copy.source, source_dir / copy.destination)
    for generated in spec.runtime_files:
        _write_generated(stage_dir / generated.destination, generated.content)
    for generated in spec.source_files:
        _write_generated(source_dir / generated.destination, generated.content)
    for directory in spec.data_dirs:
        (stage_dir / "data" / directory).mkdir(parents=True, exist_ok=True)

    if spec.launch_target:
        _write_launcher(stage_dir / spec.entry, spec.launch_target, spec.config_sync_files)

    tool_json = _tool_json(spec, package_url="")
    (stage_dir / "tool.json").write_text(json.dumps(tool_json, ensure_ascii=False, indent=2), encoding="utf-8")

    package_path = package_dir / f"{spec.id}-{spec.version}-win-x64.zip"
    if package_path.exists():
        package_path.unlink()
    _zip_dir(stage_dir, package_path)

    sha256 = _sha256(package_path)
    manifest = _tool_json(spec, package_url=package_path.resolve().as_uri())
    manifest["versions"][0]["sha256"] = sha256
    manifest["versions"][0]["size"] = package_path.stat().st_size

    manifest_path = manifest_dir / f"{spec.id}.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return PackagedTool(
        id=spec.id,
        package_path=package_path,
        manifest_path=manifest_path,
        sha256=sha256,
        size=package_path.stat().st_size,
    )


def write_index(output_root: Path, tool_ids: Iterable[str]) -> Path:
    tools = []
    for tool_id in tool_ids:
        manifest_path = output_root / "index" / "tools" / f"{tool_id}.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        tools.append(
            {
                "id": manifest["id"],
                "name": manifest["name"],
                "category": manifest["category"],
                "manifestUrl": f"tools/{tool_id}.json",
            }
        )

    payload = {
        "schemaVersion": 1,
        "toolbox": {
            "latestVersion": "0.1.0",
            "minSupportedVersion": "0.1.0",
        },
        "tools": tools,
    }
    index_path = output_root / "index" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def _tool_json(spec: ToolPackageSpec, package_url: str) -> dict:
    return {
        "schemaVersion": 1,
        "id": spec.id,
        "name": spec.name,
        "category": spec.category,
        "description": spec.description,
        "icon": "",
        "entry": spec.entry,
        "needAdmin": spec.need_admin,
        "latest": {spec.channel: spec.version},
        "versions": [
            {
                "version": spec.version,
                "channel": spec.channel,
                "releaseDate": "2026-06-22",
                "packageUrl": package_url,
                "sha256": "",
                "size": 0,
                "changelog": ["整理为物理世界的工具箱标准包"],
                "minToolboxVersion": "0.1.0",
            }
        ],
        "permissions": list(spec.permissions),
        "tags": list(spec.tags),
        "status": "active",
        "blockedVersions": [],
    }


def _write_launcher(path: Path, launch_target: str, config_sync_files: tuple[str, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    sync_to_app = []
    sync_to_config = []
    for filename in config_sync_files:
        sync_to_app.append(f'if exist "%ROOT%\\config\\{filename}" copy /Y "%ROOT%\\config\\{filename}" "%APPDIR%\\{filename}" >nul')
        sync_to_config.append(f'if exist "%APPDIR%\\{filename}" copy /Y "%APPDIR%\\{filename}" "%ROOT%\\config\\{filename}" >nul')

    launch_command = _launch_command(launch_target)
    script = [
        "@echo off",
        "setlocal",
        'set "ROOT=%~dp0.."',
        'set "APPDIR=%ROOT%\\bin\\app"',
        'if not exist "%ROOT%\\config" mkdir "%ROOT%\\config"',
        *sync_to_app,
        'pushd "%APPDIR%"',
        launch_command,
        "popd",
        *sync_to_config,
        "endlocal",
    ]
    path.write_text("\r\n".join(script) + "\r\n", encoding="utf-8")


def _launch_command(launch_target: str) -> str:
    target_path = f"%APPDIR%\\{launch_target}"
    if Path(launch_target).suffix.lower() in {".bat", ".cmd"}:
        return f'call "{target_path}"'
    return f'start "" /wait "{target_path}"'


def _copy_path(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, ignore=_ignore_packaging_noise)
    else:
        shutil.copy2(source, destination)


def _write_generated(destination: Path, content: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")


def _ignore_packaging_noise(_directory: str, names: list[str]) -> set[str]:
    ignored = {
        ".git",
        ".claude",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "build",
        "dist",
        "output",
        "temp_process",
        "_temp_blender_try",
        "music_tool_settings.json",
        "run_config.json",
        "settings.json",
        "settings.local.json",
        "timer_config.json",
        "train_ui_settings.json",
    }
    return {name for name in names if name in ignored or name.endswith((".pyc", ".pyo"))}


def _replace_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _zip_dir(source_dir: Path, package_path: Path) -> None:
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(source_dir.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(source_dir).as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
