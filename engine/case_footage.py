"""Stock footage for the sections of a case explainer: one short Pexels clip per section, shown dimmed behind the drawn scene.

Only the search words leave the PC (the section's `footage` phrase). Clips are cached by phrase, so a re-run downloads nothing.
Needs PEXELS_API_KEY; without it, or when nothing is found, the section keeps its plain background.
"""
import hashlib
import os
import re

API = "https://api.pexels.com/videos/search"


def pick_link(files, want_width=1280):
    """The download link of the clip file closest to `want_width` wide (4K is slow to fetch and gains nothing behind a dimmed scene),
    None when the list holds no usable file."""
    sized = [f for f in files or [] if f.get("link") and f.get("width") and str(f.get("file_type", "video/mp4")).endswith("mp4")]
    if not sized:
        return None
    return min(sized, key=lambda f: (abs(int(f["width"]) - want_width), int(f["width"]) < want_width))["link"]


def cache_path(cache_dir, query, orientation):
    key = hashlib.sha1(f"{query.lower().strip()}|{orientation}".encode("utf-8")).hexdigest()[:10]
    slug = re.sub(r"[^a-z0-9]+", "_", query.lower()).strip("_")[:30]
    return os.path.join(cache_dir, f"{slug}_{orientation}_{key}.mp4")


def fetch(query, cache_dir, orientation="landscape", api_key=None, get=None, max_seconds=30):
    """(path, seconds) of a clip for `query`, None when there is no key, no result or the download fails. `get` replaces requests.get."""
    query = " ".join(str(query or "").split())
    api_key = api_key or os.getenv("PEXELS_API_KEY", "")
    if not query or not api_key:
        return None
    if get is None:
        import requests
        get = requests.get
    path = cache_path(cache_dir, query, orientation)
    meta = path + ".len"
    if os.path.exists(path) and os.path.exists(meta):
        try:
            return path, float(open(meta, encoding="utf-8").read())
        except (OSError, ValueError):
            pass
    try:
        r = get(API, params={"query": query, "per_page": 8, "orientation": orientation, "size": "medium"},
                headers={"Authorization": api_key}, timeout=20)
        r.raise_for_status()
        videos = [v for v in r.json().get("videos", []) if 4 <= float(v.get("duration") or 0) <= max_seconds]
        for v in videos:
            link = pick_link(v.get("video_files"), 1280 if orientation == "landscape" else 720)
            if not link:
                continue
            data = get(link, timeout=60)
            data.raise_for_status()
            os.makedirs(cache_dir, exist_ok=True)
            with open(path, "wb") as f:
                f.write(data.content)
            with open(meta, "w", encoding="utf-8") as f:
                f.write(str(float(v["duration"])))
            return path, float(v["duration"])
    except Exception as e:
        print(f"[Warning] Stock footage for '{query}' failed ({str(e)[:100]}).")
    return None
