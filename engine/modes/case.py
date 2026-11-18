"""CASE mode: a topic (and, ideally, source links) in, a finished sectioned explainer video out.

    python main.py --mode CASE --prompt "The July 2024 CrowdStrike outages" --sources https://example.com/article --case_template case

Works for any subject that fits sections (an event, a failure, a product, a scam, a historic moment). The script is written from the
sources only (engine/case_study.py); the voice, the drawn scenes, optional Manim animation and stock footage, captions, music and
sound effects are made by engine/case_render.py and the Remotion "CaseVideo" composition. One video per format (16:9 and 9:16 by default).
"""
import json
import os
import sys
import time

MODE = "CASE"       # the --mode value that reaches run() (see shortsflow/_main.py)


def _formats(text):
    from engine.case_render import SIZES
    out = [f.strip() for f in str(text or "16:9,9:16").split(",") if f.strip()]
    bad = [f for f in out if f not in SIZES]
    if bad or not out:
        print(f"[Error] --case_formats: unknown shape {bad or text!r}; use a list such as 16:9,9:16 (known: {', '.join(SIZES)}).")
        sys.exit(2)
    return list(dict.fromkeys(out))


def run(args, target_bitrate=None, target_preset=None):
    from engine import case_render as cr
    from engine import case_study as cs
    from engine.script_gen import get_llm_response

    topic = (getattr(args, "prompt", None) or getattr(args, "category", None) or "").strip()
    if not topic:
        print("[Error] --mode CASE needs the topic: --prompt \"...\" (and, for facts you can trust, --sources LINK_OR_FILE, up to 3).")
        sys.exit(2)
    formats = _formats(getattr(args, "case_formats", None))
    try:
        template = cs.load_template(getattr(args, "case_template", None) or "case")
    except ValueError as e:
        print(f"[Error] {e}")
        sys.exit(2)
    session_dir = args.session_dir if getattr(args, "session_dir", None) else os.path.join("sessions", f"case_{int(time.time())}")
    os.makedirs(session_dir, exist_ok=True)
    print(f"--- CASE explainer: '{topic}' ({getattr(args, 'case_template', None) or 'case'} template, {', '.join(formats)}) ---")

    sources, skipped = cs.gather_sources(getattr(args, "sources", None) or [])
    for item, why in skipped:
        print(f"[Warning] Source skipped ({why}): {item}")
    if not sources:
        print("[Warning] No usable source: the video will be marked UNVERIFIED. Give --sources to ground it.")

    def ask(prompt):
        return get_llm_response(prompt, system_prompt="You write explainer video scripts. Return raw JSON only.", max_tokens=16000, timeout=300)

    def ask_code(prompt):
        return get_llm_response(prompt, system_prompt="You write Manim Community Edition code.", max_tokens=16000, timeout=300)

    try:
        script = cs.write_script(topic, template, sources, ask)
    except ValueError as e:
        print(f"[Error] The script could not be written: {e}")
        sys.exit(1)
    for d in script["dropped"]:
        print(f"[Log] Dropped (not in the sources: {', '.join(d['unsupported'])}): {d['sentence'][:100]}")
    with open(os.path.join(session_dir, "script.json"), "w", encoding="utf-8") as f:
        json.dump(script, f, indent=1, ensure_ascii=False)
    print(f"[Log] Script: '{script['title']}', {len(script['sections'])} sections, {'verified against ' + str(len(sources)) + ' source(s)' if script['verified'] else 'UNVERIFIED'}.")

    provider = getattr(args, "tts_provider", None)
    if provider in (None, "auto") and os.getenv("ELEVENLABS_API_KEY"):
        provider = "elevenlabs"
    elif provider == "auto":
        provider = None
    audios, words = cr.speak_sections(script, session_dir, provider=provider, voice=getattr(args, "voice", None),
                                      clone_voice=os.getenv("VOICE_CLONE_SAMPLE") or None)
    timing = cr.plan_timing([cr._duration(a) for a in audios])

    music = getattr(args, "music", None)
    if not music or not os.path.exists(music):
        from engine.light_music import ensure_track
        music = ensure_track()
    want_manim = not getattr(args, "case_no_manim", False)
    want_footage = not getattr(args, "case_no_footage", False) and bool(os.getenv("PEXELS_API_KEY"))
    theme = getattr(args, "case_theme", None) or "dark"

    results = []
    for aspect in formats:
        tag = aspect.replace(":", "x")
        portrait = aspect == "9:16"
        clips = cr.attach_clips(script, timing, session_dir, ask_code, portrait=portrait, scenes=("flow",)) if want_manim else None
        footage = cr.attach_footage(script, session_dir, aspect) if want_footage else None
        props = cr.build_props(script, timing, words, theme=theme, music_volume=0.2, clips=clips, footage=footage)
        voice_track = cr.join_audio(audios, timing, os.path.join(session_dir, f"voice_all_{tag}.mp3"),
                                    sfx=cr.sfx_for(props, os.path.join(session_dir, f"sfx_{tag}.wav")))
        out = cr.render_case(props, voice_track, os.path.join(session_dir, f"case_{tag}.mp4"), music_path=music, aspect=aspect)
        results.append({"aspect": aspect, "file": out})
        print(f"[Log] SUCCESS! {aspect} video: {out}")

    with open(os.path.join(session_dir, "case.json"), "w", encoding="utf-8") as f:
        json.dump({"title": script["title"], "verified": script["verified"], "sources": script["sources"], "videos": results}, f, indent=1)
    sys.exit(0)
