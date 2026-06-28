from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from physical_toolbox.manifest import ToolManifest, ToolVersion
from physical_toolbox.repository import IndexTool, ToolboxUpdate


@dataclass(frozen=True)
class RegistryCacheSnapshot:
    toolbox_update: ToolboxUpdate
    index_tools: list[IndexTool]
    manifests: dict[str, ToolManifest]


class RegistryCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.index_path = root / "index.json"
        self.tools_dir = root / "tools"

    def load(self) -> RegistryCacheSnapshot | None:
        if not self.index_path.exists():
            return None

        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
            toolbox_update = ToolboxUpdate.from_dict(data.get("toolbox", {}))
            index_tools = [IndexTool.from_dict(item) for item in data.get("tools", [])]
            manifests: dict[str, ToolManifest] = {}
            for index_tool in index_tools:
                manifest = self._load_manifest(index_tool)
                if manifest is None or manifest.id != index_tool.id:
                    continue
                manifests[manifest.id] = manifest
        except Exception:
            return None

        return RegistryCacheSnapshot(
            toolbox_update=toolbox_update,
            index_tools=index_tools,
            manifests=manifests,
        )

    def save(
        self,
        toolbox_update: ToolboxUpdate,
        index_tools: list[IndexTool],
        manifests: dict[str, ToolManifest],
    ) -> None:
        self.tools_dir.mkdir(parents=True, exist_ok=True)
        cached_tools: list[dict[str, Any]] = []

        for index_tool in index_tools:
            manifest = manifests.get(index_tool.id)
            if manifest is None:
                continue

            manifest_path = self._manifest_path(index_tool.id)
            manifest_path.write_text(
                json.dumps(_manifest_to_dict(manifest), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            cached_tools.append(
                {
                    "id": index_tool.id,
                    "name": index_tool.name,
                    "category": index_tool.category,
                    "manifestUrl": f"tools/{index_tool.id}.json",
                }
            )

        payload = {
            "schemaVersion": 1,
            "toolbox": _toolbox_update_to_dict(toolbox_update),
            "tools": cached_tools,
        }
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_manifest(self, index_tool: IndexTool) -> ToolManifest | None:
        manifest_url = index_tool.manifest_url.replace("\\", "/")
        if not manifest_url.startswith("tools/"):
            return None
        manifest_path = self.root / manifest_url
        if not manifest_path.exists():
            return None
        return ToolManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))

    def _manifest_path(self, tool_id: str) -> Path:
        return self.tools_dir / f"{tool_id}.json"


def _toolbox_update_to_dict(update: ToolboxUpdate) -> dict[str, Any]:
    data: dict[str, Any] = {
        "latestVersion": update.latest_version,
        "minSupportedVersion": update.min_supported_version,
        "releaseUrl": update.release_url,
        "packageUrl": update.package_url,
        "sha256": update.sha256,
        "changelog": list(update.changelog),
    }
    if update.size is not None:
        data["size"] = update.size
    return data


def _manifest_to_dict(manifest: ToolManifest) -> dict[str, Any]:
    return {
        "schemaVersion": manifest.schema_version,
        "id": manifest.id,
        "name": manifest.name,
        "category": manifest.category,
        "description": manifest.description,
        "icon": manifest.icon,
        "entry": manifest.entry,
        "needAdmin": manifest.need_admin,
        "projectUrl": manifest.project_url,
        "latest": manifest.latest,
        "versions": [_version_to_dict(version) for version in manifest.versions],
        "permissions": list(manifest.permissions),
        "tags": list(manifest.tags),
        "status": manifest.status,
        "blockedVersions": sorted(manifest.blocked_versions),
    }


def _version_to_dict(version: ToolVersion) -> dict[str, Any]:
    data: dict[str, Any] = {
        "version": version.version,
        "channel": version.channel,
        "packageUrl": version.package_url,
        "sha256": version.sha256,
        "releaseDate": version.release_date,
        "changelog": list(version.changelog),
    }
    if version.size is not None:
        data["size"] = version.size
    if version.min_toolbox_version is not None:
        data["minToolboxVersion"] = version.min_toolbox_version
    return data
