import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

from physical_toolbox.about import ABOUT_NAV_ID
from physical_toolbox.app_config import AppConfig
from physical_toolbox.install_state import InstalledTool, InstallStateStore
from physical_toolbox.repository import IndexTool, ToolboxIndex, ToolboxUpdate
from physical_toolbox.ui import ToolboxApp, create_application


class SlowRepository:
    started = False

    def load_index(self, url: str) -> ToolboxIndex:
        self.started = True
        time.sleep(0.25)
        return ToolboxIndex(
            schema_version=1,
            latest_toolbox_version="0.1.0",
            min_supported_version="0.1.0",
            tools=(),
        )

    def load_manifest(self, url: str):
        raise AssertionError("No manifests should be loaded for an empty index")


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


def test_window_constructs_complete_initial_ui_before_update_starts(tmp_path) -> None:
    app = create_application()
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    repository = SlowRepository()

    window = ToolboxApp(tmp_path, config)
    window.repository = repository

    assert ABOUT_NAV_ID in window.category_buttons
    assert not window.about_page.isHidden()
    assert window.tool_list.isHidden()
    assert getattr(window, "_update_thread", None) is None
    assert not repository.started

    window.close()
    app.processEvents()


def test_window_loads_installed_tools_before_background_update_starts(tmp_path) -> None:
    app = create_application()
    tool_dir = tmp_path / "tools" / "demo_tool"
    tool_dir.mkdir(parents=True)
    (tool_dir / "run.cmd").write_text("@echo off\n", encoding="utf-8")
    (tool_dir / "tool.json").write_text(
        """
        {
          "schemaVersion": 1,
          "id": "demo_tool",
          "name": "本地演示工具",
          "category": "游戏工具",
          "description": "已经安装在本地的工具",
          "icon": "",
          "entry": "run.cmd",
          "needAdmin": false,
          "latest": {"stable": "1.0.0"},
          "versions": [
            {
              "version": "1.0.0",
              "channel": "stable",
              "packageUrl": "",
              "sha256": ""
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    InstallStateStore(tmp_path / "config" / "installed.json").save(
        {
            "demo_tool": InstalledTool(
                id="demo_tool",
                name="本地演示工具",
                version="1.0.0",
                channel="stable",
                entry="run.cmd",
                installed_at="2026-06-22T12:00:00+08:00",
                updated_at="2026-06-22T12:00:00+08:00",
            )
        }
    )
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    repository = SlowRepository()

    window = ToolboxApp(tmp_path, config)
    window.repository = repository

    assert "游戏工具" in window.category_buttons
    assert window.selected_category == "游戏工具"
    assert window.tool_list.count() == 1
    assert window.tool_list.item(0).data(Qt.UserRole) == "demo_tool"
    window._select_item(window.tool_list.item(0))
    assert window.launch_button.isEnabled()
    assert getattr(window, "_update_thread", None) is None
    assert not repository.started

    window.close()
    app.processEvents()


def test_check_updates_starts_background_load_without_blocking_ui(tmp_path) -> None:
    app = create_application()
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    window = ToolboxApp(tmp_path, config)
    window.repository = SlowRepository()

    started = time.monotonic()
    window.check_updates()
    elapsed = time.monotonic() - started

    assert elapsed < 0.1
    thread = getattr(window, "_update_thread", None)
    assert thread is not None
    thread.join(timeout=1)

    window.close()
    app.processEvents()


def test_toolbox_update_notice_does_not_interrupt_loaded_tools(tmp_path) -> None:
    app = create_application()
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    window = ToolboxApp(tmp_path, config)
    window.index_tools = [IndexTool("demo", "演示工具", "游戏工具", "demo.json")]
    window.tiles = ()
    window._render_categories()
    window.select_category("游戏工具")

    update = ToolboxUpdate(
        latest_version="0.2.0",
        min_supported_version="0.1.0",
        release_url="https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/tag/v0.2.0",
        package_url="https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/download/v0.2.0/PhysicalWorldToolbox-0.2.0-win-x64.zip",
    )

    window._apply_update_result(update, window.index_tools, {}, ())

    assert window.selected_category == "游戏工具"
    assert window.toolbox_update_info == update
    assert "0.2.0" in window.hint_label.text()

    window.close()
    app.processEvents()


def test_download_toolbox_update_starts_independent_updater_when_confirmed(
    tmp_path, monkeypatch
) -> None:
    app = create_application()
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    package_path = tmp_path / "downloads" / "PhysicalWorldToolbox-0.2.0-win-x64.zip"
    package_path.parent.mkdir(parents=True)
    package_path.write_bytes(b"new")
    started: list[object] = []

    class FakeDownloader:
        def download(self, update, progress_callback=None):
            if progress_callback is not None:
                progress_callback(package_path.stat().st_size, package_path.stat().st_size)
            return package_path

    class FakeSelfUpdater:
        def start(self, package):
            started.append(package)

    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    window = ToolboxApp(tmp_path, config)
    window.toolbox_update_downloader = FakeDownloader()
    window.self_update_runner = FakeSelfUpdater()
    window.toolbox_update_info = ToolboxUpdate(
        latest_version="0.2.0",
        package_url=package_path.as_uri(),
        sha256="",
    )

    window.download_toolbox_update()

    assert started == [package_path]
    assert not window.isVisible()

    window.close()
    app.processEvents()


def test_generated_icon_is_used_only_as_window_icon_not_internal_artwork(tmp_path) -> None:
    app = create_application()
    config = AppConfig(
        name="物理世界的工具箱",
        index_url=(tmp_path / "index.json").resolve().as_uri(),
        channel="stable",
    )
    window = ToolboxApp(tmp_path, config)
    window._render_categories()
    window.select_about_page()

    assert not window.windowIcon().isNull()
    assert window.findChild(type(window.hint_label), "sideLogo") is None
    assert window.about_page.findChild(type(window.hint_label), "aboutIcon") is None

    window.close()
    app.processEvents()
