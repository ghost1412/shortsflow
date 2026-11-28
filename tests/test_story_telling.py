"""A story video is asked for as a told story: in order, the ending last, nothing about the tale; an explainer keeps its own rules."""
from engine import case_study as cs

SOURCES = [{"id": "S1", "ref": "https://example.org", "text": "A poor man stood in a cold lake all night."}]


def test_the_story_is_asked_for_as_a_told_story():
    prompt = cs.build_prompt("The cold lake", cs.PRESETS["story"], SOURCES)
    assert "TELLS a story" in prompt and "not how it ends" in prompt and "Nothing about the story itself" in prompt
    assert "dates and figures from the sources" not in prompt and "VOICE: the narration is SPOKEN" not in prompt
    assert "most dramatic or surprising moment of this story? Say it in the first sentence" not in prompt
    assert "Use ONLY the facts in these sources" in prompt                       # still only what the sources say
    assert [s["id"] for s in cs.PRESETS["story"]] == ["opening", "trouble", "turn", "climax", "end"]
    assert "Return raw JSON only:" in prompt and "told as a story to a listener" in prompt and "in this order:" in prompt


def test_an_explainer_is_asked_for_as_before():
    other = next(k for k in cs.PRESETS if k != "story" and not any(s.get("scene") == "story" for s in cs.PRESETS[k]))
    prompt = cs.build_prompt("Heat pumps", cs.PRESETS[other], SOURCES)
    assert "VOICE: the narration is SPOKEN" in prompt and "dates and figures from the sources" in prompt and "TELLS a story" not in prompt
    assert "in this order:" in prompt and "Return raw JSON only:" in prompt and "told like a presenter talking" in prompt
