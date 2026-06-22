from physical_toolbox.install_state import InstalledTool
from physical_toolbox.manifest import ToolManifest
from physical_toolbox.repository import IndexTool
from physical_toolbox.tool_grid import build_tool_tiles, default_selected_category, ordered_categories


def manifest(tool_id: str, name: str, category: str) -> ToolManifest:
    return ToolManifest.from_dict(
        {
            "schemaVersion": 1,
            "id": tool_id,
            "name": name,
            "category": category,
            "description": f"{name}说明",
            "icon": "",
            "entry": f"bin/{tool_id}.exe",
            "needAdmin": False,
            "latest": {"stable": "1.2.0"},
            "versions": [
                {
                    "version": "1.0.0",
                    "channel": "stable",
                    "packageUrl": "https://example.com/1.0.0.zip",
                    "sha256": "a" * 64,
                },
                {
                    "version": "1.2.0",
                    "channel": "stable",
                    "packageUrl": "https://example.com/1.2.0.zip",
                    "sha256": "b" * 64,
                },
            ],
        }
    )


def test_ordered_categories_keep_toolbox_style_defaults_before_extra_categories() -> None:
    tools = (
        IndexTool("damage_calculator", "伤害计算器", "角色工具", "damage.json"),
        IndexTool("screenshot_helper", "截图助手", "游戏工具", "shot.json"),
    )

    categories = ordered_categories(tools)

    assert categories[:3] == ("硬件信息", "CPU工具", "主板工具")
    assert "游戏工具" in categories
    assert categories[-1] == "角色工具"


def test_build_tool_tiles_marks_installed_tool_and_exposes_versions() -> None:
    index_tools = (
        IndexTool("damage_calculator", "伤害计算器", "角色工具", "damage.json"),
    )
    manifests = {
        "damage_calculator": manifest("damage_calculator", "伤害计算器", "角色工具"),
    }
    installed = {
        "damage_calculator": InstalledTool(
            id="damage_calculator",
            name="伤害计算器",
            version="1.0.0",
            channel="stable",
            entry="bin/damage_calculator.exe",
            installed_at="2026-06-22T12:00:00+08:00",
            updated_at="2026-06-22T12:00:00+08:00",
        )
    }

    tiles = build_tool_tiles(index_tools, manifests, installed, "stable")

    assert len(tiles) == 1
    assert tiles[0].id == "damage_calculator"
    assert tiles[0].status_text == "已安装 1.0.0"
    assert tiles[0].latest_version == "1.2.0"
    assert tiles[0].available_versions == ("1.2.0", "1.0.0")


def test_default_selected_category_prefers_first_category_that_has_tools() -> None:
    tiles = (
        build_tool_tiles(
            (IndexTool("shot", "截图助手", "游戏工具", "shot.json"),),
            {"shot": manifest("shot", "截图助手", "游戏工具")},
            {},
            "stable",
        )[0],
    )

    assert default_selected_category(ordered_categories(()), tiles) == "游戏工具"
