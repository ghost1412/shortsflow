"""Shared helpers for main.py and the standalone mode pipelines in engine/modes/."""

POOL_SIZE = 4

VIBE_VOICE_MAP = {
    "suspense": "en-US-ChristopherNeural", # Deep, intense
    "spooky": "en-US-AndrewNeural",       # Atmospheric
    "cinematic": "en-GB-SoniaNeural",      # Sophisticated narrator
    "upbeat": "en-US-AvaNeural",            # Energetic, modern
    "sarcastic": "en-US-GuyNeural",         # Witty, punchy sarcastic male narrator
    "funny": "en-US-ChristopherNeural"      # High-energy comedy commentator
}

CARTOON_VOICE_MAP = {
    "rabbit": "en-US-AnaNeural",      # Squeaky/Child
    "robot": "en-US-SteffanNeural",   # Robotic/Formal
    "squirrel": "en-US-AnaNeural",    # Squeaky
    "superhero": "en-US-ChristopherNeural", # Deep/Heroic
    "old_man": "en-US-RogerNeural",   # Grumpy/Old
    "mafia_cat": "en-US-RogerNeural", # Deep/Raspy/Boss-like
    "orange_cat": "en-US-AvaNeural",  # Girly/Energetic
    "default": "en-US-GuyNeural"      # High Energy
}

CARTOON_AUDIO_CONFIG = {
    "rabbit": {"pitch": "+25Hz", "rate": "+25%"},
    "squirrel": {"pitch": "+35Hz", "rate": "+30%"},
    "robot": {"pitch": "-15Hz", "rate": "+10%"},
    "superhero": {"pitch": "-5Hz", "rate": "+15%"},
    "old_man": {"pitch": "-20Hz", "rate": "-5%"},
    "mafia_cat": {"pitch": "-10Hz", "rate": "-5%"},
    "orange_cat": {"pitch": "+15Hz", "rate": "+10%"},
    "default": {"pitch": "+0Hz", "rate": "+15%"}
}

def star_hint(stream=None):
    """One line after a finished run in a terminal, asking for a GitHub star. Not printed into pipes or logs (the web app, CI), and
    SHORTSFLOW_NO_STAR_HINT=1 turns it off."""
    import os, sys
    stream = stream or sys.stdout
    if os.getenv("SHORTSFLOW_NO_STAR_HINT") or not getattr(stream, "isatty", lambda: False)():
        return False
    print("\nLiked the result? A star helps others find this free, local tool: https://github.com/ghost1412/shortsflow", file=stream)
    return True


def cue_text(seg):
    """The text of a subtitle cue: the words the segment still has (a clip keeps only the words inside it), else its own text."""
    words = seg.get("words")
    if words:
        text = " ".join("".join(str(w.get("word", "")) for w in words).split())
        if text:
            return text
    return str(seg.get("text", "")).strip()


def clip_cues(segments, start, end):
    """Subtitle segments of one clip [start, end] (source seconds) on the clip's own timeline. A segment that starts before the clip or ends after
    it keeps only the words inside it ("And how is ..." is not shown when the clip begins after the "And"); a segment without word times
    keeps its text and its times clamped to the clip."""
    out, length = [], end - start
    for seg in segments:
        if seg["end"] <= start or seg["start"] >= end:
            continue
        words = [dict(w, start=float(w["start"]) - start, end=float(w["end"]) - start) for w in seg.get("words") or []
                 if isinstance(w, dict) and "start" in w and "end" in w and float(w["end"]) > start and float(w["start"]) < end]
        if seg.get("words"):
            if not words:
                continue
            cue = dict(seg, words=words, start=max(0.0, words[0]["start"]), end=min(length, words[-1]["end"]))
        else:
            cue = dict(seg, start=max(0.0, seg["start"] - start), end=min(length, seg["end"] - start))
        cue["text"] = cue_text(cue)
        if cue["text"]:
            out.append(cue)
    return out


def export_srt(transcript_data, output_path):
    """Exports transcript segments to a standard .srt file."""
    segments = transcript_data.get('segments', [])
    if not segments: return
    
    def format_time(seconds):
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
        
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, seg in enumerate(segments, 1):
            start = format_time(seg.get('start', 0))
            end = format_time(seg.get('end', 0))
            text = cue_text(seg)
            f.write(f"{i}\n{start} --> {end}\n{text}\n\n")

def print_clip_score_table(highlights):
    """Prints a formatted table of clip scores to the console."""
    if not highlights: return
    print("\n" + "="*85)
    print(f"{'CLIP SCORE RANKING':^85}")
    print("="*85)
    print(f"{'Rank':<5} | {'Start':<8} | {'End':<8} | {'Score':<10} | {'Reason'}")
    print("-" * 85)
    for i, h in enumerate(highlights):
        # Look for the best available score (supports our hybrid engine output)
        score = float(h.get('final_score', h.get('viral_score', h.get('score', 0))))
        
        # Check if LLM score specifically exists for display suffix
        if 'llm_score' in h and h['llm_score'] is not None:
            score_str = f"{score:.1f} (LLM)"
        else:
            score_str = f"{score:.1f}"
            
        reason = str(h.get('reason', h.get('llm_reason', h.get('hook_text', 'Viral Moment'))))
        print(f"#{i+1:<4} | {h['start']:<7.1f}s | {h['end']:<7.1f}s | {score_str:<10} | {reason[:40]}")
    print("="*85 + "\n")


def batch_item_command(argv, item, index, python="python", entry=("-m", "shortsflow"), as_category=False):
    """Command line for one batch item: the user's own arguments (so --use_remotion, --layout, --find, --cut, --brand,
    ... all carry over), minus the batch/per-item options, plus this item's source and output file."""
    drop_with_value = {"--batch_file", "--source_video", "--output_json", "--session_dir"}
    if as_category:   # a topic line (not a video): generate modes take it as the category
        drop_with_value = drop_with_value | {"--category"}
    out, skip = [], False
    for a in argv:
        if skip:
            skip = False
            continue
        name = a.split("=", 1)[0]
        if name in drop_with_value:
            skip = "=" not in a
            continue
        out.append(a)
    cmd = [python, *entry, *out, "--category" if as_category else "--source_video", item]
    if "--output_json" in argv or any(a.startswith("--output_json=") for a in argv):
        cmd += ["--output_json", f"batch_out_{index}.json"]
    return cmd

