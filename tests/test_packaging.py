import json
import zipfile
from pathlib import Path

from physical_toolbox.packaging import FileCopy, GeneratedFile, ToolPackageSpec, package_tool, write_index
from scripts.package_local_tools import ai_search_train_launcher, base_specs, train_ui_settings_name


def test_package_tool_writes_rule_compliant_zip_and_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.exe").write_text("fake", encoding="utf-8")
    (source / "settings.json").write_text("{}", encoding="utf-8")

    output = tmp_path / "out"
    spec = ToolPackageSpec(
        id="demo_tool",
        name="演示工具",
        category="游戏工具",
        description="用于测试打包规则。",
        version="1.0.0",
        entry="bin/run.cmd",
        runtime_copies=(FileCopy(source / "app.exe", "bin/app/app.exe"),),
        source_copies=(FileCopy(source / "app.exe", "app.exe"),),
        config_copies=(FileCopy(source / "settings.json", "settings.json"),),
        runtime_files=(GeneratedFile("bin/app/README.txt", "runtime"),),
        source_files=(GeneratedFile("README.txt", "source"),),
        launch_target="app\\app.exe",
        config_sync_files=("settings.json",),
    )

    result = package_tool(spec, output)

    assert result.package_path.exists()
    assert result.manifest_path.exists()
    assert result.sha256
    assert (output / "sources" / "demo_tool" / "app.exe").exists()
    assert (output / "sources" / "demo_tool" / "README.txt").read_text(encoding="utf-8") == "source"

    with zipfile.ZipFile(result.package_path) as archive:
        names = set(archive.namelist())
    assert "tool.json" in names
    assert "bin/run.cmd" in names
    assert "bin/app/app.exe" in names
    assert "bin/app/README.txt" in names
    assert "config/settings.json" in names

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["id"] == "demo_tool"
    assert manifest["versions"][0]["sha256"] == result.sha256


def test_write_index_references_each_tool_manifest(tmp_path: Path) -> None:
    tools_dir = tmp_path / "index" / "tools"
    tools_dir.mkdir(parents=True)
    (tools_dir / "demo_tool.json").write_text(
        json.dumps({"id": "demo_tool", "name": "演示工具", "category": "游戏工具"}),
        encoding="utf-8",
    )

    index_path = write_index(tmp_path, ["demo_tool"])

    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["tools"] == [
        {
            "id": "demo_tool",
            "name": "演示工具",
            "category": "游戏工具",
            "manifestUrl": "tools/demo_tool.json",
        }
    ]


def test_ai_search_train_launcher_exposes_search_and_threaded_training_ui() -> None:
    launcher = ai_search_train_launcher()

    assert "GoogleSearchPage" in launcher
    assert "RunTrain_exe.py" in launcher
    assert "threading.Thread" in launcher
    assert "queue.Queue" in launcher
    assert "taskkill" in launcher
    assert train_ui_settings_name() in launcher


def test_package_launcher_calls_nested_command_targets_without_start(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "settings.json").write_text("{}", encoding="utf-8")

    output = tmp_path / "out"
    spec = ToolPackageSpec(
        id="cmd_tool",
        name="命令工具",
        category="游戏工具",
        description="测试嵌套命令启动",
        version="1.0.0",
        entry="bin/run.cmd",
        runtime_copies=(),
        config_copies=(FileCopy(source / "settings.json", "settings.json"),),
        runtime_files=(GeneratedFile("bin/app/launch.cmd", "@echo off\r\n"),),
        launch_target="launch.cmd",
        config_sync_files=("settings.json",),
    )

    result = package_tool(spec, output)

    with zipfile.ZipFile(result.package_path) as archive:
        run_cmd = archive.read("bin/run.cmd").decode("utf-8")

    assert 'call "%APPDIR%\\launch.cmd"' in run_cmd
    assert 'start "" /wait "%APPDIR%\\launch.cmd"' not in run_cmd


def test_package_tool_filters_local_config_when_copying_directories(tmp_path: Path) -> None:
    source = tmp_path / "source"
    app_dir = source / "app"
    (app_dir / ".claude").mkdir(parents=True)
    (app_dir / "main.py").write_text("print('ok')", encoding="utf-8")
    (app_dir / "settings.json").write_text("{}", encoding="utf-8")
    (app_dir / ".claude" / "settings.local.json").write_text("{}", encoding="utf-8")

    output = tmp_path / "out"
    spec = ToolPackageSpec(
        id="directory_tool",
        name="目录工具",
        category="游戏工具",
        description="测试目录过滤",
        version="1.0.0",
        entry="bin/run.cmd",
        runtime_copies=(FileCopy(app_dir, "bin/app"),),
        source_copies=(FileCopy(app_dir, "app"),),
        launch_target="main.py",
    )

    result = package_tool(spec, output)

    with zipfile.ZipFile(result.package_path) as archive:
        names = set(archive.namelist())
    assert "bin/app/main.py" in names
    assert "bin/app/settings.json" not in names
    assert "bin/app/.claude/settings.local.json" not in names
    assert not (output / "sources" / "directory_tool" / "app" / "settings.json").exists()
    assert not (output / "sources" / "directory_tool" / "app" / ".claude").exists()


def test_package_tool_preserves_existing_source_git_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "main.py").write_text("print('new')", encoding="utf-8")

    output = tmp_path / "out"
    source_repo = output / "sources" / "git_tool"
    (source_repo / ".git").mkdir(parents=True)
    (source_repo / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (source_repo / "old.py").write_text("old", encoding="utf-8")

    spec = ToolPackageSpec(
        id="git_tool",
        name="Git 工具",
        category="游戏工具",
        description="测试保留源码仓库",
        version="1.0.0",
        entry="bin/run.cmd",
        runtime_copies=(FileCopy(source / "main.py", "bin/app/main.py"),),
        source_copies=(FileCopy(source / "main.py", "main.py"),),
        launch_target="main.py",
    )

    package_tool(spec, output)

    assert (source_repo / ".git" / "HEAD").exists()
    assert (source_repo / "main.py").read_text(encoding="utf-8") == "print('new')"
    assert not (source_repo / "old.py").exists()


def test_one_step_run_tool_is_named_as_running_tool() -> None:
    spec = next(item for item in base_specs() if item.id == "one_step_run")

    assert spec.name == "一键奔跑工具"
    assert "奔跑" in spec.description


def test_local_tool_specs_do_not_ship_user_config_files() -> None:
    config_names = {
        "settings.json",
        "music_tool_settings.json",
        "run_config.json",
        "timer_config.json",
        "train_ui_settings.json",
    }

    for spec in base_specs():
        assert spec.config_copies == ()
        copied_names = {
            Path(copy.destination).name
            for copy in (*spec.runtime_copies, *spec.source_copies)
        }
        generated_names = {
            Path(generated.destination).name
            for generated in (*spec.runtime_files, *spec.source_files)
        }
        assert copied_names.isdisjoint(config_names)
        assert generated_names.isdisjoint(config_names)


def test_video_codec_tool_uses_dist_ffmpeg_bundle() -> None:
    spec = next(item for item in base_specs() if item.id == "neople_video_codec_tool")

    ffmpeg_copies = [
        copy for copy in (*spec.runtime_copies, *spec.source_copies)
        if Path(copy.destination).name == "ffmpeg"
    ]

    assert ffmpeg_copies
    assert all(copy.source.parts[-2:] == ("dist", "ffmpeg") for copy in ffmpeg_copies)
