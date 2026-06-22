import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from physical_toolbox.about import ABOUT_NAV_ID
from physical_toolbox.app_config import AppConfig
from physical_toolbox.repository import IndexTool
from physical_toolbox.ui import ToolboxApp, create_application


def test_about_page_is_fixed_sidebar_destination(tmp_path) -> None:
    app = create_application()
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    window = ToolboxApp(tmp_path, config)
    window.index_tools = [IndexTool("demo", "演示工具", "游戏工具", "demo.json")]

    window._render_categories()
    window.select_about_page()

    assert ABOUT_NAV_ID in window.category_buttons
    assert window.category_buttons[ABOUT_NAV_ID].text() == "关于页"
    assert not window.about_page.isHidden()
    assert window.tool_list.isHidden()
    assert window.detail_bar.isHidden()

    window.close()
    app.processEvents()
