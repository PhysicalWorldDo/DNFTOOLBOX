from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InstalledTool:
    id: str
    name: str
    version: str
    channel: str
    entry: str
    installed_at: str
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstalledTool":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            version=str(data["version"]),
            channel=str(data.get("channel", "stable")),
            entry=str(data["entry"]),
            installed_at=str(data.get("installedAt", "")),
            updated_at=str(data.get("updatedAt", "")),
        )

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        return {
            "id": data["id"],
            "name": data["name"],
            "version": data["version"],
            "channel": data["channel"],
            "entry": data["entry"],
            "installedAt": data["installed_at"],
            "updatedAt": data["updated_at"],
        }


class InstallStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[str, InstalledTool]:
        if not self.path.exists():
            return {}

        raw = json.loads(self.path.read_text(encoding="utf-8"))
        tools = raw.get("tools", {})
        return {tool_id: InstalledTool.from_dict(data) for tool_id, data in tools.items()}

    def save(self, tools: dict[str, InstalledTool]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "tools": {
                tool_id: tool.to_json()
                for tool_id, tool in sorted(tools.items(), key=lambda item: item[0])
            }
        }
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def record(self, tool: InstalledTool) -> None:
        tools = self.load()
        tools[tool.id] = tool
        self.save(tools)

    def remove(self, tool_id: str) -> None:
        tools = self.load()
        tools.pop(tool_id, None)
        self.save(tools)
