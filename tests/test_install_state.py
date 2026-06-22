from pathlib import Path

from physical_toolbox.install_state import InstalledTool, InstallStateStore


def test_install_state_round_trips_installed_tool(tmp_path: Path) -> None:
    state_path = tmp_path / "config" / "installed.json"
    store = InstallStateStore(state_path)

    store.record(
        InstalledTool(
            id="damage_calculator",
            name="伤害计算器",
            version="1.2.0",
            channel="stable",
            entry="bin/DamageCalculator.exe",
            installed_at="2026-06-22T12:00:00+08:00",
            updated_at="2026-06-22T12:00:00+08:00",
        )
    )

    loaded = InstallStateStore(state_path).load()

    assert loaded["damage_calculator"].version == "1.2.0"
    assert loaded["damage_calculator"].entry == "bin/DamageCalculator.exe"
