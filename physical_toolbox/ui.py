from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from physical_toolbox.app_config import AppConfig
from physical_toolbox.fonts import candidate_cjk_font_paths
from physical_toolbox.install_state import InstallStateStore
from physical_toolbox.launching import launch_entry
from physical_toolbox.manifest import ToolManifest
from physical_toolbox.package_manager import PackageManager
from physical_toolbox.repository import RepositoryClient
from physical_toolbox.tool_grid import ToolTile, build_tool_tiles, default_selected_category, ordered_categories


class ToolboxApp(QMainWindow):
    def __init__(self, workspace: Path, config: AppConfig) -> None:
        super().__init__()
        self.workspace = workspace
        self.config = config
        self.repository = RepositoryClient()
        self.state_store = InstallStateStore(workspace / "config" / "installed.json")
        self.package_manager = PackageManager(workspace, self.state_store)
        self.index_tools = []
        self.manifests: dict[str, ToolManifest] = {}
        self.tiles: tuple[ToolTile, ...] = ()
        self.category_buttons: dict[str, QPushButton] = {}
        self.selected_category = ""
        self.selected_tool_id: str | None = None
        self._drag_position: QPoint | None = None

        self.setWindowTitle(config.name)
        self.resize(1280, 750)
        self.setMinimumSize(1020, 620)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self._build_ui()
        QTimer.singleShot(80, self.check_updates)

    def _build_ui(self) -> None:
        root = QWidget(self)
        root.setObjectName("root")
        self.setCentralWidget(root)

        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = QFrame()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(250)
        layout.addWidget(self.sidebar)

        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 22, 0, 12)
        side_layout.setSpacing(0)

        title = QLabel(self.config.name)
        title.setObjectName("sideTitle")
        title.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(title)

        line = QFrame()
        line.setObjectName("sideLine")
        line.setFixedHeight(1)
        side_layout.addWidget(line)

        self.category_panel = QVBoxLayout()
        self.category_panel.setContentsMargins(0, 0, 0, 0)
        self.category_panel.setSpacing(0)
        side_layout.addLayout(self.category_panel)
        side_layout.addStretch()

        bottom_line = QFrame()
        bottom_line.setObjectName("sideLine")
        bottom_line.setFixedHeight(1)
        side_layout.addWidget(bottom_line)

        version = QLabel("Version : 0.1.0")
        version.setObjectName("sideVersion")
        version.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(version)

        main = QFrame()
        main.setObjectName("main")
        layout.addWidget(main, 1)

        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(20, 16, 20, 16)
        main_layout.setSpacing(16)

        top_bar = QHBoxLayout()
        top_bar.setSpacing(10)
        main_layout.addLayout(top_bar)

        self.hint_frame = QFrame()
        self.hint_frame.setObjectName("hintFrame")
        top_bar.addWidget(self.hint_frame, 1)

        hint_layout = QHBoxLayout(self.hint_frame)
        hint_layout.setContentsMargins(12, 0, 12, 0)
        self.hint_label = QLabel("提示：单击选择工具可查看工具说明，双击可启动工具。")
        self.hint_label.setObjectName("hintLabel")
        hint_layout.addWidget(self.hint_label)

        self.menu_button = self._window_button("≡")
        self.menu_button.clicked.connect(self.check_updates)
        top_bar.addWidget(self.menu_button)

        self.min_button = self._window_button("-")
        self.min_button.clicked.connect(self.showMinimized)
        top_bar.addWidget(self.min_button)

        self.close_button = self._window_button("×")
        self.close_button.clicked.connect(self.close)
        top_bar.addWidget(self.close_button)

        self.tool_list = QListWidget()
        self.tool_list.setObjectName("toolGrid")
        self.tool_list.setViewMode(QListWidget.IconMode)
        self.tool_list.setMovement(QListWidget.Static)
        self.tool_list.setResizeMode(QListWidget.Adjust)
        self.tool_list.setFlow(QListWidget.LeftToRight)
        self.tool_list.setWrapping(True)
        self.tool_list.setSpacing(14)
        self.tool_list.setIconSize(QSize(46, 46))
        self.tool_list.setGridSize(QSize(118, 96))
        self.tool_list.setUniformItemSizes(True)
        self.tool_list.setWordWrap(True)
        self.tool_list.itemClicked.connect(self._select_item)
        self.tool_list.itemDoubleClicked.connect(self._launch_item)
        main_layout.addWidget(self.tool_list, 1)

        self.detail_bar = QFrame()
        self.detail_bar.setObjectName("detailBar")
        self.detail_bar.setFixedHeight(112)
        main_layout.addWidget(self.detail_bar)

        detail_layout = QGridLayout(self.detail_bar)
        detail_layout.setContentsMargins(14, 10, 14, 10)
        detail_layout.setHorizontalSpacing(12)
        detail_layout.setVerticalSpacing(3)

        self.detail_title = QLabel("选择一个工具")
        self.detail_title.setObjectName("detailTitle")
        detail_layout.addWidget(self.detail_title, 0, 0)

        self.detail_text = QLabel("工具说明会显示在这里。")
        self.detail_text.setObjectName("detailText")
        self.detail_text.setWordWrap(True)
        detail_layout.addWidget(self.detail_text, 1, 0)

        self.version_combo = QComboBox()
        self.version_combo.setObjectName("versionCombo")
        self.version_combo.setFixedWidth(150)
        detail_layout.addWidget(self.version_combo, 0, 1, 2, 1)

        self.install_button = QPushButton("安装 / 更新")
        self.install_button.setObjectName("actionButton")
        self.install_button.clicked.connect(self.install_selected)
        detail_layout.addWidget(self.install_button, 0, 2, 2, 1)

        self.launch_button = QPushButton("启动")
        self.launch_button.setObjectName("actionButton")
        self.launch_button.clicked.connect(self.launch_selected)
        detail_layout.addWidget(self.launch_button, 0, 3, 2, 1)

        self.uninstall_button = QPushButton("卸载")
        self.uninstall_button.setObjectName("actionButton")
        self.uninstall_button.clicked.connect(self.uninstall_selected)
        detail_layout.addWidget(self.uninstall_button, 0, 4, 2, 1)

        self.open_dir_button = QPushButton("目录")
        self.open_dir_button.setObjectName("actionButton")
        self.open_dir_button.clicked.connect(self.open_selected_dir)
        detail_layout.addWidget(self.open_dir_button, 0, 5, 2, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("downloadProgress")
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setVisible(False)
        detail_layout.addWidget(self.progress_bar, 2, 0, 1, 6)

        self.install_button.setEnabled(False)
        self.launch_button.setEnabled(False)
        self.uninstall_button.setEnabled(False)
        self.open_dir_button.setEnabled(False)

        detail_layout.setColumnStretch(0, 1)

        self.setStyleSheet(
            """
            QWidget#root {
                background: transparent;
                color: white;
                font-family: "Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "SimHei", sans-serif;
            }
            QFrame#sidebar {
                background: rgba(16, 83, 161, 165);
                border-right: 1px solid rgba(255, 255, 255, 22);
            }
            QLabel#sideTitle {
                color: white;
                font-size: 20px;
                min-height: 48px;
            }
            QFrame#sideLine {
                background: rgba(0, 30, 90, 45);
            }
            QLabel#sideVersion {
                color: white;
                font-size: 14px;
                min-height: 36px;
            }
            QPushButton#categoryButton {
                background: transparent;
                border: 0;
                color: white;
                font-size: 17px;
                min-height: 50px;
                text-align: center;
            }
            QPushButton#categoryButton:hover {
                background: rgba(255, 255, 255, 22);
            }
            QPushButton#categoryButton:checked {
                background: rgba(255, 255, 255, 30);
                border-left: 4px solid rgba(255, 255, 255, 180);
                padding-left: -4px;
            }
            QFrame#main {
                background: transparent;
            }
            QFrame#hintFrame {
                background: rgba(255, 255, 255, 32);
                min-height: 40px;
                max-height: 40px;
            }
            QLabel#hintLabel {
                color: white;
                font-size: 15px;
                font-weight: 600;
            }
            QPushButton#windowButton {
                background: rgba(255, 255, 255, 16);
                border: 0;
                color: white;
                font-size: 18px;
                min-width: 38px;
                max-width: 38px;
                min-height: 40px;
                max-height: 40px;
            }
            QPushButton#windowButton:hover {
                background: rgba(255, 255, 255, 36);
            }
            QListWidget#toolGrid {
                background: transparent;
                border: 0;
                color: white;
                outline: 0;
                font-size: 13px;
            }
            QListWidget#toolGrid::item {
                background: transparent;
                border-radius: 6px;
                padding: 4px;
            }
            QListWidget#toolGrid::item:hover {
                background: rgba(255, 255, 255, 24);
            }
            QListWidget#toolGrid::item:selected {
                background: rgba(255, 255, 255, 38);
            }
            QFrame#detailBar {
                background: rgba(255, 255, 255, 24);
                border-top: 1px solid rgba(255, 255, 255, 34);
            }
            QLabel#detailTitle {
                color: white;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#detailText {
                color: rgba(235, 252, 255, 225);
                font-size: 13px;
            }
            QComboBox#versionCombo {
                background: rgba(255, 255, 255, 238);
                border: 0;
                color: #165172;
                min-height: 32px;
                padding-left: 8px;
            }
            QPushButton#actionButton {
                background: rgba(255, 255, 255, 235);
                border: 0;
                color: #11536f;
                min-width: 82px;
                min-height: 34px;
                font-weight: 700;
            }
            QPushButton#actionButton:hover {
                background: white;
            }
            QProgressBar#downloadProgress {
                background: rgba(255, 255, 255, 52);
                border: 0;
                color: white;
                min-height: 14px;
                max-height: 14px;
                text-align: center;
                font-size: 10px;
            }
            QProgressBar#downloadProgress::chunk {
                background: rgba(83, 227, 178, 210);
            }
            """
        )

    def _window_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("windowButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        return button

    def check_updates(self) -> None:
        try:
            index = self.repository.load_index(self.config.index_url)
            self.index_tools = list(index.tools)
            self.manifests = {
                item.id: self.repository.load_manifest(item.manifest_url)
                for item in self.index_tools
            }
            self.tiles = build_tool_tiles(
                self.index_tools,
                self.manifests,
                self.package_manager.installed_tools(),
                self.config.channel,
            )
        except Exception as exc:
            self.hint_label.setText(f"清单加载失败：{exc}")
            return

        self._render_categories()
        if not self.selected_category:
            self.select_category(default_selected_category(ordered_categories(self.index_tools), self.tiles))
        else:
            self.select_category(self.selected_category)
        self.hint_label.setText(f"提示：已加载 {len(self.tiles)} 个工具。单击查看说明，双击启动工具。")
        self._sync_action_buttons()

    def _render_categories(self) -> None:
        for button in self.category_buttons.values():
            button.deleteLater()
        self.category_buttons.clear()

        for category in ordered_categories(self.index_tools):
            button = QPushButton(category)
            button.setObjectName("categoryButton")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, name=category: self.select_category(name))
            self.category_panel.addWidget(button)
            self.category_buttons[category] = button

    def select_category(self, category: str) -> None:
        self.selected_category = category
        for name, button in self.category_buttons.items():
            button.setChecked(name == category)
        self._render_tools(category)

    def _render_tools(self, category: str) -> None:
        self.tool_list.clear()
        visible_tiles = [tile for tile in self.tiles if tile.category == category]
        for tile in visible_tiles:
            item = QListWidgetItem(self._icon_for_tile(tile), tile.name)
            item.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            item.setToolTip(f"{tile.name}\n{tile.status_text}\n{tile.description}")
            item.setData(Qt.UserRole, tile.id)
            self.tool_list.addItem(item)

        if not visible_tiles:
            self.detail_title.setText(category)
            self.detail_text.setText("这个分类下暂时没有工具。")
            self.version_combo.clear()
            self.selected_tool_id = None

    def _select_item(self, item: QListWidgetItem) -> None:
        tool_id = item.data(Qt.UserRole)
        self.selected_tool_id = tool_id
        tile = self._tile(tool_id)
        if tile is None:
            return

        self.detail_title.setText(f"{tile.name} · {tile.status_text}")
        self.detail_text.setText(tile.description or "暂无说明。")
        self.hint_label.setText(f"工具说明：{tile.description or tile.name}")
        self.version_combo.clear()
        self.version_combo.addItems(tile.available_versions)
        if tile.latest_version:
            index = self.version_combo.findText(tile.latest_version)
            if index >= 0:
                self.version_combo.setCurrentIndex(index)
        self._sync_action_buttons()

    def _launch_item(self, item: QListWidgetItem) -> None:
        self.selected_tool_id = item.data(Qt.UserRole)
        self.launch_selected()

    def install_selected(self) -> None:
        manifest = self._selected_manifest()
        if manifest is None:
            return
        version = self.version_combo.currentText()
        if not version:
            QMessageBox.information(self, "请选择版本", "请先选择要安装的版本。")
            return
        try:
            self._set_busy(True)
            self._show_progress("准备下载...")
            self.package_manager.install(manifest, version, progress_callback=self._update_download_progress)
        except Exception as exc:
            self._show_progress("下载 / 安装失败")
            QMessageBox.critical(self, "安装失败", str(exc))
            return
        finally:
            self._set_busy(False)
        self.hint_label.setText(f"{manifest.name} 已安装：{version}")
        self._show_progress("完成")
        self.check_updates()

    def uninstall_selected(self) -> None:
        manifest = self._selected_manifest()
        if manifest is None:
            return
        if manifest.id not in self.package_manager.installed_tools():
            QMessageBox.information(self, "未安装", "这个工具还没有安装。")
            return
        result = QMessageBox.question(
            self,
            "确认卸载",
            f"确定卸载 {manifest.name} 吗？这会删除本地 tools 目录下的安装文件。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if result != QMessageBox.Yes:
            return
        try:
            self.package_manager.uninstall(manifest.id)
        except Exception as exc:
            QMessageBox.critical(self, "卸载失败", f"{exc}\n\n请先关闭这个工具后再卸载。")
            return
        self.hint_label.setText(f"{manifest.name} 已卸载")
        self.progress_bar.setVisible(False)
        self.check_updates()

    def launch_selected(self) -> None:
        manifest = self._selected_manifest()
        if manifest is None:
            return
        installed = self.package_manager.installed_tools().get(manifest.id)
        if installed is None:
            QMessageBox.information(self, "未安装", "请先安装这个工具。")
            return
        entry = self.workspace / "tools" / manifest.id / installed.entry
        if not entry.exists():
            QMessageBox.critical(self, "启动失败", f"入口文件不存在：{entry}")
            return
        launch_entry(entry)

    def open_selected_dir(self) -> None:
        manifest = self._selected_manifest()
        if manifest is None:
            return
        path = self.workspace / "tools" / manifest.id
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(path)])

    def _selected_manifest(self) -> ToolManifest | None:
        if self.selected_tool_id is None:
            QMessageBox.information(self, "请选择工具", "请先选择一个工具。")
            return None
        return self.manifests.get(self.selected_tool_id)

    def _tile(self, tool_id: str) -> ToolTile | None:
        for tile in self.tiles:
            if tile.id == tool_id:
                return tile
        return None

    def _set_busy(self, busy: bool) -> None:
        if busy:
            for button in (self.install_button, self.launch_button, self.uninstall_button, self.open_dir_button):
                button.setEnabled(False)
            return
        self._sync_action_buttons()

    def _sync_action_buttons(self) -> None:
        tile = self._tile(self.selected_tool_id) if self.selected_tool_id else None
        has_selection = tile is not None
        is_installed = bool(tile and tile.is_installed)
        self.install_button.setEnabled(has_selection)
        self.launch_button.setEnabled(is_installed)
        self.open_dir_button.setEnabled(is_installed)
        self.uninstall_button.setEnabled(is_installed)

    def _show_progress(self, text: str) -> None:
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100 if text == "完成" else 0)
        self.progress_bar.setFormat(text)
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def _update_download_progress(self, downloaded: int, total: int | None) -> None:
        if total and total > 0:
            percent = min(100, int(downloaded * 100 / total))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"下载中 {percent}%")
        else:
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(f"下载中 {downloaded // 1024} KB")
        app = QApplication.instance()
        if app is not None:
            app.processEvents()

    def _icon_for_tile(self, tile: ToolTile) -> QIcon:
        icon_path = Path(tile.icon)
        if tile.icon and icon_path.exists():
            return QIcon(str(icon_path))
        return QIcon(self._fallback_icon(tile))

    def _fallback_icon(self, tile: ToolTile) -> QPixmap:
        pixmap = QPixmap(56, 56)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)

        seed = sum(ord(char) for char in tile.id)
        hue = seed % 360
        color_a = QColor.fromHsv(hue, 180, 245)
        color_b = QColor.fromHsv((hue + 36) % 360, 210, 210)

        gradient = QLinearGradient(8, 8, 48, 48)
        gradient.setColorAt(0, color_a)
        gradient.setColorAt(1, color_b)

        path = QPainterPath()
        path.addRoundedRect(QRect(7, 7, 42, 42), 8, 8)
        painter.fillPath(path, gradient)
        painter.setPen(QPen(QColor(255, 255, 255, 210), 2))
        painter.drawPath(path)

        painter.setFont(QFont("Microsoft YaHei UI", 14, QFont.Bold))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(QRect(8, 8, 40, 40), Qt.AlignCenter, tile.name[:1])

        if tile.is_installed:
            painter.setBrush(QColor(80, 220, 125))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QRect(39, 6, 11, 11))

        painter.end()
        return pixmap

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        gradient = QLinearGradient(self.rect().topLeft(), self.rect().topRight())
        gradient.setColorAt(0, QColor("#1f63bf"))
        gradient.setColorAt(0.55, QColor("#118ccd"))
        gradient.setColorAt(1, QColor("#17c5c8"))
        painter.fillRect(self.rect(), gradient)
        super().paintEvent(event)

    def mousePressEvent(self, event) -> None:  # type: ignore[override]
        if event.button() == Qt.LeftButton and event.position().y() <= 62:
            self._drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[override]
        if self._drag_position is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_position)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # type: ignore[override]
        self._drag_position = None
        super().mouseReleaseEvent(event)


def create_application() -> QApplication:
    app = QApplication.instance()
    if app is not None:
        return app
    QApplication.setStyle("Fusion")
    app = QApplication([])
    configure_application_font(app)
    return app


def configure_application_font(app: QApplication) -> None:
    for path in candidate_cjk_font_paths():
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id < 0:
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
            return

    for family in QFontDatabase.families():
        if family in {"Noto Sans SC", "Microsoft YaHei UI", "Microsoft YaHei", "SimHei", "SimSun", "DengXian"}:
            app.setFont(QFont(family, 10))
            return
