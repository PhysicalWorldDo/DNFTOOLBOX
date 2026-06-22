from __future__ import annotations

import hashlib
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

from physical_toolbox.install_state import InstalledTool, InstallStateStore
from physical_toolbox.manifest import ToolManifest


class PackageManager:
    def __init__(self, workspace: Path, state_store: InstallStateStore) -> None:
        self.workspace = workspace
        self.state_store = state_store
        self.tools_dir = workspace / "tools"
        self.downloads_dir = workspace / "downloads"
        self.installing_dir = workspace / "cache" / "installing"

    def installed_tools(self) -> dict[str, InstalledTool]:
        return self.state_store.load()

    def download(self, url: str, filename: str | None = None) -> Path:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        parsed = urllib.parse.urlparse(url)
        target_name = filename or Path(parsed.path).name or "package.zip"
        target = self.downloads_dir / target_name

        if parsed.scheme == "file":
            shutil.copy2(Path(urllib.request.url2pathname(parsed.path)), target)
            return target

        with urllib.request.urlopen(url, timeout=60) as response:
            target.write_bytes(response.read())
        return target

    def install(self, manifest: ToolManifest, version: str) -> InstalledTool:
        selected = manifest.version(version)
        package_path = self.download(selected.package_url)
        return self.install_from_archive(manifest, version, package_path)

    def install_from_archive(self, manifest: ToolManifest, version: str, archive_path: Path) -> InstalledTool:
        selected = manifest.version(version)
        self._verify_sha256(archive_path, selected.sha256)

        staging = self.installing_dir / manifest.id
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(archive_path) as archive:
            self._safe_extract(archive, staging)

        self._validate_package(staging, manifest.entry)
        target = self.tools_dir / manifest.id
        self._merge_package(staging, target)

        now = datetime.now().astimezone().isoformat(timespec="seconds")
        previous = self.state_store.load().get(manifest.id)
        installed = InstalledTool(
            id=manifest.id,
            name=manifest.name,
            version=selected.version,
            channel=selected.channel,
            entry=manifest.entry,
            installed_at=previous.installed_at if previous else now,
            updated_at=now,
        )
        self.state_store.record(installed)
        shutil.rmtree(staging, ignore_errors=True)
        return installed

    def _verify_sha256(self, archive_path: Path, expected_sha256: str) -> None:
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if expected_sha256 and digest.lower() != expected_sha256.lower():
            raise ValueError(f"sha256 mismatch for {archive_path.name}")

    def _safe_extract(self, archive: zipfile.ZipFile, destination: Path) -> None:
        root = destination.resolve()
        for member in archive.infolist():
            target = (destination / member.filename).resolve()
            if root != target and root not in target.parents:
                raise ValueError(f"unsafe zip path: {member.filename}")
        archive.extractall(destination)

    def _validate_package(self, staging: Path, entry: str) -> None:
        if not (staging / "tool.json").exists():
            raise ValueError("package must contain tool.json")
        if not (staging / entry).exists():
            raise ValueError(f"package entry does not exist: {entry}")

    def _merge_package(self, staging: Path, target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for item in staging.iterdir():
            destination = target / item.name
            if item.name in {"config", "data"}:
                self._copy_preserving_existing(item, destination)
            else:
                if destination.exists():
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    else:
                        destination.unlink()
                self._copy_item(item, destination)

    def _copy_preserving_existing(self, source: Path, destination: Path) -> None:
        if source.is_file():
            if not destination.exists():
                self._copy_item(source, destination)
            return

        destination.mkdir(parents=True, exist_ok=True)
        for child in source.iterdir():
            self._copy_preserving_existing(child, destination / child.name)

    def _copy_item(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, destination)
        else:
            shutil.copy2(source, destination)
