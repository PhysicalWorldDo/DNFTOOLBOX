from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

OUTPUT_ROOT = Path("E:/DNFAutoPlay/DNFtoolall")
TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLBOX_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLBOX_ROOT))

from physical_toolbox.packaging import FileCopy, GeneratedFile, ToolPackageSpec, package_tool, write_index

DECRYPT_ROOT = Path("E:/Deee")
MUSIC_ROOT = Path("E:/DNFAutoPlay/DNFMusicDetect")
NBA_ROOT = Path("E:/DNFAutoPlay/DNFNBA")
NPK_PS_ROOT = Path("E:/DNFAutoPlay/DNFNPK_PS")
REPLACE_IMG_ROOT = Path("E:/DNFAutoPlay/DNFreplaceimg")
PALETTE_ROOT = Path("E:/DNFAutoPlay/DNFskillConvers/Version/V1.51/code")
UI_ROOT = Path("E:/DNFAutoPlay/DNFUIImage")
ONE_STEP_ROOT = Path("E:/DNFAutoPlay/OnestepRun")


def python_gui_launcher(script_name: str) -> str:
    return f"""@echo off
cd /d "%~dp0"
where pythonw.exe >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  start "" /wait pythonw.exe "%~dp0{script_name}"
) else (
  python "%~dp0{script_name}"
)
"""


def palette_single_page_launcher(page_key: str, title: str) -> str:
    return f'''from __future__ import annotations

import os
import sys

APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from main import MainApplication


def main() -> None:
    app = MainApplication()
    app.title("{title}")
    try:
        app.sidebar.pack_forget()
    except Exception:
        pass
    app.show_page("{page_key}")
    app.mainloop()


if __name__ == "__main__":
    main()
'''


def train_ui_settings_name() -> str:
    return "train_ui_settings.json"


def ai_search_train_launcher() -> str:
    settings_name = train_ui_settings_name()
    return f'''from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from modules.mod_ai import GoogleSearchPage

SETTINGS_FILE = APP_DIR / "{settings_name}"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {{}}
    return {{}}


def save_settings(data: dict) -> None:
    try:
        SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def python_executable() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "pythonw.exe":
        candidate = executable.with_name("python.exe")
        if candidate.exists():
            return str(candidate)
    return str(executable)


def no_window_flags() -> int:
    if os.name != "nt":
        return 0
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


class TrainCliPage(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f5f6f8")
        self.settings = load_settings()
        self.npk_dir = tk.StringVar(value=self.settings.get("npk_dir", ""))
        self.output_dir = tk.StringVar(value=self.settings.get("output_dir", ""))
        self.batch_size = tk.IntVar(value=int(self.settings.get("batch_size", 2048)))
        self.num_workers = tk.IntVar(value=int(self.settings.get("num_workers", 10)))
        self.shard_size = tk.IntVar(value=int(self.settings.get("shard_size", 1000000)))
        self.process = None
        self.output_queue = queue.Queue()
        self.reader_thread = None
        self.build_ui()
        self.after(100, self.drain_output)

    def build_ui(self) -> None:
        tk.Label(self, text="AI 特征库训练", font=("微软雅黑", 16, "bold"), bg="#f5f6f8", fg="#333").pack(pady=10)

        paths = ttk.LabelFrame(self, text=" 1. 路径设置 ", padding=10)
        paths.pack(fill="x", padx=10)

        row = ttk.Frame(paths); row.pack(fill="x", pady=3)
        ttk.Label(row, text="NPK 素材目录:", width=14).pack(side="left")
        ttk.Entry(row, textvariable=self.npk_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择", command=self.choose_npk_dir).pack(side="left", padx=5)

        row = ttk.Frame(paths); row.pack(fill="x", pady=3)
        ttk.Label(row, text="索引输出目录:", width=14).pack(side="left")
        ttk.Entry(row, textvariable=self.output_dir).pack(side="left", fill="x", expand=True)
        ttk.Button(row, text="选择", command=self.choose_output_dir).pack(side="left", padx=5)

        params = ttk.LabelFrame(self, text=" 2. 训练参数 ", padding=10)
        params.pack(fill="x", padx=10, pady=10)

        row = ttk.Frame(params); row.pack(fill="x")
        ttk.Label(row, text="Batch Size").pack(side="left")
        ttk.Spinbox(row, from_=1, to=8192, textvariable=self.batch_size, width=8).pack(side="left", padx=(5, 18))
        ttk.Label(row, text="Workers").pack(side="left")
        ttk.Spinbox(row, from_=1, to=64, textvariable=self.num_workers, width=8).pack(side="left", padx=(5, 18))
        ttk.Label(row, text="Shard Size").pack(side="left")
        ttk.Spinbox(row, from_=1000, to=10000000, textvariable=self.shard_size, width=12).pack(side="left", padx=5)

        actions = ttk.Frame(self)
        actions.pack(fill="x", padx=10)
        self.start_button = ttk.Button(actions, text="开始训练", command=self.start_training)
        self.start_button.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.stop_button = ttk.Button(actions, text="停止训练", command=self.stop_training, state="disabled")
        self.stop_button.pack(side="left", fill="x", expand=True, padx=(5, 0))

        self.status_label = ttk.Label(self, text="准备就绪")
        self.status_label.pack(fill="x", padx=10, pady=(8, 4))

        self.log_box = tk.Text(self, bg="#20242b", fg="#e8edf2", insertbackground="#e8edf2", font=("Consolas", 9), state="disabled")
        self.log_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

    def choose_npk_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.npk_dir.set(path)
            self.persist_settings()

    def choose_output_dir(self) -> None:
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)
            self.persist_settings()

    def persist_settings(self) -> None:
        save_settings({{
            "npk_dir": self.npk_dir.get(),
            "output_dir": self.output_dir.get(),
            "batch_size": self.batch_size.get(),
            "num_workers": self.num_workers.get(),
            "shard_size": self.shard_size.get(),
        }})

    def start_training(self) -> None:
        if self.process and self.process.poll() is None:
            return
        npk_dir = self.npk_dir.get().strip()
        output_dir = self.output_dir.get().strip()
        if not npk_dir or not Path(npk_dir).exists():
            messagebox.showerror("错误", "NPK 素材目录无效")
            return
        if not output_dir:
            messagebox.showerror("错误", "请选择索引输出目录")
            return
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.persist_settings()
        self.clear_log()
        cmd = [
            python_executable(),
            str(APP_DIR / "RunTrain_exe.py"),
            "--npk_dir", npk_dir,
            "--output_dir", output_dir,
            "--batch_size", str(self.batch_size.get()),
            "--num_workers", str(self.num_workers.get()),
            "--shard_size", str(self.shard_size.get()),
        ]
        self.write_log("启动训练进程...")
        self.process = subprocess.Popen(
            cmd,
            cwd=str(APP_DIR),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=no_window_flags(),
        )
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_label.config(text=f"训练中，PID: {{self.process.pid}}")
        self.reader_thread = threading.Thread(target=self.read_process_output, daemon=True)
        self.reader_thread.start()

    def read_process_output(self) -> None:
        assert self.process is not None
        if self.process.stdout is not None:
            for line in self.process.stdout:
                self.output_queue.put(line.rstrip())
        code = self.process.wait()
        self.output_queue.put(f"__PROCESS_DONE__{{code}}")

    def drain_output(self) -> None:
        while True:
            try:
                line = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if line.startswith("__PROCESS_DONE__"):
                code = line.replace("__PROCESS_DONE__", "")
                self.status_label.config(text=f"训练进程结束，退出码: {{code}}")
                self.start_button.config(state="normal")
                self.stop_button.config(state="disabled")
            else:
                self.write_log(line)
        self.after(100, self.drain_output)

    def stop_training(self) -> None:
        if not self.process or self.process.poll() is not None:
            return
        if not messagebox.askyesno("确认停止", "确定要停止当前训练进程吗？"):
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=no_window_flags(),
            )
        else:
            self.process.terminate()
        self.status_label.config(text="正在停止训练...")

    def clear_log(self) -> None:
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")

    def write_log(self, text: str) -> None:
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")


class AIHubApplication(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("全库秒搜与识图训练")
        self.geometry("1100x760")
        self.sidebar = tk.Frame(self, bg="#2c3e50", width=170)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        tk.Label(self.sidebar, text="AI 工具", bg="#2c3e50", fg="#ecf0f1", font=("微软雅黑", 18, "bold")).pack(pady=(28, 18))
        self.content = tk.Frame(self, bg="#f5f6f8")
        self.content.pack(side="right", fill="both", expand=True)
        self.buttons = {{}}
        self.pages = {{}}
        self.add_nav("AI 搜图", "search")
        self.add_nav("识图训练", "train")
        self.show_page("search")

    def add_nav(self, text: str, key: str) -> None:
        button = tk.Button(
            self.sidebar,
            text=text,
            bg="#2c3e50",
            fg="#ecf0f1",
            bd=0,
            padx=22,
            pady=12,
            anchor="w",
            font=("微软雅黑", 11),
            command=lambda: self.show_page(key),
        )
        button.pack(fill="x")
        self.buttons[key] = button

    def show_page(self, key: str) -> None:
        for name, button in self.buttons.items():
            button.config(bg="#1abc9c" if name == key else "#2c3e50")
        for page in self.pages.values():
            page.pack_forget()
        if key not in self.pages:
            if key == "search":
                self.pages[key] = GoogleSearchPage(self.content)
            else:
                self.pages[key] = TrainCliPage(self.content)
        self.pages[key].pack(fill="both", expand=True)


def main() -> None:
    app = AIHubApplication()
    app.mainloop()


if __name__ == "__main__":
    main()
'''


def patched_palette_common() -> str:
    text = (PALETTE_ROOT / "common.py").read_text(encoding="utf-8")
    return text.replace(
        "\ncheck_path_safety()\n",
        "\n# Packaged copies may live under a Chinese output folder; keep the original source untouched.\n# check_path_safety()\n",
    )


def open_directory_launcher() -> str:
    return """@echo off
cd /d "%~dp0"
explorer "%~dp0"
"""


def photoshop_plugin_installer() -> str:
    return """@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0release\\install.bat' -Verb RunAs"
"""


def base_specs() -> list[ToolPackageSpec]:
    common_palette_runtime = (
        FileCopy(PALETTE_ROOT / "main.py", "bin/app/main.py"),
        FileCopy(PALETTE_ROOT / "modules", "bin/app/modules"),
        FileCopy(PALETTE_ROOT / "avatar.jpg", "bin/app/avatar.jpg"),
        FileCopy(PALETTE_ROOT / "Background.jpeg", "bin/app/Background.jpeg"),
        FileCopy(PALETTE_ROOT / "Background.png", "bin/app/Background.png"),
        FileCopy(PALETTE_ROOT / "dnf_ImagePacks2.txt", "bin/app/dnf_ImagePacks2.txt"),
        FileCopy(PALETTE_ROOT / "mobilenet_v3_small.onnx", "bin/app/mobilenet_v3_small.onnx"),
        FileCopy(PALETTE_ROOT / "mobilenet_v3_small.pth", "bin/app/mobilenet_v3_small.pth"),
        FileCopy(PALETTE_ROOT / "NpkPatcher.exe", "bin/app/NpkPatcher.exe"),
        FileCopy(PALETTE_ROOT / "Palette.ico", "bin/app/Palette.ico"),
        FileCopy(PALETTE_ROOT / "qrcode.png", "bin/app/qrcode.png"),
        FileCopy(PALETTE_ROOT / "zlib1.dll", "bin/app/zlib1.dll"),
    )
    common_palette_source = (
        FileCopy(PALETTE_ROOT / "main.py", "main.py"),
        FileCopy(PALETTE_ROOT / "modules", "modules"),
        FileCopy(PALETTE_ROOT / "avatar.jpg", "assets/avatar.jpg"),
        FileCopy(PALETTE_ROOT / "Background.jpeg", "assets/Background.jpeg"),
        FileCopy(PALETTE_ROOT / "Background.png", "assets/Background.png"),
        FileCopy(PALETTE_ROOT / "dnf_ImagePacks2.txt", "assets/dnf_ImagePacks2.txt"),
        FileCopy(PALETTE_ROOT / "mobilenet_v3_small.onnx", "assets/mobilenet_v3_small.onnx"),
        FileCopy(PALETTE_ROOT / "mobilenet_v3_small.pth", "assets/mobilenet_v3_small.pth"),
        FileCopy(PALETTE_ROOT / "NpkPatcher.exe", "assets/NpkPatcher.exe"),
        FileCopy(PALETTE_ROOT / "Palette.ico", "assets/Palette.ico"),
        FileCopy(PALETTE_ROOT / "qrcode.png", "assets/qrcode.png"),
        FileCopy(PALETTE_ROOT / "zlib1.dll", "assets/zlib1.dll"),
    )
    palette_runtime_files = (
        GeneratedFile("bin/app/common.py", patched_palette_common()),
        GeneratedFile("bin/app/launch.cmd", python_gui_launcher("single_page_launcher.py")),
    )
    palette_source_files = (
        GeneratedFile("common.py", patched_palette_common()),
        GeneratedFile("launch.cmd", python_gui_launcher("single_page_launcher.py")),
    )

    specs = [
        ToolPackageSpec(
            id="neople_video_codec_tool",
            name="视频解密加密工具",
            category="资源工具",
            description="Neople Video File / BK2 / AVI 批量解密、加密与转码工具。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(
                FileCopy(DECRYPT_ROOT / "decrypt_ui.py", "bin/app/decrypt_ui.py"),
                FileCopy(DECRYPT_ROOT / "dist" / "ffmpeg", "bin/app/ffmpeg"),
            ),
            source_copies=(
                FileCopy(DECRYPT_ROOT / "decrypt_ui.py", "decrypt_ui.py"),
                FileCopy(DECRYPT_ROOT / "dist" / "ffmpeg", "ffmpeg"),
            ),
            runtime_files=(GeneratedFile("bin/app/launch.cmd", python_gui_launcher("decrypt_ui.py")),),
            source_files=(GeneratedFile("launch.cmd", python_gui_launcher("decrypt_ui.py")),),
            launch_target="launch.cmd",
            tags=("视频", "解密", "BK2"),
        ),
        ToolPackageSpec(
            id="dnf_music_detect",
            name="DNF 音乐检测工具",
            category="音频工具",
            description="DNF 音频 NPK 检测、试听、替换与音乐索引工具。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(FileCopy(MUSIC_ROOT / "MusicNpkTool.dist", "bin/app"),),
            source_copies=(
                FileCopy(MUSIC_ROOT / "MusicNpkTool.py", "MusicNpkTool.py"),
                FileCopy(MUSIC_ROOT / "MusicNpkTrainer.py", "MusicNpkTrainer.py"),
                FileCopy(MUSIC_ROOT / "MusicNpkTool_UIShell.py", "MusicNpkTool_UIShell.py"),
                FileCopy(MUSIC_ROOT / "dnf_fashion_lab_scraper.py", "dnf_fashion_lab_scraper.py"),
                FileCopy(MUSIC_ROOT / "requirements.txt", "requirements.txt"),
                FileCopy(MUSIC_ROOT / "icon.ico", "icon.ico"),
            ),
            launch_target="DNFMusicDetect.exe",
            config_sync_files=("music_tool_settings.json",),
            data_dirs=("recordings",),
            tags=("音乐", "音频", "NPK"),
        ),
        ToolPackageSpec(
            id="dnf_nba_assistant",
            name="DNF NBA 图色助手",
            category="游戏工具",
            description="DNF NBA 活动图色识别与按键辅助工具。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(
                FileCopy(NBA_ROOT / "dist" / "DNFNBA.exe", "bin/app/DNFNBA.exe"),
                FileCopy(NBA_ROOT / "dist" / "%sprite_live_event_chn_2026_0514_nba_event.NPK", "bin/app/%sprite_live_event_chn_2026_0514_nba_event.NPK"),
            ),
            source_copies=(
                FileCopy(NBA_ROOT / "dnfnba.py", "dnfnba.py"),
            ),
            launch_target="DNFNBA.exe",
            config_sync_files=("settings.json",),
            need_admin=True,
            permissions=("screen_capture", "keyboard"),
            tags=("活动", "图色识别", "按键"),
        ),
        ToolPackageSpec(
            id="dnf_img_photoshop_plugin",
            name="DNF IMG Photoshop 插件",
            category="插件工具",
            description="Photoshop DNF IMG 格式插件及安装脚本。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(FileCopy(NPK_PS_ROOT / "release", "bin/app/release"),),
            source_copies=(
                FileCopy(NPK_PS_ROOT / "README.md", "README.md"),
                FileCopy(NPK_PS_ROOT / "API.md", "API.md"),
                FileCopy(NPK_PS_ROOT / "CMakeLists.txt", "CMakeLists.txt"),
                FileCopy(NPK_PS_ROOT / "include", "include"),
                FileCopy(NPK_PS_ROOT / "resources", "resources"),
                FileCopy(NPK_PS_ROOT / "src", "src"),
                FileCopy(NPK_PS_ROOT / "release", "release"),
                FileCopy(NPK_PS_ROOT / "UXP_Plugin", "UXP_Plugin"),
            ),
            runtime_files=(GeneratedFile("bin/app/install_plugin.cmd", photoshop_plugin_installer()),),
            source_files=(GeneratedFile("install_plugin.cmd", photoshop_plugin_installer()),),
            launch_target="install_plugin.cmd",
            need_admin=True,
            tags=("Photoshop", "IMG", "插件"),
        ),
        ToolPackageSpec(
            id="dnf_img_replacer",
            name="DNF IMG 帧替换工具",
            category="图像工具",
            description="替换 DNF IMG 帧图片并重新写入 NPK 的可视化工具。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(FileCopy(REPLACE_IMG_ROOT / "exe", "bin/app"),),
            source_copies=(
                FileCopy(REPLACE_IMG_ROOT / "app.py", "app.py"),
                FileCopy(REPLACE_IMG_ROOT / "dnflib_py.py", "dnflib_py.py"),
                FileCopy(REPLACE_IMG_ROOT / "frame_ops.py", "frame_ops.py"),
                FileCopy(REPLACE_IMG_ROOT / "main.py", "main.py"),
                FileCopy(REPLACE_IMG_ROOT / "ui_panels.py", "ui_panels.py"),
            ),
            launch_target="DNF_IMG_Replacer.exe",
            tags=("IMG", "替换", "NPK"),
        ),
        ToolPackageSpec(
            id="dnf_ui_visual_editor",
            name="DNF UI 可视编辑器",
            category="UI工具",
            description="DNF UI 素材可视化组合、图层布局与预览工具。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(
                FileCopy(UI_ROOT / "DNFVisualeditor" / "dnf_ui_composer.py", "bin/app/dnf_ui_composer.py"),
                FileCopy(UI_ROOT / "app_resources_rc.py", "bin/app/app_resources_rc.py"),
            ),
            source_copies=(
                FileCopy(UI_ROOT / "DNFVisualeditor" / "dnf_ui_composer.py", "dnf_ui_composer.py"),
                FileCopy(UI_ROOT / "app_resources_rc.py", "app_resources_rc.py"),
                FileCopy(UI_ROOT / "DNFVisualeditor" / "LICENSE", "LICENSE"),
                FileCopy(UI_ROOT / "DNFVisualeditor" / "README.md", "README.md"),
                FileCopy(UI_ROOT / "requirements.txt", "requirements.txt"),
            ),
            runtime_files=(GeneratedFile("bin/app/launch.cmd", python_gui_launcher("dnf_ui_composer.py")),),
            source_files=(GeneratedFile("launch.cmd", python_gui_launcher("dnf_ui_composer.py")),),
            launch_target="launch.cmd",
            tags=("UI", "布局", "可视化"),
        ),
        ToolPackageSpec(
            id="one_step_run",
            name="一键奔跑工具",
            category="游戏工具",
            description="DNF 一键奔跑与按键触发辅助工具。",
            version="1.0.0",
            entry="bin/run.cmd",
            runtime_copies=(
                FileCopy(ONE_STEP_ROOT / "dist" / "OneStepRun.exe", "bin/app/OneStepRun.exe"),
                FileCopy(ONE_STEP_ROOT / "dist" / "icon_off.ico", "bin/app/icon_off.ico"),
                FileCopy(ONE_STEP_ROOT / "dist" / "icon_on.ico", "bin/app/icon_on.ico"),
                FileCopy(ONE_STEP_ROOT / "dist" / "off.mp3", "bin/app/off.mp3"),
                FileCopy(ONE_STEP_ROOT / "dist" / "on.mp3", "bin/app/on.mp3"),
            ),
            source_copies=(
                FileCopy(ONE_STEP_ROOT / "OneStepRun_UI.py", "OneStepRun_UI.py"),
                FileCopy(ONE_STEP_ROOT / "timer_main.py", "timer_main.py"),
                FileCopy(ONE_STEP_ROOT / "off.mp3", "off.mp3"),
                FileCopy(ONE_STEP_ROOT / "on.mp3", "on.mp3"),
            ),
            launch_target="OneStepRun.exe",
            config_sync_files=("run_config.json",),
            permissions=("keyboard",),
            tags=("连发", "按键", "辅助"),
        ),
    ]

    specs.extend(
        palette_spec(
            tool_id=tool_id,
            name=name,
            description=description,
            page_key=page_key,
            runtime_copies=common_palette_runtime,
            source_copies=common_palette_source,
            runtime_files=palette_runtime_files,
            source_files=palette_source_files,
        )
        for tool_id, name, page_key, description in (
            ("dnf_palette_prism", "阿拉德调色", "prism", "DNF NPK / IMG 调色盘与整体换色工具。"),
            ("dnf_palette_blender", "Blender 渲染", "blender", "将序列帧接入 Blender 模板进行批量渲染。"),
            ("dnf_palette_recolor", "指定色替换", "recolor", "按指定颜色映射替换 DNF IMG 帧颜色。"),
            ("dnf_palette_buff", "BUFF 替换", "buff", "BUFF 动画序列和 BK2 隐藏帧构建工具。"),
        )
    )
    specs.append(
        ai_search_spec(
            runtime_copies=common_palette_runtime,
            source_copies=common_palette_source,
            runtime_files=palette_runtime_files,
            source_files=palette_source_files,
        )
    )
    return specs


def palette_spec(
    tool_id: str,
    name: str,
    description: str,
    page_key: str,
    runtime_copies: tuple[FileCopy, ...],
    source_copies: tuple[FileCopy, ...],
    runtime_files: tuple[GeneratedFile, ...],
    source_files: tuple[GeneratedFile, ...],
) -> ToolPackageSpec:
    return ToolPackageSpec(
        id=tool_id,
        name=name,
        category="图像工具",
        description=description,
        version="1.0.0",
        entry="bin/run.cmd",
        runtime_copies=runtime_copies,
        source_copies=source_copies,
        runtime_files=runtime_files
        + (GeneratedFile("bin/app/single_page_launcher.py", palette_single_page_launcher(page_key, name)),),
        source_files=source_files
        + (GeneratedFile("single_page_launcher.py", palette_single_page_launcher(page_key, name)),),
        launch_target="launch.cmd",
        config_sync_files=("settings.json",),
        tags=("幻色棱镜", "图像", "NPK"),
    )


def ai_search_spec(
    runtime_copies: tuple[FileCopy, ...],
    source_copies: tuple[FileCopy, ...],
    runtime_files: tuple[GeneratedFile, ...],
    source_files: tuple[GeneratedFile, ...],
) -> ToolPackageSpec:
    return ToolPackageSpec(
        id="dnf_palette_ai_search",
        name="全库秒搜与识图训练",
        category="图像工具",
        description="基于图库特征进行素材搜索，并通过后台训练进程构建 AI 索引。",
        version="1.0.0",
        entry="bin/run.cmd",
        runtime_copies=runtime_copies
        + (FileCopy(PALETTE_ROOT.parent / "RunTrain_exe.py", "bin/app/RunTrain_exe.py"),),
        source_copies=source_copies
        + (FileCopy(PALETTE_ROOT.parent / "RunTrain_exe.py", "RunTrain_exe.py"),),
        runtime_files=runtime_files
        + (
            GeneratedFile("bin/app/ai_search_train_launcher.py", ai_search_train_launcher()),
            GeneratedFile("bin/app/launch.cmd", python_gui_launcher("ai_search_train_launcher.py")),
        ),
        source_files=source_files
        + (
            GeneratedFile("ai_search_train_launcher.py", ai_search_train_launcher()),
            GeneratedFile("launch.cmd", python_gui_launcher("ai_search_train_launcher.py")),
        ),
        launch_target="launch.cmd",
        config_sync_files=("settings.json", train_ui_settings_name()),
        tags=("AI", "识图", "训练", "NPK"),
    )


def update_toolbox_local_config(index_path: Path) -> None:
    config_dir = TOOLBOX_ROOT / "config"
    config_dir.mkdir(exist_ok=True)
    payload = {
        "name": "物理世界的工具箱",
        "indexUrl": str(index_path.resolve()),
        "channel": "stable",
    }
    (config_dir / "app.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for name in ("staged", "sources", "packages", "index"):
        target = OUTPUT_ROOT / name
        if target.exists():
            shutil.rmtree(target)

    results = []
    specs = base_specs()
    for spec in specs:
        print(f"Packaging {spec.id} ...")
        results.append(package_tool(spec, OUTPUT_ROOT))

    index_path = write_index(OUTPUT_ROOT, [result.id for result in results])
    update_toolbox_local_config(index_path)

    print()
    print(f"Packaged {len(results)} tools.")
    print(f"Output: {OUTPUT_ROOT}")
    print(f"Index: {index_path}")
    for result in results:
        print(f"- {result.package_path.name}  {result.size / 1024 / 1024:.1f} MB  sha256={result.sha256}")


if __name__ == "__main__":
    main()
