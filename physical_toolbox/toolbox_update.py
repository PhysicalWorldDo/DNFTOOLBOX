from __future__ import annotations

import hashlib
import urllib.parse
from pathlib import Path

from physical_toolbox.install_state import InstallStateStore
from physical_toolbox.manifest import VersionKey
from physical_toolbox.package_manager import PackageManager, ProgressCallback
from physical_toolbox.repository import ToolboxUpdate


def is_toolbox_update_available(update: ToolboxUpdate, current_version: str) -> bool:
    if not update.latest_version:
        return False
    try:
        return VersionKey.parse(current_version) < VersionKey.parse(update.latest_version)
    except ValueError:
        return update.latest_version != current_version


class ToolboxUpdateDownloader:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.package_manager = PackageManager(
            workspace,
            InstallStateStore(workspace / "config" / "installed.json"),
        )

    def download(
        self,
        update: ToolboxUpdate,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        if not update.package_url:
            raise ValueError("toolbox update packageUrl is empty")

        package_path = self.package_manager.download(
            update.package_url,
            filename=self._filename(update),
            progress_callback=progress_callback,
        )
        self._verify_sha256(package_path, update.sha256)
        return package_path

    def _filename(self, update: ToolboxUpdate) -> str:
        parsed = urllib.parse.urlparse(update.package_url)
        name = Path(parsed.path).name
        if name:
            return name
        version = update.latest_version or "latest"
        return f"PhysicalWorldToolbox-{version}-win-x64.zip"

    def _verify_sha256(self, package_path: Path, expected_sha256: str) -> None:
        if not expected_sha256:
            return
        digest = hashlib.sha256(package_path.read_bytes()).hexdigest()
        if digest.lower() == expected_sha256.lower():
            return
        try:
            package_path.unlink()
        except FileNotFoundError:
            pass
        raise ValueError(f"sha256 mismatch for {package_path.name}")
