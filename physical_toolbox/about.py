from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from physical_toolbox.repository import IndexTool
from physical_toolbox.tool_grid import ordered_categories

ABOUT_NAV_ID = "__about__"
ABOUT_NAV_LABEL = "关于页"
ASSET_DIR = Path(__file__).resolve().parent / "assets"


@dataclass(frozen=True)
class AboutLogEntry:
    version: str
    date: str
    items: tuple[str, ...]


@dataclass(frozen=True)
class SponsorQr:
    id: str
    title: str
    image_path: Path


@dataclass(frozen=True)
class AboutInfo:
    title: str
    author: str
    tagline: str
    qq_number: str
    bilibili_url: str
    github_url: str
    feedback_url: str
    sponsor_qrs: tuple[SponsorQr, ...]
    logs: tuple[AboutLogEntry, ...]


def toolbox_about_info() -> AboutInfo:
    return AboutInfo(
        title="物理世界的工具箱",
        author="物理世界的欺骗",
        tagline="集中安装、更新、启动和管理 DNF 工具的桌面工具箱。",
        qq_number="1548220577",
        bilibili_url="https://space.bilibili.com/492488982",
        github_url="https://github.com/PhysicalWorldDo/DNFTOOLBOX",
        feedback_url="https://github.com/PhysicalWorldDo/DNFTOOLBOX/issues",
        sponsor_qrs=(
            SponsorQr("weixin", "微信赞助", ASSET_DIR / "sponsor-weixin.jpg"),
            SponsorQr("zhifubao", "支付宝赞助", ASSET_DIR / "sponsor-zhifubao.jpg"),
        ),
        logs=(
            AboutLogEntry(
                version="v0.1.7",
                date="2026-06-24",
                items=(
                    "新增 GitHub 公共加速代理配置，检查更新和下载安装包会自动按代理列表回退。",
                    "右上角菜单新增下载代理设置，支持启用、关闭、修改代理站和恢复默认。",
                    "启动时不再自动检查更新，需要时可从右上角菜单手动检查。",
                ),
            ),
            AboutLogEntry(
                version="v0.1.6",
                date="2026-06-23",
                items=(
                    "关于页新增赞助支持区域，显示微信和支付宝赞助二维码。",
                    "README 同步加入赞助二维码说明。",
                ),
            ),
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
