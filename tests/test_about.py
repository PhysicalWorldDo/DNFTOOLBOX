from physical_toolbox.about import ABOUT_NAV_LABEL, sidebar_navigation_labels, toolbox_about_info
from physical_toolbox.repository import IndexTool


def test_sidebar_navigation_always_includes_about_page_after_tool_categories() -> None:
    tools = (
        IndexTool("shot", "截图助手", "游戏工具", "shot.json"),
        IndexTool("music", "音乐检测", "音频工具", "music.json"),
    )

    labels = sidebar_navigation_labels(tools)

    assert labels[-1] == ABOUT_NAV_LABEL
    assert labels[:-1] == ("游戏工具", "音频工具")


def test_toolbox_about_info_keeps_author_contact_and_release_log() -> None:
    info = toolbox_about_info()

    assert info.title == "物理世界的工具箱"
    assert info.author == "物理世界的欺骗"
    assert info.qq_number == "1548220577"
    assert info.bilibili_url.startswith("https://space.bilibili.com/")
    assert info.github_url.endswith("/DNFTOOLBOX")
    assert info.feedback_url.endswith("/DNFTOOLBOX/issues")
    assert info.logs
    assert info.logs[0].version == "v0.1.0"
