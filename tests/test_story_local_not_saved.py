"""People planned by the model on this PC are not kept for later videos, also when the cloud chain itself ended at Ollama."""
import json

from engine import case_llm, case_story, script_gen

SCRIPT = {"title": "T", "sections": [{"id": "a", "title": "t", "scene": "story", "narration": "Gretel walks home."}]}
REPLY = json.dumps({"characters": {"Gretel": {"figure": "man"}}, "sections": [{"beats": [{"sentence": 1, "character": "Gretel"}]}]})


def run(tmp_path, monkeypatch, answered_locally):
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(tmp_path / "lib"))

    def cloud(prompt, system):
        script_gen.LAST_ANSWERED_LOCALLY = answered_locally
        return REPLY
    ask = case_llm.make_ask("s", "auto", cloud=cloud, local=lambda p, s: REPLY)
    assert case_story.plan(SCRIPT, ask, str(tmp_path / "run"), library={})
    return ask, case_story.load_library(str(tmp_path / "lib"))


def test_the_chain_that_ends_at_ollama_counts_as_local_and_nothing_is_saved(tmp_path, monkeypatch, capsys):
    ask, library = run(tmp_path, monkeypatch, True)
    assert ask.last_source == "local" and library == {}
    assert "planned by the model on this PC" in capsys.readouterr().out


def test_a_cloud_plan_is_saved_as_before(tmp_path, monkeypatch):
    ask, library = run(tmp_path, monkeypatch, False)
    assert ask.last_source == "cloud" and "Gretel" in library
