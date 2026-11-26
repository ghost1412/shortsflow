"""The example in the art director's prompt shows the shape only: a model that copies it gets no picture, not somebody else's."""
import json
import re

from engine import art_kit as kit
from engine import case_art


def test_a_reply_that_copies_the_prompts_example_is_refused():
    section = {"title": "What it is", "narration": "Magma and rock come out of a vent.", "on_screen": ["magma", "rock"]}
    prompt = case_art.request(section, "volcanoes", ["magma", "rock"])
    example = re.search(r'^\{"setting".*\}$', prompt, re.M).group(0)
    json.loads(example)                                                 # the shape itself is valid JSON
    spec, problem = case_art.check_spec(example, 2)
    assert spec is None and problem
    assert not [k for k in kit.ICONS if f'"kind": "{k}"' in prompt]     # no ready-made icon is offered as an answer
