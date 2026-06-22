from pathlib import Path

from physical_toolbox.fonts import candidate_cjk_font_paths


def test_candidate_cjk_font_paths_prefer_modern_simplified_chinese_fonts(tmp_path: Path) -> None:
    fonts = tmp_path / "Fonts"
    fonts.mkdir()
    (fonts / "simhei.ttf").write_text("", encoding="utf-8")
    (fonts / "NotoSansSC-VF.ttf").write_text("", encoding="utf-8")
    (fonts / "arial.ttf").write_text("", encoding="utf-8")

    candidates = candidate_cjk_font_paths(fonts)

    assert candidates[0].name == "NotoSansSC-VF.ttf"
    assert candidates[1].name == "simhei.ttf"
    assert all(candidate.name != "arial.ttf" for candidate in candidates)
