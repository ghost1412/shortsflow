"""Readers for the kinds of source a case explainer can use besides a plain web page: a PDF, a YouTube video's captions, a caption file (.srt, .vtt),
and local text files. Each returns plain text, or raises `SourceError` with a plain reason (`engine.case_study.gather_sources` turns that into
a "skipped" line). Network and PDF access are injectable, so the tests run offline.

    pip install pypdf          # only for PDFs (optional: pip install "shortsflow[sources]")
"""
import os
import re

MAX_PDF_PAGES = 60


class SourceError(RuntimeError):
    """A source that could not be read; the message is for the user."""


def is_youtube(url):
    return bool(re.match(r"https?://(?:www\.|m\.)?(?:youtube\.com/(?:watch|shorts|live)|youtu\.be/)", str(url or "").strip(), re.I))


def is_pdf_name(text):
    return str(text or "").split("?")[0].split("#")[0].lower().endswith(".pdf")


def subtitle_text(raw):
    """The spoken words of an .srt or .vtt file: no header, numbering, timing lines or tags, and the lines that automatic captions repeat
    from one cue to the next are kept once."""
    out, last = [], ""
    for line in str(raw or "").splitlines():
        line = line.strip()
        if (not line or line.startswith(("WEBVTT", "NOTE", "Kind:", "Language:", "STYLE")) or re.fullmatch(r"\d+", line)
                or re.search(r"\d\d:\d\d[:.,]\d\d\d?\s*-->", line)):
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"&nbsp;|&amp;|&gt;|&lt;", lambda m: {"&nbsp;": " ", "&amp;": "&", "&gt;": ">", "&lt;": "<"}[m.group(0)], line).strip()
        if line and line != last:
            out.append(line)
            last = line
    return " ".join(out)


def pdf_text(source, max_pages=MAX_PDF_PAGES, reader=None):
    """The text of a PDF given as a file path or as bytes (first `max_pages` pages). Raises SourceError when pypdf is missing, the file is
    protected, or it holds no text (a scanned PDF needs OCR, which is not done here). `reader` replaces pypdf.PdfReader (tests)."""
    if reader is None:
        try:
            from pypdf import PdfReader as reader
        except ImportError:
            raise SourceError("reading a PDF needs the pypdf package: pip install pypdf")
    import io
    try:
        doc = reader(io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source)
        if getattr(doc, "is_encrypted", False):
            raise SourceError("the PDF is password protected")
        text = " ".join((page.extract_text() or "") for page in list(doc.pages)[:max_pages])
    except SourceError:
        raise
    except Exception as e:
        raise SourceError(f"the PDF could not be read ({str(e)[:80]})")
    text = " ".join(text.split())
    if len(text) < 40:
        raise SourceError("the PDF has almost no text (a scan? OCR is not done here)")
    return text


def youtube_text(url, workdir, download=None):
    """The captions of a YouTube video as text (its own subtitles, else the automatic ones, English first). Nothing but the captions is
    downloaded. Raises SourceError when the video has none. `download(url, workdir)` returns the path of a caption file (tests replace it)."""
    download = download or _download_captions
    path = download(url, workdir)
    if not path or not os.path.isfile(path):
        raise SourceError("this video has no captions to read")
    with open(path, encoding="utf-8", errors="replace") as f:
        text = subtitle_text(f.read())
    if len(text) < 40:
        raise SourceError("this video has almost no captions")
    return text


def _download_captions(url, workdir):
    try:
        import yt_dlp
    except ImportError:
        raise SourceError("reading a YouTube video needs yt-dlp")
    os.makedirs(workdir, exist_ok=True)
    opts = {"skip_download": True, "writesubtitles": True, "writeautomaticsub": True, "subtitleslangs": ["en", "en-orig"], "subtitlesformat": "vtt",
            "outtmpl": os.path.join(workdir, "captions.%(ext)s"), "quiet": True, "no_warnings": True, "noprogress": True,
            "socket_timeout": 40, "retries": 3}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        raise SourceError("the video could not be reached (" + " ".join(str(e).split())[:80] + ")")
    found = sorted(n for n in os.listdir(workdir) if n.startswith("captions.") and n.endswith(".vtt"))
    return os.path.join(workdir, found[0]) if found else None


def read_file(path):
    """The text of a local file by its kind: .pdf, caption files (.srt, .vtt), anything else as text (HTML is stripped by the caller)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return pdf_text(path)
    with open(path, encoding="utf-8", errors="replace") as f:
        raw = f.read()
    return subtitle_text(raw) if ext in (".srt", ".vtt") else raw
