from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from physical_toolbox.github_proxy import (
    DEFAULT_GITHUB_PROXY_URLS,
    LEGACY_DEFAULT_GITHUB_PROXY_URLS,
    GitHubProxyConfig,
    normalize_proxy_urls,
)

DEFAULT_INDEX_URL = "https://raw.githubusercontent.com/PhysicalWorldDo/DNFTOOLBOX-Registry/main/index.json"
GITHUB_RAW_INDEX_URL = "https://github.com/PhysicalWorldDo/DNFTOOLBOX-Registry/raw/refs/heads/main/index.json"


@dataclass(frozen=True)
class AppConfig:
    name: str
    index_url: str
    channel: str
    github_proxy_enabled: bool = True
    github_proxy_urls: tuple[str, ...] = field(default_factory=lambda: DEFAULT_GITHUB_PROXY_URLS)
    suppress_directory_warning: bool = False

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
        proxy = data.get("githubProxy", {})
        if isinstance(proxy, dict):
            proxy_enabled = bool(proxy.get("enabled", default.github_proxy_enabled))
            proxy_urls = normalize_proxy_urls(proxy.get("urls", default.github_proxy_urls))
            if proxy_urls == LEGACY_DEFAULT_GITHUB_PROXY_URLS:
                proxy_urls = DEFAULT_GITHUB_PROXY_URLS
        else:
            proxy_enabled = default.github_proxy_enabled
            proxy_urls = default.github_proxy_urls
        return cls(
            name=str(data.get("name", default.name)),
            index_url=str(data.get("indexUrl", default.index_url)),
            channel=str(data.get("channel", default.channel)),
            github_proxy_enabled=proxy_enabled,
            github_proxy_urls=proxy_urls or default.github_proxy_urls,
            suppress_directory_warning=bool(
                data.get("suppressDirectoryWarning", default.suppress_directory_warning)
            ),
        )

    def github_proxy_config(self) -> GitHubProxyConfig:
        return GitHubProxyConfig(
            enabled=self.github_proxy_enabled,
            proxy_urls=self.github_proxy_urls,
        )

    def with_github_proxy(self, *, enabled: bool, urls: tuple[str, ...]) -> "AppConfig":
        return replace(
            self,
            github_proxy_enabled=enabled,
            github_proxy_urls=normalize_proxy_urls(urls) or DEFAULT_GITHUB_PROXY_URLS,
        )

    def with_directory_warning_suppressed(self, suppressed: bool) -> "AppConfig":
        return replace(self, suppress_directory_warning=suppressed)


def load_or_create_config(workspace: Path) -> AppConfig:
    path = workspace / "config" / "app.json"
    if not path.exists():
        config = AppConfig.default(workspace)
        _save_config(path, config)
        return config

    raw = json.loads(path.read_text(encoding="utf-8"))
    config = AppConfig.from_dict(raw, workspace)
    saved_proxy = raw.get("githubProxy", {})
    saved_proxy_urls = (
        normalize_proxy_urls(saved_proxy.get("urls", ())) if isinstance(saved_proxy, dict) else ()
    )
    needs_save = "githubProxy" not in raw or saved_proxy_urls == LEGACY_DEFAULT_GITHUB_PROXY_URLS
    if _uses_missing_old_example_index(config.index_url) or _uses_github_raw_index(config.index_url):
        config = AppConfig(
            name=config.name,
            index_url=DEFAULT_INDEX_URL,
            channel=config.channel,
            github_proxy_enabled=config.github_proxy_enabled,
            github_proxy_urls=config.github_proxy_urls,
            suppress_directory_warning=config.suppress_directory_warning,
        )
        needs_save = True
    if needs_save:
        _save_config(path, config)
    return config


def save_config(workspace: Path, config: AppConfig) -> None:
    _save_config(workspace / "config" / "app.json", config)


def _save_config(path: Path, config: AppConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "name": config.name,
                "indexUrl": config.index_url,
                "channel": config.channel,
                "suppressDirectoryWarning": config.suppress_directory_warning,
                "githubProxy": {
                    "enabled": config.github_proxy_enabled,
                    "urls": list(config.github_proxy_urls),
                },
            },
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


def _uses_github_raw_index(index_url: str) -> bool:
    return index_url.rstrip("/").lower() == GITHUB_RAW_INDEX_URL.lower()
