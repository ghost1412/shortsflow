import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def ts_themes():
    src = (ROOT / "remotion-video" / "src" / "CaseVideo.tsx").read_text(encoding="utf-8")
    block = re.search(r"CASE_THEMES = \[(.*?)\] as const", src, re.S).group(1)
    return re.findall(r'"([a-z]+)"', block)


def cli_themes():
    src = (ROOT / "shortsflow" / "_main.py").read_text(encoding="utf-8")
    block = re.search(r'"--case_theme", choices=\[(.*?)\]', src, re.S).group(1)
    return re.findall(r'"([a-z]+)"', block)


def test_the_cli_offers_exactly_the_styles_the_video_composition_knows():
    assert ts_themes() == cli_themes() and len(ts_themes()) >= 9


def test_every_style_has_a_palette_entry():
    src = (ROOT / "remotion-video" / "src" / "CaseVideo.tsx").read_text(encoding="utf-8")
    palette = src[src.index("const PALETTES"):src.index("const FONT =")]
    for name in ts_themes():
        assert re.search(r"\n  %s: \{" % name, palette), name
