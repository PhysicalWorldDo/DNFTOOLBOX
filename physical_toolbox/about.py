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
                version="v0.1.11",
                date="2026-06-28",
                items=(
                    "启动时优先加载上次检查更新缓存的完整工具列表，未手动检查更新时也能显示已缓存的远程工具。",
                    "已安装工具缺少本地 tool.json 时仍会显示在工具箱中，避免本地工具从界面消失。",
                    "新增工具箱目录安全提示，建议放在独立英文目录中，避免与桌面、下载、游戏目录或个人文件混放。",
                ),
            ),
            AboutLogEntry(
                version="v0.1.10",
                date="2026-06-26",
                items=(
                    "紧急修复工具箱自更新逻辑：只替换更新包内文件，不再枚举、移动或删除安装目录中的其他文件。",
                    "防止工具箱直接放在桌面运行时，自更新误处理桌面文件。",
                ),
            ),
            AboutLogEntry(
                version="v0.1.9",
                date="2026-06-24",
                items=(
                    "底部工具详情栏改为直接显示已安装版本、最新版本和可更新状态，并修复长标题遮挡版本选择框的问题。",
                    "安装、更新和工具箱自更新开始下载时会先重置进度条，并显示正在选择最快下载节点。",
                    "界面切换为星界紫金主题，使用紫色星云雾和白色法阵背景图。",
                ),
            ),
            AboutLogEntry(
                version="v0.1.8",
                date="2026-06-24",
                items=(
                    "下载 GitHub 资源前自动测速代理节点，优先使用当前最快可用节点。",
                    "安装或卸载工具后只刷新本地安装状态，不再自动全量检查远程更新。",
                    "安装后自动清理 downloads 安装包和 cache 临时目录，自更新成功后清理 self-update 残留。",
                ),
            ),
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
