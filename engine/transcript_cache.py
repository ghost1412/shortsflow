"""A shared cache of transcripts, so the same video is only transcribed once, whichever session it is in.

The session folder already keeps a `transcript.json`, but every new run starts in a new folder, so the same long video was transcribed
again on each run (minutes of GPU time). The key is the video's content (size plus the first and last megabyte), the language, the
filler setting and the speech model, so a different video, language or model never gets a wrong transcript. The files stay on this PC
under ~/.shortsflow/cache/transcripts (SHORTSFLOW_CACHE_DIR moves it, SHORTSFLOW_TRANSCRIPT_CACHE=off turns it off).
"""
import hashlib
import json
import os
import shutil

_CHUNK = 1024 * 1024
KEEP = 200            # transcripts kept; the oldest cache files beyond this are removed, so the folder cannot grow for ever


def enabled():
    return os.environ.get("SHORTSFLOW_TRANSCRIPT_CACHE", "on").strip().lower() not in ("off", "0", "no", "false")


def cache_dir():
    base = os.environ.get("SHORTSFLOW_CACHE_DIR") or os.path.join(os.path.expanduser("~"), ".shortsflow", "cache")
    return os.path.join(base, "transcripts")


def cache_key(video_path, language, keep_fillers, model_name):
    """Hex key for this video, language, filler setting and speech model; None when the video cannot be read."""
    try:
        size = os.path.getsize(video_path)
        h = hashlib.sha1()
        with open(video_path, "rb") as f:
            h.update(f.read(_CHUNK))
            if size > 2 * _CHUNK:
                f.seek(size - _CHUNK)
                h.update(f.read(_CHUNK))
    except OSError:
        return None
    h.update(repr((size, str(language or "en").lower(), bool(keep_fillers), str(model_name))).encode("utf-8"))
    return h.hexdigest()


def lookup(key):
    """Path of the cached transcript for `key`, or None."""
    if not key:
        return None
    path = os.path.join(cache_dir(), f"{key}.json")
    return path if os.path.isfile(path) and os.path.getsize(path) > 2 else None


def restore(cached_path, session_transcript_path, video_path):
    """Put the cached transcript into the session folder, pointing at this run's video path. Returns True on success."""
    try:
        with open(cached_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("segments"):
            return False
        data["source_video_path"] = os.path.abspath(video_path)
        os.makedirs(os.path.dirname(os.path.abspath(session_transcript_path)), exist_ok=True)
        with open(session_transcript_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except (OSError, ValueError):
        return False


def store(key, session_transcript_path):
    """Keep a finished transcript for later runs (never raises: a cache that cannot be written is only a missed speed-up)."""
    if not key:
        return False
    try:
        with open(session_transcript_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not data.get("segments"):
            return False
        os.makedirs(cache_dir(), exist_ok=True)
        tmp = os.path.join(cache_dir(), f"{key}.json.tmp")
        shutil.copyfile(session_transcript_path, tmp)
        os.replace(tmp, os.path.join(cache_dir(), f"{key}.json"))
        prune()
        return True
    except (OSError, ValueError):
        return False


def prune(keep=None):
    """Remove the oldest transcript files (only this cache's own <key>.json files) beyond `keep`. Never raises."""
    keep = KEEP if keep is None else keep
    try:
        folder = cache_dir()
        files = [os.path.join(folder, n) for n in os.listdir(folder) if n.endswith(".json") and len(n) == 45]
        files.sort(key=os.path.getmtime, reverse=True)
        for old in files[keep:]:
            try:
                os.remove(old)
            except OSError:
                pass
    except OSError:
        pass
