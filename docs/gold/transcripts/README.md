# Transcripts of the public test videos

Word-timed Whisper `base` transcripts (CPU, from the Clip Benchmark workflow) of the four public videos in `docs/BENCHMARKS.md`, kept so
`python scripts/picker_bench.py` can measure the moment picker in seconds, with no video, no AI and no network.

| File | Video | Licence of the source |
|---|---|---|
| `podcast_space.json` | Two-speaker space podcast, 35 min | Public domain |
| `nasa_interview.json` | NASA interview (Star Talk), 22 min | Public domain (NASA, Wikimedia Commons) |
| `keynote.json` | Stage keynote, 25 min | CC0 (Internet Archive) |
| `slides_talk.json` | Slides talk, 21 min, Wikimania 2021 | CC BY-SA 4.0; this transcript is a derivative and is shared under CC BY-SA 4.0 too |

The transcripts are machine-made and contain Whisper's mistakes on purpose: the picker has to work with what Whisper gives it.
Only `start`, `end`, `text` and the word times are kept.
