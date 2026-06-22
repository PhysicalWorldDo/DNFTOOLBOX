import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from physical_toolbox.install_state import InstallStateStore
from physical_toolbox.manifest import ToolManifest
from physical_toolbox import package_manager as package_manager_module
from physical_toolbox.package_manager import PackageManager


def test_package_manager_installs_zip_and_preserves_config(tmp_path: Path) -> None:
    workspace = tmp_path / "toolbox"
    package_path = tmp_path / "damage_calculator.zip"
    manifest_dict = {
        "schemaVersion": 1,
        "id": "damage_calculator",
        "name": "伤害计算器",
        "category": "角色工具",
        "description": "测试工具",
        "icon": "",
        "entry": "bin/DamageCalculator.exe",
        "needAdmin": False,
        "latest": {"stable": "1.2.0"},
        "versions": [
            {
                "version": "1.2.0",
                "channel": "stable",
                "packageUrl": package_path.as_uri(),
                "sha256": "",
            }
        ],
    }

    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("tool.json", json.dumps(manifest_dict, ensure_ascii=False))
        archive.writestr("bin/DamageCalculator.exe", "fake exe")
        archive.writestr("config/user.json", '{"keep": true}')

    sha256 = hashlib.sha256(package_path.read_bytes()).hexdigest()
    manifest_dict["versions"][0]["sha256"] = sha256
    manifest = ToolManifest.from_dict(manifest_dict)

    existing_config = workspace / "tools" / "damage_calculator" / "config" / "user.json"
    existing_config.parent.mkdir(parents=True)
    existing_config.write_text('{"keep": "old"}', encoding="utf-8")

    manager = PackageManager(workspace, InstallStateStore(workspace / "config" / "installed.json"))

    manager.install_from_archive(manifest, "1.2.0", package_path)

    assert (workspace / "tools" / "damage_calculator" / "bin" / "DamageCalculator.exe").exists()
    assert existing_config.read_text(encoding="utf-8") == '{"keep": "old"}'
    assert manager.installed_tools()["damage_calculator"].version == "1.2.0"


def test_package_manager_reports_download_progress_for_file_urls(tmp_path: Path) -> None:
    workspace = tmp_path / "toolbox"
    source = tmp_path / "package.zip"
    source.write_bytes(b"abcdef" * 1024)
    progress: list[tuple[int, int | None]] = []
    manager = PackageManager(workspace, InstallStateStore(workspace / "config" / "installed.json"))

    downloaded = manager.download(
        source.as_uri(),
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert downloaded.read_bytes() == source.read_bytes()
    assert progress
    assert progress[-1] == (source.stat().st_size, source.stat().st_size)


def test_package_manager_uninstalls_tool_and_removes_state(tmp_path: Path) -> None:
    workspace = tmp_path / "toolbox"
    tool_root = workspace / "tools" / "one_step_run"
    (tool_root / "bin").mkdir(parents=True)
    (tool_root / "bin" / "OneStepRun.exe").write_text("fake exe", encoding="utf-8")
    state_store = InstallStateStore(workspace / "config" / "installed.json")
    state_store.record(
        package_manager_module.InstalledTool(
            id="one_step_run",
            name="一键奔跑工具",
            version="1.0.0",
            channel="stable",
            entry="bin/run.cmd",
            installed_at="2026-06-22T12:00:00+08:00",
            updated_at="2026-06-22T12:00:00+08:00",
        )
    )
    manager = PackageManager(workspace, state_store)

    manager.uninstall("one_step_run")

    assert not tool_root.exists()
    assert "one_step_run" not in manager.installed_tools()


def test_package_manager_keeps_runtime_intact_when_replacement_is_locked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "toolbox"
    package_path = tmp_path / "ai_search.zip"
    manifest_dict = {
        "schemaVersion": 1,
        "id": "ai_search",
        "name": "AI 搜图",
        "category": "图像工具",
        "description": "测试工具",
        "icon": "",
        "entry": "bin/run.cmd",
        "needAdmin": False,
        "latest": {"stable": "1.0.0"},
        "versions": [
            {
                "version": "1.0.0",
                "channel": "stable",
                "packageUrl": package_path.as_uri(),
                "sha256": "",
            }
        ],
    }

    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("tool.json", json.dumps(manifest_dict, ensure_ascii=False))
        archive.writestr("bin/run.cmd", "new runner")
        archive.writestr("bin/app/launch.cmd", "new launcher")
        archive.writestr("config/settings.json", '{"new": true}')

    sha256 = hashlib.sha256(package_path.read_bytes()).hexdigest()
    manifest_dict["versions"][0]["sha256"] = sha256
    manifest = ToolManifest.from_dict(manifest_dict)

    old_launcher = workspace / "tools" / "ai_search" / "bin" / "app" / "launch.cmd"
    old_launcher.parent.mkdir(parents=True)
    old_launcher.write_text("old launcher", encoding="utf-8")
    old_config = workspace / "tools" / "ai_search" / "config" / "settings.json"
    old_config.parent.mkdir(parents=True)
    old_config.write_text('{"keep": true}', encoding="utf-8")

    original_rmtree = package_manager_module.shutil.rmtree

    def locked_runtime_delete(path: Path, *args, **kwargs) -> None:
        target = Path(path)
        if target == workspace / "tools" / "ai_search" / "bin":
            old_launcher.unlink()
            raise PermissionError("runtime is locked")
        original_rmtree(path, *args, **kwargs)

    original_rename = Path.rename

    def locked_runtime_rename(self: Path, target: Path) -> Path:
        if self == workspace / "tools" / "ai_search" / "bin":
            raise PermissionError("runtime is locked")
        return original_rename(self, target)

    monkeypatch.setattr(package_manager_module.shutil, "rmtree", locked_runtime_delete)
    monkeypatch.setattr(Path, "rename", locked_runtime_rename)
    manager = PackageManager(workspace, InstallStateStore(workspace / "config" / "installed.json"))

    with pytest.raises(PermissionError):
        manager.install_from_archive(manifest, "1.0.0", package_path)

    assert old_launcher.read_text(encoding="utf-8") == "old launcher"
    assert old_config.read_text(encoding="utf-8") == '{"keep": true}'
