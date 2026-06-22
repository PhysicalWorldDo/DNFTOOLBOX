from pathlib import Path

from physical_toolbox.launching import launch_creation_flags


def test_launch_creation_flags_hide_command_windows_on_windows() -> None:
    assert launch_creation_flags(Path("bin/run.cmd"), platform_name="nt") != 0
    assert launch_creation_flags(Path("bin/run.bat"), platform_name="nt") != 0


def test_launch_creation_flags_do_not_hide_normal_executables() -> None:
    assert launch_creation_flags(Path("bin/app/tool.exe"), platform_name="nt") == 0
    assert launch_creation_flags(Path("bin/run.cmd"), platform_name="posix") == 0
