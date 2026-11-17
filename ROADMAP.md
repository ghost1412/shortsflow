# ShortsFlow: status and how to verify changes

For agents and people working on this repo. Read [AGENTS.md](AGENTS.md) first for architecture and commands.
What changed in each release is in [CHANGELOG.md](CHANGELOG.md); measured clip quality is in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

_Last updated: 2026-11-17_

- **Never** push generated media, `.env`, `token*.json` or `client_secrets*.json`.
- `main` feeds a scheduled channel (`.github/workflows/daily_generate.yml`): anything that changes the scheduled output must be
  render-checked first (see *Verifying changes*).

### Hot-spot files (keep edits small, one change at a time)
| File | Why it's risky |
|---|---|
| `engine/video_gen.py` (~3.6k lines) | Cutting, cropping and rendering of every clip; `extract_segments` is one long function |
| `engine/modes/clip_extract.py` | The whole clip path in one `run()` |
| `engine/analysis.py` | Transcription and moment picking; a change here moves the benchmark numbers |
| `engine/modes/generate.py` (~1.3k lines) | The idea-to-video path the scheduled channel runs |
| `engine/script_gen.py` (~2.7k lines) | All LLM prompts and the provider fallback chain (Gemini → Ollama → HuggingFace) |
| `engine/trip_recap.py` (~2.6k lines) | The recap modes |
| `webui.py` (~2k lines) | The browser app; several tests depend on the order of its form values |
| `remotion-video/src/ShortFlow.tsx` (~2.3k lines) | Single composition used by every Remotion mode |
| `.github/workflows/daily_generate.yml` | Runs the scheduled channel |

---

## Verifying changes

| What | Command |
|---|---|
| Tests | `python -m pytest` (offline, a few minutes) |
| Python syntax | `python -m py_compile main.py engine/*.py engine/modes/*.py webui.py mcp_server.py` |
| Remotion types | `cd remotion-video && npx tsc --noEmit -p .` (must be 0 errors - CI enforces it) |
| CI | `tests.yml` (pytest + tsc + lint, every push/PR), `e2e.yml` (real FACTS render) |
| Clip picking | `python scripts/picker_bench.py` (offline, seconds); full measure: the Clip Benchmark workflow, see [docs/BENCHMARKS.md](docs/BENCHMARKS.md) |
| Clip quality of a run | `python scripts/clip_benchmark.py <session> --picture` |
| Full FACTS render **without an LLM key** | `python scripts/offline_facts_render.py` → `sessions/offline_test/*.mp4` (needs `PEXELS_API_KEY`, Node, FFmpeg) |
| Real FACTS render | `python main.py --mode FACTS --use_remotion --skip-upload` (needs an LLM key) |
| Inspect frames | `ffmpeg -ss 9 -i <video>.mp4 -frames:v 1 frame.jpg` |
| WebUI | `python webui.py` → http://localhost:7860 |

`main.py` exits **non-zero** when nothing is rendered, so a red Actions run means no video was posted.

---

## Recently done

See [CHANGELOG.md](CHANGELOG.md) for the full list. Highlights since the first public release:

- Browser app with a review step (the tool proposes moments, you keep or drop them), dubbing, recaps and photo reels
- `pip install shortsflow`, Windows installer, `install.sh`, Docker image, MCP server, REST API with webhooks
- Active-speaker layouts, face-safe captions, auto-enhance, word-level cuts after a render
- Clip benchmark on public videos with published weak spots, gold sets and an offline picker benchmark
- Scheduled channel: topic memory, second-pass fact check, weighted mode mix

---

## Known issues

- **Picking is the weakest number**: see "Weak spots, honestly" in [docs/BENCHMARKS.md](docs/BENCHMARKS.md). The gold sets are model-labelled.
- The bundled caption fonts are not loaded by the Remotion bundle; captions fall back to system fonts.
- Remotion props are not schema-validated at render time; `null` is passed for optional fields and works today.
- `get_video_duration` in `engine/modes/generate.py` returns 10.0 on ffprobe failure, which can mis-size backgrounds silently.
- The command line has many flags and no grouping in `--help`.
