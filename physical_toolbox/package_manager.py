from __future__ import annotations

import hashlib
import shutil
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Callable
from uuid import uuid4

from physical_toolbox.github_proxy import GitHubProxyConfig, github_url_candidates
from physical_toolbox.install_state import InstalledTool, InstallStateStore
from physical_toolbox.manifest import ToolManifest

ProgressCallback = Callable[[int, int | None], None]


class PackageManager:
    def __init__(
        self,
        workspace: Path,
        state_store: InstallStateStore,
        proxy_config: GitHubProxyConfig | None = None,
    ) -> None:
        self.workspace = workspace
        self.state_store = state_store
        self.proxy_config = proxy_config or GitHubProxyConfig(enabled=False, proxy_urls=())
        self.tools_dir = workspace / "tools"
        self.downloads_dir = workspace / "downloads"
        self.installing_dir = workspace / "cache" / "installing"

    def installed_tools(self) -> dict[str, InstalledTool]:
        return self.state_store.load()

    def download(
        self,
        url: str,
        filename: str | None = None,
        progress_callback: ProgressCallback | None = None,
        expected_sha256: str = "",
    ) -> Path:
        self.downloads_dir.mkdir(parents=True, exist_ok=True)
        parsed = urllib.parse.urlparse(url)
        target_name = filename or Path(parsed.path).name or "package.zip"
        target = self.downloads_dir / target_name

        if parsed.scheme == "file":
            source = Path(urllib.request.url2pathname(parsed.path))
            self._copy_file_with_progress(source, target, progress_callback)
            try:
                self._verify_sha256(target, expected_sha256)
            except Exception:
                self._remove_path(target, ignore_errors=True)
                raise
            return target

        last_error: Exception | None = None
        for candidate_url in github_url_candidates(url, self.proxy_config):
            try:
                with urllib.request.urlopen(candidate_url, timeout=60) as response:
                    total = response.headers.get("Content-Length")
                    self._write_response_with_progress(
                        response,
                        target,
                        int(total) if total else None,
                        progress_callback,
                    )
                    self._verify_sha256(target, expected_sha256)
                return target
            except Exception as exc:
                last_error = exc
                self._remove_path(target, ignore_errors=True)

        if last_error is not None:
            raise last_error
        raise ValueError(f"no URL candidates for {url}")

    def install(
        self,
        manifest: ToolManifest,
        version: str,
        progress_callback: ProgressCallback | None = None,
    ) -> InstalledTool:
        selected = manifest.version(version)
        package_path = self.download(
            selected.package_url,
            progress_callback=progress_callback,
            expected_sha256=selected.sha256,
        )
        return self.install_from_archive(manifest, version, package_path)

    def uninstall(self, tool_id: str) -> None:
        target = self.tools_dir / tool_id
        if target.exists():
            trash = self._sibling_path(target, "uninstall")
            target.rename(trash)
            try:
                self._remove_path(trash)
            except Exception:
                if not target.exists() and trash.exists():
                    trash.rename(target)
                raise
        self.state_store.remove(tool_id)

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
        if not expected_sha256:
            return
        digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
        if digest.lower() != expected_sha256.lower():
            raise ValueError(f"sha256 mismatch for {archive_path.name}")

    def _copy_file_with_progress(
        self,
        source: Path,
        target: Path,
        progress_callback: ProgressCallback | None,
    ) -> None:
        total = source.stat().st_size
        copied = 0
        with source.open("rb") as reader, target.open("wb") as writer:
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                writer.write(chunk)
                copied += len(chunk)
                if progress_callback is not None:
                    progress_callback(copied, total)
        shutil.copystat(source, target)
        if progress_callback is not None and copied == 0:
            progress_callback(0, total)

    def _write_response_with_progress(
        self,
        response,
        target: Path,
        total: int | None,
        progress_callback: ProgressCallback | None,
    ) -> None:
        downloaded = 0
        with target.open("wb") as writer:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                writer.write(chunk)
                downloaded += len(chunk)
                if progress_callback is not None:
                    progress_callback(downloaded, total)
        if progress_callback is not None and downloaded == 0:
            progress_callback(0, total)

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
                self._replace_item(item, destination)

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

    def _replace_item(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            self._copy_item(source, destination)
            return

        temp_destination = self._sibling_path(destination, "new")
        backup_destination = self._sibling_path(destination, "old")
        self._copy_item(source, temp_destination)

        try:
            destination.rename(backup_destination)
        except Exception:
            self._remove_path(temp_destination, ignore_errors=True)
            raise

        try:
            temp_destination.rename(destination)
        except Exception:
            try:
                backup_destination.rename(destination)
            finally:
                self._remove_path(temp_destination, ignore_errors=True)
            raise

        self._remove_path(backup_destination, ignore_errors=True)

    def _sibling_path(self, path: Path, label: str) -> Path:
        return path.with_name(f".{path.name}.{label}-{uuid4().hex}")

    def _remove_path(self, path: Path, ignore_errors: bool = False) -> None:
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=ignore_errors)
        else:
            try:
                path.unlink()
            except Exception:
                if not ignore_errors:
                    raise
