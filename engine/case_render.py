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


def plan_timing(durations, intro=2.5, pad=0.6):
    """[(start, end)] of every section: the first starts after the intro, each lasts its narration plus `pad` seconds of air."""
    out, t = [], float(intro)
    for d in durations:
        out.append((round(t, 3), round(t + float(d) + pad, 3)))
        t = out[-1][1]
    return out


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


def attach_clips(script, timing, session_dir, ask, scenes=("flow",), portrait=False, accent="#00e5a8", make=None, probe=None):
    """Manim animations for the sections whose scene kind is in `scenes`: [None | {"path", "rate"}] per section. `rate` is the
    playback speed that makes the clip last as long as its section (kept between 0.6 and 1.6). A section whose animation could not
    be made stays None and keeps its plain scene. `make` / `probe` replace case_manim.make_section_clip and the duration probe."""
    from engine import case_manim
    make = make or case_manim.make_section_clip
    probe = probe or _duration
    out = []
    for i, (sec, (start, end)) in enumerate(zip(script["sections"], timing), start=1):
        if sec.get("scene") not in scenes:
            out.append(None)
            continue
        folder = os.path.join(session_dir, f"manim_{i:02d}")
        path = make(sec, end - start, folder, ask, lambda code, d, p: case_manim.render_scene(code, d, p), topic=script.get("title", ""),
                    portrait=portrait, accent=accent)
        if not path:
            print(f"[Warning] No animation could be made for section '{sec['title']}'; the plain scene is used.")
            out.append(None)
            continue
        length = float(probe(path) or 0.0)
        rate = max(0.6, min(1.6, length / (end - start))) if length > 0 else 1.0
        out.append({"path": path, "rate": round(rate, 3)})
    return out


def build_props(script, timing, words_per_section, theme="dark", accent=None, intro=2.5, outro=3.0, audio_url=None, music_url=None,
                music_volume=0.12, captions=True, clips=None):
    """The CaseVideo props: sections with their times, every word shifted to where its section starts. `clips` (from attach_clips)
    puts a rendered animation on a section."""
    sections, words = [], []
    clips = clips or [None] * len(script["sections"])
    for sec, (start, end), ws, clip in zip(script["sections"], timing, words_per_section, clips):
        labels, cues = spoken_order(list(sec.get("on_screen") or []), ws, duration=end - start)
        sections.append({"title": sec["title"], "scene": sec["scene"], "labels": labels, "cues": cues, "start": start, "end": end})
        if clip:
            sections[-1]["clip"] = clip["path"]
            sections[-1]["clipRate"] = clip["rate"]
        words += [{"word": w["word"], "start": round(w["start"] + start, 3), "end": round(w["end"] + start, 3)} for w in ws]
    props = {"title": script["title"], "theme": theme, "introSeconds": intro, "outroSeconds": outro, "verified": bool(script.get("verified")),
             "sources": [s["ref"] for s in script.get("sources", [])], "captionsOff": not captions, "sections": sections, "words": words,
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
    for i, sec in enumerate(sections, start=1):
        audio = os.path.join(session_dir, f"voice_{i:02d}.mp3")
        subs = os.path.join(session_dir, f"subs_{i:02d}.json")
        result_audio = result_subs = None
        if provider == "elevenlabs" and generate_is_default and os.getenv("ELEVENLABS_API_KEY"):
            try:
                result_audio, result_subs = speak_elevenlabs(
                    sec["narration"], audio, subs, voice_id=voice,
                    previous_text=sections[i - 2]["narration"] if i > 1 else None,
                    next_text=sections[i]["narration"] if i < len(sections) else None)
            except Exception as e:
                print(f"[Warning] ElevenLabs narration failed for '{sec['title']}' ({str(e)[:120]}); using the general voice step.")
        if not result_audio:
            kwargs = {"output_audio": audio, "output_subs": subs, "add_cta": False}
            if provider:
                kwargs["provider"] = provider
            if voice and provider != "elevenlabs":
                kwargs["voice_name"] = voice
            if clone_voice:
                kwargs["clone_voice"] = clone_voice
            result_audio, result_subs = generate(sec["narration"], **kwargs)
        if not result_audio or not os.path.exists(result_audio):
            raise RuntimeError(f"No voice was produced for section '{sec['title']}'.")
        audios.append(result_audio)
        words.append(read_words(result_subs or subs))
    return audios, words


def join_audio(audios, timing, out_path):
    """One track: each section's audio placed at its start time (ffmpeg adelay + amix). Returns out_path."""
    cmd = [_ffmpeg(), "-y"]
    for a in audios:
        cmd += ["-i", a]
    delays = [f"[{i}:a]adelay={int(start * 1000)}|{int(start * 1000)}[a{i}]" for i, (start, _) in enumerate(timing)]
    mix = "".join(f"[a{i}]" for i in range(len(audios))) + f"amix=inputs={len(audios)}:normalize=0:duration=longest,loudnorm=I=-16:TP=-1.5:LRA=11[out]"
    cmd += ["-filter_complex", ";".join(delays + [mix]), "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", out_path]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0 or not os.path.exists(out_path):
        raise RuntimeError("Joining the voice pieces failed: " + (res.stderr or "")[-300:])
    return out_path


def render_case(props, audio_path, output_path, music_path=None, aspect="16:9"):
    """Render the CaseVideo composition to `output_path`. Returns the absolute path."""
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
        with open(props_path, "w", encoding="utf-8") as f:
            json.dump(props, f)
        end = max([s["end"] for s in props["sections"]] or [5.0]) + props["outroSeconds"]
        frames = max(30, int(end * FPS))
        width, height = SIZES.get(aspect, SIZES["16:9"])
        is_ci = os.getenv("CI") == "true" or os.getenv("GITHUB_ACTIONS") == "true"
        cmd = ["npx", "remotion", "render", "CaseVideo", render_output, f"--props={props_name}", f"--frames=0-{frames - 1}",
               f"--width={width}", f"--height={height}", "--codec=h264", *quality_flags(), "--pixel-format=yuv420p", "--gl=angle",
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
