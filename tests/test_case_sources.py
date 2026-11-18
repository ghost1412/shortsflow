import pytest

from engine import case_sources as src
from engine import case_study as cs

VTT = """WEBVTT
Kind: captions
Language: en

00:00:00.000 --> 00:00:02.000 align:start position:0%
All right, so here we are

00:00:02.000 --> 00:00:04.000
All right, so here we are
<c.colorE5E5E5>in front</c> of the elephants &amp; more

1
00:00:04,000 --> 00:00:06,000
in front of the elephants &amp; more
the cool thing about them is the trunks
"""


def test_is_youtube_and_pdf_names():
    assert src.is_youtube("https://www.youtube.com/watch?v=abc") and src.is_youtube("https://youtu.be/abc") and src.is_youtube("https://m.youtube.com/shorts/x")
    assert not src.is_youtube("https://example.com/watch?v=abc")
    assert src.is_pdf_name("https://a.example/report.PDF?download=1") and src.is_pdf_name("C:/x/y.pdf") and not src.is_pdf_name("https://a.example/page")


def test_subtitle_text_drops_timing_tags_and_repeated_lines():
    text = src.subtitle_text(VTT)
    assert text == "All right, so here we are in front of the elephants & more the cool thing about them is the trunks"
    assert "-->" not in text and "WEBVTT" not in text and "<c" not in text


def test_pdf_text_with_a_fake_reader_and_its_errors():
    class Page:
        def __init__(self, t):
            self.t = t

        def extract_text(self):
            return self.t

    class Reader:
        is_encrypted = False

        def __init__(self, source):
            self.pages = [Page("A ship ran aground on 23 March."), Page("The canal stayed closed for six days.")]
    assert "six days" in src.pdf_text(b"%PDF", reader=Reader)

    class Locked(Reader):
        is_encrypted = True

    class Empty(Reader):
        def __init__(self, source):
            self.pages = [Page("")]

    class Broken:
        def __init__(self, source):
            raise ValueError("bad xref")
    for bad, word in ((Locked, "password"), (Empty, "almost no text"), (Broken, "could not be read")):
        with pytest.raises(src.SourceError) as e:
            src.pdf_text(b"%PDF", reader=bad)
        assert word in str(e.value)


def test_youtube_text_uses_the_downloaded_captions(tmp_path):
    vtt = tmp_path / "captions.en.vtt"
    vtt.write_text(VTT, encoding="utf-8")
    assert "elephants" in src.youtube_text("https://youtu.be/x", str(tmp_path), download=lambda url, d: str(vtt))
    with pytest.raises(src.SourceError):
        src.youtube_text("https://youtu.be/x", str(tmp_path), download=lambda url, d: None)


def test_gather_sources_reads_every_kind(tmp_path, monkeypatch):
    srt = tmp_path / "talk.srt"
    srt.write_text(VTT, encoding="utf-8")
    note = tmp_path / "notes.md"
    note.write_text("A plain note about the case that is long enough to count as a source for the test.", encoding="utf-8")
    monkeypatch.setattr(src, "pdf_text", lambda data, **k: "Text of the pdf: " + ("x" * 60) + (" bytes" if isinstance(data, bytes) else " file"))
    vtt = tmp_path / "c.vtt"
    vtt.write_text(VTT, encoding="utf-8")
    items = ["https://example.com/report.pdf", "https://www.youtube.com/watch?v=abc", str(srt), str(note), str(tmp_path / "missing.pdf")]
    sources, skipped = cs.gather_sources(items, fetch=lambda u: "<p>unused</p>", fetch_raw=lambda u: b"%PDF-bytes", youtube=lambda u, d: str(vtt),
                                         workdir=str(tmp_path))
    assert [s["ref"] for s in sources] == ["https://example.com/report.pdf", "https://www.youtube.com/watch?v=abc", "talk.srt"]
    assert sources[0]["text"].endswith("bytes") and "elephants" in sources[1]["text"] and "elephants" in sources[2]["text"]
    assert any("only 3 sources" in why for _, why in skipped)           # the fourth is over the limit, the fifth too


def test_a_pdf_without_the_package_says_what_to_install(monkeypatch):
    import builtins
    real = builtins.__import__

    def fake(name, *a, **k):
        if name == "pypdf":
            raise ImportError("no pypdf")
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", fake)
    with pytest.raises(src.SourceError) as e:
        src.pdf_text(b"%PDF")
    assert "pip install pypdf" in str(e.value)
