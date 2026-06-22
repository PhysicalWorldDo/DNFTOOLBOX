from __future__ import annotations

from pathlib import Path

from physical_toolbox.app_config import load_or_create_config
from physical_toolbox.ui import ToolboxApp, create_application


def main() -> None:
    workspace = Path(__file__).resolve().parent
    config = load_or_create_config(workspace)
    app = create_application()
    window = ToolboxApp(workspace, config)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
