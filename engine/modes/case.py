"""CASE mode: a topic (and, ideally, source links) in, a finished sectioned explainer video out.

    python main.py --mode CASE --prompt "The topic" --sources https://example.com/article
    python main.py --mode CASE --case resume=sessions/case_123 --case theme=neon      # same script and voice, new look: minutes, no new voice
    python main.py --mode CASE --case resume=sessions/case_123 --case draft           # a small, fast render to judge the pictures and pacing
    python main.py --mode CASE --case help                                            # every option (they live in engine/case_options.py)

Works for any subject that fits sections (an event, a failure, a product, a scam, a historic moment). The script is written from the
sources only (engine/case_study.py); the voice, the drawn scenes, optional Manim animation and stock footage, captions, music and
sound effects are made by engine/case_render.py and the Remotion "CaseVideo" composition. One video per format (16:9 and 9:16 by default).
A finished session keeps its script, narration and animations, so only the render is redone when the look, background or shape changes.
"""
import json
import os
import sys
import time

MODE = "CASE"       # the --mode value that reaches run() (see shortsflow/_main.py)
DRAFT_SCALE = 0.5   # a draft is rendered at half size: about a quarter of the pixels


def _options(args):
    """The validated CASE options (engine/case_options.py). Exits with the reason on a bad key or value; `--case help` lists them all."""
    from engine import case_options
    try:
        return case_options.from_args(args)
    except case_options.OptionError as e:
        print(("[Log] " if "CASE options" in str(e) else "[Error] ") + str(e))
        sys.exit(0 if "CASE options" in str(e) else 2)


def _make_script(args, session_dir, opts):
    """Write the script from the topic and sources. Exits with a clear message when it cannot."""
    from engine import case_study as cs
    topic =(getattr(args, "prompt", None) or getattr(args, "category", None) or "").strip()
    if not topic:
        print("[Error] --mode CASE needs the topic: --prompt \"...\" (and, for facts you can trust, --sources LINK_OR_FILE, up to 3), "
              "or --case resume=FOLDER to redo a finished run.")
        sys.exit(2)
    try:
        template = cs.load_template(opts["template"])
    except ValueError as e:
        print(f"[Error] {e}")
        sys.exit(2)
    sources, skipped = cs.gather_sources(getattr(args, "sources", None) or [])
    for item, why in skipped:
        print(f"[Warning] Source skipped ({why}): {item}")
    if not sources:
        print("[Warning] No usable source: the video will be marked UNVERIFIED. Give --sources to ground it.")

    from engine.case_llm import make_ask
    ask = make_ask("You write explainer video scripts. Return raw JSON only.", opts["llm"], json_mode=True)
    script, error = None, None
    for attempt in (1, 2):                  # a model that is busy sometimes answers with something that is not the script: one more try
        try:
            script = cs.write_script(topic, template, sources, ask, opts["layouts"])
            break
        except ValueError as e:
            error = e
            if attempt == 1:
                print(f"[Warning] The model's answer was not a usable script ({e}); asking once more.")
    if script is None:
        print(f"[Error] The script could not be written: {error}")
        sys.exit(1)
    for d in script["dropped"]:
        print(f"[Log] Dropped (not in the sources: {', '.join(d['unsupported'])}): {d['sentence'][:100]}")
    with open(os.path.join(session_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, indent=1, ensure_ascii=False)
    print(f"[Log] Script: '{script['title']}', {len(script['sections'])} sections, "
          + (f"verified against {len(sources)} source(s)." if script["verified"] else "UNVERIFIED."))
    return script


def _narration(args, script, session_dir, resumed):
    """([audio], [words]): the saved narration of a resumed session, else newly spoken (ElevenLabs when its key is set)."""
    from engine import case_render as cr
    if resumed:
        cached = cr.cached_voice(script, session_dir)
        if cached:
            print("[Log] Reusing the saved narration (no new voice is made).")
            return cached
        print("[Warning] The saved narration is missing or incomplete; making it again.")
    provider = getattr(args, "tts_provider", None)
    if provider in (None, "auto") and os.getenv("ELEVENLABS_API_KEY"):
        provider = "elevenlabs"
    elif provider == "auto":
        provider = None
    return cr.speak_sections(script, session_dir, provider=provider, voice=getattr(args, "voice", None),
                             clone_voice=os.getenv("VOICE_CLONE_SAMPLE") or None)


def missing_animations(script, clips):
    """Titles of the sections that are one animation (scene "animation") but have no clip: without it such a section would be a bare title card."""
    if not clips:
        return []
    return [str(s.get("title", "")) for s, c in zip(script["sections"], clips) if s.get("scene") == "animation" and not c]


def run(args, target_bitrate=None, target_preset=None):
    from engine import case_render as cr

    opts = _options(args)
    formats = opts["formats"].split(",")
    draft = bool(opts["draft"])
    resume = opts["resume"]
    if resume:
        session_dir = resume
        try:
            with open(os.path.join(session_dir, "script.json"), encoding="utf-8") as f:
                script = json.load(f)
        except (OSError, ValueError):
            print(f"[Error] --case resume: no script.json in '{session_dir}'. Give the folder of an earlier CASE run.")
            sys.exit(2)
        print(f"--- CASE explainer, redoing the render of '{script.get('title', '')}' ({', '.join(formats)}{', draft' if draft else ''}) ---")
    else:
        session_dir = args.session_dir if getattr(args, "session_dir", None) else os.path.join("sessions", f"case_{int(time.time())}")
        os.makedirs(session_dir, exist_ok=True)
        topic = (getattr(args, "prompt", None) or getattr(args, "category", None) or "").strip()
        print(f"--- CASE explainer: '{topic}' ({opts['template']} template, {', '.join(formats)}{', draft' if draft else ''}) ---")
        script = _make_script(args, session_dir, opts)
        if opts["plan_only"]:
            print(f"[Log] Script written to {os.path.join(session_dir, 'script.json')}. Nothing was spoken or rendered (plan_only). "
                  f"Edit it if you like, then: --mode CASE --case resume={session_dir}")
            sys.exit(0)

    audios, words = _narration(args, script, session_dir, bool(resume))
    timing = cr.plan_timing([cr._duration(a) for a in audios])

    music = getattr(args, "music", None)
    if not music or not os.path.exists(music):
        from engine.light_music import ensure_track
        music = ensure_track()
    want_manim = bool(opts["manim"])
    choice = opts["background"]
    theme = opts["theme"]

    from engine.case_llm import make_ask
    ask_code = make_ask("You write Manim Community Edition code.", opts["llm"])

    results = []
    for aspect in formats:
        tag = aspect.replace(":", "x")
        portrait = aspect == "9:16"
        # a draft never spends model calls on animations: it shows the ones a full run already made, and the plain scene otherwise
        clips = (cr.attach_clips(script, timing, session_dir, ask_code, portrait=portrait, scenes=("flow", "animation"), tag=tag, reuse=bool(resume) or draft,
                                 generate=not draft) if want_manim else None)
        lost = [] if draft else missing_animations(script, clips)
        if lost or (not clips and not draft and any(s.get("scene") == "animation" for s in script["sections"])):
            print(f"[Error] The animation could not be made for: {', '.join(lost) or 'this video'} (the model was busy or its scenes kept failing the checks; "
                  f"see the lines above). The script and the narration are saved: run again with --case resume={session_dir}")
            sys.exit(1)
        footage = cr.backgrounds_for(script, session_dir, aspect, choice, has_pexels=bool(os.getenv("PEXELS_API_KEY")))
        props = cr.build_props(script, timing, words, theme=theme, music_volume=0.2, clips=clips, footage=footage, portrait=portrait)
        voice_track = cr.join_audio(audios, timing, os.path.join(session_dir, f"voice_all_{tag}.mp3"),
                                    sfx=cr.sfx_for(props, os.path.join(session_dir, f"sfx_{tag}.wav")))
        name = f"case_draft_{tag}.mp4" if draft else f"case_{tag}.mp4"
        out = cr.render_case(props, voice_track, os.path.join(session_dir, name), music_path=music, aspect=aspect,
                             scale=DRAFT_SCALE if draft else 1.0)
        results.append({"aspect": aspect, "file": out, "draft": draft})
        print(f"[Log] SUCCESS! {aspect} {'draft ' if draft else ''}video: {out}")

    if not draft:
        with open(os.path.join(session_dir, "case.json"), "w", encoding="utf-8") as f:
            json.dump({"title": script["title"], "verified": script["verified"], "sources": script["sources"], "videos": results}, f, indent=1)
    sys.exit(0)
