# 🤖 ShortsFlow AI Studio - Agent Prompt & Onboarding Guide

> **System Prompt for AI Agents (Antigravity, Cursor, Claude Code, Copilot, AutoGPT, LLMs)**

Welcome Agent! This document provides structured architectural context, setup instructions, CLI capabilities, and operational guidelines for working with **ShortsFlow** (`shortsflow`).

---

## 🏗️ 1. Project Overview & Architecture

ShortsFlow AI Studio is an open-source, local-first AI video generator and automated clipping engine (an open-source alternative to Opus Clip).

### Tech Stack Components:
* **Core Pipeline (`main.py`)**: Slices, transcribes, scores hooks, crops 9:16 vertical video, and renders final shorts.
* **Transcription Engine (`Whisper / CUDA`)**: Local GPU-accelerated word-timestamped transcription.
* **Animation & Rendering Engine (`remotion-video/`)**: React-based video engine rendering high-retention spring captions (Hormozi, Glow Box, Bounce, Minimal).
* **Educational Explainer Engine (`Manim`)**: Renders programmatic 2D/3D math and computer science animations (`test_manim.py`).
* **Case Explainer (`--mode CASE`)**: a topic plus sources (web page, PDF, YouTube, audio or video file) in, a sectioned explainer video out (16:9 and 9:16): script written only from the sources, narration, drawn scenes, Manim animation, stock footage, captions, music. See `docs/FEATURES.md` and `python main.py --mode CASE --case help`.
* **Animated Explainer (`--mode ANIMATE`)**: the case pipeline with the `animation` template: one continuous Manim animation under the whole narration (equations, processes, diagrams). The old `--mode EXPLAINER` is separate and unchanged.
* **Browser App (`webui.py`)**: Gradio app (`shortsflow webui`) with a card per thing you can make, including the Case explainer. **CLI / pip**: `pip install shortsflow` gives the `shortsflow` command (`shortsflow doctor`, `init`, ...).
* **Desktop Studio GUI (`gui_app.py`)**: Single-window 3-column CustomTkinter studio interface with live 9:16 video canvas preview.
* **Automated CI/CD Workflows (`.github/workflows/daily_generate.yml`)**: GitHub Action for scheduled autonomous short generation and social posting.

---

## ⚙️ 2. Quick Setup & Environment Commands

### Prerequisites Check
* **Python**: `3.10+` (CI tests 3.10, 3.11 and 3.12; 3.12 is the one the docs assume)
* **Node.js**: `v18+` (Required for Remotion React video rendering)
* **FFmpeg**: Must be available in system `PATH`
* **Optional extras** (`pip install "shortsflow[clip,explainer,sources,webui]"`): Whisper and face tracking (`clip`), Manim (`explainer`, needed for case animations), `pypdf` for PDF sources (`sources`), Gradio (`webui`)

### 1-Click Installation & GUI Launch
```bash
# Windows Setup & Interactive Launcher
setup.bat
launch.bat  # Select Option 1 for Desktop Studio GUI

# Launch GUI directly via Python:
python gui_app.py

# Linux / macOS
chmod +x setup.sh && ./setup.sh
python3 gui_app.py

# Docker Container
docker compose up -d
```

### Required `.env` File Schema
```env
GEMINI_API_KEY=your_gemini_key_here
HF_API_KEY=your_huggingface_key_here
PEXELS_API_KEY=your_pexels_key_here
# optional: ELEVENLABS_API_KEY (narrator voice; without it the Edge voice is used), GROQ_API_KEY, OPENAI_API_KEY, ... see env.example for the full list
```

---

## 🎬 3. Execution Commands & Skills Reference

### Skill 1: Extract Shorts from Long Videos or YouTube Links
```bash
python main.py \
  --source_video "https://www.youtube.com/watch?v=YOUR_VIDEO_ID" \
  --extract_mode shorts \
  --clip_count 3 \
  --smart_crop \
  --tighten \
  --use_remotion \
  --caption_style HORMOZI
```

### Skill 2: Educational Math & Code Explainers (Manim)
```bash
python main.py \
  --mode EXPLAINER \
  --prompt "Explain how gravity works visually" \
  --skip-upload
```

### Skill 3: High-Retention AI Facts & Narrative Shorts
```bash
python main.py \
  --mode FACTS \
  --category "space mysteries" \
  --vibe "suspense" \
  --use_remotion \
  --caption_style GLOW_BOX
```

### Skill 4: Interactive Dilemma Challenges ("This or That")
```bash
python main.py \
  --mode WYR \
  --category "superpowers" \
  --use_remotion
```

### Skill 5: Case Explainer from a Topic and Sources
```bash
python main.py --mode CASE --prompt "The topic" --sources https://example.com/article
python main.py --mode CASE --prompt "The topic" --sources LINK --case theme=neon --case formats=16:9 --case background=images
python main.py --mode CASE --prompt "The topic" --sources LINK --case plan_only            # write the script, edit script.json, then:
python main.py --mode CASE --case resume=sessions/case_123 --case draft                    # a quick small render; drop `draft` for the full one
python main.py --mode CASE --case help                                                     # every option
```

### Skill 5b: Animated Explainer (one continuous animation)
```bash
python main.py --mode ANIMATE --prompt "The Pythagorean theorem and why it works" --sources https://example.com/article
python main.py --mode ANIMATE --prompt "How binary search halves the work" --case theme=blueprint --case formats=16:9
```

### Skill 6: Launch Single-Window Interactive Studio GUI
```bash
# Launch visual CustomTkinter 3-column studio layout
python gui_app.py
```

---

## 📜 4. Engine Codebase Map

| File Path | Functional Role |
| :--- | :--- |
| `main.py` | CLI entry point: argument parsing, quality presets and dispatch to `engine/modes/` |
| `gui_app.py` | Single-window 3-column CustomTkinter Desktop Studio application |
| `engine/media_gen.py` | Stock media downloader (Pexels API fallback), AI image generation |
| `engine/video_gen.py` | FFmpeg filters, face-tracking EMA, silence removal (`--tighten`) |
| `engine/remotion_renderer.py` | Bridge between Python pipeline and Node.js Remotion React renderer |
| `engine/voice_gen.py` | Text-to-Speech synthesizer (ElevenLabs / EdgeTTS) |
| `engine/script_gen.py` | Multi-LLM prompt orchestration (Gemini -> DeepSeek -> OpenAI -> local Ollama -> Groq -> HuggingFace fallback; `LLM_PROVIDER` or `--llm_provider` forces one) |
| `engine/pipeline.py` | Shared helpers used by `main.py` and mode pipelines (status reporting, SRT export, voice maps) |
| `engine/modes/*.py` | Pipelines, each with `run(args, target_bitrate, target_preset)`: `generate` (idea-to-video, all content modes), `clip_extract`, `music`, `explainer`, `photo_reel`, `video_filter` |
| `engine/modes/case.py`, `engine/case_study.py`, `engine/case_render.py`, `engine/case_options.py`, `engine/case_manim.py`, `engine/manim_kit.py`, `engine/manim_overlap.py`, `engine/case_footage.py`, `engine/case_sources.py`, `engine/case_sfx.py`, `engine/light_music.py` | `--mode CASE`: sources (web page, PDF, YouTube, audio or video file) -> a script written only from them (a template of sections; the model picks each layout) -> narration -> `remotion-video/src/CaseVideo.tsx` render (16:9 and 9:16); optional Manim animation built from a tested kit and checked for overlaps, Pexels footage or photos, synthesised music and sound effects. Options live in one schema (`engine/case_options.py`): `--case KEY=VALUE`, `--case help` |
| `engine/modes/animate.py` | `--mode ANIMATE`: hands the case pipeline the `animation` template (one section, one Manim animation over the whole narration) and `background=none` unless the user chose otherwise |
| `engine/mode_options.py` | Reusable option schema for a mode (`OptionSet`, `Option`): one `--<mode> KEY=VALUE` flag instead of a flag per option (house rule, section 5) |
| Also worth knowing | `engine/analysis.py` (transcription, highlight picking), `engine/highlight_rank.py` (LLM / local rerank), `engine/rerender.py` (redo one finished short), `engine/dubbing.py` (`--mode DUB`), `engine/transcript_edit.py` (`--cut`), `engine/clip_quality.py` + `scripts/picker_bench.py` (benchmarks), `shortsflow/workspace.py` (pip-install workspace, `doctor`), `shortsflow/review.py`, `shortsflow/brand.py`, `shortsflow/batch.py` |
| `engine/speaker_focus.py` | Active-speaker shot planning for `--layout active` |
| `engine/trip_recap.py` | `--mode TRIP` (own `run(args, ...)`): several travel videos -> one recap (hook, glimpses, day/stop cards, closing card, itinerary); look auto-decided from the footage; portrait + landscape versions; look-alike shot removal; sideways-clip fix |
| `engine/enhance.py` | Auto-enhance: measures frames of a video (tones, colour cast, saturation, noise) and builds an FFmpeg correction chain (`plan`, `build_filter`, `enhance_filter`); used by the trip recap and by clip extraction (`video_gen.extract_segments`) via `--enhance auto` |
| `engine/geo.py` | GPS from a video's `location` tag, grouping into places, OpenStreetMap name/attraction lookup (cached; `SHORTSFLOW_GEOCODE=off` or `--recap_no_geocode` disables it) |
| `engine/visual_context.py` | Picture descriptions for story-aware picking and the trip recap: Gemini when `GEMINI_API_KEY` is set (frames leave the PC), else local Ollama (`SHORTSFLOW_VISION=ollama` forces local); also scenery rating and sideways-frame check |
| `engine/drive_upload.py` | Optional upload of finished videos to a Google Drive folder (`--upload_drive`, `python -m engine.drive_upload`); needs the user's own OAuth client, never commit `client_secrets_drive.json` / `token_drive.json` |
| `engine/gphotos_album.py` | Download the videos of a Google Photos shared-album link (unofficial page parsing) for the trip recap |
| `shortsflow/settings.py` | Browser app Settings: the known API keys (masked, add/remove in `.env`), upload preferences (a small settings file in the workspace, auto-publish OFF by default), routing of tall/wide videos to platforms, publishing a finished run through `engine/publish.py` (never twice to the same platform: each run folder remembers where it went) |
| `shortsflow/reuse.py` | Browser app: seed a new run with an earlier run's transcript, descriptions, moments and cut pieces (never finished clips) |
| `webui.py` / `shortsflow/web_args.py` | Gradio browser app (tabs: Start here, Clip, Dub, Recap (trip, wedding, event, family), Photo reel, Generate) and the pure functions that turn its form values into CLI arguments (testable without gradio) |
| `tests/` | Offline pytest suite (`python -m pytest`), run in CI on every push/PR |
| `remotion-video/src/` | React video components & animated subtitle spring physics |

---

## 🛡️ 5. Operational Rules for AI Agents

1. **Repository Cleanliness**:
   * NEVER commit raw `.mp4` video outputs or binary assets from `assets/backgrounds/local/` into Git tracking.
   * Store temporary outputs inside `sessions/` or root directory (covered by `.gitignore`).
2. **Fallback Integrity**:
   * Always verify that `PEXELS_API_KEY` fallback works seamlessly when local background media is absent.
   * Maintain the Multi-LLM fallback order of `engine/script_gen.get_llm_response`: **Gemini -> DeepSeek -> OpenAI -> local Ollama -> Groq -> HuggingFace** (a key you did not set is skipped). A case-mode section whose Manim animation cannot be made keeps its plain scene, and an ElevenLabs failure drops to the Edge voice for the rest of the video: keep those fallbacks.
3. **Subtitles & Caption Positioning**:
   * Remotion captions use vertical `y_pos` offset defaulting to `1150` for 9:16 vertical resolution (1080x1920).
   * Left at the default, plain (non-Remotion) clip captions use the lower third (`video_gen.plain_caption_y`, 1400), and animated captions move to 1400 on close-up faces (`caption_layout.face_safe_y`). An explicit height or `--caption_position` is used as given.
   * Measure clip changes before and after with `python scripts/clip_benchmark.py <session> --picture`; try it on the public-domain sample (`shortsflow/sample.py`).
4. **Privacy of the optional cloud helpers**:
   * Everything runs locally by default. Only these leave the PC, and each is optional: Gemini/Groq/HF LLM calls (`--llm_provider`), Gemini picture descriptions (`--visual_context` with a key), OpenStreetMap place names (trip recap; off with `--recap_no_geocode`), Google Drive upload (only when asked), publishing through Upload-Post (the video and its title; only when you press Publish or switch on auto-publish in the app's Settings). Say so in any docs or UI text you add about them.
   * `--mode CASE` also sends: the text of its sources and the topic to the AI text provider, two to four word stock-footage search phrases to Pexels, and the narration text to ElevenLabs (or Edge). The audio of a YouTube video without captions is downloaded and transcribed on this PC. Say so in any docs or UI text you add about it.
   * Personal footage, its recaps and any user-pasted links (Drive, Photos) never go into the README, docs, tests or the CHANGELOG; use made-up ids in tests.
5. **Options of a mode** (house rule):
   * A mode takes its options through ONE schema (`engine/mode_options.py`: `OptionSet`, `Option`), as one repeatable flag `--<mode> KEY=VALUE` plus `--<mode>_file FILE.json`; see `engine/case_options.py` and `--mode CASE --case help`.
   * Do NOT add one command-line flag per option to `shortsflow/_main.py`. A new option is one line in the mode's schema; the browser tab builds its `--<mode>` pairs from the same schema (`web_args.case_args`), and a test pins the flag set.
   * Existing modes keep their old flags until someone touches them; when you do, move them into a schema and keep the old flags working (hidden) so nobody's scripts break.
6. **Verifying Work**:
   * Hot-spot files, verification steps and known issues live in **[ROADMAP.md](ROADMAP.md)**.
   * Verify rendering without an LLM key: `python scripts/offline_facts_render.py`.
