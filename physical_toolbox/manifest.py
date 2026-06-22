from __future__ import annotations

from dataclasses import dataclass, field
from functools import total_ordering
from typing import Any


@total_ordering
@dataclass(frozen=True)
class VersionKey:
    major: int
    minor: int
    patch: int
    prerelease: tuple[str | int, ...] = ()

    @classmethod
    def parse(cls, value: str) -> "VersionKey":
        core, separator, prerelease = value.partition("-")
        parts = core.split(".")
        if len(parts) != 3:
            raise ValueError(f"version must use MAJOR.MINOR.PATCH: {value}")

        pre_parts: list[str | int] = []
        if separator:
            for part in prerelease.split("."):
                pre_parts.append(int(part) if part.isdigit() else part)

        return cls(
            major=int(parts[0]),
            minor=int(parts[1]),
            patch=int(parts[2]),
            prerelease=tuple(pre_parts),
        )

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, VersionKey):
            return NotImplemented

        core_self = (self.major, self.minor, self.patch)
        core_other = (other.major, other.minor, other.patch)
        if core_self != core_other:
            return core_self < core_other

        if not self.prerelease and other.prerelease:
            return False
        if self.prerelease and not other.prerelease:
            return True

        return self._compare_prerelease(other) < 0

    def _compare_prerelease(self, other: "VersionKey") -> int:
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            if isinstance(left, int) and isinstance(right, str):
                return -1
            if isinstance(left, str) and isinstance(right, int):
                return 1
            return -1 if left < right else 1

        if len(self.prerelease) == len(other.prerelease):
            return 0
        return -1 if len(self.prerelease) < len(other.prerelease) else 1


@dataclass(frozen=True)
class ToolVersion:
    version: str
    channel: str
    package_url: str
    sha256: str
    release_date: str = ""
    size: int | None = None
    changelog: tuple[str, ...] = ()
    min_toolbox_version: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolVersion":
        return cls(
            version=str(data["version"]),
            channel=str(data.get("channel", "stable")),
            package_url=str(data.get("packageUrl", "")),
            sha256=str(data.get("sha256", "")),
            release_date=str(data.get("releaseDate", "")),
            size=data.get("size"),
            changelog=tuple(str(item) for item in data.get("changelog", [])),
            min_toolbox_version=data.get("minToolboxVersion"),
        )


@dataclass(frozen=True)
class ToolManifest:
    schema_version: int
    id: str
    name: str
    category: str
    description: str
    icon: str
    entry: str
    need_admin: bool
    project_url: str
    latest: dict[str, str]
    versions: tuple[ToolVersion, ...]
    permissions: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    status: str = "active"
    blocked_versions: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolManifest":
        versions = tuple(ToolVersion.from_dict(item) for item in data.get("versions", []))
        if not versions:
            raise ValueError("manifest must contain at least one version")

        manifest = cls(
            schema_version=int(data.get("schemaVersion", 1)),
            id=str(data["id"]),
            name=str(data["name"]),
            category=str(data.get("category", "其他工具")),
            description=str(data.get("description", "")),
            icon=str(data.get("icon", "")),
            entry=str(data["entry"]),
            need_admin=bool(data.get("needAdmin", False)),
            project_url=str(data.get("projectUrl", "")),
            latest={str(key): str(value) for key, value in data.get("latest", {}).items()},
            versions=versions,
            permissions=tuple(str(item) for item in data.get("permissions", [])),
            tags=tuple(str(item) for item in data.get("tags", [])),
            status=str(data.get("status", "active")),
            blocked_versions=frozenset(str(item) for item in data.get("blockedVersions", [])),
        )
        manifest._validate_latest_versions()
        return manifest

    def _validate_latest_versions(self) -> None:
        known_versions = {item.version for item in self.versions}
        for channel, version in self.latest.items():
            if version not in known_versions:
                raise ValueError(f"latest.{channel} points to unknown version: {version}")

    def version(self, version: str, *, allow_blocked: bool = False) -> ToolVersion:
        if version in self.blocked_versions and not allow_blocked:
            raise ValueError(f"version is blocked: {version}")

        for item in self.versions:
            if item.version == version:
                return item
        raise ValueError(f"unknown version: {version}")

    def latest_version(self, channel: str = "stable") -> ToolVersion:
        if channel not in self.latest:
            raise ValueError(f"unknown channel: {channel}")
        return self.version(self.latest[channel])

    def versions_for_channel(self, channel: str = "stable") -> tuple[ToolVersion, ...]:
        return tuple(
            sorted(
                (item for item in self.versions if item.channel == channel and item.version not in self.blocked_versions),
                key=lambda item: VersionKey.parse(item.version),
                reverse=True,
            )
        )

    def has_update(self, installed_version: str, channel: str = "stable") -> bool:
        latest = self.latest_version(channel)
        return VersionKey.parse(installed_version) < VersionKey.parse(latest.version)
