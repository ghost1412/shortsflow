# ShortsFlow Launch Drafts

Post from your own accounts. Edit freely - keep the honest tone; HN and Reddit punish hype.
Best timing: Show HN on a weekday morning US Eastern; stay around for the first 2 hours to answer comments.
Drafts last checked against the code on 2026-11-28. Check them again before posting: the tool changes quickly.

## Before you post (checklist)

- [ ] **The release people will download has the fixes in the changelog's "Unreleased" section.** 0.9.5 does not: among other things, its speaker switching often shows the silent listener
- [ ] `pip install shortsflow` works in a fresh environment; `shortsflow doctor` shows no missing required item; `shortsflow clip some_video.mp4` makes shorts with no keys
- [ ] The Windows installer (on the latest GitHub release) has been run end to end on a PC that is not yours (or a fresh VM) and made a short; mention the SmartScreen "More info > Run anyway" step in your post
- [ ] GHCR package `ghcr.io/ghost1412/shortsflow` is public and `docker run` starts the browser app
- [ ] Colab notebook runs top to bottom
- [ ] CI badge on the README is green
- [ ] README demo GIFs load and each credits its source and licence
- [ ] You have watched, with sound, every video or GIF you link in the post
- [ ] Each venue's self-promotion rules allow the post from your account (Show HN and some subreddits restrict new or low-activity accounts)

## What to show

- **Long video to Shorts:** moments picked, cut to 9:16, captioned. No account or API key needed to clip.
- **Highlights video:** the best moments of a long recording in order, with chapters, subtitles and optional cold open and pause cutting.
- **Also in the same tool:** dubbing into another language, explainer videos from your sources, trip and event recaps, a voice-over in your own cloned voice (needs the optional voice server). The animated story look is experimental.
- **Ask for moments:** `--find "where they discuss pricing"`. **Edit by transcript:** `--cut "you know"`, or delete words in `transcript.txt` and re-run with `--edit_transcript`.
- **Runs on your PC:** Whisper locally, an Ollama model for the text work, Kokoro for narration (`--tts_provider kokoro`; the default narrator is Microsoft's online Edge voice).

---

## 1. Show HN

**Title** (max 80 chars):
Show HN: ShortsFlow – open-source, local-first alternative to Opus Clip

**URL:** https://github.com/ghost1412/shortsflow

**Text:**
I built ShortsFlow to make vertical Shorts from long videos without paying per minute for a clipping service or uploading my footage to one.

On Windows there is a one-click installer (no Python or API key needed): open it, paste a link or drop in a video, press a button. Otherwise `pip install shortsflow` (or Docker, or Colab) and `shortsflow clip my_video.mp4` works with no key. Under the hood:

- Whisper transcribes on your machine with word timestamps; the best moments are picked and, if you have an AI model (a local Ollama one is enough) or a key, ranked and titled. FFmpeg cuts 9:16 clips with face tracking, and the animated captions are rendered with Remotion.
- `--find "where they discuss pricing"` clips only the moments that match.
- You can edit a video by editing its transcript.
- The same tool makes a highlights video, dubs into another language, and makes explainer videos from your own sources. There is a REST API with webhooks and an MCP server.

What leaves your PC: your video does not. If you add an AI provider's key, transcript text goes to that provider, and a few other options (stock footage, online voices, publishing) are listed in the guide. With Ollama and the Kokoro voice, clipping needs nothing online beyond the video you give it. MIT licensed.

Honest limitations: switching the camera between two speakers is the weakest part. It judges from mouth movement and voice pitch, can pick the wrong person, and often shows both when it is unsure; I have checked it on very few interviews. Moment picking is useful but not as good as a human editor, so expect to discard some clips. A small local model sometimes writes weak or wrong titles. The Windows installer is not code-signed (SmartScreen will warn you), the download is a few GB, and transcribing a long video on a CPU is slow.

I'd love feedback on clipping quality and on which features are worth keeping.

---

## 2. r/selfhosted

**Title:** ShortsFlow – self-hosted Opus Clip alternative: long videos to captioned Shorts (pip/Docker, local Whisper, MIT)

**Body:**
Hi r/selfhosted! I've been building an open-source tool that makes short vertical videos from long ones on your own machine.

- **Clipping:** YouTube link or local file → local Whisper → moment picking → 9:16 clips with face tracking and animated captions
- **Highlights video:** the best moments of a long recording, with chapters and subtitles
- **Ask for moments:** `--find "where they discuss pricing"`
- **Edit by transcript:** delete words from a text file and the video follows
- **Two people on screen:** it tries to cut to whoever is speaking, or shows both stacked when unsure (the weakest part; it can pick the wrong one)
- **Local:** Whisper on your GPU, Ollama for the text work, Kokoro for narration. Cloud AI, stock footage, online voices and publishing are optional
- **Automate it:** REST API with API keys and signed webhooks
- **Install:** a Windows installer from the Releases page (unsigned, so SmartScreen warns), `pip install shortsflow` then `shortsflow clip video.mp4`, `docker run -p 7860:7860 ghcr.io/ghost1412/shortsflow`, or the Colab notebook

Repo: https://github.com/ghost1412/shortsflow

Feedback and issues welcome. ROADMAP.md lists what's open.

*(Check the subreddit's self-promotion rules first; some require mod approval or a flair like "Release".)*

---

## 3. r/LocalLLaMA (angle: runs on local models)

**Title:** Open-source Shorts clipper that runs on local models (Whisper + Ollama + Kokoro), with a REST API and MCP server

**Body:** Lead with the local stack: Whisper on the GPU, an Ollama model for ranking, titles and `--find`, Kokoro for narration. Choosing Ollama (`--llm_provider ollama`) means no text goes to a cloud model. Left on automatic, the app tries the providers you have keys for first and then Ollama, so say which you mean. Be plain that a 7B model is enough to rank moments but its titles and notes are sometimes weak or wrong.

---

## 4. MCP directories

Short description (reuse everywhere):
> ShortsFlow MCP server: make vertical Shorts from a topic or cut moments out of a long video, dub a video, or make an explainer. Tools: generate_short, extract_clips, create_explainer, dub_video, generate_social_package, publish_video, get_render_status, list_videos, list_supported_modes. Local-first, MIT.

- **awesome-mcp-servers** (github.com/punkpeye/awesome-mcp-servers): one line under a media/video category:
  `- [ghost1412/shortsflow](https://github.com/ghost1412/shortsflow) 🐍 🏠 - Generate Shorts from topics or clip YouTube videos into captioned vertical shorts.`
- **Smithery** (smithery.ai): sign in with GitHub → "Add server" → point at the repo (`mcp_server.py`, stdio).
- **Glama** (glama.ai/mcp/servers): "Add server" with the repo URL.

---

## 5. Product Hunt (optional, later)

Tagline: "Open-source Opus Clip - local Shorts from any long video"
Wait until the installer, Colab notebook and Docker image are confirmed working; most visitors won't install from source.
