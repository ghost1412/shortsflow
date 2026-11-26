"""A line the model left out is asked for once more, alone."""
import json
import re

from engine import dubbing


def segments(n):
    return [{"start": i * 2.0, "end": i * 2.0 + 1.5, "text": f"line {i}"} for i in range(n)]


def model(skip_first_time=(), never=()):
    asked = []

    def llm(prompt):
        rows = json.loads(re.search(r"^Lines: (.*)$", prompt, re.M).group(1))
        asked.append([r["text"] for r in rows])
        out = [{"id": r["id"], "text": "es " + r["text"]} for r in rows
               if r["text"] not in never and not (r["text"] in skip_first_time and len(asked) == 1)]
        return json.dumps({"translations": out})
    return llm, asked


def test_only_the_missed_lines_are_asked_again_and_put_back_in_their_places():
    llm, asked = model(skip_first_time=("line 1", "line 3"))
    segs, missed = segments(5), []
    texts, failed = dubbing.translate_segments(segs, "es", llm=llm, failed_ids=missed)
    assert failed == 2 and missed == [1, 3]
    texts, still = dubbing.retry_untranslated(segs, texts, missed, "es", llm=llm)
    assert texts == [f"es line {i}" for i in range(5)] and still == []
    assert asked[-1] == ["line 1", "line 3"]


def test_a_line_that_fails_again_stays_in_the_source_language_with_its_own_id():
    llm, _ = model(skip_first_time=("line 1",), never=("line 3",))
    segs, missed = segments(5), []
    texts, _count = dubbing.translate_segments(segs, "es", llm=llm, failed_ids=missed)
    texts, still = dubbing.retry_untranslated(segs, texts, missed, "es", llm=llm)
    assert texts[1] == "es line 1" and texts[3] == "line 3" and still == [3]
