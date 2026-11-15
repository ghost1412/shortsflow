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


def clone(video, name, caption_style="HORMOZI", folder=None, ffmpeg=None, run=subprocess.run, frames=None):
    """Analyse `video` and save the template `name`. Returns (path, lines). Raises ValueError for a bad name or an unreadable video."""
    from engine import auto_edit
    if not video or not os.path.isfile(video):
        raise ValueError("The reference video was not found. Give the path of a video file on this PC.")
    m = analyse(video, ffmpeg, run, frames)
    if not m["duration"]:
        raise ValueError("The reference video could not be read.")
    tpl, lines = to_template(m, caption_style)
    tpl["label"] = "Style of " + str(name).strip().replace("-", " ").replace("_", " ")
    tpl["about"] = "Made by copying the rhythm and look of a reference reel. " + lines[0]
    path = auto_edit.save_user_template(name, tpl, folder)
    return path, lines


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Copy the rhythm and look of a reference reel into a saved template.")
    p.add_argument("reference", help="a video file on this PC")
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
