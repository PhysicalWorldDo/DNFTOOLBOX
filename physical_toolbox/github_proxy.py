from __future__ import annotations

import urllib.parse
from dataclasses import dataclass
from typing import Iterable

DEFAULT_GITHUB_PROXY_URLS: tuple[str, ...] = (
    "https://ghfast.top/",
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
    "https://github.akams.cn/",
    "https://gitproxy.click/",
)

GITHUB_DOWNLOAD_HOSTS = {
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "api.github.com",
}


@dataclass(frozen=True)
class GitHubProxyConfig:
    enabled: bool = True
    proxy_urls: tuple[str, ...] = DEFAULT_GITHUB_PROXY_URLS


def normalize_proxy_urls(urls: Iterable[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    seen: set[str] = set()
    for item in urls:
        url = item.strip()
        if not url or url.startswith("#"):
            continue
        if "://" not in url:
            url = f"https://{url}"
        if "{" not in url and not url.endswith("/"):
            url = f"{url}/"
        if url in seen:
            continue
        seen.add(url)
        normalized.append(url)
    return tuple(normalized)


def github_url_candidates(url: str, config: GitHubProxyConfig) -> tuple[str, ...]:
    if not config.enabled or not _is_github_download_url(url):
        return (url,)

    proxy_urls = normalize_proxy_urls(config.proxy_urls)
    if not proxy_urls:
        return (url,)

    candidates = [_apply_proxy(proxy_url, url) for proxy_url in proxy_urls]
    candidates.append(url)
    return tuple(candidates)


def _is_github_download_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    return parsed.netloc.lower() in GITHUB_DOWNLOAD_HOSTS


def _apply_proxy(proxy_url: str, target_url: str) -> str:
    if "{encoded_url}" in proxy_url:
        return proxy_url.replace("{encoded_url}", urllib.parse.quote(target_url, safe=""))
    if "{url}" in proxy_url:
        return proxy_url.replace("{url}", target_url)
    return f"{proxy_url}{target_url}"
