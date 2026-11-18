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


def build_props(script, timing, words_per_section, theme="dark", accent=None, intro=2.5, outro=3.0, audio_url=None, music_url=None,
                music_volume=0.12, captions=True):
    """The CaseVideo props: sections with their times, every word shifted to where its section starts."""
    sections, words = [], []
    for sec, (start, end), ws in zip(script["sections"], timing, words_per_section):
        labels = list(sec.get("on_screen") or [])
        sections.append({"title": sec["title"], "scene": sec["scene"], "labels": labels,
                         "cues": label_cues(labels, ws, duration=end - start), "start": start, "end": end})
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


def speak_sections(script, session_dir, provider=None, voice=None, clone_voice=None, generate=None):
    """Speak every section. Returns ([audio paths], [word lists]). `generate` replaces engine.voice_gen.generate_voice (tests)."""
    if generate is None:
        from engine.voice_gen import generate_voice as generate
    audios, words = [], []
    for i, sec in enumerate(script["sections"], start=1):
        audio = os.path.join(session_dir, f"voice_{i:02d}.mp3")
        subs = os.path.join(session_dir, f"subs_{i:02d}.json")
        kwargs = {"output_audio": audio, "output_subs": subs, "add_cta": False}
        if provider:
            kwargs["provider"] = provider
        if voice:
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
    mix = "".join(f"[a{i}]" for i in range(len(audios))) + f"amix=inputs={len(audios)}:normalize=0:duration=longest[out]"
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
