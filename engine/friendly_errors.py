"""Plain-language explanations for the errors a first-time user actually hits (bad key, no credits, rate limit, offline)."""
import re


def explain_http_error(error, provider="the AI service"):
    """One-line fix for an LLM/API failure, or None when nothing useful can be said. `error` is an exception or text."""
    text = str(error)
    code = None
    m = re.search(r"\b(40[0-9]|42[0-9]|50[0-9])\b", text)
    if m:
        code = int(m.group(1))
    low = text.lower()
    if code == 402 or "payment required" in low or "insufficient" in low and "credit" in low:
        return (f"{provider} says this account has no credits left. Add credits there, or use a free option instead: "
                "put a free GROQ_API_KEY (console.groq.com) in your .env, or install Ollama (ollama.com) to run it on your PC.")
    if code in (401, 403) or "invalid api key" in low or "unauthorized" in low:
        return (f"{provider} rejected the API key. Copy the key again with no spaces or quotes into your .env file "
                "(and check it has not expired).")
    if code == 429 or "rate limit" in low or "quota" in low:
        return (f"{provider} is rate limiting you (free-tier limit reached). Wait a minute and retry, or add a second key "
                "such as GROQ_API_KEY as a fallback.")
    if code and code >= 500:
        return f"{provider} is having problems right now (error {code}). Retry in a few minutes."
    if any(w in low for w in ("connection refused", "connection error", "max retries", "timed out", "timeout", "name resolution",
                              "getaddrinfo")):
        return (f"Could not reach {provider}. Check your internet connection"
                + (" - or start Ollama if you meant to use it locally." if "11434" in text or "ollama" in low else "."))
    return None


NO_LLM_HELP = (
    "No AI text provider answered. Clipping long videos into shorts works without one, but titles, descriptions and idea-to-video "
    "modes need one. Easiest free fixes: (1) get a free key at console.groq.com and add GROQ_API_KEY=... to your .env, "
    "or (2) install Ollama from ollama.com and run `ollama pull qwen2.5:7b`. Run `shortsflow doctor` to check your setup."
)


_RUN_FAILURES = [
    # (words that must all be in the lower-cased log text (any one of the groups), what to tell the user)
    ([("ffmpeg", "not found"), ("ffmpeg", "no such file"), ("ffprobe", "not found"), ("'ffmpeg' is not recognized",)],
     "FFmpeg was not found. Install it (Windows: `winget install Gyan.FFmpeg`; Mac: `brew install ffmpeg`; Linux: `sudo apt install ffmpeg`), "
     "then close and reopen this program so it is on your PATH."),
    ([("node", "not found"), ("npm", "not found"), ("'node' is not recognized",), ("remotion", "enoent")],
     "Node.js was not found, and the animated captions need it. Install Node.js 18 or newer from nodejs.org and restart this program, "
     "or turn off animated captions."),
    ([("nvenc",), ("openencodesessionex",), ("no capable devices found",), ("cuda_error_out_of_memory",), ("cuda out of memory",)],
     "The graphics card could not be used for encoding or transcribing (another program, often a game, may be using it). Close that "
     "program and run again; the tool retries on the processor automatically for encoding, which is slower."),
    ([("huggingface.co", "connection"), ("whisper", "urlopen error"), ("snapshot_download",), ("failed to download", "model")],
     "The speech model could not be downloaded (it is fetched once, a few hundred MB). Check your internet connection and run again."),
    ([("no space left on device",), ("not enough space on the disk",), ("errno 28",)],
     "The disk is full. Free some space (the finished videos and the `sessions/` folder are the big ones) and run again."),
    ([("video unavailable",), ("private video",), ("sign in to confirm",), ("http error 403",), ("unable to download",)],
     "That link could not be downloaded (private, removed, age- or region-limited, or the site blocked the download). Download the video "
     "yourself and use the file instead."),
]


def explain_run_failure(log):
    """One plain sentence for the most likely cause of a failed run, read from its log text; None when nothing matches."""
    low = str(log or "").lower()
    for groups, message in _RUN_FAILURES:
        if any(all(word in low for word in group) for group in groups):
            return message
    return None
