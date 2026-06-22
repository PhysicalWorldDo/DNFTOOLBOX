from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from physical_toolbox.manifest import ToolManifest


@dataclass(frozen=True)
class ToolboxUpdate:
    latest_version: str = ""
    min_supported_version: str = ""
    release_url: str = ""
    package_url: str = ""
    sha256: str = ""
    size: int | None = None
    changelog: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_url: str = "") -> "ToolboxUpdate":
        release_url = str(data.get("releaseUrl", ""))
        package_url = str(data.get("packageUrl", ""))
        if base_url and release_url:
            release_url = _resolve_url(base_url, release_url)
        if base_url and package_url:
            package_url = _resolve_url(base_url, package_url)
        return cls(
            latest_version=str(data.get("latestVersion", "")),
            min_supported_version=str(data.get("minSupportedVersion", "")),
            release_url=release_url,
            package_url=package_url,
            sha256=str(data.get("sha256", "")),
            size=data.get("size"),
            changelog=tuple(str(item) for item in data.get("changelog", [])),
        )


@dataclass(frozen=True)
class IndexTool:
    id: str
    name: str
    category: str
    manifest_url: str

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_url: str = "") -> "IndexTool":
        manifest_url = str(data["manifestUrl"])
        if base_url:
            manifest_url = _resolve_url(base_url, manifest_url)
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            category=str(data.get("category", "其他工具")),
            manifest_url=manifest_url,
        )


@dataclass(frozen=True)
class ToolboxIndex:
    schema_version: int
    latest_toolbox_version: str
    min_supported_version: str
    tools: tuple[IndexTool, ...]
    toolbox_update: ToolboxUpdate = field(default_factory=ToolboxUpdate)

    @classmethod
    def from_dict(cls, data: dict[str, Any], base_url: str = "") -> "ToolboxIndex":
        toolbox = data.get("toolbox", {})
        toolbox_update = ToolboxUpdate.from_dict(toolbox, base_url)
        return cls(
            schema_version=int(data.get("schemaVersion", 1)),
            latest_toolbox_version=toolbox_update.latest_version,
            min_supported_version=toolbox_update.min_supported_version,
            tools=tuple(IndexTool.from_dict(item, base_url) for item in data.get("tools", [])),
            toolbox_update=toolbox_update,
        )


class RepositoryClient:
    def load_index(self, url: str) -> ToolboxIndex:
        data = self._load_json(url)
        return ToolboxIndex.from_dict(data, url)

    def load_manifest(self, url: str) -> ToolManifest:
        return ToolManifest.from_dict(self._load_json(url))

    def _load_json(self, url: str) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme in {"http", "https"}:
            with urllib.request.urlopen(url, timeout=30) as response:
                raw = response.read().decode("utf-8")
        elif parsed.scheme == "file":
            raw = Path(urllib.request.url2pathname(parsed.path)).read_text(encoding="utf-8")
        else:
            raw = Path(url).read_text(encoding="utf-8")
        return json.loads(raw)


def _resolve_url(base_url: str, url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme:
        return url

    base = urllib.parse.urlparse(base_url)
    if base.scheme in {"http", "https", "file"}:
        return urllib.parse.urljoin(base_url, url)

    base_path = Path(base_url)
    return str((base_path.parent / url).resolve())
