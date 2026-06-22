from physical_toolbox.manifest import ToolManifest


def make_manifest() -> ToolManifest:
    return ToolManifest.from_dict(
        {
            "schemaVersion": 1,
            "id": "damage_calculator",
            "name": "伤害计算器",
            "category": "角色工具",
            "description": "用于计算角色装备、词条、增益后的伤害。",
            "icon": "https://example.com/icon.png",
            "entry": "bin/DamageCalculator.exe",
            "needAdmin": False,
            "latest": {"stable": "1.2.0", "beta": "1.3.0-beta.1"},
            "versions": [
                {
                    "version": "1.1.0",
                    "channel": "stable",
                    "packageUrl": "https://example.com/1.1.0.zip",
                    "sha256": "a" * 64,
                },
                {
                    "version": "1.2.0",
                    "channel": "stable",
                    "packageUrl": "https://example.com/1.2.0.zip",
                    "sha256": "b" * 64,
                },
                {
                    "version": "1.3.0-beta.1",
                    "channel": "beta",
                    "packageUrl": "https://example.com/1.3.0-beta.1.zip",
                    "sha256": "c" * 64,
                },
            ],
            "permissions": ["network"],
            "tags": ["计算", "装备"],
            "status": "active",
            "blockedVersions": ["1.1.0"],
        }
    )


def test_manifest_selects_latest_version_for_channel() -> None:
    manifest = make_manifest()

    stable_version = manifest.latest_version("stable")
    beta_version = manifest.latest_version("beta")

    assert stable_version.version == "1.2.0"
    assert stable_version.channel == "stable"
    assert beta_version.version == "1.3.0-beta.1"
    assert beta_version.channel == "beta"


def test_manifest_rejects_blocked_version_selection() -> None:
    manifest = make_manifest()

    try:
        manifest.version("1.1.0")
    except ValueError as exc:
        assert "blocked" in str(exc)
    else:
        raise AssertionError("blocked version should not be selectable")


def test_manifest_reports_update_when_remote_version_is_newer() -> None:
    manifest = make_manifest()

    assert manifest.has_update("1.1.9", "stable") is True
    assert manifest.has_update("1.2.0", "stable") is False
