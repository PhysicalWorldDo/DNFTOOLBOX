import hashlib
from pathlib import Path

from physical_toolbox.repository import ToolboxIndex, ToolboxUpdate
from physical_toolbox.self_updater import SelfUpdateRunner
from physical_toolbox.toolbox_update import ToolboxUpdateDownloader, is_toolbox_update_available


def test_toolbox_index_parses_toolbox_update_metadata() -> None:
    index = ToolboxIndex.from_dict(
        {
            "schemaVersion": 1,
            "toolbox": {
                "latestVersion": "0.2.0",
                "minSupportedVersion": "0.1.0",
                "releaseUrl": "https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/tag/v0.2.0",
                "packageUrl": "https://github.com/PhysicalWorldDo/DNFTOOLBOX/releases/download/v0.2.0/PhysicalWorldToolbox-0.2.0-win-x64.zip",
                "sha256": "abc123",
                "size": 1024,
                "changelog": ["新增自动下载工具箱更新"],
            },
            "tools": [],
        },
        "https://raw.githubusercontent.com/PhysicalWorldDo/DNFTOOLBOX-Registry/main/index.json",
    )

    assert index.latest_toolbox_version == "0.2.0"
    assert index.min_supported_version == "0.1.0"
    assert index.toolbox_update.latest_version == "0.2.0"
    assert index.toolbox_update.package_url.endswith("PhysicalWorldToolbox-0.2.0-win-x64.zip")
    assert index.toolbox_update.changelog == ("新增自动下载工具箱更新",)


def test_toolbox_update_available_uses_semantic_versions() -> None:
    update = ToolboxUpdate(latest_version="0.2.0", min_supported_version="0.1.0")

    assert is_toolbox_update_available(update, "0.1.0") is True
    assert is_toolbox_update_available(update, "0.2.0") is False


def test_toolbox_update_downloader_downloads_and_verifies_package(tmp_path: Path) -> None:
    workspace = tmp_path / "toolbox"
    source = tmp_path / "PhysicalWorldToolbox-0.2.0-win-x64.zip"
    source.write_bytes(b"new toolbox package")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    progress: list[tuple[int, int | None]] = []
    update = ToolboxUpdate(
        latest_version="0.2.0",
        package_url=source.as_uri(),
        sha256=digest,
    )

    downloaded = ToolboxUpdateDownloader(workspace).download(
        update,
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert downloaded == workspace / "downloads" / source.name
    assert downloaded.read_bytes() == source.read_bytes()
    assert progress
    assert progress[-1] == (source.stat().st_size, source.stat().st_size)


def test_self_update_runner_writes_independent_wait_copy_restart_script(tmp_path: Path) -> None:
    workspace = tmp_path / "toolbox"
    package = tmp_path / "downloads" / "PhysicalWorldToolbox-0.2.0-win-x64.zip"
    package.parent.mkdir(parents=True)
    package.write_bytes(b"zip")

    plan = SelfUpdateRunner(workspace).prepare(
        package,
        current_pid=1234,
        restart_command=("python.exe", "toolbox.py"),
    )

    script = plan.script_path.read_text(encoding="utf-8")
    assert plan.script_path.parent == workspace / "cache" / "self-update"
    assert "Wait-Process -Id 1234" in script
    assert "Get-Process -Id 1234" in script
    assert "Expand-Archive" in script
    assert "config', 'tools', 'downloads', 'cache', 'logs', '.git" in script
    assert "Start-Process -FilePath 'python.exe'" in script
    assert "toolbox.py" in script
    assert str(package) in script
    assert str(workspace) in script
    assert plan.command[:5] == (
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
    )
    assert plan.command[-2:] == ("-File", str(plan.script_path))
