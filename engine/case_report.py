"""What ShortsFlow decided for a case video, in plain words (`decisions.md`), and a picture sheet of the finished video (`contact_<shape>.png`).

Both land in the run's folder after every case run (a draft too). The report answers "what did the tool choose, and what did it fall back on?" for a reviewer:
the hook, the layout and mood of each section, the labels, and for a picture section which icon each label got and where it came from (built in, or drawn by the
model and saved in the icon library). Nothing here changes a video, and a problem while writing either file never fails a run.
"""
import os
import subprocess

SCENE_NAMES = {"illustration": "a picture that explains", "story": "a story scene with drawn characters", "diagram": "a diagram", "counters": "number cards", "checklist": "a checklist", "timeline": "a timeline",
               "flow": "a row of steps", "quote": "a key line", "compare": "two things side by side", "chart": "a bar chart", "animation": "one animation",
               "terminal": "a terminal", "equation": "a formula"}


def icon_origin(kind):
    """Where an icon came from: the built-in kit, or the library of icons the model drew earlier."""
    from engine import art_icons, art_kit
    if kind in art_kit.ICONS:
        return "built in"
    return "drawn by the model, saved in the icon library" if art_icons.load(kind) else "unknown"


def build(script, opts=None, art=None, results=None, avatar=None, warnings=None):
    """The report as markdown. `art` is {aspect: [None | picture plan per section]}, `results` the rendered files, `warnings` the narration timing warnings."""
    opts = opts or {}
    lines = [f"# {script.get('title', 'Video')}", ""]
    if script.get("hook"):
        lines.append(f"**Opening line (hook):** {script['hook']}")
    sources = script.get("sources") or []
    dropped = script.get("dropped") or []
    lines.append(f"**Sources:** {len(sources)}" + (" (every sentence was checked against them)" if script.get("verified") else " (none: nothing could be checked)")
                 + (f"; {len(dropped)} sentence(s) were removed because the sources do not say them." if dropped else "."))
    chosen = [f"template {opts.get('template', 'explainer')}", f"look {opts.get('theme', 'dark')}", f"shapes {opts.get('formats', '')}",
              f"length {opts.get('length', 'standard')}", f"voice {opts.get('narrator', 'standard')}"]
    chosen.append("presenter " + str((avatar or {}).get("name") or (opts.get("avatar") if opts.get("avatar") not in (None, "off") else "none")))
    lines += ["**Settings:** " + ", ".join(x.strip() for x in chosen if x.strip()), ""]
    first_art = next(iter((art or {}).values()), None) or []
    for n, sec in enumerate(script.get("sections", []), 1):
        scene = sec.get("scene", "quote")
        plan = first_art[n - 1] if n - 1 < len(first_art) else None
        lines.append(f"## {n}. {sec.get('title', '')}: {SCENE_NAMES.get(scene, scene)}")
        lines.append(f"- narrator mood: {sec.get('mood') or 'not set'}; {len((sec.get('narration') or '').split())} words spoken")
        lines.append("- on-screen labels: " + (" | ".join(sec.get("on_screen") or []) or "none"))
        if scene == "illustration":
            if plan:
                kinds = plan.get("kinds") or {}
                shown = [f"{label} -> {kinds[label]} ({icon_origin(kinds[label])})" for label in (sec.get("on_screen") or []) if label in kinds]
                lines.append("- icons: " + ("; ".join(shown) if shown else "not recorded (a picture made before icons were recorded)"))
            elif art:                                           # picture details were collected and this section has none: it fell back
                lines.append("- the picture could not be made, so this section shows its labels as a checklist")
        if scene == "story" and plan:
            lines.append("- on screen: " + (", ".join(plan.get("characters") or []) or "no characters") + ("; cards: " + ", ".join(plan["cards"]) if plan.get("cards") else "; no cards"))
            for o in plan.get("objects") or []:
                lines.append(f"- thing asked for: {o['name']}: {o['status']}" + (" (shown)" if o["shown"] else " (not shown)"))
        if sec.get("footage"):
            lines.append("- background ideas: " + "; ".join(sec["footage"]))
        lines.append("")
    story_review_ = next((p["review"] for p in first_art if isinstance(p, dict) and p.get("review")), None)
    if story_review_:
        from engine import story_review
        lines += ["## ShortsFlow's own review of the story", *story_review.summary(story_review_), ""]
    if warnings:
        lines += ["## Narration timing warnings", *[f"- {w}" for w in warnings], ""]
    if results:
        lines += ["## Files", *[f"- {os.path.basename(r.get('file', ''))}" + (" (draft)" if r.get("draft") else "") for r in results], ""]
    return "\n".join(lines)


def contact_sheet(video, out, frames=8, cols=4, width=None, run=subprocess.run):
    """A PNG grid of `frames` evenly spaced pictures of `video`, or None when ffmpeg cannot make it. `run` replaces subprocess.run (tests)."""
    try:
        probe = run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                    capture_output=True, text=True)
        values = [x for x in str(probe.stdout).replace(",", "\n").split() if x.replace(".", "", 1).isdigit()]
        w, h, duration = float(values[0]), float(values[1]), float(values[-1])
        if duration <= 0:
            return None
        width = width or (480 if w >= h else 270)
        rows = (frames + cols - 1) // cols
        step = duration / (frames + 1)
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", video, "-vf", f"fps=1/{step:.3f},scale={width}:-2,tile={cols}x{rows}:padding=4:margin=4", "-frames:v", "1", out]
        res = run(cmd, capture_output=True, text=True)
        return out if getattr(res, "returncode", 1) == 0 and os.path.isfile(out) else None
    except Exception:
        return None


def write(session_dir, script, opts=None, art=None, results=None, avatar=None, warnings=None, sheet=contact_sheet):
    """Write `decisions.md` and one contact sheet per rendered video into `session_dir`; the list of the paths written. Never raises."""
    written = []
    try:
        path = os.path.join(session_dir, "decisions.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(build(script, opts, art, results, avatar, warnings))
        written.append(path)
    except Exception as e:
        print(f"[Warning] The decisions report could not be written ({str(e)[:80]}).")
    for r in results or []:
        try:
            shape = str(r.get("aspect", "")).replace(":", "x")
            made = sheet(r["file"], os.path.join(session_dir, f"contact_{shape}.png"))
            if made:
                written.append(made)
        except Exception:
            continue
    return written
