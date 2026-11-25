# Clip quality benchmark

How good are the clips ShortsFlow picks **without any AI key**? This page is measured, not claimed. The numbers come from
`.github/workflows/clip_benchmark.yml`, which runs the real pipeline on public videos on GitHub's runners (CPU, Whisper `base` model, no
API keys, no upload) and then `python scripts/clip_benchmark.py bench --picture`. Nothing here was picked by hand.

**Run:** 2026-11-12, main at commit 305e9ae (version 0.7.6 plus the fixes made after an independent code review). Shorts mode: 5 clips, target 30 s, `--smart_crop --tighten --layout auto`.

## Results

| Video (public) | Clips | Start / end on a sentence | Overlap | Length near target | Hook ok | Hook cue | Self-contained | Clean end | Titles grounded | Face found | Jitter | Silence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Two-speaker space podcast, 35 min | 5 | 1.0 / 1.0 | 0 s | 1.0 | 0.8 | 0.4 | 1.0 | 1.0 | 1.0 | 0.88 | 0.018 | 0.03 |
| NASA interview (Star Talk), 22 min | 5 | 1.0 / 1.0 | 0 s | 1.0 | 0.8 | 0.6 | 0.8 | 1.0 | 1.0 | 1.0 | 0.025 | 0.03 |
| Slides talk (screen recording), 21 min | 5 | 1.0 / 1.0 | 0 s | 1.0 | 0.8 | 0.4 | 1.0 | 1.0 | 1.0 | 0.0 (no presenter on screen) | n/a | 0.13 |
| Stage keynote, 25 min, 534x300 source | 5 | 1.0 / 1.0 | 0 s | 0.4 | 1.0 | 0.4 | 1.0 | 1.0 | 1.0 | 0.75 | 0.193 | 0.02 |

Highlights video (`--extract_mode long`, 180 s target) on the NASA interview: 4 moments, **169.3 s** (target 180 s, 6% short), every edge on a sentence,
no overlap, hook ok 1.0, hook cue 0.75, self-contained 0.75, clean end 1.0, titles grounded 1.0.

All five videos are public domain or Creative Commons and are used only as test input: NASA footage (public domain, Wikimedia Commons),
the space podcast (public domain), the keynote (CC0, Internet Archive), the slides talk (CC BY-SA 4.0, Wikimania 2021).

## What each number means

All values are shares of clips from 0 to 1 unless noted; higher is better except overlap, jitter and silence.

- **Start / end on a sentence:** the clip starts where a sentence starts and stops where one ends (no cut mid-word or mid-thought).
- **Overlap:** seconds where two clips show the same moment.
- **Length near target:** within 25% of the asked length (here 22.5 to 37.5 s). A clip that gives up a few seconds to end on a complete sentence can fall outside it.
- **Hook ok:** the clip opens on a line that stands alone: a word within 1.5 s, not a filler or connective ("and", "uh", "so,"), and a full first sentence (a short question counts).
- **Hook cue:** the first 3 seconds hold a reason to keep watching: a question, a number (any digit, so "In 2019, ..." counts), or a promise word ("never", "why", "how", "mistake", "secret"). The picker looks for the same cue in a clip's first sentence, so this is a rule the picker itself aims at, not an independent judgement of how catchy the line is.
- **Self-contained:** the first word is not a pronoun that points at something said before the clip ("They said ...", "This is why ...").
- **Clean end:** the last sentence does not stop on a word that needs a continuation ("... the places that"). The rule is narrow and the picker applies it too, so a score of 1.0 means little on its own.
- **Titles grounded:** the title and description say only what the clip says (a number or name that is not in the transcript counts as invented).
- **Face found / jitter:** on the finished 9:16 clips, the share of sampled frames with a face and how much the crop moves between samples (lower is steadier).
- **Silence:** share of the clip that is silent, measured on the finished file after `--tighten`.

## Weak spots, honestly

- **Hook cue is low without an AI key** (0.4 to 0.6 on all four videos, 0.75 on the highlights reel). The picker only looks at signals and a few opening rules; an AI key lets it judge the hook itself. This is the clearest gap against tools that always use an AI.
- **Low-resolution sources track poorly.** The keynote video is 534x300, a face is only a few pixels wide, and the crop jitters (0.193). Use the original resolution when you have it.
- **Slides and screen recordings have no face to follow.** ShortsFlow fits the whole picture over a blurred copy instead of cropping, which keeps the content but makes small text small.
- **Silence on the slides talk is 0.13.** Long quiet stretches inside a screen recording stay in the clip when words are nearby.
- **Length can miss the target** when a clip runs on to finish a sentence: three videos score 1.0, but on the keynote only 2 of 5 clips are within 25% of 30 s (clips of 39.7 s, 39.3 s and 21.7 s). Since then a clip aimed at a length is no longer finished past 125% of it when the sentence before still gives 75% (offline, on the keynote transcript: 4 of 5 clips within 25% of 30 s, was 2 of 5; the full video benchmark has not been rerun).
- **Picking quality is the weakest number.** Against a gold set of best moments (`docs/gold/`, up to five per video, **labelled by an AI model, not by people**), the picker without an AI key reaches a mean recall of 0.15 and precision of 0.30 on the four public videos; with a Groq key, 0.20 and 0.41 (four runs, mixed: better on two videos, worse on one). With so few moments per video these numbers are soft. That is why ShortsFlow has a review step (tick \"Let me review the moments first\") and why the tool never edits your source video: it proposes, you decide. A hand-labelled gold set is the next thing to add.
- **No comparison with Opus Clip yet.** These numbers measure ShortsFlow against its own rules, several of which the picker uses too. They do not show that the clips are better than a competitor's. A side-by-side on public footage is the next thing to publish; recall and precision against a set of "best moments" (`--gold`) are in the next item.
- **One run per video, Whisper `base` on CPU.** The `medium` or `large` models are more accurate (and much faster on a GPU). Results vary a little between runs because the picker is not seeded.

## Picking beyond the final clips: recall@k

A run now saves every moment that was in the running, best first, as `candidates.json` in its session folder. With `--gold`,
`scripts/clip_benchmark.py` adds **recall@5** and **recall@8**: the share of gold moments among the best 5 and best 8 candidates.
Recall@8 above recall@5 means the picker had the moment within reach and ranked it too low; equal values mean it never saw it.

For quick work on the picking rules there is an offline benchmark on the transcripts of the four public videos
(`docs/gold/transcripts/`): no video, no AI, no network, under a minute. It leaves out the loudness and motion signals, so the
workflow above stays the full measure.

```bash
python scripts/picker_bench.py                  # against the model-labelled gold sets
python scripts/picker_bench.py --suffix _human  # against docs/gold/<name>_human.json, once a person has labelled them
```

Transcript-only baseline, no AI key (2026-11-17, model-labelled gold): mean recall 0.12, precision 0.25, recall@8 0.20.

With the opt-in local rerank (`SHORTSFLOW_LOCAL_RERANK=1`, `qwen2.5:7b` on Ollama, 15 candidates, one request, a single run per video): recall 0.12, precision 0.30, recall@8 0.25. The 15 candidates hold 44% of the gold moments (recall@15), so most of what the picker misses it never proposes; a 7B model rates nearly every clip 7 to 9 and does not separate them well. Run to run the ranking varies (the model is not seeded), so treat these as soft.

## Reproduce

```bash
# on GitHub: Actions -> Clip Benchmark -> Run workflow (paste any direct video URL; mode "long" for a highlights video)
# locally, on a finished session folder:
python scripts/clip_benchmark.py sessions/<name> --picture
```
