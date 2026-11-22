"""VOICEOVER pipeline: a script read aloud in the user's own cloned voice (runs when: getattr(args, "mode", None) == "VOICEOVER")."""
import os
import sys
import time

from engine.mode_options import OptionError


def read_script(value):
    """`--script` is the text itself, or the path of a text file."""
    value = (value or "").strip()
    if value and len(value) < 260 and os.path.isfile(value):
        with open(value, "r", encoding="utf-8") as f:
            return f.read()
    return value


def run(args, target_bitrate=None, target_preset=None):
    from engine.voiceover import OPTIONS, make_voiceover

    try:
        opts = OPTIONS.from_args(args)
    except OptionError as e:
        print(f"[Error] {e}" if not str(e).startswith("VOICEOVER options") else str(e))
        sys.exit(0 if str(e).startswith("VOICEOVER options") else 2)

    session_dir = args.session_dir if getattr(args, "session_dir", None) else f"sessions/voiceover_{int(time.time())}"
    os.makedirs(session_dir, exist_ok=True)
    script = read_script(getattr(args, "script", None))
    print("[Log] Cloning only your own voice, or the voice of someone who agreed to it. The script and the sample go to the voice "
          "server at the address you set (by default one on this PC).")
    server = opts["server"] or None
    if not server and not os.getenv("VOICE_STUDIO_URL"):
        from engine import voice_server
        try:
            server = voice_server.ensure_running()        # None when the add-on is not installed: then the default address is tried
        except RuntimeError as e:
            print(f"[Error] {e}")
            sys.exit(1)
    try:
        res = make_voiceover(script, session_dir, opts["sample"], tone=opts["tone"], fmt=opts["format"], out=opts["out"] or None,
                             server=server, language=opts["language"])
    except (ValueError, RuntimeError) as e:
        print(f"[Error] {e}")
        sys.exit(1)
    print(f"[Success] Voice-over ready at: {res['audio']} ({res['passages']} passage(s), tone: {res['tone']})")
    sys.exit(0)
