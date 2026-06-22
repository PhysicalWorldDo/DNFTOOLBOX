from __future__ import annotations

from dataclasses import dataclass

from physical_toolbox.install_state import InstalledTool
from physical_toolbox.manifest import ToolManifest
from physical_toolbox.repository import IndexTool


DEFAULT_CATEGORIES: tuple[str, ...] = (
    "游戏工具",
    "图像工具",
    "音频工具",
    "UI工具",
    "插件工具",
    "补丁工具",
    "资源工具",
    "角色工具",
    "其他工具",
)


@dataclass(frozen=True)
class ToolTile:
    id: str
    name: str
    category: str
    description: str
    icon: str
    status_text: str
    is_installed: bool
    installed_version: str | None
    latest_version: str
    available_versions: tuple[str, ...]


def ordered_categories(index_tools: tuple[IndexTool, ...] | list[IndexTool]) -> tuple[str, ...]:
    dynamic_categories = {tool.category for tool in index_tools}
    preferred = tuple(category for category in DEFAULT_CATEGORIES if category in dynamic_categories)
    extras = tuple(sorted(dynamic_categories.difference(DEFAULT_CATEGORIES)))
    return preferred + extras


def build_tool_tiles(
    index_tools: tuple[IndexTool, ...] | list[IndexTool],
    manifests: dict[str, ToolManifest],
    installed_tools: dict[str, InstalledTool],
    channel: str,
) -> tuple[ToolTile, ...]:
    tiles: list[ToolTile] = []
    for index_tool in index_tools:
        manifest = manifests.get(index_tool.id)
        if manifest is None:
            continue

        installed = installed_tools.get(index_tool.id)
        versions = manifest.versions_for_channel(channel)
        latest = manifest.latest_version(channel)
        tiles.append(
            ToolTile(
                id=manifest.id,
                name=manifest.name,
                category=manifest.category,
                description=manifest.description,
                icon=manifest.icon,
                status_text=f"已安装 {installed.version}" if installed else "未安装",
                is_installed=installed is not None,
                installed_version=installed.version if installed else None,
                latest_version=latest.version,
                available_versions=tuple(item.version for item in versions),
            )
        )
    return tuple(tiles)


def default_selected_category(categories: tuple[str, ...], tiles: tuple[ToolTile, ...]) -> str:
    categories_with_tools = {tile.category for tile in tiles}
    for category in categories:
        if category in categories_with_tools:
            return category
    if tiles:
        return tiles[0].category
    return categories[0] if categories else ""
