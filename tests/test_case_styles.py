import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ts_themes():
    src = (ROOT / "remotion-video" / "src" / "CaseVideo.tsx").read_text(encoding="utf-8")
    block = re.search(r"CASE_THEMES = \[(.*?)\] as const", src, re.S).group(1)
    return re.findall(r'"([a-z]+)"', block)


def cli_themes():
    from engine import case_options
    return list(case_options.THEMES)


def test_the_cli_offers_exactly_the_styles_the_video_composition_knows():
    assert ts_themes() == cli_themes() and len(ts_themes()) >= 9


def test_every_style_has_a_palette_entry():
    src = (ROOT / "remotion-video" / "src" / "CaseVideo.tsx").read_text(encoding="utf-8")
    palette = src[src.index("const PALETTES"):src.index("const FONT =")]
    for name in ts_themes():
        assert re.search(r"\n  %s: \{" % name, palette), name


def test_case_tab_arguments():
    from shortsflow import web_args
    assert web_args.parse_sources("  https://a.example/x \n\n notes here \nthree\nfour") == ["https://a.example/x", "notes here", "three"]
    args = web_args.case_args("The topic", "https://a.example/x\nnotes", "postmortem", "neon", ["9:16", "bogus"], True, True, "sessions/s")
    assert args[:4] == ["--mode", "CASE", "--prompt", "The topic"]
    pairs = [args[i + 1] for i, a in enumerate(args) if a == "--case"]
    assert "template=postmortem" in pairs and "theme=neon" in pairs and "formats=9:16" in pairs
    assert "manim=off" in pairs and "background=none" in pairs                       # no_footage means no pictures
    assert args.count("--sources") == 2
    bad = web_args.case_args("t", theme="nonsense")
    assert "theme=nonsense" not in [bad[i + 1] for i, a in enumerate(bad) if a == "--case"]    # an unknown look falls back to the default (nothing sent)
    try:
        web_args.case_args("  ")
    except ValueError as e:
        assert "topic" in str(e)
    else:
        raise AssertionError("an empty topic must be refused")


def test_the_case_theme_list_in_the_web_args_matches_the_cli():
    from shortsflow import web_args
    assert web_args.CASE_THEMES == cli_themes() and set(web_args.CASE_THEME_LABELS) == set(web_args.CASE_THEMES)


def test_find_case_videos_lists_landscape_first(tmp_path):
    from shortsflow import web_args
    (tmp_path / "case_9x16.mp4").write_bytes(b"x")
    (tmp_path / "case_16x9.mp4").write_bytes(b"x")
    import os
    assert [os.path.basename(p) for p in web_args.find_case_videos(str(tmp_path))] == ["case_16x9.mp4", "case_9x16.mp4"]
