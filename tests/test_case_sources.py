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


def _fake_transcribe(text):
    import json
    import os

    def run(path, workdir, language):
        out = os.path.join(workdir, "transcript.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"segments": [{"text": text[:50]}, {"text": text[50:]}]}, f)
        return out
    return run


def test_transcribe_file_listens_to_the_trimmed_audio_and_joins_the_segments(tmp_path):
    seen = {}

    def trim(path, workdir, seconds):
        seen["seconds"] = seconds
        return str(tmp_path / "short.wav")
    speech = "The ship ran aground on the morning of 23 March and the canal closed for six days."
    text = src.transcribe_file(str(tmp_path / "talk.mp4"), str(tmp_path), transcribe=_fake_transcribe(speech), trim=trim)
    assert text.replace("  ", " ") == " ".join(speech[:50].split() + speech[50:].split()) and seen["seconds"] == src.MAX_TRANSCRIBE_MINUTES * 60
    with pytest.raises(src.SourceError) as e:
        src.transcribe_file(str(tmp_path / "x.mp3"), str(tmp_path), transcribe=_fake_transcribe("hmm"), trim=lambda p, w, s: p)
    assert "almost no speech" in str(e.value)

    def broken(path, workdir, language):
        raise RuntimeError("model missing")
    with pytest.raises(src.SourceError) as e:
        src.transcribe_file(str(tmp_path / "x.mp3"), str(tmp_path), transcribe=broken, trim=lambda p, w, s: p)
    assert "could not be transcribed" in str(e.value)


def test_a_youtube_video_without_captions_is_listened_to(tmp_path):
    audio = tmp_path / "audio.m4a"
    audio.write_bytes(b"x")
    speech = "Nobody wrote captions for this one, so the speech model heard it instead, and it said enough."
    sources, skipped = cs.gather_sources(["https://www.youtube.com/watch?v=abc"], youtube=lambda u, d: None, audio=lambda u, d: str(audio),
                                         transcribe=_fake_transcribe(speech), trim=lambda p, w, s: p, workdir=str(tmp_path))
    assert not skipped and "speech model heard it" in sources[0]["text"] and sources[0]["ref"].endswith("abc")


def test_a_local_audio_or_video_file_is_transcribed_and_a_failure_is_a_skip(tmp_path):
    clip = tmp_path / "interview.mp4"
    clip.write_bytes(b"x")
    speech = "The engineer explained that the update changed one file and that every machine then failed to start."
    sources, skipped = cs.gather_sources([str(clip)], transcribe=_fake_transcribe(speech), trim=lambda p, w, s: p, workdir=str(tmp_path))
    assert sources[0]["ref"] == "interview.mp4" and "engineer explained" in sources[0]["text"] and not skipped

    def nothing(path, workdir, language):
        raise src.SourceError("almost no speech was heard in this file")
    sources, skipped = cs.gather_sources([str(clip)], transcribe=nothing, trim=lambda p, w, s: p, workdir=str(tmp_path))
    assert sources == [] and "almost no speech" in skipped[0][1]


def test_audio_extensions():
    assert src.is_audio_or_video_file("C:/x/Talk.MP3") and src.is_audio_or_video_file("a.mkv") and not src.is_audio_or_video_file("a.pdf")
    assert not src.is_audio_or_video_file("notes.txt")


def test_pdf_behind_a_link_without_pdf_ending_is_read_as_pdf():
    from engine import case_sources, case_study as cs
    assert case_sources.is_pdf_name("https://arxiv.org/pdf/2611.23219")
    seen = []
    import engine.case_sources as m
    orig = m.pdf_text
    m.pdf_text = lambda raw, **k: seen.append(raw) or "the paper text " * 10
    try:
        src, skipped = cs.gather_sources(["https://example.org/download?id=7"], fetch=lambda u: "%PDF-1.7 binary", fetch_raw=lambda u: b"%PDF-1.7 bytes")
    finally:
        m.pdf_text = orig
    assert seen == [b"%PDF-1.7 bytes"] and src[0]["text"].startswith("the paper text") and not skipped


def test_pdf_text_joins_a_decimal_split_by_a_stray_space():
    from engine import case_sources as m

    class Page:
        def extract_text(self): return "The factor is 2 .14 and the error 0 .143% per cycle, in 2019. 5 labs joined, which is long enough."
    class Doc:
        pages = [Page()]
    assert "2.14" in m.pdf_text(b"x", reader=lambda f: Doc()) and "0.143%" in m.pdf_text(b"x", reader=lambda f: Doc())
    assert "2019. 5 labs" in m.pdf_text(b"x", reader=lambda f: Doc())


def test_a_page_that_is_empty_until_its_scripts_run_is_read_through_the_browser_and_a_short_static_page_is_not():
    from engine import case_study as cs
    shell = "<html><head><script src='app.js'></script></head><body><div id='root'></div></body></html>"
    rendered = "<html><body><main>" + "".join(f"<li>Base hero Health increased from {100 + i} to {200 + i} in this patch</li>" for i in range(12)) + "</main></body></html>"
    seen = []
    sources, skipped = cs.gather_sources(["https://example.com/app"], fetch=lambda u: shell, render=lambda u: seen.append(u) or rendered)
    assert seen == ["https://example.com/app"] and not skipped and "Base hero Health increased from 100 to 200" in sources[0]["text"]
    # a short page that has a script but real text is read as it is: no browser is started
    seen.clear()
    short = "<html><script>x=1</script><p>Three short sentences about a topic that has enough words to be read as it stands now.</p></html>"
    cs.gather_sources(["https://example.com/short"], fetch=lambda u: short, render=lambda u: seen.append(u) or rendered)
    assert seen == []


def test_readable_text_drops_menus_and_numbers_but_keeps_statements_and_bullets():
    from engine import case_study as cs
    html = ("<nav><a>Home</a> <a>News and many other links here today</a></nav><ul><li>Home</li><li>Heroes</li></ul>"
            "<div>2d 7.22c 7.22b 7.22 7.21d 7.21c 7.21b 7.21</div>"
            "<main><h1>Patch 7.42 notes for everyone who plays</h1>"
            + "".join(f"<li>Base hero Health increased from {100 + i} to {200 + i}</li>" for i in range(10)) + "</main><footer>Terms of use and privacy policy of this website</footer>")
    text = cs._readable(html)
    assert "Base hero Health increased from 100 to 200" in text and "Patch 7.42 notes" in text
    assert "Home" not in text and "7.22c" not in text and "Terms of use" not in text and "News and many" not in text


def test_the_browser_command_for_a_page_and_its_failures():
    from engine import case_sources as cso
    import pytest
    ran = []

    def run(cmd, limit):
        ran.append(cmd)
        return "<html>" + "x " * 200 + "</html>"
    out = cso.rendered_html("https://example.com/p", browser=r"C:\x\chrome-headless-shell.exe", run=run)
    assert "--dump-dom" in ran[0] and "https://example.com/p" in ran[0] and "--headless=new" not in ran[0] and any(a.startswith("--virtual-time-budget") for a in ran[0])
    cso.rendered_html("https://example.com/p", browser=r"C:\Chrome\chrome.exe", run=run)
    assert "--headless=new" in ran[1]
    with pytest.raises(cso.SourceError):
        cso.rendered_html("https://example.com/p", browser=r"C:\x\chrome-headless-shell.exe", run=lambda c, t: "<html></html>")


def test_no_browser_at_all_is_a_clear_skip_reason(monkeypatch):
    from engine import case_sources as cso
    import pytest
    monkeypatch.setattr(cso, "find_browser", lambda: None)
    with pytest.raises(cso.SourceError) as e:
        cso.rendered_html("https://example.com/p")
    assert "no browser was found" in str(e.value)
