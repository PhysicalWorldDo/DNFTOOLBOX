from __future__ import annotations

import urllib.parse
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable

LEGACY_DEFAULT_GITHUB_PROXY_URLS: tuple[str, ...] = (
    "https://ghfast.top/",
    "https://gh-proxy.com/",
    "https://ghproxy.net/",
    "https://github.akams.cn/",
    "https://gitproxy.click/",
)

GITHUB_AKAMS_PROXY_URLS: tuple[str, ...] = (
    "https://gh.llkk.cc/",
    "https://github.tbedu.top/",
    "https://ghfile.geekertao.top/",
    "https://cdn.gh-proxy.com/",
    "https://github.dpik.top/",
    "https://gh.dpik.top/",
    "https://j.1lin.dpdns.org/",
    "https://github.starrlzy.cn/",
    "https://github-proxy.memory-echoes.cn/",
    "https://gh.felicity.ac.cn/",
    "https://cdn.akaere.online/",
    "https://slink.ltd/",
    "https://github.tmby.shop/",
    "https://ghpr.cc/",
    "https://gh.tryxd.cn/",
    "https://github.chenc.dev/",
    "https://gh.ddlc.top/",
    "https://gitproxy.mrhjx.cn/",
    "https://gh.sixyin.com/",
    "https://gh.monlor.com/",
)

DEFAULT_GITHUB_PROXY_URLS: tuple[str, ...] = (*LEGACY_DEFAULT_GITHUB_PROXY_URLS, *GITHUB_AKAMS_PROXY_URLS)

GITHUB_DOWNLOAD_HOSTS = {
    "github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "api.github.com",
}

DEFAULT_SPEED_TEST_TIMEOUT = 3.0
SPEED_TEST_CACHE_SECONDS = 60.0
MAX_SPEED_TEST_WORKERS = 8
ProbeCandidate = Callable[[str, float], float | None]
_RANKING_CACHE: dict[tuple[tuple[str, ...], str, float], tuple[float, tuple[str, ...]]] = {}


@dataclass(frozen=True)
class GitHubProxyConfig:
    enabled: bool = True
    proxy_urls: tuple[str, ...] = DEFAULT_GITHUB_PROXY_URLS
    auto_select_fastest: bool = True
    speed_test_timeout: float = DEFAULT_SPEED_TEST_TIMEOUT


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


def github_url_candidates(
    url: str,
    config: GitHubProxyConfig,
    probe_candidate: ProbeCandidate | None = None,
) -> tuple[str, ...]:
    if not config.enabled or not _is_github_download_url(url):
        return (url,)

    proxy_urls = normalize_proxy_urls(config.proxy_urls)
    if not proxy_urls:
        return (url,)

    candidate_sources = (*proxy_urls, "")
    if config.auto_select_fastest:
        candidate_sources = _rank_candidate_sources_by_latency(
            url,
            candidate_sources,
            timeout=config.speed_test_timeout,
            probe_candidate=probe_candidate,
        )
    return tuple(_source_candidate_url(source, url) for source in candidate_sources)


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


def _source_candidate_url(source: str, target_url: str) -> str:
    if not source:
        return target_url
    return _apply_proxy(source, target_url)


def _rank_candidate_sources_by_latency(
    target_url: str,
    candidate_sources: tuple[str, ...],
    *,
    timeout: float,
    probe_candidate: ProbeCandidate | None,
) -> tuple[str, ...]:
    parsed = urllib.parse.urlparse(target_url)
    cache_key = (candidate_sources, parsed.netloc.lower(), timeout)
    now = time.monotonic()
    if probe_candidate is None:
        cached = _RANKING_CACHE.get(cache_key)
        if cached is not None and now - cached[0] <= SPEED_TEST_CACHE_SECONDS:
            return cached[1]

    ranked = _rank_sources_by_latency(
        target_url,
        candidate_sources,
        timeout=timeout,
        probe_candidate=probe_candidate or _probe_candidate,
    )
    if probe_candidate is None:
        _RANKING_CACHE[cache_key] = (now, ranked)
    return ranked


def _rank_sources_by_latency(
    target_url: str,
    candidate_sources: tuple[str, ...],
    *,
    timeout: float,
    probe_candidate: ProbeCandidate,
) -> tuple[str, ...]:
    successful: list[tuple[float, int, str]] = []
    failed: list[tuple[int, str]] = []
    with ThreadPoolExecutor(max_workers=min(MAX_SPEED_TEST_WORKERS, len(candidate_sources))) as executor:
        futures = {
            executor.submit(
                _safe_probe,
                probe_candidate,
                _source_candidate_url(source, target_url),
                timeout,
            ): (index, source)
            for index, source in enumerate(candidate_sources)
        }
        for future in as_completed(futures):
            index, source = futures[future]
            elapsed = future.result()
            if elapsed is None:
                failed.append((index, source))
            else:
                successful.append((elapsed, index, source))

    successful.sort(key=lambda item: (item[0], item[1]))
    failed.sort(key=lambda item: item[0])
    return tuple(item[2] for item in successful) + tuple(item[1] for item in failed)


def _safe_probe(probe_candidate: ProbeCandidate, candidate_url: str, timeout: float) -> float | None:
    try:
        return probe_candidate(candidate_url, timeout)
    except Exception:
        return None


def _probe_candidate(candidate_url: str, timeout: float) -> float | None:
    request = urllib.request.Request(
        candidate_url,
        headers={
            "Range": "bytes=0-0",
            "User-Agent": "PhysicalWorldToolbox/1.0",
            "Cache-Control": "no-cache",
        },
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=timeout) as response:
        response.read(1)
    return time.monotonic() - started
