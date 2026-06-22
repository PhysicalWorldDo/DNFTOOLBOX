import hashlib
import json
import zipfile
from pathlib import Path

from physical_toolbox.install_state import InstallStateStore
from physical_toolbox.manifest import ToolManifest
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
