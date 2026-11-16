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
    '"role": "headline|label|cta|caption|none", "font": "script|display_serif|serif|condensed|sans|none", "fills_frame": true, '
    '"color": "#RRGGBB", "size": "small|medium|large|huge", "weight": "thin|regular|bold", "glow": false}}, ...]. '
    "font: script = joined handwritten or cursive letters like a pen; display_serif = heavy decorative serif letters with thick strokes, like a magazine or poster title (even if slightly curly); serif = ordinary book letters; condensed = tall narrow bold capitals; sans = plain modern letters. "
    "color is the main colour of the label text as a hex code, size how big the label text is compared with the frame, "
    "glow true when the text has a soft glow or halo. "
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


def measure_text_colour(jpegs, top=0.12, bottom=0.40):
    """The colour of the label text as "#rrggbb", measured from the pixels of the upper part of the frames (bright, warm-tinted pixels:
    cream or yellow script over sky or footage), or None when the text is plain white or cannot be found. The reader's own colour guess
    is often just "white"; the pixels are what the eye sees."""
    import io
    import numpy as np
    from PIL import Image
    found = []
    for jpg in jpegs or []:
        try:
            im = np.asarray(Image.open(io.BytesIO(jpg)).convert("RGB")).astype(np.float32) / 255.0
        except Exception:
            continue
        h = im.shape[0]
        band = im[int(h * top):int(h * bottom)].reshape(-1, 3)
        mx, mn = band.max(1), band.min(1)
        sat = (mx - mn) / np.maximum(mx, 1e-6)
        luma = band @ np.array([0.2126, 0.7152, 0.0722], np.float32)
        pick = (luma > 0.75) & (sat > 0.18) & (band[:, 0] >= band[:, 2])
        if pick.sum() > 0.0015 * len(band):
            found.append(np.median(band[pick], axis=0))
    if len(found) < max(2, len(jpegs or []) // 2):
        return None
    r, g, b = (np.median(np.array(found), axis=0) * 255).astype(int)
    return "#%02x%02x%02x" % (r, g, b)


def merge_entries(a, b):
    """One list from two readings of the same frames: for each frame, text and role come from the reading that found text, and a
    style trait (font, size, weight, glow, fills_frame) is kept when either reading found it (script, bold, glow, true win over the plain ones)."""
    if not a or not b or len(a) != len(b):
        return a or b
    out = []
    for x, y in zip(a, b):
        e = dict(x if (x.get("text") or not y.get("text")) else y)
        for key in ("font", "weight", "size"):
            vals = [str(v.get(key, "none")).lower() for v in (x, y)]
            pref = {"font": ("display_serif", "script", "serif", "condensed", "bold", "sans"), "weight": ("bold", "regular", "thin"), "size": ("huge", "large", "medium", "small")}[key]
            e[key] = next((p for p in pref if p in vals), vals[0])
        e["glow"] = bool(x.get("glow")) or bool(y.get("glow"))
        e["fills_frame"] = bool(x.get("fills_frame")) and bool(y.get("fills_frame"))
        if y.get("color") and (not e.get("color") or str(e.get("color")).lower() == "#ffffff"):
            e["color"] = y["color"]
        out.append(e)
    return out


def read_structure(video, duration, ask=None, grab=None, frames=10, keep=None):
    """What text the reference shows and where: a list of per-frame entries (see STRUCTURE_PROMPT), [] when no picture reader is available.
    `ask(frames, prompt)` and `grab(video, start, end, n)` can be given for tests. With Gemini the frames leave this PC."""
    from engine import visual_context as vc
    grab = grab or vc.grab_frames
    pics = grab(video, 0.0, float(duration or MAX_ANALYSED), frames)
    if keep is not None:
        keep.extend(pics)
    if not pics:
        return []
    prompt = STRUCTURE_PROMPT.format(n=len(pics))
    reader = ask or ask_frames_json
    first = reader(pics, prompt)
    if ask is not None or not first:
        return first
    second = reader(pics, prompt)          # the reader's answers vary a little between calls: ask twice and keep what agrees
    return merge_entries(first, second)


def _text_look(entries):
    """The most common text colour, size and weight, and whether the text glows, among the entries."""
    colours = [str(e.get("color", "")).lower() for e in entries if re.fullmatch(r"#[0-9a-f]{6}", str(e.get("color", "")).lower())]
    sizes = [str(e.get("size", "")).lower() for e in entries if str(e.get("size", "")).lower() in ("small", "medium", "large", "huge")]
    weights = [str(e.get("weight", "")).lower() for e in entries]
    return {"text_color": max(set(colours), key=colours.count) if colours else None,
            "text_size": max(set(sizes), key=sizes.count) if sizes else None,
            "text_bold": weights.count("bold") > len(weights) / 2 if weights else False,
            "text_glow": sum(1 for e in entries if e.get("glow") is True) > len(entries) / 2 if entries else False}


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
            "full_bleed": sum(1 for e in entries if e.get("fills_frame") is True) > len(entries) / 2,
            **_text_look(labels or texted)}


def to_recap_recipe(m, structure, days=5, max_seconds=60):
    """(recipe, lines): the recap options that make a recap like the reference. recipe maps option names (without --) to values.
    Without a read structure only the pace, shape and length are set. The reference's colour look is not forced on other footage."""
    shot = m["shot_seconds"]
    recipe = {"recap_pace": "fast" if shot < 3.0 else "normal"}
    lines = [f"Pace: {pace_label(shot)}, about {shot:.1f} s per shot."]
    if m.get("width") and m.get("height"):
        ratio = m["width"] / max(1, m["height"])
        recipe["recap_aspect"] = "9:16" if ratio < 1 else "2.35:1" if ratio > 2.0 else "16:9"
        if recipe["recap_aspect"] != "9:16":
            recipe["recap_orientation"] = "landscape"        # a wide recap uses the wide clips (a vertical clip would sit in blurred bars)
        lines.append("Shape: " + {"9:16": "vertical 9:16", "2.35:1": "widescreen 2.35:1", "16:9": "wide 16:9"}[recipe["recap_aspect"]] + ".")
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
        if not structure.get("font"):
            lines.append("Font: the reader could not tell the lettering, so the normal font is kept.")
        if structure.get("font") == "script":
            recipe["recap_font"] = "handwritten"
            lines.append("Font: a script face (the bundled handwritten one is the closest).")
        elif structure.get("font") in ("display_serif", "serif"):
            recipe["recap_font"] = "display"
            lines.append("Font: heavy display serif letters (the bundled Abril Fatface is the closest; the exact font cannot be copied).")
        look = []
        if structure.get("text_color") and structure["text_color"] != "#ffffff":
            look.append("color=" + structure["text_color"])
        scale = {"small": 0.85, "medium": 1.1, "large": 1.4, "huge": 1.7}.get(structure.get("text_size"))
        if scale and scale != 1.0:
            look.append(f"size={scale}")
        look += [w for w, on in (("bold", structure.get("text_bold")), ("glow", structure.get("text_glow"))) if on]
        if structure.get("label_position") in ("bottom", "lower") and structure.get("text_size") in ("small", None):
            look.append("subtitle")          # small lines at the bottom of the picture, like film subtitles
            if not structure.get("day_labels"):
                recipe.pop("recap_itinerary", None)
        if look:
            recipe["recap_text_style"] = ",".join(look)
            lines.append("Text look: " + ", ".join(look) + " (the exact font cannot be copied; the closest bundled one is used).")
        end_on_shot = structure.get("closing_cta") or structure.get("full_bleed")
        recipe["recap_end"] = "result" if end_on_shot else "card"
        lines.append("Ending: " + ("finishes on a full-picture shot with a short line (the reference's own promotion text is not copied)." if end_on_shot
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
    look, why = grade_for(m.get("colour"))
    if look:
        recipe["video_filter"] = look
        lines.append(f"Colour: the {look.replace('_', ' ')} look ({why}), applied to your footage.")
    else:
        lines.append("Colour: " + why + "; your footage's own colours are kept.")
    lines.append("The reference's music and graphics are not copied.")
    return recipe, lines


def recipe_for(reference, days=5, max_seconds=60, ffmpeg=None, run=subprocess.run, ask=None, grab=None):
    """Analyse a reference (file or link) and return (recipe, lines) for a recap. Raises ValueError like `clone`."""
    video = str(reference or "").strip().strip('"')
    if video.lower().startswith(("http://", "https://", "www.")):
        video = fetch_reference(video)
    if not video or not os.path.isfile(video):
        raise ValueError("The reference video was not found. Give a link or the path of a video file on this PC.")
    m = analyse(video, ffmpeg, run)
    if not m["duration"]:
        raise ValueError("The reference video could not be read.")
    pics = []
    entries = read_structure(video, m["duration"], ask=ask, grab=grab, keep=pics)
    structure = summarise_structure(entries) if entries else None
    if structure and structure.get("labels_over_footage"):
        measured = measure_text_colour(pics)
        if measured:
            structure["text_color"] = measured
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
