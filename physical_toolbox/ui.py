from __future__ import annotations

import json
import queue
import subprocess
import threading
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QProgressBar,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from physical_toolbox import __version__
from physical_toolbox.about import ABOUT_NAV_ID, ABOUT_NAV_LABEL, toolbox_about_info
from physical_toolbox.app_config import AppConfig, DEFAULT_GITHUB_PROXY_URLS, save_config
from physical_toolbox.github_proxy import normalize_proxy_urls
from physical_toolbox.fonts import candidate_cjk_font_paths
from physical_toolbox.install_state import InstallStateStore
from physical_toolbox.launching import launch_entry
from physical_toolbox.manifest import ToolManifest
from physical_toolbox.package_manager import PackageManager
from physical_toolbox.repository import IndexTool, RepositoryClient, ToolboxUpdate
from physical_toolbox.self_updater import SelfUpdateRunner
from physical_toolbox.toolbox_update import ToolboxUpdateDownloader, is_toolbox_update_available
from physical_toolbox.tool_grid import ToolTile, build_tool_tiles, default_selected_category, ordered_categories

ASSET_DIR = Path(__file__).resolve().parent / "assets"
APP_ICON_PATH = ASSET_DIR / "toolbox-icon.ico"
MAX_UPDATE_WORKERS = 8


class AboutPage(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.info = toolbox_about_info()
        self.setObjectName("aboutPage")

        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setObjectName("aboutScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        page_layout.addWidget(scroll)

        content = QWidget()
        content.setObjectName("aboutContent")
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(4, 4, 12, 4)
        layout.setSpacing(14)

        layout.addWidget(self._hero())
        layout.addWidget(
            self._card(
                "工具箱说明",
                (
                    "这是一个集中管理 DNF 工具的桌面工具箱，用来统一处理工具下载、安装、更新、启动和卸载。\n"
                    "每个工具都按独立 manifest 和 GitHub Release 安装包管理，更新内容由远程 registry 提供。"
                ),
            )
        )
        layout.addWidget(
            self._card(
                "联系方式",
                f"作者：{self.info.author}\nQQ号：{self.info.qq_number}\n问题反馈：{self.info.feedback_url}\nGitHub：{self.info.github_url}",
            )
        )
        layout.addWidget(self._sponsor_card())
        layout.addWidget(self._log_card())
        layout.addStretch()

    def _hero(self) -> QFrame:
        hero = QFrame()
        hero.setObjectName("aboutHero")
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(10)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(8)
        layout.addLayout(text_layout)

        title = QLabel(self.info.title)
        title.setObjectName("aboutTitle")
        text_layout.addWidget(title)

        tagline = QLabel(self.info.tagline)
        tagline.setObjectName("aboutTagline")
        tagline.setWordWrap(True)
        text_layout.addWidget(tagline)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        text_layout.addLayout(button_layout)
        button_layout.addWidget(self._small_button("复制QQ号", self.copy_qq_number))
        button_layout.addWidget(self._small_button("问题反馈", lambda: self.open_url(self.info.feedback_url)))
        button_layout.addWidget(self._small_button("Bilibili", lambda: self.open_url(self.info.bilibili_url)))
        button_layout.addWidget(self._small_button("GitHub", lambda: self.open_url(self.info.github_url)))
        button_layout.addStretch()

        return hero

    def _card(self, title: str, body: str) -> QFrame:
        card = QFrame()
        card.setObjectName("aboutCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("aboutCardTitle")
        layout.addWidget(title_label)

        body_label = QLabel(body)
        body_label.setObjectName("aboutCardText")
        body_label.setWordWrap(True)
        body_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(body_label)
        return card

    def _sponsor_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("aboutCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        title_label = QLabel("赞助支持")
        title_label.setObjectName("aboutCardTitle")
        layout.addWidget(title_label)

        hint = QLabel("如果这些工具对你有帮助，可以请作者喝杯咖啡")
        hint.setObjectName("sponsorHint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        qr_layout = QHBoxLayout()
        qr_layout.setSpacing(18)
        layout.addLayout(qr_layout)

        for qr in self.info.sponsor_qrs:
            qr_layout.addWidget(self._sponsor_qr(qr))
        qr_layout.addStretch()
        return card

    def _sponsor_qr(self, qr) -> QFrame:
        item = QFrame()
        item.setObjectName("sponsorItem")
        layout = QVBoxLayout(item)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        image_label = QLabel()
        image_label.setObjectName(f"sponsorQr_{qr.id}")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedSize(420, 620)

        pixmap = QPixmap(str(qr.image_path))
        if not pixmap.isNull():
            image_label.setPixmap(pixmap.scaled(QSize(400, 580), Qt.KeepAspectRatio, Qt.FastTransformation))

        title_label = QLabel(qr.title)
        title_label.setObjectName("sponsorTitle")
        title_label.setAlignment(Qt.AlignCenter)

        layout.addWidget(image_label)
        layout.addWidget(title_label)
        return item

    def _log_card(self) -> QFrame:
        text = []
        for entry in self.info.logs:
            text.append(f"{entry.version}  {entry.date}")
            text.extend(f"  - {item}" for item in entry.items)
            text.append("")
        return self._card("更新日志", "\n".join(text).strip())

    def _small_button(self, text: str, callback) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("aboutButton")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(callback)
        return button

    def copy_qq_number(self) -> None:
        QApplication.clipboard().setText(self.info.qq_number)
        QMessageBox.information(self, "已复制", f"QQ号 {self.info.qq_number} 已复制到剪贴板。")

    def open_url(self, url: str) -> None:
        QDesktopServices.openUrl(QUrl(url))


class ProxySettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("下载代理设置")
        self.setMinimumWidth(560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        self.enabled_checkbox = QCheckBox("启用 GitHub 公共加速代理")
        self.enabled_checkbox.setChecked(config.github_proxy_enabled)
        layout.addWidget(self.enabled_checkbox)

        hint = QLabel("每行填写一个代理站。普通前缀会自动拼接 GitHub 原始地址，也支持 {url} 或 {encoded_url} 模板。")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.proxy_edit = QPlainTextEdit()
        self.proxy_edit.setPlaceholderText("https://ghfast.top/")
        self.proxy_edit.setPlainText("\n".join(config.github_proxy_urls))
        self.proxy_edit.setMinimumHeight(180)
        layout.addWidget(self.proxy_edit)

        actions = QHBoxLayout()
        restore_button = QPushButton("恢复默认代理")
        restore_button.clicked.connect(self.restore_defaults)
        actions.addWidget(restore_button)
        actions.addStretch()

        buttons = QDialogButtonBox()
        save_button = buttons.addButton("保存", QDialogButtonBox.AcceptRole)
        cancel_button = buttons.addButton("取消", QDialogButtonBox.RejectRole)
        save_button.setDefault(True)
        cancel_button.setAutoDefault(False)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        actions.addWidget(buttons)
        layout.addLayout(actions)

    def restore_defaults(self) -> None:
        self.enabled_checkbox.setChecked(True)
        self.proxy_edit.setPlainText("\n".join(DEFAULT_GITHUB_PROXY_URLS))

    def proxy_enabled(self) -> bool:
        return self.enabled_checkbox.isChecked()

    def proxy_urls(self) -> tuple[str, ...]:
        return normalize_proxy_urls(self.proxy_edit.toPlainText().splitlines())


class ToolboxApp(QMainWindow):
    def __init__(self, workspace: Path, config: AppConfig) -> None:
        super().__init__()
        self.workspace = workspace
        self.config = config
        self.repository = RepositoryClient(proxy_config=config.github_proxy_config())
        self.state_store = InstallStateStore(workspace / "config" / "installed.json")
        self.package_manager = PackageManager(workspace, self.state_store, proxy_config=config.github_proxy_config())
        self.toolbox_update_downloader = ToolboxUpdateDownloader(workspace, proxy_config=config.github_proxy_config())
        self.self_update_runner = SelfUpdateRunner(workspace)
        self.index_tools = []
        self.manifests: dict[str, ToolManifest] = {}
        self.tiles: tuple[ToolTile, ...] = ()
        self.toolbox_update_info: ToolboxUpdate | None = None
        self.category_buttons: dict[str, QPushButton] = {}
        self.selected_category = ""
        self.selected_tool_id: str | None = None
        self._drag_position: QPoint | None = None
        self._update_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._update_thread: threading.Thread | None = None
        self._startup_about_pending_remote = False

        self.setWindowTitle(config.name)
        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.resize(1280, 750)
        self.setMinimumSize(1020, 620)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.setAttribute(Qt.WA_TranslucentBackground, False)

        self._build_ui()
        self._render_initial_ui()

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

        version = QLabel(f"Version : {__version__}")
        version.setObjectName("sideVersion")
        version.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(version)

        self.side_update_status = QLabel("")
        self.side_update_status.setObjectName("sideUpdateStatus")
        self.side_update_status.setAlignment(Qt.AlignCenter)
        self.side_update_status.setVisible(False)
        side_layout.addWidget(self.side_update_status)

        self.side_update_progress = QProgressBar()
        self.side_update_progress.setObjectName("sideUpdateProgress")
        self.side_update_progress.setRange(0, 100)
        self.side_update_progress.setValue(0)
        self.side_update_progress.setTextVisible(False)
        self.side_update_progress.setVisible(False)
        side_layout.addWidget(self.side_update_progress)

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
        self.menu_button.clicked.connect(self.show_app_menu)
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
        self.tool_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tool_list.customContextMenuRequested.connect(self.show_tool_context_menu)
        self.tool_list.itemClicked.connect(self._select_item)
        self.tool_list.itemDoubleClicked.connect(self._launch_item)
        main_layout.addWidget(self.tool_list, 1)

        self.about_page = AboutPage()
        self.about_page.setVisible(False)
        main_layout.addWidget(self.about_page, 1)

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
            QLabel#sideUpdateStatus {
                color: rgba(235, 252, 255, 220);
                font-size: 11px;
                min-height: 18px;
                max-height: 18px;
            }
            QProgressBar#sideUpdateProgress {
                margin-left: 58px;
                margin-right: 58px;
                margin-bottom: 8px;
                background: rgba(255, 255, 255, 45);
                border: 0;
                min-height: 5px;
                max-height: 5px;
            }
            QProgressBar#sideUpdateProgress::chunk {
                background: rgba(83, 227, 178, 220);
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
            QFrame#aboutPage, QWidget#aboutContent {
                background: transparent;
            }
            QScrollArea#aboutScroll {
                background: transparent;
                border: 0;
            }
            QFrame#aboutHero {
                background: rgba(255, 255, 255, 32);
                border: 1px solid rgba(255, 255, 255, 34);
            }
            QLabel#aboutTitle {
                color: white;
                font-size: 25px;
                font-weight: 800;
            }
            QLabel#aboutTagline {
                color: rgba(235, 252, 255, 225);
                font-size: 14px;
            }
            QPushButton#aboutButton {
                background: rgba(255, 255, 255, 226);
                border: 0;
                color: #11536f;
                min-width: 78px;
                min-height: 30px;
                font-weight: 700;
            }
            QPushButton#aboutButton:hover {
                background: white;
            }
            QFrame#aboutCard {
                background: rgba(255, 255, 255, 26);
                border-top: 1px solid rgba(255, 255, 255, 30);
            }
            QLabel#aboutCardTitle {
                color: white;
                font-size: 16px;
                font-weight: 800;
            }
            QLabel#aboutCardText {
                color: rgba(235, 252, 255, 230);
                font-size: 13px;
            }
            QLabel#sponsorHint {
                color: rgba(235, 252, 255, 230);
                font-size: 13px;
            }
            QFrame#sponsorItem {
                background: transparent;
                border: 0;
            }
            QLabel#sponsorQr_weixin, QLabel#sponsorQr_zhifubao {
                background: rgba(255, 255, 255, 235);
                border: 1px solid rgba(255, 255, 255, 120);
            }
            QLabel#sponsorTitle {
                color: rgba(235, 252, 255, 235);
                font-size: 13px;
                font-weight: 700;
            }
            """
        )

    def _window_button(self, text: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("windowButton")
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)
        return button

    def show_app_menu(self) -> None:
        menu = QMenu(self)

        check_action = QAction("检查更新", self)
        check_action.triggered.connect(self.check_updates)
        menu.addAction(check_action)

        proxy_action = QAction("下载代理设置", self)
        proxy_action.triggered.connect(self.configure_github_proxy)
        menu.addAction(proxy_action)

        if self.toolbox_update_info is not None:
            download_action = QAction(f"下载工具箱 {self.toolbox_update_info.latest_version}", self)
            download_action.setEnabled(bool(self.toolbox_update_info.package_url))
            download_action.triggered.connect(self.download_toolbox_update)
            menu.addAction(download_action)

            release_action = QAction("打开新版发布页", self)
            release_action.setEnabled(bool(self.toolbox_update_info.release_url))
            release_action.triggered.connect(self.open_toolbox_release)
            menu.addAction(release_action)
        else:
            current_action = QAction("工具箱已是当前版本", self)
            current_action.setEnabled(False)
            menu.addAction(current_action)

        feedback_action = QAction("问题反馈", self)
        feedback_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(toolbox_about_info().feedback_url)))
        menu.addAction(feedback_action)

        menu.exec(self.menu_button.mapToGlobal(self.menu_button.rect().bottomLeft()))

    def configure_github_proxy(self) -> None:
        dialog = ProxySettingsDialog(self.config, self)
        if dialog.exec() != QDialog.Accepted:
            return

        self.config = self.config.with_github_proxy(
            enabled=dialog.proxy_enabled(),
            urls=dialog.proxy_urls(),
        )
        save_config(self.workspace, self.config)
        self._apply_network_config()
        self.hint_label.setText("下载代理设置已保存，后续检查更新和下载会使用新配置。")

    def _apply_network_config(self) -> None:
        proxy_config = self.config.github_proxy_config()
        self.repository.proxy_config = proxy_config
        self.package_manager.proxy_config = proxy_config
        self.toolbox_update_downloader = ToolboxUpdateDownloader(self.workspace, proxy_config=proxy_config)

    def show_tool_context_menu(self, position: QPoint) -> None:
        item = self.tool_list.itemAt(position)
        if item is None:
            return
        tool_id = item.data(Qt.UserRole)
        if not tool_id:
            return

        menu = QMenu(self)
        copy_action = QAction("复制项目地址", self)
        copy_action.triggered.connect(lambda _checked=False, item_id=tool_id: self.copy_project_address(item_id))
        menu.addAction(copy_action)
        menu.exec(self.tool_list.mapToGlobal(position))

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)

    def _render_initial_ui(self) -> None:
        if self._load_local_tools():
            self._startup_about_pending_remote = False
            self.hint_label.setText("本地工具已就绪。需要更新时可在右上角菜单手动检查。")
            return

        self._render_categories()
        self.select_about_page()
        self._startup_about_pending_remote = True
        self.hint_label.setText("工具箱已启动。可在右上角菜单手动检查更新。")

    def _load_local_tools(self) -> bool:
        installed_tools = self.package_manager.installed_tools()
        index_tools: list[IndexTool] = []
        manifests: dict[str, ToolManifest] = {}

        for tool_id in sorted(installed_tools):
            manifest_path = self.workspace / "tools" / tool_id / "tool.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = ToolManifest.from_dict(json.loads(manifest_path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if manifest.id != tool_id:
                continue
            manifests[manifest.id] = manifest
            index_tools.append(
                IndexTool(
                    id=manifest.id,
                    name=manifest.name,
                    category=manifest.category,
                    manifest_url=str(manifest_path),
                )
            )

        tiles = build_tool_tiles(index_tools, manifests, installed_tools, self.config.channel)
        self.index_tools = index_tools
        self.manifests = manifests
        self.tiles = tiles
        if not tiles:
            return False

        self._render_categories()
        self.select_category(default_selected_category(ordered_categories(self.index_tools), self.tiles))
        return True

    def check_updates(self) -> None:
        if self._update_thread is not None and self._update_thread.is_alive():
            self._show_update_activity("检查更新中...", None, None)
            self.hint_label.setText("后台检查更新中...")
            return

        self.hint_label.setText("后台检查更新中...")
        self._clear_update_queue()
        self._show_update_activity("连接更新源...", None, None)
        self.menu_button.setEnabled(False)
        self._update_thread = threading.Thread(target=self._load_updates_worker, daemon=True)
        self._update_thread.start()
        QTimer.singleShot(50, self._poll_update_queue)

    def _load_updates_worker(self) -> None:
        try:
            self._update_queue.put(("progress", ("连接更新源...", None, None)))
            index = self.repository.load_index(self.config.index_url)
            index_tools = list(index.tools)
            manifests = self._load_manifests_concurrently(index_tools)
            self._update_queue.put(("progress", ("整理工具列表...", len(index_tools), len(index_tools))))
            tiles = build_tool_tiles(
                index_tools,
                manifests,
                self.package_manager.installed_tools(),
                self.config.channel,
            )
        except Exception as exc:
            self._update_queue.put(("error", exc))
            return
        self._update_queue.put(("ok", (index.toolbox_update, index_tools, manifests, tiles)))

    def _load_manifests_concurrently(self, index_tools: list[IndexTool]) -> dict[str, ToolManifest]:
        if not index_tools:
            return {}

        total = len(index_tools)
        done = 0
        manifests: dict[str, ToolManifest] = {}
        worker_count = min(MAX_UPDATE_WORKERS, total)
        self._update_queue.put(("progress", (f"加载工具清单 0/{total}", 0, total)))

        work_queue: queue.Queue[IndexTool] = queue.Queue()
        result_queue: queue.Queue[tuple[str, str, object]] = queue.Queue()

        for item in index_tools:
            work_queue.put(item)

        def worker() -> None:
            while True:
                try:
                    item = work_queue.get_nowait()
                except queue.Empty:
                    return

                try:
                    manifest = self.repository.load_manifest(item.manifest_url)
                except Exception as exc:
                    result_queue.put(("error", item.id, exc))
                else:
                    result_queue.put(("ok", item.id, manifest))
                finally:
                    work_queue.task_done()

        for _ in range(worker_count):
            thread = threading.Thread(target=worker, daemon=True)
            thread.start()

        first_error: tuple[str, Exception] | None = None
        while done < total:
            status, tool_id, value = result_queue.get()
            done += 1
            if status == "ok":
                manifests[tool_id] = value  # type: ignore[assignment]
            elif first_error is None and isinstance(value, Exception):
                first_error = (tool_id, value)
            self._update_queue.put(("progress", (f"加载工具清单 {done}/{total}", done, total)))

        if first_error is not None:
            tool_id, error = first_error
            raise RuntimeError(f"{tool_id}: {error}") from error

        return manifests

    def _poll_update_queue(self) -> None:
        try:
            status, payload = self._update_queue.get_nowait()
        except queue.Empty:
            if self._update_thread is not None and self._update_thread.is_alive():
                QTimer.singleShot(50, self._poll_update_queue)
            else:
                self.menu_button.setEnabled(True)
                self._hide_update_activity()
            return

        if status == "progress":
            text, current, total = payload  # type: ignore[misc]
            self._show_update_activity(str(text), current, total)
            QTimer.singleShot(80, self._poll_update_queue)
            return

        self.menu_button.setEnabled(True)
        if status == "error":
            self._finish_update_activity("检查失败", success=False)
            self.hint_label.setText(f"清单加载失败：{payload}")
            self._sync_action_buttons()
            return

        toolbox_update, index_tools, manifests, tiles = payload  # type: ignore[misc]
        self._finish_update_activity("检查完成", success=True)
        self._apply_update_result(toolbox_update, index_tools, manifests, tiles)

    def _apply_update_result(
        self,
        toolbox_update: ToolboxUpdate,
        index_tools: list,
        manifests: dict[str, ToolManifest],
        tiles: tuple[ToolTile, ...],
    ) -> None:
        self.toolbox_update_info = (
            toolbox_update
            if is_toolbox_update_available(toolbox_update, __version__)
            else None
        )
        self.index_tools = index_tools
        self.manifests = manifests
        self.tiles = tiles

        self._render_categories()
        if self.selected_category == ABOUT_NAV_ID and self._startup_about_pending_remote and self.tiles:
            self._startup_about_pending_remote = False
            self.select_category(default_selected_category(ordered_categories(self.index_tools), self.tiles))
        elif self.selected_category == ABOUT_NAV_ID:
            self.select_about_page()
        elif not self.selected_category:
            self.select_category(default_selected_category(ordered_categories(self.index_tools), self.tiles))
        else:
            self.select_category(self.selected_category)
        if self.toolbox_update_info is not None:
            self.hint_label.setText(
                f"发现工具箱新版本 {self.toolbox_update_info.latest_version}，点击右上角菜单下载更新。"
            )
        elif self.selected_category != ABOUT_NAV_ID:
            self.hint_label.setText(f"提示：已加载 {len(self.tiles)} 个工具。单击查看说明，双击启动工具。")
        self._sync_action_buttons()

    def open_toolbox_release(self) -> None:
        if self.toolbox_update_info is None or not self.toolbox_update_info.release_url:
            return
        QDesktopServices.openUrl(QUrl(self.toolbox_update_info.release_url))

    def copy_project_address(self, tool_id: str) -> None:
        address = self._project_address_for_tool(tool_id)
        if not address:
            QMessageBox.information(self, "没有项目地址", "这个工具暂时没有配置项目地址。")
            return
        QApplication.clipboard().setText(address)
        self.hint_label.setText(f"已复制项目地址：{address}")

    def _project_address_for_tool(self, tool_id: str) -> str:
        manifest = self.manifests.get(tool_id)
        if manifest is not None and manifest.project_url:
            return manifest.project_url
        return ""

    def download_toolbox_update(self) -> None:
        update = self.toolbox_update_info
        if update is None:
            QMessageBox.information(self, "没有新版本", "当前工具箱已经是最新版本。")
            return
        if not update.package_url:
            self.open_toolbox_release()
            return

        try:
            self.menu_button.setEnabled(False)
            self._set_busy(True)
            self._show_progress("准备下载工具箱更新...")
            package_path = self.toolbox_update_downloader.download(
                update,
                progress_callback=self._update_download_progress,
            )
        except Exception as exc:
            self._show_progress("工具箱更新下载失败")
            QMessageBox.critical(self, "下载失败", str(exc))
            return
        finally:
            self._set_busy(False)
            self.menu_button.setEnabled(True)

        self._show_progress("完成")
        self.hint_label.setText(f"工具箱 {update.latest_version} 已下载：{package_path.name}。")
        result = QMessageBox.question(
            self,
            "下载完成",
            f"新版工具箱已下载到：\n{package_path}\n\n是否立即关闭工具箱并自动安装新版？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if result == QMessageBox.Yes:
            try:
                self.self_update_runner.start(package_path)
            except Exception as exc:
                QMessageBox.critical(self, "启动更新器失败", str(exc))
                return
            self.hint_label.setText("正在启动独立更新器，工具箱即将关闭...")
            self.close()
            app = QApplication.instance()
            if app is not None:
                app.quit()
            return

        subprocess.Popen(["explorer", f"/select,{package_path}"])

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

        button = QPushButton(ABOUT_NAV_LABEL)
        button.setObjectName("categoryButton")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(self.select_about_page)
        self.category_panel.addWidget(button)
        self.category_buttons[ABOUT_NAV_ID] = button

    def select_category(self, category: str) -> None:
        if category == ABOUT_NAV_ID:
            self.select_about_page()
            return
        self._startup_about_pending_remote = False
        self.selected_category = category
        for name, button in self.category_buttons.items():
            button.setChecked(name == category)
        self.about_page.setVisible(False)
        self.tool_list.setVisible(True)
        self.detail_bar.setVisible(True)
        self._render_tools(category)

    def select_about_page(self) -> None:
        self.selected_category = ABOUT_NAV_ID
        self.selected_tool_id = None
        for name, button in self.category_buttons.items():
            button.setChecked(name == ABOUT_NAV_ID)
        self.tool_list.setVisible(False)
        self.detail_bar.setVisible(False)
        self.about_page.setVisible(True)
        self.progress_bar.setVisible(False)
        self.hint_label.setText("关于页：查看工具箱说明、作者信息和更新日志。")
        self._sync_action_buttons()

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

    def _clear_update_queue(self) -> None:
        while True:
            try:
                self._update_queue.get_nowait()
            except queue.Empty:
                return

    def _show_update_activity(self, text: str, current: object, total: object) -> None:
        self.side_update_status.setText(text)
        self.side_update_status.setVisible(True)
        self.side_update_progress.setVisible(True)

        if isinstance(current, int) and isinstance(total, int) and total > 0:
            self.side_update_progress.setRange(0, total)
            self.side_update_progress.setValue(min(current, total))
            return

        self.side_update_progress.setRange(0, 0)

    def _finish_update_activity(self, text: str, *, success: bool) -> None:
        self.side_update_status.setText(text)
        self.side_update_status.setVisible(True)
        self.side_update_progress.setVisible(True)
        self.side_update_progress.setRange(0, 100)
        self.side_update_progress.setValue(100 if success else 0)
        QTimer.singleShot(1600 if success else 3000, self._hide_update_activity)

    def _hide_update_activity(self) -> None:
        if self._update_thread is not None and self._update_thread.is_alive():
            return
        self.side_update_status.setVisible(False)
        self.side_update_progress.setVisible(False)
        self.side_update_progress.setRange(0, 100)
        self.side_update_progress.setValue(0)

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
