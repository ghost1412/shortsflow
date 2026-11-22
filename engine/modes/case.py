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


def _narrator_tag(narrator, voice_sample, avatar, voice=None):
    """What the narration is spoken with, as kept in voice_cache.json, so a redo with another narrator, another recording or another presenter
    voice speaks it again: "standard", "voice_server:own_<hash>.wav" (a person's recording) or "voice_server:voice_<edge voice>.wav"."""
    if narrator != "voice_server":
        return "standard"
    if voice_sample and os.path.isfile(voice_sample):
        import hashlib
        with open(voice_sample, "rb") as f:
            return "voice_server:own_" + hashlib.sha1(f.read()).hexdigest()[:12] + ".wav"
    from engine import avatars
    from engine.case_render import NARRATOR_VOICE
    copy = voice if voice in avatars.VOICES else (avatars.voice_for(avatar)[0] if avatar else NARRATOR_VOICE)
    return f"voice_server:voice_{copy}.wav"


def _narration(args, script, session_dir, resumed, avatar=None, narrator="standard", voice_sample=""):
    """([audio], [words]): the saved narration of a resumed session, else newly spoken (ElevenLabs when its key is set)."""
    from engine import case_render as cr
    if resumed:
        cached = cr.cached_voice(script, session_dir, _narrator_tag(narrator, voice_sample, avatar, getattr(args, "voice", None)))
        if cached:
            print("[Log] Reusing the saved narration (no new voice is made).")
            return cached
        print("[Warning] The saved narration is missing, incomplete or was spoken another way; making it again.")
    provider = getattr(args, "tts_provider", None)
    if provider in (None, "auto") and os.getenv("ELEVENLABS_API_KEY"):
        provider = "elevenlabs"
    elif provider == "auto":
        provider = None
    voice, edge_voice = getattr(args, "voice", None), None
    if avatar and not voice:                       # the presenter's own voice, so a man is not voiced by a woman (or the other way round)
        from engine import avatars
        edge_voice, eleven = avatars.voice_for(avatar)
        voice = eleven if provider == "elevenlabs" else edge_voice
        print(f"[Log] Voice: {avatars.VOICES[edge_voice][0]} (the presenter's voice).")
    expressive = None
    if narrator == "voice_server":
        from engine import expressive_voice as ev
        if ev.available():
            from engine import avatars
            from engine.case_render import NARRATOR_VOICE
            sample, tag = None, _narrator_tag(narrator, voice_sample, avatar, getattr(args, "voice", None))
            if voice_sample:
                try:
                    sample, copy = ev.own_sample(voice_sample, os.path.join(session_dir, "voice_samples")), "your recording"
                except RuntimeError as e:
                    print(f"[Warning] Your voice recording is not used ({e}); the presenter's voice is copied instead.")
            if not sample:
                copy = edge_voice or (avatars.voice_for(avatar)[0] if avatar else NARRATOR_VOICE)
                sample = ev.sample_for(copy, os.path.join(session_dir, "voice_samples"))
                tag = f"voice_server:voice_{copy}.wav"
            expressive = {"speak": ev.speak, "sample": sample, "tag": tag}
            print(f"[Log] Narration: the local voice server, each section in its mood (voice copied from {copy}).")
        else:
            print(f"[Warning] narrator=voice_server, but no voice server answers at {ev.server_url()} (start it on the Voice-over card, or "
                  "`python -m engine.voice_server start`). The standard voice is used.")
    return cr.speak_sections(script, session_dir, provider=provider, voice=voice, edge_voice=edge_voice, expressive=expressive,
                             clone_voice=os.getenv("VOICE_CLONE_SAMPLE") or None)


def missing_animations(script, clips):
    """Titles of the sections that are one animation (scene "animation") but have no clip: without it such a section would be a bare title card."""
    if not clips:
        return []
    return [str(s.get("title", "")) for s, c in zip(script["sections"], clips) if s.get("scene") == "animation" and not c]


def _photo_presenter(avatar, audios, timing, session_dir, draft):
    """{image} or {video} for a realistic presenter: the still photo in a draft, the photo talking with the narration in a full render (made once
    per run with the optional talking-head add-on; without it, or if it fails, the still photo is shown and the run goes on)."""
    from engine import avatars, talking_head
    from engine import case_render as cr
    photo = avatars.photo_path(avatar, os.getcwd())
    if not photo:
        print(f"[Warning] The presenter's photo is missing (presenters/{avatar.get('photo')}); no presenter is shown.")
        return {}
    if draft:
        return {"image": photo}
    if not talking_head.installed():
        print("[Warning] The realistic presenter needs the talking-head add-on (python -m engine.talking_head install); the photo is shown still.")
        return {"image": photo}
    out = os.path.join(session_dir, "presenter_talking.mp4")
    if not os.path.isfile(out):
        voice = cr.join_audio(audios, timing, os.path.join(session_dir, "presenter_voice.mp3"))     # the narration alone, on the video's clock
        try:
            talking_head.make(photo, voice, out)
        except Exception as e:                       # the video still renders, with the still photo
            print(f"[Warning] The talking face could not be made ({str(e)[:200]}); the photo is shown still.")
            return {"image": photo}
    return {"video": out}


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

    from engine import avatars
    avatar = avatars.load(opts["avatar"], os.getcwd())
    if opts["voice_sample"] and opts["narrator"] != "voice_server":
        print("[Warning] voice_sample is used only with narrator=voice_server (the local voice server copies it); it is ignored.")
    audios, words = _narration(args, script, session_dir, bool(resume), avatar, opts["narrator"], opts["voice_sample"])
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
        footage = cr.backgrounds_for(script, session_dir, aspect, choice, has_pexels=bool(os.getenv("PEXELS_API_KEY")),
                                     cartoon=opts["cartoon"], ask=ask_code)
        props = cr.build_props(script, timing, words, theme=theme, music_volume=0.2, clips=clips, footage=footage, portrait=portrait, avatar=avatar, transition=opts["transition"])
        voice_track = cr.join_audio(audios, timing, os.path.join(session_dir, f"voice_all_{tag}.mp3"),
                                    sfx=cr.sfx_for(props, os.path.join(session_dir, f"sfx_{tag}.wav")))
        if avatar and avatar["kind"] == "photo":
            props["avatar"] = dict(props["avatar"], **_photo_presenter(avatar, audios, timing, session_dir, draft))
        name = f"case_draft_{tag}.mp4" if draft else f"case_{tag}.mp4"
        out = cr.render_case(props, voice_track, os.path.join(session_dir, name), music_path=music, aspect=aspect,
                             scale=DRAFT_SCALE if draft else 1.0)
        results.append({"aspect": aspect, "file": out, "draft": draft})
        print(f"[Log] SUCCESS! {aspect} {'draft ' if draft else ''}video: {out}")

    if not draft:
        with open(os.path.join(session_dir, "case.json"), "w", encoding="utf-8") as f:
            json.dump({"title": script["title"], "verified": script["verified"], "sources": script["sources"], "videos": results}, f, indent=1)
    sys.exit(0)
