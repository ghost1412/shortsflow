"""Case explainer, second half: voice for each section, one timed audio track, and the Remotion "CaseVideo" render.

`engine.case_study` writes the script; this turns it into a video: each section's narration is spoken (any provider `generate_voice`
knows: ElevenLabs, a cloned voice, Kokoro, Edge), the pieces are laid on one track after an intro, word timings follow, and the
CaseVideo composition draws one scene per section with captions. `plan_timing` and `build_props` are pure and tested offline.
"""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid

FPS = 30
SIZES = {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080), "4:5": (1080, 1350)}


def plan_timing(durations, intro=1.8, pad=0.5):
    """[(start, end)] of every section: the first starts after the intro, each lasts its narration plus `pad` seconds of air."""
    out, t = [], float(intro)
    for d in durations:
        out.append((round(t, 3), round(t + float(d) + pad, 3)))
        t = out[-1][1]
    return out


def beats_for(words, duration, min_len=3.5, max_len=6.5):
    """[[start, end]] seconds (after the section's audio starts) of the short beats a section is cut into: a beat ends at a sentence end
    once it is at least `min_len` long, or at the nearest pause or word before `max_len`; the last beat runs to `duration`. Each beat gets
    its own picture, so nothing stays on screen for a whole section."""
    duration = float(duration)
    if not words:
        count = max(1, round(duration / 6.5))
        return [[round(i * duration / count, 2), round((i + 1) * duration / count, 2)] for i in range(count)]
    beats, start = [], 0.0
    for i, w in enumerate(words):
        length = w["end"] - start
        nxt = words[i + 1]["start"] if i + 1 < len(words) else duration
        sentence_end = str(w["word"]).rstrip("\"')").endswith((".", "!", "?"))
        if (length >= min_len and sentence_end) or length >= max_len or (length >= min_len + 1.5 and nxt - w["end"] > 0.35):
            cut = round(min(w["end"] + 0.15, duration), 2)
            if duration - cut < 2.0:
                break                                        # too little left for a beat of its own: it joins this one
            beats.append([round(start, 2), cut])
            start = cut
    beats.append([round(start, 2), round(duration, 2)])
    return beats


def read_words(path):
    """[{word, start, end}] from a subs file written by generate_voice (a list of words, or segments holding words)."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return []
    raw = data if isinstance(data, list) else [w for seg in (data.get("segments") or []) for w in (seg.get("words") or [])]
    out = []
    for w in raw:
        try:
            start = float(w["start"])
            end = float(w["end"]) if "end" in w else start + float(w.get("duration", 0.4))
            out.append({"word": str(w["word"]).strip(), "start": start, "end": end})
        except (KeyError, TypeError, ValueError):
            continue
    return [w for w in out if w["word"]]


def label_cues(labels, words, duration=None, min_gap=0.8):
    """Seconds (after the section's audio starts) at which each on-screen label is spoken: the first word, searched in order,
    that matches a content word of the label (numbers match by digits). A label with no match follows the previous one by
    `min_gap` and a little more; cues never go backwards and stay inside `duration` when it is given."""
    import re
    keys = [re.sub(r"\W+", "", (w["word"] or "").lower()) for w in words]
    digits = [re.sub(r"\D", "", w["word"] or "") for w in words]
    cues, cursor, prev = [], 0, -min_gap
    for label in labels:
        tokens = [re.sub(r"\W+", "", x.lower()) for x in re.findall(r"[\w$.,]+", label)]
        tokens = [x for x in tokens if len(x) >= 4 or x.isdigit()]
        found = None
        for i in range(cursor, len(words)):
            if any(tok and ((tok.isdigit() and digits[i] == tok) or (not tok.isdigit() and keys[i] and (tok == keys[i] or tok[:5] == keys[i][:5] and len(keys[i]) >= 4)))
                   for tok in tokens):
                found = i
                break
        if found is not None:
            at = max(words[found]["start"] - 0.15, prev + 0.3, 0.2)
            cursor = found + 1
        else:
            at = prev + min_gap + 0.4
        if duration:
            at = min(at, max(0.2, duration - 0.5))
        cues.append(round(at, 2))
        prev = cues[-1]
    return cues


def _first_spoken(label, words):
    """Index of the first word that matches a content word of `label` (numbers match by digits), None when none does."""
    import re
    tokens = [re.sub(r"\W+", "", x.lower()) for x in re.findall(r"[\w$.,]+", label)]
    tokens = [x for x in tokens if len(x) >= 4 or x.isdigit()]
    for i, w in enumerate(words):
        key, digits = re.sub(r"\W+", "", (w["word"] or "").lower()), re.sub(r"\D", "", w["word"] or "")
        for tok in tokens:
            if tok and ((tok.isdigit() and digits == tok) or (not tok.isdigit() and key and (tok == key or (tok[:5] == key[:5] and len(key) >= 4)))):
                return i
    return None


ORDERED_SCENES = ("compare", "chart", "quote")      # their labels keep the order the script gave; the others follow the narration


def even_cues(count, duration, first=0.8, tail=2.5):
    """`count` appearance times spread evenly from `first` seconds to `tail` seconds before the end of a section (a timeline: its events
    come in the order of time and each one stays until the next arrives)."""
    if count <= 0:
        return []
    last = max(first, (duration or 0) - tail)
    if count == 1:
        return [round(first, 2)]
    return [round(first + (last - first) * i / (count - 1), 2) for i in range(count)]


def spoken_order(labels, words, duration=None, first_by=1.5, gap=0.8):
    """(labels, cues): the labels in the order the narrator reaches them, each with the second it is spoken. A label the narrator
    never says follows the last one. The first cue is at most `first_by` seconds in, so a scene is never empty while the narrator
    talks about something else first; cues are `gap` apart at least and stay inside `duration`."""
    found = [(_first_spoken(label, words), n, label) for n, label in enumerate(labels)]
    spoken = sorted([f for f in found if f[0] is not None], key=lambda f: (f[0], f[1]))
    silent = [f for f in found if f[0] is None]
    cues, ordered, prev = [], [], None
    for index, _, label in spoken + silent:
        at = words[index]["start"] - 0.15 if index is not None else (prev if prev is not None else 0.0) + gap + 0.4
        if prev is None:
            at = min(max(at, 0.2), first_by)
        else:
            at = max(at, prev + gap)
        if duration:
            at = min(at, max(0.2, duration - 0.5))
        cues.append(round(at, 2))
        ordered.append(label)
        prev = cues[-1]
    return ordered, cues


def clip_aspect(path, default=16 / 9):
    """Width / height of a clip, read from FFmpeg's description of the file (clips made before the wide panel are 16:9, newer ones 2.2);
    `default` when it cannot be read."""
    import re
    import shutil
    import subprocess
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        try:
            import imageio_ffmpeg
            ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return round(default, 3)
    try:
        res = subprocess.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        m = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", res.stderr or "")
        return round(int(m.group(1)) / int(m.group(2)), 3) if m and int(m.group(2)) else round(default, 3)
    except Exception:
        return round(default, 3)


def attach_clips(script, timing, session_dir, ask, scenes=("flow",), portrait=False, accent="#00e5a8", make=None, probe=None,
                 tag="", reuse=False, generate=True):
    """Manim animations for the sections whose scene kind is in `scenes`: [None | {"path", "rate"}] per section. `rate` is the
    playback speed that makes the clip last as long as its section (kept between 0.6 and 1.6). A section whose animation could not
    be made stays None and keeps its plain scene. `make` / `probe` replace case_manim.make_section_clip and the duration probe.
    `tag` (the video shape, e.g. "16x9") gives each shape its own folder, so one shape's animation does not overwrite the other's;
    `reuse` takes an animation already rendered in that folder; `generate=False` never asks the model for a new one."""
    from engine import case_manim
    make = make or case_manim.make_section_clip
    probe = probe or _duration
    out = []
    for i, (sec, (start, end)) in enumerate(zip(script["sections"], timing), start=1):
        if sec.get("scene") not in scenes:
            out.append(None)
            continue
        folder = os.path.join(session_dir, f"manim_{i:02d}" + (f"_{tag}" if tag else ""))
        path = case_manim.find_clip(folder) if reuse else None
        if not path and generate:
            whole = sec.get("scene") == "animation"        # the animation IS the picture: a full frame, not a panel
            path = make(sec, end - start, folder, ask, lambda code, d, p, check=True, whole=whole: case_manim.render_scene(code, d, p, full=whole, check=check),
                        topic=script.get("title", ""), portrait=portrait, accent=accent, **({"full": True} if whole else {}))
        if not path:
            if generate:
                print(f"[Warning] No animation could be made for section '{sec['title']}'; the plain scene is used.")
            out.append(None)
            continue
        length = float(probe(path) or 0.0)
        rate = max(0.6, min(1.6, length / (end - start))) if length > 0 else 1.0
        out.append({"path": path, "rate": round(rate, 3), "aspect": clip_aspect(path)})
    return out


def source_label(ref):
    """A short name for a source to show on screen: a link's host without "www.", a file's name, or "notes"."""
    import re
    ref = str(ref or "").strip()
    m = re.match(r"https?://(?:www\.)?([^/?#]+)", ref)
    if m:
        return m.group(1)[:40]
    return (os.path.basename(ref) or ref or "notes")[:40]


def build_props(script, timing, words_per_section, theme="dark", accent=None, intro=1.8, outro=2.5, audio_url=None, music_url=None,
                music_volume=0.12, captions=True, clips=None, footage=None):
    """The CaseVideo props: sections with their times, every word shifted to where its section starts. `clips` (from attach_clips)
    puts a rendered animation on a section."""
    sections, words = [], []
    clips = clips or [None] * len(script["sections"])
    footage = footage or [None] * len(script["sections"])
    for sec, (start, end), ws, clip, foot in zip(script["sections"], timing, words_per_section, clips, footage):
        labels, cues = list(sec.get("on_screen") or []), None
        if sec["scene"] == "timeline":                     # events in the order of time, whatever order the narrator mentions them in
            cues = even_cues(len(labels), end - start)
        elif sec["scene"] in ORDERED_SCENES:               # a heading row, a ranking or a main line: the authored order is part of the meaning
            cues = label_cues(labels, ws, duration=end - start)
            if cues:
                cues[0] = min(cues[0], 1.5)                # the first one does not wait for the narrator to reach it
        else:
            labels, cues = spoken_order(labels, ws, duration=end - start)
        sections.append({"title": sec["title"], "scene": sec["scene"], "labels": labels, "cues": cues, "start": start, "end": end})
        by_id = {s["id"]: s["ref"] for s in script.get("sources", [])}
        cited = [by_id[c] for c in sec.get("cites") or [] if c in by_id] or (list(by_id.values()) if script.get("verified") else [])
        sections[-1]["sourceLabels"] = list(dict.fromkeys(source_label(r) for r in cited))[:2]
        if clip:
            sections[-1]["clip"] = clip["path"]
            sections[-1]["clipRate"] = clip["rate"]
            sections[-1]["clipAspect"] = clip.get("aspect") or round(16 / 9, 3)
        sections[-1]["beats"] = beats_for(ws, end - start)
        if foot:
            sections[-1]["footage"] = [{"src": f["path"], "seconds": f.get("seconds") or 10.0, "kind": f.get("kind", "video")} for f in foot]
        words += [{"word": w["word"], "start": round(w["start"] + start, 3), "end": round(w["end"] + start, 3)} for w in ws]
    props = {"title": script["title"], "hook": str(script.get("hook") or ""), "theme": theme, "introSeconds": intro, "outroSeconds": outro, "verified": bool(script.get("verified")),
             "sources": [source_label(s["ref"]) for s in script.get("sources", [])], "removedClaims": len(script.get("dropped") or []),
             "captionsOff": not captions, "sections": sections, "words": words,
             "bgMusicVolume": music_volume}
    if accent:
        props["accent"] = accent
    if audio_url:
        props["audioUrl"] = audio_url
    if music_url:
        props["bgMusicUrl"] = music_url
    return props


def _duration(path):
    from engine.remotion_renderer import _probe_duration
    return float(_probe_duration(path) or 0.0)


def _ffmpeg():
    return shutil.which("ffmpeg") or __import__("imageio_ffmpeg").get_ffmpeg_exe()


# A calm, authoritative narrator and the more natural of the two ElevenLabs models. Both can be changed with the environment.
DEFAULT_VOICE_ID = "onwK4e9ZLuTAKqWW03F9"      # premade "Daniel": steady British broadcaster
DEFAULT_VOICE_MODEL = "eleven_multilingual_v2"
VOICE_SETTINGS = {"stability": 0.42, "similarity_boost": 0.8, "style": 0.3, "use_speaker_boost": True}


def prepare_speech(text):
    """Narration as it should be spoken: no brackets, footnote marks or short asides in parentheses, 'e.g.' written out, one space
    between words. Words stay as written, because the captions show the same words the voice timings come from."""
    import re
    text = re.sub(r"\[[^\]]*\]", "", str(text or ""))
    text = re.sub(r"\s*\([^)]{0,40}\)", "", text)
    for short, spoken in (("e.g.", "for example"), ("i.e.", "that is")):
        text = text.replace(short, spoken)
    return " ".join(text.split())


def words_from_alignment(alignment):
    """[{word, start, end}] from an ElevenLabs character alignment (characters + start/end seconds per character)."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    words, cur, w_start, w_end = [], "", None, None
    for ch, a, b in zip(chars, starts, ends):
        if ch.isspace():
            if cur:
                words.append({"word": cur, "start": round(w_start, 3), "end": round(max(w_end, w_start + 0.05), 3)})
            cur, w_start = "", None
        else:
            if w_start is None:
                w_start = a
            cur += ch
            w_end = b
    if cur:
        words.append({"word": cur, "start": round(w_start, 3), "end": round(max(w_end, w_start + 0.05), 3)})
    return words


def speak_elevenlabs(text, audio, subs, voice_id=None, model=None, previous_text=None, next_text=None, api_key=None, post=None):
    """One section's narration through ElevenLabs with word timings, tuned for a narrator (livelier settings, and the sentences
    before and after are passed so the delivery carries over between sections). Returns (audio, subs). `post` replaces requests.post."""
    import base64
    if post is None:
        import requests
        post = requests.post
    api_key = api_key or os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY is not set")
    voice_id = voice_id or os.getenv("CASE_VOICE_ID") or DEFAULT_VOICE_ID
    payload = {"text": prepare_speech(text), "model_id": model or os.getenv("CASE_VOICE_MODEL") or DEFAULT_VOICE_MODEL,
               "voice_settings": VOICE_SETTINGS}
    if previous_text:
        payload["previous_text"] = prepare_speech(previous_text)[-400:]
    if next_text:
        payload["next_text"] = prepare_speech(next_text)[:400]
    r = post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps",
             headers={"xi-api-key": api_key, "Content-Type": "application/json"}, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    with open(audio, "wb") as f:
        f.write(base64.b64decode(data["audio_base64"]))
    with open(subs, "w", encoding="utf-8") as f:
        json.dump(words_from_alignment(data.get("alignment") or {}), f)
    return audio, subs


def speak_sections(script, session_dir, provider=None, voice=None, clone_voice=None, generate=None):
    """Speak every section. Returns ([audio paths], [word lists]). `generate` replaces engine.voice_gen.generate_voice (tests)."""
    generate_is_default = generate is None
    if generate is None:
        from engine.voice_gen import generate_voice as generate
    audios, words = [], []
    sections = script["sections"]
    eleven_failed = False        # after one failure (no credits left, a bad key) the rest of the run goes straight to the fallback voice
    for i, sec in enumerate(sections, start=1):
        audio = os.path.join(session_dir, f"voice_{i:02d}.mp3")
        subs = os.path.join(session_dir, f"subs_{i:02d}.json")
        result_audio = result_subs = None
        if provider == "elevenlabs" and generate_is_default and os.getenv("ELEVENLABS_API_KEY") and not eleven_failed:
            try:
                result_audio, result_subs = speak_elevenlabs(
                    sec["narration"], audio, subs, voice_id=voice,
                    previous_text=sections[i - 2]["narration"] if i > 1 else None,
                    next_text=sections[i]["narration"] if i < len(sections) else None)
            except Exception as e:
                eleven_failed = True
                print(f"[Warning] ElevenLabs narration failed for '{sec['title']}' ({str(e)[:120]}); the rest of this video uses the Edge voice.")
        if not result_audio:
            kwargs = {"output_audio": audio, "output_subs": subs, "add_cta": False}
            fallback = provider == "elevenlabs" and generate_is_default
            if provider and not (fallback and eleven_failed):
                kwargs["provider"] = provider
            elif fallback and eleven_failed:
                kwargs["provider"] = "edgetts"
            if voice and provider != "elevenlabs":
                kwargs["voice_name"] = voice
            if clone_voice:
                kwargs["clone_voice"] = clone_voice
            result_audio, result_subs = generate(sec["narration"], **kwargs)
        if not result_audio or not os.path.exists(result_audio):
            raise RuntimeError(f"No voice was produced for section '{sec['title']}'.")
        audios.append(result_audio)
        words.append(read_words(result_subs or subs))
    try:
        with open(os.path.join(session_dir, "voice_cache.json"), "w", encoding="utf-8") as f:
            json.dump({"narration": _narration_hashes(script)}, f)
    except OSError:
        pass
    return audios, words


def join_audio(audios, timing, out_path, sfx=None):
    """One track: each section's audio placed at its start time (ffmpeg adelay + amix), level-matched; the sound-effects wav `sfx`,
    when given, is mixed in after that so it stays under the voice. Returns out_path."""
    cmd = [_ffmpeg(), "-y"]
    for a in audios:
        cmd += ["-i", a]
    if sfx:
        cmd += ["-i", sfx]
    delays = [f"[{i}:a]adelay={int(start * 1000)}|{int(start * 1000)}[a{i}]" for i, (start, _) in enumerate(timing)]
    voices = "".join(f"[a{i}]" for i in range(len(audios))) + f"amix=inputs={len(audios)}:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=11"
    if sfx:
        graph = delays + [voices + "[v]", f"[v][{len(audios)}:a]amix=inputs=2:normalize=0:duration=first[out]"]
    else:
        graph = delays + [voices + "[out]"]
    cmd += ["-filter_complex", ";".join(graph), "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", out_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("Joining the voice pieces failed: " + (res.stderr or "")[-300:])
    return out_path


def attach_footage(script, session_dir, aspect="16:9", fetch=None, cache_dir=None):
    """[None | [{"path", "seconds"}]] per section: a stock clip for each of the section's `footage` phrases, one per beat
    (see engine.case_footage); a phrase with no result is skipped."""
    from engine import case_footage
    fetch = fetch or case_footage.fetch
    cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".shortsflow", "footage")
    orientation = "portrait" if aspect == "9:16" else "landscape"
    out = []
    for sec in script["sections"]:
        phrases = sec.get("footage") or []
        phrases = [phrases] if isinstance(phrases, str) else phrases
        found = []
        for phrase in phrases:
            got = fetch(phrase, cache_dir, orientation) if phrase else None
            if got and all(got[0] != f["path"] for f in found):
                found.append({"path": got[0], "seconds": got[1]})
        out.append(found or None)
    return out


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
VIDEO_EXTS = (".mp4", ".mov", ".webm", ".mkv", ".m4v")


def attach_images(script, session_dir, aspect="16:9", fetch=None, cache_dir=None):
    """[None | [{"path", "kind": "image"}]] per section: a stock photo for each of the section's `footage` phrases, one per beat."""
    from engine import case_footage
    fetch = fetch or case_footage.fetch_image
    cache_dir = cache_dir or os.path.join(os.path.expanduser("~"), ".shortsflow", "photos")
    orientation = "portrait" if aspect == "9:16" else "landscape"
    out = []
    for sec in script["sections"]:
        phrases = sec.get("footage") or []
        phrases = [phrases] if isinstance(phrases, str) else phrases
        found = []
        for phrase in phrases:
            got = fetch(phrase, cache_dir, orientation) if phrase else None
            if got and all(got != f["path"] for f in found):
                found.append({"path": got, "kind": "image"})
        out.append(found or None)
    return out


def user_background(script, path, probe=None):
    """The same background for every section: the user's own image or video. Returns the per-section list, or None when `path` is not
    a readable image or video file."""
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        item = {"path": path, "kind": "image"}
    elif ext in VIDEO_EXTS:
        item = {"path": path, "seconds": float((probe or _duration)(path) or 10.0), "kind": "video"}
    else:
        return None
    return [[dict(item)] for _ in script["sections"]]


def backgrounds_for(script, session_dir, aspect, choice="footage", has_pexels=True):
    """Per-section backgrounds for the `--case_background` choice: "footage" (stock video, needs the Pexels key), "images" (stock photos,
    needs the key), "none" (the style's own animated background only), or the path of the user's own image or video."""
    choice = (choice or "footage").strip()
    if choice == "none":
        return None
    if choice == "footage":
        return attach_footage(script, session_dir, aspect) if has_pexels else None
    if choice == "images":
        return attach_images(script, session_dir, aspect) if has_pexels else None
    own = user_background(script, choice.strip('"'))
    if own is None:
        print(f"[Warning] --case_background '{choice}' is not an image or video file; using the style's own background.")
    return own


def sfx_for(props, path):
    """Write the sound-effects wav for a props dict: a whoosh at each section start, a pop at each label cue."""
    from engine import case_sfx
    starts = [s["start"] for s in props["sections"]]
    labels = [s["start"] + c for s in props["sections"] for c in s.get("cues", [])]
    total = max([s["end"] for s in props["sections"]] or [5.0])
    return case_sfx.build_track(path, total, starts, labels)


def _narration_hashes(script):
    import hashlib
    return [hashlib.sha1(str(s.get("narration", "")).encode("utf-8")).hexdigest()[:12] for s in script["sections"]]


def cached_voice(script, session_dir):
    """([audio paths], [word lists]) of a session whose narration was already made (voice_NN.mp3 and subs_NN.json for every section),
    None when any piece is missing, has no words, or was spoken from a narration that has since been edited."""
    try:
        with open(os.path.join(session_dir, "voice_cache.json"), encoding="utf-8") as f:
            if json.load(f).get("narration") != _narration_hashes(script):
                return None
    except (OSError, ValueError, AttributeError):
        pass                                          # a session from before the check: the files are taken as they are
    audios, words = [], []
    for i in range(1, len(script["sections"]) + 1):
        audio, subs = os.path.join(session_dir, f"voice_{i:02d}.mp3"), os.path.join(session_dir, f"subs_{i:02d}.json")
        if not (os.path.isfile(audio) and os.path.isfile(subs)):
            return None
        ws = read_words(subs)
        if not ws:
            return None
        audios.append(audio)
        words.append(ws)
    return audios, words


def render_case(props, audio_path, output_path, music_path=None, aspect="16:9", scale=1.0):
    """Render the CaseVideo composition to `output_path`. Returns the absolute path. `scale` below 1 renders a smaller, much faster draft."""
    from engine.paths import project_root
    from engine.remotion_renderer import concurrency_flag, copy_to_public, quality_flags
    remotion_dir = os.path.join(project_root(), "remotion-video")
    run_id = f"run_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    assets = os.path.join(remotion_dir, "public", "temp_assets", run_id)
    os.makedirs(assets, exist_ok=True)
    props_name = f"temp_props_{run_id}.json"
    props_path = os.path.join(remotion_dir, props_name)
    render_output = os.path.join(remotion_dir, f"out_{run_id}.mp4")
    try:
        props = dict(props)
        props["audioUrl"] = copy_to_public(audio_path, assets)
        if music_path:
            props["bgMusicUrl"] = copy_to_public(music_path, assets)
        props["sections"] = [dict(s) for s in props["sections"]]
        for s in props["sections"]:
            if s.get("clip"):
                s["clip"] = copy_to_public(s["clip"], assets) or None
                if not s["clip"]:
                    s.pop("clip")
            if s.get("footage"):
                kept = []
                for f in s["footage"]:
                    rel = copy_to_public(f["src"], assets)
                    if rel:
                        kept.append({"src": rel, "seconds": f["seconds"], "kind": f.get("kind", "video")})
                if kept:
                    s["footage"] = kept
                else:
                    s.pop("footage")
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f)
        end = max([s["end"] for s in props["sections"]] or [5.0]) + props["outroSeconds"]
        frames = max(30, int(end * FPS))
        width, height = SIZES.get(aspect, SIZES["16:9"])
        is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
        cmd = ["npx", "remotion", "render", "CaseVideo", render_output, f"--props={props_name}", f"--frames=0-{frames - 1}",
               f"--width={width}", f"--height={height}", *([f"--scale={scale}"] if scale and scale != 1 else []), "--codec=h264", *quality_flags(), "--pixel-format=yuv420p", "--gl=angle",
               "--chromium-options=--no-sandbox --disable-dev-shm-usage", "--timeout=180000", concurrency_flag(False, is_ci)]
        is_win = sys.platform == "win32"
        proc = subprocess.Popen(" ".join(cmd) if is_win else cmd, cwd=remotion_dir, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, shell=is_win, bufsize=1)
        lines = []
        for line in proc.stdout or []:
            lines.append(line)
            sys.stdout.write(line)
        proc.wait()
        if proc.returncode != 0 or not os.path.exists(render_output):
            raise RuntimeError(f"Remotion render failed ({proc.returncode}): {''.join(lines)[-300:]}")
        out = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            os.remove(out)
        shutil.move(render_output, out)
        return out
    finally:
        shutil.rmtree(assets, ignore_errors=True)
        for p in (props_path, render_output):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
