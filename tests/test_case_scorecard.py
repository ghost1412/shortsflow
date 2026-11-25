"""The scorecard of the case explainer's decisions (engine/case_scorecard.py): scoring, the table, the command and the runner, all offline."""
import json
import os

from engine import case_scorecard as sc

PAD = " ".join(["Every sentence here simply adds a few more spoken words."] * 5)         # a real section has 40 to 80 words, so none of the examples is thin

GOOD = {"title": "How a Rainbow Forms", "hook": "Can a rainbow really last for nearly nine hours?", "verified": True, "dropped": [],
        "sections": [
            {"id": "what", "scene": "illustration", "narration": "Sunlight hits water droplets and forms a circular arc. " + PAD, "on_screen": ["Sunlight", "Water droplets", "Circular arc"]},
            {"id": "how", "scene": "diagram", "narration": "Light bends inside each drop. " + PAD, "on_screen": ["Refraction", "Reflection"]},
            {"id": "why", "scene": "counters", "narration": "The angle is forty two degrees. " + PAD, "on_screen": ["42 degrees", "7 colours", "10 million viewers"]},
            {"id": "do", "scene": "checklist", "narration": "Stand with the sun behind you. " + PAD, "on_screen": ["Sun behind you", "Look at the rain"]},
        ]}
BAD = {"hook": "{", "verified": False, "dropped": [{"section": "what", "sentence": "x", "unsupported": "y"}],
       "sections": [
           {"id": "what", "scene": "illustration", "narration": "A refrigerator moves warmth outside.", "on_screen": ["Heat transfer", "External environment", "Vapor compression cycle"]},
           {"id": "why", "scene": "counters", "narration": "It was invented long ago.", "on_screen": ["1913 home invention", "2 x 10^25 molecules", "50 percent"]},
           {"id": "extra", "scene": "checklist", "narration": "Words.", "on_screen": ["a"]},
           {"id": "do", "scene": "checklist", "narration": "Words.", "on_screen": ["b"]},
       ]}


def test_a_good_script_passes_every_check():
    m = sc.score(GOOD)
    assert m["picture_sections"] == 1 and m["picture_labels"] == 3 and m["abstract_labels"] == 0 and m["spoken_labels"] == 3
    assert m["bad_counter_labels"] == 0 and m["hook_ok"] and m["fallbacks"] == 0 and m["removed_sentences"] == 0 and m["verified"]
    assert sc.passes(m)


def test_a_bad_script_is_marked_down_on_each_count():
    m = sc.score(BAD)
    assert m["abstract_labels"] == 3 and m["spoken_labels"] == 0 and m["bad_counter_labels"] == 2 and not m["hook_ok"]
    assert m["fallbacks"] == 1 and m["removed_sentences"] == 1 and not m["verified"] and not sc.passes(m)             # the template's last checklist is not a fallback
    assert not sc.passes(sc.score({"hook": "A real line about heat.", "sections": [{"id": "a", "scene": "quote", "narration": "x", "on_screen": []}]}))     # no picture scene


def test_labels_that_are_ideas_sentences_or_numbers_are_abstract_and_the_spoken_check_forgives_plurals():
    assert sc.is_abstract("Heat transfer") and sc.is_abstract("External environment") and sc.is_abstract("3 layers")
    assert sc.is_abstract("The film is placed on a crystal and compressed")
    assert not sc.is_abstract("Compressor") and not sc.is_abstract("Cold air") and not sc.is_abstract("Water droplets")
    assert sc.is_spoken("QR code", "Attackers use QR codes and phone calls.") and not sc.is_spoken("Dragon", "A fridge keeps food cold.")


def test_the_table_lists_each_topic_and_counts_the_passes():
    text = sc.table({"rainbow": sc.score(GOOD), "fridge": sc.score(BAD), "sky": "no script (timeout)"})
    assert "| rainbow | ? | 1 | 3/3 | 3/3 | 0 | ok | 0 | 0 | 0 | 0 |" in text and "| pass |" in text
    assert "| fridge | ? | 1 | 0/3 | 0/3 | 2 | BAD | 1 | 0 | 4 | 1 |" in text and "FAIL" in text
    assert "no script" in text and "1 of 3 topics pass every check." in text


def test_the_command_runs_the_script_step_only_for_a_known_topic():
    cmd = sc.command("fridge", "out/fridge", "short", "local", python="py")
    assert cmd[:4] == ["py", "main.py", "--mode", "CASE"] and "How a refrigerator keeps food cold, explained simply" in cmd
    assert "https://en.wikipedia.org/wiki/Refrigerator" in cmd and "plan_only" in cmd and "length=short" in cmd and "llm=local" in cmd and cmd[-2:] == ["--session_dir", "out/fridge"]
    assert set(sc.TOPICS) >= {"rainbow", "fridge", "vaccine", "phishing", "sky", "telescope", "versailles", "inflation", "digestion", "binsearch", "habeas", "sourdough"}


def test_the_runner_reads_the_script_each_run_wrote_and_survives_a_run_that_wrote_none(tmp_path):
    calls = []

    def runner(cmd, **kw):
        calls.append(cmd)
        folder = cmd[cmd.index("--session_dir") + 1]
        if "rainbow" in folder:
            with open(os.path.join(folder, "script.json"), "w", encoding="utf-8") as f:
                json.dump(GOOD, f)
    results = sc.run(["rainbow", "fridge"], str(tmp_path), runner=runner, log=lambda m: None)
    assert len(calls) == 2 and isinstance(results["rainbow"], dict) and sc.passes(results["rainbow"])
    assert isinstance(results["fridge"], str) and results["fridge"].startswith("no script")



def test_thin_narration_and_sections_without_labels_fail_and_the_model_that_wrote_it_is_recorded(tmp_path):
    thin = {"hook": "A real line about the sky.", "sections": [
        {"id": "what", "scene": "illustration", "narration": "Short words here.", "on_screen": ["Sunlight", "Air"]},
        {"id": "do", "scene": "checklist", "narration": "Fine words " * 20, "on_screen": []}]}
    m = sc.score(thin)
    assert m["thin_sections"] == 1 and m["empty_sections"] == 1 and not sc.passes(m)
    assert sc.score(thin, "short")["thin_sections"] == 1 and sc.score({"hook": "x", "sections": [{"id": "a", "scene": "animation", "narration": "w " * 30, "on_screen": []}]})["empty_sections"] == 0

    class Done:
        def __init__(self, text):
            self.stdout, self.stderr = text, ""

    def runner(text):
        def run(cmd, **kw):
            folder = cmd[cmd.index("--session_dir") + 1]
            with open(os.path.join(folder, "script.json"), "w", encoding="utf-8") as f:
                json.dump(GOOD, f)
            return Done(text)
        return run
    cloud = sc.run(["rainbow"], str(tmp_path / "a"), runner=runner("all good"), log=lambda m: None)
    fell = sc.run(["rainbow"], str(tmp_path / "b"), runner=runner("[Log] The cloud text model did not answer (503); using the model on this PC from here on."), log=lambda m: None)
    assert cloud["rainbow"]["model"] == "cloud" and fell["rainbow"]["model"] == "local fallback"
    assert sc.run(["rainbow"], str(tmp_path / "c"), llm="local", runner=runner("x"), log=lambda m: None)["rainbow"]["model"] == "local fallback"
    text = sc.table({"rainbow": cloud["rainbow"], "sky": fell["rainbow"]})
    assert "| rainbow | cloud |" in text and "| sky | local fallback |" in text and "Written by the model on this PC" in text and "sky" in text.split("Written by the model on this PC")[1]
