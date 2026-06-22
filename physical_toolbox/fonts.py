from __future__ import annotations

from pathlib import Path


PREFERRED_CJK_FONT_FILES: tuple[str, ...] = (
    "NotoSansSC-VF.ttf",
    "msyh.ttc",
    "msyh.ttf",
    "Microsoft YaHei UI.ttf",
    "simhei.ttf",
    "simsun.ttc",
    "simsunb.ttf",
    "Deng.ttf",
)


def candidate_cjk_font_paths(fonts_dir: Path | None = None) -> tuple[Path, ...]:
    directory = fonts_dir or Path("C:/Windows/Fonts")
    candidates: list[Path] = []
    for filename in PREFERRED_CJK_FONT_FILES:
        path = directory / filename
        if path.exists():
            candidates.append(path)
    return tuple(candidates)
