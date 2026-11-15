"""Style cloning: measure a reference reel and turn what is measured into a saved template.

    python main.py --clone_style reference.mp4 --save_as my-style
    python -m engine.style_clone reference.mp4 my-style

What is measured (all on this PC, the reference is only read, never changed):

* the pace: how long a shot lasts on average (scene cuts found with FFmpeg), how long the first shot is;
* the colour: brightness, contrast, colourfulness and cast of a few frames (the same measurements as --enhance auto);
* the sound: how loud the reference is.

What is *inferred* (a guess from the pace, said so in the summary): the cutting of pauses and fillers, punch-in zooms, b-roll and the
sound effects on cuts. What is NOT detected: the caption font and animation, graphics, logos and the music track. The caption style
is whatever you pass in (default HORMOZI). The result is an ordinary template (see engine/auto_edit.py): it shows in the Auto-edit list
and works as `--auto_edit NAME`. It is a close match in rhythm and look, not a copy: nothing of the reference's footage, music or
graphics is reused.
"""
import os
import re
import subprocess

MAX_ANALYSED = 120.0          # seconds of the reference that are read (the opening is enough to tell the pace)
CUT_THRESHOLD = 0.30          # FFmpeg scene score above which a frame counts as a cut


def _ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def _run_info(video, ffmpeg=None, run=subprocess.run, extra=None, limit=None):
    cmd = [ffmpeg or _ffmpeg(), "-hide_banner", "-nostats"]
    if limit:
        cmd += ["-t", f"{limit:.0f}"]
    cmd += ["-i", video] + (extra or [])
    return run(cmd, capture_output=True, text=True, errors="replace").stderr or ""


def probe(video, ffmpeg=None, run=subprocess.run):
    """{"duration", "width", "height"} of the video (None for what cannot be read)."""
    text = _run_info(video, ffmpeg, run)
    m = re.search(r"Duration: (\d+):(\d+):([\d.]+)", text)
    duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    size = re.search(r"Video:.*?,\s*(\d{2,5})x(\d{2,5})", text)
    return {"duration": duration, "width": int(size.group(1)) if size else None, "height": int(size.group(2)) if size else None}


def scene_cuts(video, duration, ffmpeg=None, run=subprocess.run, threshold=CUT_THRESHOLD):
    """Times (seconds) of the cuts in the first MAX_ANALYSED seconds of the video."""
    limit = min(duration or MAX_ANALYSED, MAX_ANALYSED)
    text = _run_info(video, ffmpeg, run, ["-vf", f"scale=320:-2,select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"], limit)
    return sorted({round(float(t), 2) for t in re.findall(r"pts_time:([\d.]+)", text)})


def loudness(video, ffmpeg=None, run=subprocess.run, limit=60.0):
    """(mean dB, peak dB) of the sound, or (None, None) when the video has no sound."""
    text = _run_info(video, ffmpeg, run, ["-vn", "-af", "volumedetect", "-f", "null", "-"], limit)
    mean = re.search(r"mean_volume: (-?[\d.]+) dB", text)
    peak = re.search(r"max_volume: (-?[\d.]+) dB", text)
    return (float(mean.group(1)) if mean else None, float(peak.group(1)) if peak else None)


def analyse(video, ffmpeg=None, run=subprocess.run, frames=None):
    """The measurements of a reference reel (see the module text). `frames` can be given for tests."""
    info = probe(video, ffmpeg, run)
    seen = min(info["duration"] or MAX_ANALYSED, MAX_ANALYSED)
    cuts = [c for c in scene_cuts(video, info["duration"], ffmpeg, run) if 0.2 < c < seen]
    shots = len(cuts) + 1
    from engine import enhance
    if frames is None:
        frames = enhance.sample_frames(video, ffmpeg=ffmpeg, n=8, run=run)
    colour = enhance.measure(frames)
    mean_db, peak_db = loudness(video, ffmpeg, run)
    return {"duration": info["duration"], "width": info["width"], "height": info["height"], "analysed_seconds": seen, "cuts": len(cuts),
            "shot_seconds": seen / shots, "first_shot_seconds": cuts[0] if cuts else seen, "colour": colour,
            "mean_db": mean_db, "peak_db": peak_db}


def pace_label(shot_seconds):
    return "fast" if shot_seconds < 2.5 else "medium" if shot_seconds < 4.5 else "slow"


def grade_for(colour):
    """(grade name or None, reason) from the colour statistics: only a clear look is copied, otherwise the picture is left natural."""
    if not colour:
        return None, "the colour could not be measured, so no colour look is added"
    avg = max(1e-6, (colour["r"] + colour["g"] + colour["b"]) / 3.0)
    warm, cold = colour["r"] / avg - 1.0, colour["b"] / avg - 1.0
    spread = colour["p99"] - colour["p1"]
    if colour["p50"] < 0.28:
        return "moody_dark", "the picture is dark"
    if colour["sat"] > 0.45:
        return "vibrant_action", "the colours are very strong"
    if warm > 0.08 and cold < -0.04:
        return "cinematic_warm", "the picture leans warm (orange)"
    if cold > 0.08 and warm < -0.04:
        return "cold_thriller", "the picture leans cold (blue)"
    if spread > 0.9 and colour["sat"] > 0.35:
        return "hdr_pop", "high contrast with strong colour"
    return None, "the colour is natural, so no colour look is added"


def to_template(m, caption_style="HORMOZI"):
    """(template dict, [plain-language lines]) for the measurements. The lines say what was measured and what was only inferred."""
    shot = m["shot_seconds"]
    pace = pace_label(shot)
    lines = [f"Pace: {pace}, about {shot:.1f} s per shot ({m['cuts']} cut(s) in the first {m['analysed_seconds']:.0f} s)."]
    tpl = {"caption_style": caption_style, "tighten": shot < 6.0, "remove_fillers": shot < 2.5, "clean_audio": True,
           "auto_zoom": shot >= 3.0, "broll": shot < 3.0, "caption_emoji": False, "hook_overlay": False, "cold_open": False,
           "stat_pops": False, "sfx": {"zoom": "whoosh" if shot >= 3.0 else None, "broll": "pop" if shot < 3.0 else None,
                                       "cut": "whoosh" if shot < 2.5 else None, "stat": None}}
    lines.append("Inferred from the pace (a guess, not measured): "
                 + ("pauses and filler words are cut, " if tpl["remove_fillers"] else "pauses are cut, " if tpl["tighten"] else "pauses are kept, ")
                 + ("punch-in zooms" if tpl["auto_zoom"] else "extra cutaway pictures (b-roll)") + " to keep it moving.")
    grade, why = grade_for(m.get("colour"))
    tpl["video_filter"] = grade
    lines.append(f"Colour: {grade.replace('_', ' ')} look because {why}." if grade else f"Colour: {why}.")
    if m.get("mean_db") is not None:
        lines.append(f"Sound: about {m['mean_db']:.0f} dB on average; volume is evened out (clean-up is on).")
    if m.get("width") and m.get("height"):
        lines.append("Shape: " + ("vertical" if m["height"] > m["width"] else "wide") + f" ({m['width']}x{m['height']}); your clips keep the shape you choose.")
    lines.append(f"Captions: not detected; the {caption_style} style is used (change it in the template or with --caption_style). "
                 "The music, graphics and logos of the reference are not copied.")
    return tpl, lines


def fetch_reference(url, download=None):
    """Download a reference reel from a link (YouTube, TikTok, Instagram, X or a direct video link, whatever yt-dlp reads) into
    sessions/style_refs and return its path. The reel is only measured, never reused. Raises ValueError with a plain message on failure."""
    if download is None:
        from engine.media_gen import download_source_video_from_url as download
    try:
        path = download(url, os.path.join("sessions", "style_refs"), filename="reference.mp4")
    except Exception as e:
        raise ValueError(f"The link could not be downloaded ({str(e)[:120]}). It may be private, removed or limited to some regions; "
                         "download the reel yourself and give the file instead.")
    if not path or not os.path.isfile(path):
        raise ValueError("The link could not be downloaded. Download the reel yourself and give the file instead.")
    return path


def clone(video, name, caption_style="HORMOZI", folder=None, ffmpeg=None, run=subprocess.run, frames=None):
    """Analyse `video` and save the template `name`. Returns (path, lines). Raises ValueError for a bad name or an unreadable video."""
    from engine import auto_edit
    video = str(video or "").strip().strip('"')
    if video.lower().startswith(("http://", "https://", "www.")):
        video = fetch_reference(video)
    if not video or not os.path.isfile(video):
        raise ValueError("The reference video was not found. Give a link or the path of a video file on this PC.")
    m = analyse(video, ffmpeg, run, frames)
    if not m["duration"]:
        raise ValueError("The reference video could not be read.")
    tpl, lines = to_template(m, caption_style)
    tpl["label"] = "Style of " + str(name).strip().replace("-", " ").replace("_", " ")
    tpl["about"] = "Made by copying the rhythm and look of a reference reel. " + lines[0]
    path = auto_edit.save_user_template(name, tpl, folder)
    return path, lines


STRUCTURE_PROMPT = (
    "These are {n} frames from one short reel, in time order. For EACH frame describe the text drawn on it (not a street or shop sign in the scene). "
    "Reply with JSON only, an array with exactly {n} entries: "
    '[{{"id": 1, "text": ["line 1", "line 2"], "position": "top|upper|middle|lower|bottom|none", '
    '"role": "headline|label|cta|caption|none", "font": "script|sans|serif|bold|none", "fills_frame": true}}, ...]. '
    "fills_frame is true when the picture fills the whole frame, false when it sits in a smaller strip with black or blurred bars. "
    "headline = a big title for the whole reel, label = a short tag for this shot (a day number, a place name), "
    "cta = a call to action or promotion (comment, follow, win, link), caption = spoken words. Use an empty text list and role none when a frame has no added text.")
DAY_WORD = re.compile(r"^\s*(day|part|stop|chapter|step)\s*\d+", re.IGNORECASE)


def _parse_json_array(text):
    import json
    text = str(text or "").strip()
    start, end = text.find("["), text.rfind("]")
    if start < 0 or end <= start:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except ValueError:
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def ask_frames_json(frames, prompt, timeout=120):
    """The model's JSON answer about these JPEG frames: Gemini when a key is set (the frames are sent to Google), else a local Ollama vision
    model; [] when neither is available or the answer cannot be read."""
    import base64
    import json
    import urllib.request
    from engine import visual_context as vc
    key = vc.gemini_key() if (os.getenv("SHORTSFLOW_VISION") or "auto").strip().lower() in ("auto", "gemini") else None
    if key:
        parts = [{"text": prompt}] + [{"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(f).decode()}} for f in frames]
        body = json.dumps({"contents": [{"parts": parts}], "generationConfig": {"temperature": 0, "maxOutputTokens": 2500}}).encode()
        for name in vc.GEMINI_MODELS:
            req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{name}:generateContent", body,
                                         {"Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    data = json.load(r)
                found = _parse_json_array("".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"]))
                if found:
                    return found
            except Exception as e:
                print(f"[Warning] Style clone: {name} did not answer ({str(e)[:80]}).")
        return []
    model = vc.pick_vision_model()
    if not model:
        return []
    body = json.dumps({"model": model, "stream": False, "options": {"temperature": 0},
                       "messages": [{"role": "user", "content": prompt, "images": [base64.b64encode(f).decode() for f in frames]}]}).encode()
    req = urllib.request.Request(f"{vc.ollama_base()}/api/chat", body, {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            return _parse_json_array(json.load(r)["message"]["content"])
    except Exception as e:
        print(f"[Warning] Style clone: the local vision model did not answer ({str(e)[:80]}).")
        return []


def read_structure(video, duration, ask=None, grab=None, frames=10):
    """What text the reference shows and where: a list of per-frame entries (see STRUCTURE_PROMPT), [] when no picture reader is available.
    `ask(frames, prompt)` and `grab(video, start, end, n)` can be given for tests. With Gemini the frames leave this PC."""
    from engine import visual_context as vc
    grab = grab or vc.grab_frames
    pics = grab(video, 0.0, float(duration or MAX_ANALYSED), frames)
    if not pics:
        return []
    entries = (ask or ask_frames_json)(pics, STRUCTURE_PROMPT.format(n=len(pics)))
    return entries


def summarise_structure(entries):
    """The layout facts in the entries: {"labels_over_footage", "day_labels", "label_position", "font", "headline", "closing_cta"}."""
    def lines(e):
        t = e.get("text") or []
        return [str(x).strip() for x in (t if isinstance(t, list) else [t]) if str(x).strip()]
    texted = [e for e in entries if lines(e) and str(e.get("role", "none")).lower() != "none"]
    labels = [e for e in texted if str(e.get("role")).lower() == "label"]
    day_labels = sum(1 for e in labels if any(DAY_WORD.match(x) for x in lines(e))) >= 2
    pos = [str(e.get("position", "none")).lower() for e in labels if str(e.get("position", "none")).lower() != "none"]
    fonts = [str(e.get("font", "none")).lower() for e in texted if str(e.get("font", "none")).lower() != "none"]
    first = entries[0] if entries else {}
    last = entries[-1] if entries else {}
    return {"labels_over_footage": bool(labels), "day_labels": day_labels,
            "label_position": max(set(pos), key=pos.count) if pos else None,
            "font": max(set(fonts), key=fonts.count) if fonts else None,
            "headline": bool(lines(first)) and str(first.get("role", "")).lower() in ("headline", "label"),
            "closing_cta": bool(lines(last)) and str(last.get("role", "")).lower() == "cta",
            "full_bleed": sum(1 for e in entries if e.get("fills_frame") is True) > len(entries) / 2}


def to_recap_recipe(m, structure, days=5, max_seconds=60):
    """(recipe, lines): the recap options that make a recap like the reference. recipe maps option names (without --) to values.
    Without a read structure only the pace, shape and length are set. The reference's colour look is not forced on other footage."""
    shot = m["shot_seconds"]
    recipe = {"recap_pace": "fast" if shot < 3.0 else "normal", "video_filter": "none"}
    lines = [f"Pace: {pace_label(shot)}, about {shot:.1f} s per shot."]
    if m.get("width") and m.get("height"):
        recipe["recap_aspect"] = "9:16" if m["height"] > m["width"] else "16:9"
        lines.append("Shape: " + ("vertical 9:16" if m["height"] > m["width"] else "wide 16:9") + ".")
    days = max(1, int(days))
    seconds = round(max(shot, 2.8) * (days + 2))   # one shot for each day, plus the opening and the ending (a label needs about 2.8 s to be read)
    recipe["recap_length"] = int(max(15, min(max_seconds, seconds)))
    lines.append(f"Length: about {recipe['recap_length']} s for {days} day(s), one shot each, like the reference's rhythm (never more than {max_seconds} s).")
    if structure and structure.get("labels_over_footage"):
        recipe["recap_style"] = "cinematic"
        lines.append("Text: labels sit over the shots (not on separate cards), so the recap uses text over the footage.")
        if structure.get("day_labels"):
            recipe["recap_itinerary"] = True
            lines.append("Labels: a small \"DAY N\" above the place name on each day's first shot.")
        if structure.get("label_position") in ("top", "upper"):
            recipe["recap_safe_text"] = True
            lines.append("Position: the text sits in the upper part of the frame.")
        if structure.get("font") == "script":
            recipe["recap_font"] = "handwritten"
            lines.append("Font: a script face (the bundled handwritten one is the closest).")
        recipe["recap_end"] = "result" if structure.get("closing_cta") else "card"
        lines.append("Ending: " + ("finishes on the last shot with a short line (the reference's own promotion text is not copied)." if structure.get("closing_cta")
                                    else "a closing card."))
    if structure and structure.get("full_bleed") and recipe.get("recap_aspect") == "9:16":
        recipe["layout"] = "crop"
        lines.append("Picture: fills the whole frame (no blurred bars); landscape clips are cropped to fill it.")
    if structure and structure.get("labels_over_footage"):
        pass
    elif structure is not None:
        lines.append("Text: no text over the shots was found, so the normal recap look is kept.")
    else:
        lines.append("Text: not read (no picture reader is available: set GEMINI_API_KEY, or run Ollama with a vision model), so only pace, shape and length are copied.")
    lines.append("Your footage's own colours are kept, and the reference's music and graphics are not copied.")
    return recipe, lines


def recipe_for(reference, days=5, max_seconds=60, ffmpeg=None, run=subprocess.run, ask=None, grab=None):
    """Analyse a reference (file or link) and return (recipe, lines) for a recap. Raises ValueError like `clone`."""
    video = str(reference or "").strip().strip('"')
    if video.lower().startswith(("http://", "https://", "www.")):
        video = fetch_reference(video)
    if not video or not os.path.isfile(video):
        raise ValueError("The reference video was not found. Give a link or the path of a video file on this PC.")
    m = analyse(video, ffmpeg, run, frames=[])
    if not m["duration"]:
        raise ValueError("The reference video could not be read.")
    entries = read_structure(video, m["duration"], ask=ask, grab=grab)
    structure = summarise_structure(entries) if entries else None
    return to_recap_recipe(m, structure, days, max_seconds)


def apply_recipe(args, recipe, argv=None):
    """Set the recipe's options on `args` unless the user gave that option on the command line. Returns the names that were set."""
    argv = list(argv or [])
    set_names = []
    for name, value in recipe.items():
        flag = "--" + name
        if any(a == flag or a.startswith(flag + "=") for a in argv):
            continue
        setattr(args, name, value)
        set_names.append(name)
    return set_names


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Copy the rhythm and look of a reference reel into a saved template.")
    p.add_argument("reference", help="a link (YouTube and others) or a video file on this PC")
    p.add_argument("name", help="name of the new template (letters, digits, - or _)")
    p.add_argument("--caption_style", default="HORMOZI")
    a = p.parse_args(argv)
    try:
        path, lines = clone(a.reference, a.name, a.caption_style)
    except ValueError as e:
        print(f"[Error] {e}")
        return 1
    print("\n".join("- " + line for line in lines))
    shown = os.path.splitext(os.path.basename(path))[0]
    print(f"Saved {path}. Use it with: --auto_edit {shown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
