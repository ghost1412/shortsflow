"""Settings of the browser app: which keys are set (never shown in full), adding and removing them, and the upload preferences.

Keys live in the workspace `.env` (the same file the command line reads), so a key added here works everywhere. Only the names in `KEYS` can be
set from the app. A key is shown as its last four characters at most. Upload preferences (which platforms, whether a finished run is published
by itself) live in `settings.json` next to the `.env`; auto-publish is OFF unless the person turns it on.

Publishing goes through engine/publish.py (the Upload-Post service, which holds the platform sign-ins): one key and one profile name cover
YouTube, TikTok, Instagram, Facebook, LinkedIn, X, Threads and Pinterest. Say so in any text that offers it: the video and its title leave the PC.
"""
import json
import os
import re

# (env name, label, group, what it is for, where to get it)
KEYS = (
    ("GEMINI_API_KEY", "Gemini", "AI text", "Scripts, titles, descriptions (free tier has a daily limit)", "aistudio.google.com/apikey"),
    ("GROQ_API_KEY", "Groq", "AI text", "Fast free fallback for scripts and titles", "console.groq.com"),
    ("OPENAI_API_KEY", "OpenAI", "AI text", "Scripts and titles", "platform.openai.com/api-keys"),
    ("ANTHROPIC_API_KEY", "Anthropic", "AI text", "Scripts and titles", "console.anthropic.com"),
    ("DEEPSEEK_API_KEY", "DeepSeek", "AI text", "Scripts and titles", "platform.deepseek.com"),
    ("OPENROUTER_API_KEY", "OpenRouter", "AI text", "Scripts and titles through one account", "openrouter.ai/keys"),
    ("HF_API_KEY", "Hugging Face", "AI text", "Last-resort text model", "huggingface.co/settings/tokens"),
    ("PEXELS_API_KEY", "Pexels", "Media", "Stock footage and photos behind scenes (free)", "pexels.com/api"),
    ("ELEVENLABS_API_KEY", "ElevenLabs", "Voice", "A natural narrator voice (without it the free Edge voice is used)", "elevenlabs.io"),
    ("UPLOAD_POST_API_KEY", "Upload-Post key", "Uploads", "Publishes to YouTube, TikTok, Instagram and more", "upload-post.com"),
    ("UPLOAD_POST_USER", "Upload-Post profile", "Uploads", "The profile name you made at upload-post.com (it holds your connected accounts)", "upload-post.com"),
)
KEY_NAMES = tuple(k[0] for k in KEYS)
SECRET_NAMES = tuple(n for n in KEY_NAMES if n != "UPLOAD_POST_USER")      # the profile name is not a secret: it is shown as is

# platforms that want a tall video, platforms that want a wide one; YouTube takes both (Shorts and a normal video)
PORTRAIT_PLATFORMS = ("tiktok", "instagram", "pinterest", "threads")
LANDSCAPE_PLATFORMS = ("linkedin", "facebook", "x")
PREFS_FILE = "settings.json"
DEFAULT_PREFS = {"auto_publish": False, "platforms": []}


def is_real(value):
    """False for the placeholders env.example ships (your_gemini_key_here) and for empty values."""
    value = (value or "").strip()
    return bool(value) and "your_" not in value and not value.endswith("_here")


def mask(value):
    """The last four characters of a secret, the rest as dots; short values are only dots."""
    value = (value or "").strip()
    if not value:
        return ""
    return "••••" + value[-4:] if len(value) >= 12 else "••••"


def read_env(env_path):
    """{NAME: value} of the real (non-placeholder) values in a .env file."""
    values = {}
    try:
        with open(env_path, encoding="utf-8") as f:
            for line in f.read().splitlines():
                m = re.match(r"\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
                if m and not line.lstrip().startswith("#"):
                    value = re.sub(r"\s+#.*$", "", m.group(2)).strip().strip("\"'")
                    if is_real(value):
                        values[m.group(1)] = value
    except OSError:
        pass
    return values


def key_rows(env_path, environ=None):
    """[{env, label, group, purpose, where, set, shown}] for every known key. `shown` is the masked secret (the profile name in full)."""
    environ = os.environ if environ is None else environ
    stored = read_env(env_path)
    rows = []
    for name, label, group, purpose, where in KEYS:
        value = stored.get(name) or (environ.get(name) if is_real(environ.get(name)) else "")
        rows.append({"env": name, "label": label, "group": group, "purpose": purpose, "where": where, "set": bool(value),
                     "shown": ("" if not value else (value if name not in SECRET_NAMES else mask(value)))})
    return rows


def rows_markdown(rows):
    """The key list as a Markdown table for the page."""
    lines = ["| Key | Used for | Status |", "| :--- | :--- | :--- |"]
    for r in rows:
        status = f"✅ set ({r['shown']})" if r["set"] else f"not set · get one at {r['where']}"
        lines.append(f"| **{r['label']}** ({r['group']}) | {r['purpose']} | {status} |")
    return "\n".join(lines)


def choices(rows):
    """[(label, env name)] for a dropdown, with ✅ on the keys that are set."""
    return [(("✅ " if r["set"] else "") + f"{r['label']} ({r['group']})", r["env"]) for r in rows]


def set_key(env_path, name, value):
    """Add or replace a known key. Returns (ok, message). The key is never echoed."""
    from shortsflow import onboarding
    if name not in KEY_NAMES:
        return False, "Choose which key this is first."
    if not (value or "").strip():
        return False, "Paste the key first."
    if onboarding.save_env_key(env_path, name, value):
        return True, f"Saved. It is used from the next run."
    return False, "That does not look like a key (no spaces, nothing else on the line). Copy it again from the provider's page."


def remove_key(env_path, name, environ=None):
    """Delete a known key from the .env file and from this process. Returns (ok, message)."""
    environ = os.environ if environ is None else environ
    if name not in KEY_NAMES:
        return False, "Choose which key to remove first."
    lines, found = [], False
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for ln in f.read().splitlines():
                if re.match(rf"\s*{re.escape(name)}\s*=", ln):
                    found = True
                    continue
                lines.append(ln)
        if found:
            with open(env_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + ("\n" if lines else ""))
    had_env = name in environ
    environ.pop(name, None)
    if found or had_env:
        return True, "Removed."
    return False, "That key was not set."


def prefs_path(home):
    return os.path.join(home, PREFS_FILE)


def load_prefs(home):
    """The saved upload preferences, with defaults for anything missing or invalid."""
    from engine.publish import PLATFORMS
    prefs = dict(DEFAULT_PREFS)
    try:
        with open(prefs_path(home), encoding="utf-8") as f:
            data = json.load(f)
        prefs["auto_publish"] = bool(data.get("auto_publish", False))
        prefs["platforms"] = [p for p in (data.get("platforms") or []) if p in PLATFORMS]
    except (OSError, ValueError, AttributeError):
        pass
    return prefs


def save_prefs(home, auto_publish, platforms):
    """Save the upload preferences. Returns the saved dict."""
    from engine.publish import PLATFORMS
    prefs = {"auto_publish": bool(auto_publish), "platforms": [p for p in (platforms or []) if p in PLATFORMS]}
    with open(prefs_path(home), "w", encoding="utf-8", newline="\n") as f:
        json.dump(prefs, f, indent=1)
    return prefs


def publish_ready(env_path, environ=None):
    """(ok, message): whether uploads can be made (key and profile set)."""
    rows = {r["env"]: r for r in key_rows(env_path, environ)}
    missing = [rows[n]["label"] for n in ("UPLOAD_POST_API_KEY", "UPLOAD_POST_USER") if not rows[n]["set"]]
    if missing:
        return False, "Add " + " and ".join(missing) + " above first (made at upload-post.com, where you also connect YouTube, TikTok and the rest)."
    return True, ""


def route(videos, platforms):
    """{platform: [video paths]}: tall videos (…_9x16, …_4x5) go to the platforms that want tall ones, wide ones (…_16x9) to those that want wide
    ones, YouTube gets both. A platform with no fitting video gets whatever there is (a square or the only shape made)."""
    def shape(path):
        name = os.path.basename(path).lower()
        return "tall" if ("9x16" in name or "4x5" in name) else ("wide" if "16x9" in name else "other")
    tall = [v for v in videos if shape(v) == "tall"]
    wide = [v for v in videos if shape(v) == "wide"]
    other = [v for v in videos if shape(v) == "other"]
    out = {}
    for p in platforms:
        if p in PORTRAIT_PLATFORMS:
            pick = tall or other or wide
        elif p in LANDSCAPE_PLATFORMS:
            pick = wide or other or tall
        else:
            pick = tall + wide + other
        if pick:
            out[p] = list(pick)
    return out


def write_metadata(folder, videos, title, description, tags=None):
    """publish_metadata.json in `folder` for engine.publish: [{file, title, description, tags}] with the file names relative to the folder."""
    items = [{"file": os.path.relpath(v, folder).replace("\\", "/"), "title": title, "description": description, "tags": list(tags or [])} for v in videos]
    path = os.path.join(folder, "publish_metadata.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=1, ensure_ascii=False)
    return path


def publish_videos(folder, videos, title, description, platforms, dry_run=False, publisher=None, env_path=None, environ=None):
    """Publish videos (paths inside `folder`) to platforms, routing each shape to the platforms that want it. Returns (ok, [message lines]).
    `publisher(metadata_path, [platform], dry_run)` replaces engine.publish.publish_all (tests)."""
    if not platforms:
        return False, ["Choose at least one platform."]
    if not dry_run and env_path is not None:
        ok, why = publish_ready(env_path, environ)
        if not ok:
            return False, [why]
    routed = route(videos, platforms)
    if not routed:
        return False, ["There is no video to publish."]
    if publisher is None:
        from engine import publish

        def publisher(meta, plats, dry):
            return publish.publish_all(meta, plats, dry_run=dry)
    lines, all_ok = [], True
    # one request per set of identical video lists, so a video is sent once to all the platforms that take it
    groups = {}
    for plat, vids in routed.items():
        groups.setdefault(tuple(vids), []).append(plat)
    for vids, plats in groups.items():
        meta = write_metadata(folder, list(vids), title, description)
        try:
            results = publisher(meta, plats, dry_run)
        except SystemExit as e:                  # engine.publish exits with its message when a key is missing
            return False, [str(e)]
        except Exception as e:
            return False, [f"Upload failed: {str(e)[:160]}"]
        for r in results:
            good = bool(r.get("ok"))
            all_ok = all_ok and good
            name = os.path.basename(str(r.get("file", "")))
            mark = "✅" if good else "❌"
            lines.append(f"{mark} {name} → {', '.join(plats)}" + (" (preview only, nothing sent)" if r.get("dry_run") else "")
                         + ("" if good else f": {r.get('error') or r.get('response') or 'failed'}"))
    return all_ok, lines


def _case_title(folder):
    """(title, description) of a case run: the script's title and the first sentences of its first section."""
    try:
        with open(os.path.join(folder, "script.json"), encoding="utf-8") as f:
            script = json.load(f)
        title = str(script.get("title") or "").strip()
        sentences = re.split(r"(?<=[.!?])\s+", str((script.get("sections") or [{}])[0].get("narration") or "").strip())
        return title or os.path.basename(folder), " ".join(sentences[:2])[:280]
    except (OSError, ValueError, AttributeError, IndexError):
        return os.path.basename(folder), ""


def list_runs(root, limit=15):
    """[(label, folder, kind)] of finished runs that can be published, newest first: kind "case" (case_*.mp4 videos) or "clips" (a metadata.json
    next to the clips)."""
    import glob
    import time
    found = []
    for folder in glob.glob(os.path.join(root, "sessions", "*")):
        if not os.path.isdir(folder):
            continue
        videos = [p for p in glob.glob(os.path.join(folder, "case_*.mp4")) if "draft" not in os.path.basename(p)]
        meta = os.path.join(folder, "metadata.json")
        if videos:
            kind, newest, name = "case", max(os.path.getmtime(p) for p in videos), _case_title(folder)[0]
        elif os.path.isfile(meta):
            kind, newest, name = "clips", os.path.getmtime(meta), os.path.basename(folder)
        else:
            continue
        found.append((newest, f"{name} ({time.strftime('%d %b %H:%M', time.localtime(newest))}, {kind})", folder, kind))
    found.sort(reverse=True)
    return [(label, folder, kind) for _, label, folder, kind in found[:limit]]


PUBLISHED_FILE = "published.json"


def published_to(folder):
    """{platform: "date time"} of where a run folder was already published."""
    try:
        with open(os.path.join(folder, PUBLISHED_FILE), encoding="utf-8") as f:
            data = json.load(f)
        return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def record_published(folder, platforms):
    import time
    data = published_to(folder)
    stamp = time.strftime("%Y-%m-%d %H:%M")
    for p in platforms:
        data[p] = stamp
    with open(os.path.join(folder, PUBLISHED_FILE), "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1)


def publish_run(folder, kind, platforms, dry_run=False, publisher=None, env_path=None, environ=None, again=False):
    """Publish a finished run and remember where. A platform the run was already published to is refused unless `again` (so a re-render or a
    second click never posts twice)."""
    if not dry_run and not again:
        done = [p for p in platforms if p in published_to(folder)]
        if done:
            when = published_to(folder)[done[0]]
            return False, [f"Already published to {', '.join(done)} (on {when}). Tick \"publish again\" if you really want to post it once more."]
    ok, lines = _publish_run(folder, kind, platforms, dry_run, publisher, env_path, environ)
    if ok and not dry_run:
        record_published(folder, platforms)
    return ok, lines


def _publish_run(folder, kind, platforms, dry_run=False, publisher=None, env_path=None, environ=None):
    """Publish a finished run (see list_runs). Returns (ok, [message lines]). Case videos are routed by shape; clips all go to every platform."""
    if kind == "case":
        import glob
        videos = sorted(p for p in glob.glob(os.path.join(folder, "case_*.mp4")) if "draft" not in os.path.basename(p))
        title, description = _case_title(folder)
        return publish_videos(folder, videos, title, description, platforms, dry_run=dry_run, publisher=publisher, env_path=env_path, environ=environ)
    meta = os.path.join(folder, "metadata.json")
    if not os.path.isfile(meta):
        return False, ["This run has no clips to publish."]
    if not platforms:
        return False, ["Choose at least one platform."]
    if not dry_run and env_path is not None:
        ok, why = publish_ready(env_path, environ)
        if not ok:
            return False, [why]
    if publisher is None:
        from engine import publish

        def publisher(m, plats, dry):
            return publish.publish_all(m, plats, dry_run=dry)
    try:
        results = publisher(meta, list(platforms), dry_run)
    except SystemExit as e:
        return False, [str(e)]
    except Exception as e:
        return False, [f"Upload failed: {str(e)[:160]}"]
    lines = [("✅" if r.get("ok") else "❌") + f" {os.path.basename(str(r.get('file', '')))} → {', '.join(platforms)}"
             + (" (preview only, nothing sent)" if r.get("dry_run") else "") + ("" if r.get("ok") else f": {r.get('error') or r.get('response') or 'failed'}")
             for r in results]
    return bool(results) and all(r.get("ok") for r in results), lines or ["Nothing was published."]


def auto_publish(home, since, publisher=None, environ=None):
    """After a run: when auto-publish is on and set up, publish the newest run that finished after `since` (a time.time() value).
    Returns a list of message lines ([] when auto-publish is off or nothing new finished)."""
    prefs = load_prefs(home)
    if not prefs["auto_publish"] or not prefs["platforms"]:
        return []
    runs = [r for r in list_runs(home, limit=5) if _finished_after(r[1], r[2], since)]
    if not runs:
        return []
    _label, folder, kind = runs[0]
    todo = [p for p in prefs["platforms"] if p not in published_to(folder)]
    if not todo:
        return ["Auto-publish: this run was already published to " + ", ".join(prefs["platforms"]) + ", so nothing was sent."]
    ok, lines = publish_run(folder, kind, todo, publisher=publisher, env_path=os.path.join(home, ".env"), environ=environ)
    return ["Auto-publish:"] + lines


def _finished_after(folder, kind, since):
    import glob
    files = glob.glob(os.path.join(folder, "case_*.mp4")) if kind == "case" else [os.path.join(folder, "metadata.json")]
    return any(os.path.isfile(p) and os.path.getmtime(p) >= since for p in files)
