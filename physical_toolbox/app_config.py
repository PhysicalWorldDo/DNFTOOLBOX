from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_INDEX_URL = "https://raw.githubusercontent.com/PhysicalWorldDo/DNFTOOLBOX-Registry/main/index.json"


@dataclass(frozen=True)
class AppConfig:
    name: str
    index_url: str
    channel: str

    @classmethod
    def default(cls, workspace: Path) -> "AppConfig":
        return cls(
            name="物理世界的工具箱",
            index_url=DEFAULT_INDEX_URL,
            channel="stable",
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any], workspace: Path) -> "AppConfig":
        default = cls.default(workspace)
        return cls(
            name=str(data.get("name", default.name)),
            index_url=str(data.get("indexUrl", default.index_url)),
            channel=str(data.get("channel", default.channel)),
        )


def load_or_create_config(workspace: Path) -> AppConfig:
    path = workspace / "config" / "app.json"
    if not path.exists():
        config = AppConfig.default(workspace)
        _save_config(path, config)
        return config

    config = AppConfig.from_dict(json.loads(path.read_text(encoding="utf-8")), workspace)
    if _uses_missing_old_example_index(config.index_url):
        config = AppConfig(name=config.name, index_url=DEFAULT_INDEX_URL, channel=config.channel)
        _save_config(path, config)
    return config


def _save_config(path: Path, config: AppConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {"name": config.name, "indexUrl": config.index_url, "channel": config.channel},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _uses_missing_old_example_index(index_url: str) -> bool:
    normalized = index_url.replace("\\", "/").lower()
    if not normalized.endswith("/examples/remote-index/index.json"):
        return False
    return not Path(index_url).exists()
