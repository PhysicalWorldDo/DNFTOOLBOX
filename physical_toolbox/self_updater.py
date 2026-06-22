from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class SelfUpdatePlan:
    script_path: Path
    command: tuple[str, ...]


class SelfUpdateRunner:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.update_dir = workspace / "cache" / "self-update"

    def prepare(
        self,
        package_path: Path,
        *,
        current_pid: int | None = None,
        restart_command: Sequence[str] | None = None,
    ) -> SelfUpdatePlan:
        self.update_dir.mkdir(parents=True, exist_ok=True)
        pid = current_pid if current_pid is not None else os.getpid()
        restart = tuple(restart_command or default_restart_command(self.workspace))
        script_path = self.update_dir / f"apply-toolbox-update-{pid}.ps1"
        script_path.write_text(
            self._script(package_path.resolve(), pid, restart),
            encoding="utf-8",
        )
        return SelfUpdatePlan(
            script_path=script_path,
            command=(
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-WindowStyle",
                "Hidden",
                "-File",
                str(script_path),
            ),
        )

    def start(self, package_path: Path) -> SelfUpdatePlan:
        plan = self.prepare(package_path)
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            plan.command,
            cwd=str(self.workspace),
            creationflags=creation_flags,
            close_fds=True,
            env=_sanitized_update_environment(),
        )
        return plan

    def _script(self, package_path: Path, pid: int, restart_command: tuple[str, ...]) -> str:
        update_root = self.update_dir.resolve()
        extract_dir = update_root / f"extracted-{pid}"
        backup_dir = update_root / f"backup-{pid}"
        log_path = update_root / f"update-{pid}.log"
        restart_args = ", ".join(_ps_quote(part) for part in restart_command[1:])
        argument_list = f" -ArgumentList @({restart_args})" if restart_command[1:] else ""
        return "\n".join(
            [
                "$ErrorActionPreference = 'Stop'",
                f"$PackagePath = {_ps_quote(str(package_path))}",
                f"$InstallDir = {_ps_quote(str(self.workspace.resolve()))}",
                f"$ExtractDir = {_ps_quote(str(extract_dir))}",
                f"$BackupDir = {_ps_quote(str(backup_dir))}",
                f"$LogPath = {_ps_quote(str(log_path))}",
                "$PreserveNames = @('config', 'tools', 'downloads', 'cache', 'logs', '.git')",
                "",
                "function Write-Log([string]$Message) {",
                "  $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'",
                "  Add-Content -LiteralPath $LogPath -Value \"[$timestamp] $Message\" -Encoding UTF8",
                "}",
                "",
                "try {",
                "  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $LogPath) | Out-Null",
                f"  Wait-Process -Id {pid} -Timeout 120 -ErrorAction SilentlyContinue",
                f"  if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{",
                "    Write-Log 'Toolbox process is still running; update cancelled'",
                "    exit 1",
                "  }",
                "  Remove-Item -LiteralPath $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue",
                "  Remove-Item -LiteralPath $BackupDir -Recurse -Force -ErrorAction SilentlyContinue",
                "  New-Item -ItemType Directory -Force -Path $ExtractDir | Out-Null",
                "  New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null",
                "  Write-Log 'Expanding toolbox package'",
                "  Expand-Archive -LiteralPath $PackagePath -DestinationPath $ExtractDir -Force",
                "  $children = @(Get-ChildItem -LiteralPath $ExtractDir -Force)",
                "  if ($children.Count -eq 1 -and $children[0].PSIsContainer) {",
                "    $PayloadRoot = $children[0].FullName",
                "  } else {",
                "    $PayloadRoot = $ExtractDir",
                "  }",
                "  Write-Log 'Backing up current toolbox files'",
                "  Get-ChildItem -LiteralPath $InstallDir -Force | Where-Object { $PreserveNames -notcontains $_.Name } | ForEach-Object {",
                "    Move-Item -LiteralPath $_.FullName -Destination (Join-Path $BackupDir $_.Name) -Force",
                "  }",
                "  Write-Log 'Copying new toolbox files'",
                "  Get-ChildItem -LiteralPath $PayloadRoot -Force | Where-Object { $PreserveNames -notcontains $_.Name } | ForEach-Object {",
                "    Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $InstallDir $_.Name) -Recurse -Force",
                "  }",
                "  Write-Log 'Restarting toolbox'",
                "  Write-Log 'Resetting PyInstaller environment'",
                "  Get-ChildItem Env: | Where-Object { $_.Name -like '_PYI_*' } | ForEach-Object {",
                "    Remove-Item -LiteralPath ('Env:' + $_.Name) -ErrorAction SilentlyContinue",
                "  }",
                "  $env:PYINSTALLER_RESET_ENVIRONMENT = '1'",
                f"  Start-Process -FilePath {_ps_quote(restart_command[0])}{argument_list} -WorkingDirectory $InstallDir",
                "  Write-Log 'Update completed'",
                "}",
                "catch {",
                "  Write-Log \"Update failed: $($_.Exception.Message)\"",
                "  if (Test-Path -LiteralPath $BackupDir) {",
                "    Get-ChildItem -LiteralPath $BackupDir -Force | ForEach-Object {",
                "      $target = Join-Path $InstallDir $_.Name",
                "      Remove-Item -LiteralPath $target -Recurse -Force -ErrorAction SilentlyContinue",
                "      Move-Item -LiteralPath $_.FullName -Destination $target -Force -ErrorAction SilentlyContinue",
                "    }",
                "  }",
                "  exit 1",
                "}",
                "",
            ]
        )


def default_restart_command(workspace: Path) -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        return (sys.executable,)
    return (sys.executable, str(workspace / "toolbox.py"))


def _sanitized_update_environment() -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if not key.startswith("_PYI_")}
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    return env


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"
