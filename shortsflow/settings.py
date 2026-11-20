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
DEFAULT_PREFS = {"auto_publish": False, "platforms": [], "youtube_privacy": "private", "youtube_account": "1"}
DIRECT = "youtube_direct"          # a "platform" that goes straight to the person's own YouTube channel (their own Google app), not through Upload-Post
PRIVACY = ("private", "unlisted", "public")
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


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


def valid_platforms():
    from engine.publish import PLATFORMS
    return tuple(PLATFORMS) + (DIRECT,)


def clean_account(account):
    """The YouTube account slot ("1", "2", ...): letters and digits only, at most 8, "1" when empty."""
    return re.sub(r"[^A-Za-z0-9]", "", str(account or "1"))[:8] or "1"


def load_prefs(home):
    """The saved upload preferences, with defaults for anything missing or invalid."""
    prefs = dict(DEFAULT_PREFS)
    try:
        with open(prefs_path(home), encoding="utf-8") as f:
            data = json.load(f)
        prefs["auto_publish"] = bool(data.get("auto_publish", False))
        prefs["platforms"] = [p for p in (data.get("platforms") or []) if p in valid_platforms()]
        prefs["youtube_privacy"] = data.get("youtube_privacy") if data.get("youtube_privacy") in PRIVACY else "private"
        prefs["youtube_account"] = clean_account(data.get("youtube_account"))
    except (OSError, ValueError, AttributeError):
        pass
    return prefs


def save_prefs(home, auto_publish, platforms, youtube_privacy=None, youtube_account=None):
    """Save the upload preferences (a YouTube setting left as None keeps its saved value). Returns the saved dict."""
    before = load_prefs(home)
    prefs = {"auto_publish": bool(auto_publish), "platforms": [p for p in (platforms or []) if p in valid_platforms()],
             "youtube_privacy": youtube_privacy if youtube_privacy in PRIVACY else before["youtube_privacy"],
             "youtube_account": clean_account(youtube_account) if youtube_account is not None else before["youtube_account"]}
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


def publish_run(folder, kind, platforms, dry_run=False, publisher=None, env_path=None, environ=None, again=False, direct=None):
    """Publish a finished run and remember where. A platform the run was already published to is refused unless `again` (so a re-render or a
    second click never posts twice). The platforms that go through Upload-Post and the direct YouTube route are sent separately; `direct` is
    {"home", "privacy", "account", "uploader"} for the latter."""
    if not platforms:
        return False, ["Choose at least one platform."]
    if not dry_run and not again:
        done = [p for p in platforms if p in published_to(folder)]
        if done:
            when = published_to(folder)[done[0]]
            return False, [f"Already published to {', '.join(done)} (on {when}). Tick \"publish again\" if you really want to post it once more."]
    parts = []
    others = [p for p in platforms if p != DIRECT]
    if others:
        ok, lines = _publish_run(folder, kind, others, dry_run, publisher, env_path, environ)
        parts.append((others, ok, lines))
    if DIRECT in platforms:
        d = direct or {}
        ok, lines = publish_direct(folder, kind, d.get("privacy", "private"), d.get("account", "1"), d.get("home"), dry_run=dry_run, uploader=d.get("uploader"))
        parts.append(([DIRECT], ok, lines))
    all_ok, all_lines = True, []
    for plats, ok, lines in parts:
        all_ok = all_ok and ok
        all_lines += lines
        if ok and not dry_run:
            record_published(folder, plats)               # only what really went out is remembered
    return all_ok, all_lines


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
    direct = {"home": home, "privacy": prefs["youtube_privacy"], "account": prefs["youtube_account"]}
    ok, lines = publish_run(folder, kind, todo, publisher=publisher, env_path=os.path.join(home, ".env"), environ=environ, direct=direct)
    return ["Auto-publish:"] + lines


def _finished_after(folder, kind, since):
    import glob
    files = glob.glob(os.path.join(folder, "case_*.mp4")) if kind == "case" else [os.path.join(folder, "metadata.json")]
    return any(os.path.isfile(p) and os.path.getmtime(p) >= since for p in files)


# ---- YouTube, direct to the person's own channel (their own Google OAuth client; nothing goes through a third party)
def youtube_paths(home, account="1"):
    """(client secrets file, token file) of an account slot, the same names engine.social_gen.YouTubeUploader uses ("client_secrets.json" /
    "token.json" for account 1, "client_secrets_2.json" / "token_2.json" for account 2)."""
    acc = clean_account(account)
    suffix = "" if acc == "1" else "_" + acc.lower()
    return os.path.join(home, f"client_secrets{suffix}.json"), os.path.join(home, f"token{suffix}.json")


def _token_ok(path):
    """True when the saved sign-in can be used or refreshed (never opens a browser)."""
    try:
        from google.oauth2.credentials import Credentials
        creds = Credentials.from_authorized_user_file(path, YOUTUBE_SCOPES)
        return bool(creds.valid or creds.refresh_token)
    except Exception:
        return False


def youtube_status(home, account="1"):
    """{"secrets": the Google client file is saved, "connected": a usable sign-in is saved}."""
    secrets, token = youtube_paths(home, account)
    return {"secrets": os.path.isfile(secrets), "connected": os.path.isfile(token) and _token_ok(token)}


def youtube_status_markdown(home, account="1"):
    st = youtube_status(home, account)
    return (f"**Account {clean_account(account)}:** client file " + ("✅ saved" if st["secrets"] else "❌ not added yet") + " · sign-in "
            + ("✅ connected" if st["connected"] else "❌ not connected"))


def save_client_secrets(home, account, raw):
    """Save the Google OAuth client file of an account slot. `raw` is its text or bytes. Returns (ok, message)."""
    try:
        text = raw.decode("utf-8-sig") if isinstance(raw, (bytes, bytearray)) else str(raw or "")
        data = json.loads(text)
    except (ValueError, UnicodeDecodeError):
        return False, "That is not a valid JSON file. Download the OAuth client file again from Google Cloud Console."
    section = data.get("installed") if isinstance(data, dict) else None
    if isinstance(data, dict) and not section and isinstance(data.get("web"), dict):
        return False, "This is a Web client. Create the OAuth client ID again with the type **Desktop app**, and download that file."
    if not isinstance(section, dict) or not section.get("client_id") or not section.get("client_secret"):
        return False, "This does not look like a Google OAuth client file (a Desktop app client with client_id and client_secret)."
    secrets, _ = youtube_paths(home, account)
    with open(secrets, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=1)
    return True, "Client file saved. Now press Connect YouTube."


def connect_youtube(home, account, run_flow=None):
    """Sign in once: opens the browser on this PC for the Google sign-in and saves the token. `run_flow(secrets_path)` returns the credentials as
    JSON text and replaces the real sign-in (tests). Returns (ok, message)."""
    secrets, token = youtube_paths(home, account)
    if not os.path.isfile(secrets):
        return False, "Add the Google client file first."
    if run_flow is None:
        def run_flow(path):
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(path, YOUTUBE_SCOPES)
            return flow.run_local_server(port=0, timeout_seconds=300).to_json()
    try:
        creds_json = run_flow(secrets)
    except Exception as e:
        return False, f"The sign-in did not finish ({' '.join(str(e).split())[:120]}). Press Connect YouTube to try again."
    with open(token, "w", encoding="utf-8", newline="\n") as f:
        f.write(creds_json)
    return True, "Connected. Videos can now be published to this channel."


def disconnect_youtube(home, account):
    """Forget the saved sign-in of an account slot (the client file stays). Returns (ok, message)."""
    _, token = youtube_paths(home, account)
    if not os.path.isfile(token):
        return False, "This account was not connected."
    os.remove(token)
    return True, "Disconnected. The client file is kept."


def publish_direct(folder, kind, privacy, account, home, dry_run=False, uploader=None):
    """Upload a finished run to the person's own YouTube channel. A case video goes up once (the tall version when there is one, as a Short), a
    set of clips goes up clip by clip. `uploader` replaces engine.social_gen.YouTubeUploader (tests). Returns (ok, [message lines])."""
    import glob
    from engine.platform_limits import LIMITS, truncate_words
    privacy = privacy if privacy in PRIVACY else "private"
    items = []                                              # (path, title, description, tags)
    if kind == "case":
        videos = sorted(p for p in glob.glob(os.path.join(folder, "case_*.mp4")) if "draft" not in os.path.basename(p))
        picked = route(videos, ["tiktok"]).get("tiktok") or []
        if not picked:
            return False, ["There is no video to upload."]
        title, description = _case_title(folder)
        tall = any(k in os.path.basename(picked[0]).lower() for k in ("9x16", "4x5"))
        items.append((picked[0], title, description + ("\n\n#Shorts" if tall else ""), []))
    else:
        meta = os.path.join(folder, "metadata.json")
        try:
            with open(meta, encoding="utf-8") as f:
                for it in json.load(f):
                    path = os.path.join(folder, it.get("file", ""))
                    if os.path.isfile(path):
                        items.append((path, it.get("title") or "New short", it.get("description") or "", list(it.get("tags") or [])))
        except (OSError, ValueError):
            return False, ["This run has no clips to upload."]
        if not items:
            return False, ["This run has no clips to upload."]
    if dry_run:
        return True, [f"✅ {os.path.basename(path)} → YouTube ({privacy}) as: {truncate_words(title, LIMITS['youtube']['title'])} (preview only, nothing sent)" for path, title, _d, _t in items]
    if home is None:
        return False, ["Settings need the app folder to find the saved YouTube sign-in."]
    secrets, token = youtube_paths(home, account)
    if not youtube_status(home, account)["connected"]:
        return False, ["YouTube is not connected: add the client file and press Connect YouTube in Settings first."]
    if uploader is None:
        from engine.social_gen import YouTubeUploader
        uploader = YouTubeUploader(secrets_file=secrets, token_file=token, account=clean_account(account))
    try:
        if not uploader.authenticate():
            return False, ["The saved YouTube sign-in no longer works: press Connect YouTube again."]
    except Exception as e:
        return False, [f"YouTube sign-in failed: {str(e)[:140]}"]
    lines, all_ok = [], True
    for path, title, description, tags in items:
        try:
            vid = uploader.upload_video(path, truncate_words(title, LIMITS["youtube"]["title"]), description, [str(t).lstrip("#") for t in tags][:15], privacy=privacy)
        except Exception as e:
            vid = None
            lines.append(f"❌ {os.path.basename(path)} → YouTube: {str(e)[:140]}")
            all_ok = False
            continue
        if vid:
            lines.append(f"✅ {os.path.basename(path)} → YouTube ({privacy}): https://youtu.be/{vid}")
        else:
            lines.append(f"❌ {os.path.basename(path)} → YouTube: the upload did not return a video id")
            all_ok = False
    return all_ok, lines
