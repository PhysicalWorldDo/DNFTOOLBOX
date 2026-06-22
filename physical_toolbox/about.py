from __future__ import annotations

from dataclasses import dataclass

from physical_toolbox.repository import IndexTool
from physical_toolbox.tool_grid import ordered_categories

ABOUT_NAV_ID = "__about__"
ABOUT_NAV_LABEL = "关于页"


@dataclass(frozen=True)
class AboutLogEntry:
    version: str
    date: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class AboutInfo:
    title: str
    author: str
    tagline: str
    qq_group: str
    bilibili_url: str
    github_url: str
    logs: tuple[AboutLogEntry, ...]


def toolbox_about_info() -> AboutInfo:
    return AboutInfo(
        title="物理世界的工具箱",
        author="物理世界的欧皇",
        tagline="集中安装、更新、启动和管理 DNF 工具的桌面工具箱。",
        qq_group="1077552159",
        bilibili_url="https://space.bilibili.com/492488982",
        github_url="https://github.com/PhysicalWorldDo/DNFTOOLBOX",
        logs=(
            AboutLogEntry(
                version="v0.1.0",
                date="2026-06-22",
                items=(
                    "建立工具箱框架，支持远程清单、版本选择、安装、更新、卸载和启动。",
                    "接入 GitHub Releases 安装包与 DNFTOOLBOX-Registry 更新索引。",
                    "整理第一批 DNF 工具，并按工具规则拆分源码仓库和 release 包。",
                ),
            ),
        ),
    )


def sidebar_navigation_labels(index_tools: tuple[IndexTool, ...] | list[IndexTool]) -> tuple[str, ...]:
    return ordered_categories(index_tools) + (ABOUT_NAV_LABEL,)
