from __future__ import annotations

from pathlib import Path
import sys

from physical_toolbox.app_config import load_or_create_config
from physical_toolbox.ui import ToolboxApp, create_application


def workspace_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def main() -> None:
    workspace = workspace_root()
    config = load_or_create_config(workspace)
    app = create_application()
    window = ToolboxApp(workspace, config)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
