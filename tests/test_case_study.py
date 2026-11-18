import json

import pytest

from engine import case_study as cs

SRC = "In March 2021 the Acme payment portal was breached. Attackers used a stolen password and reached 4,200 customer records."


def test_presets_have_four_sections_with_known_scenes():
    for name, sections in cs.PRESETS.items():
        assert len(sections) == 4
        assert all(s["scene"] in cs.SCENES for s in sections), name


def test_load_template_preset_file_and_errors(tmp_path):
    assert [s["id"] for s in cs.load_template("case")] == ["what", "how", "impact", "prevent"]
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"sections": [{"id": "a", "question": "Why?", "scene": "bogus"}]}), encoding="utf-8")
    assert cs.load_template(str(p)) == [{"id": "a", "title": "a", "question": "Why?", "scene": "quote"}]
    p.write_text(json.dumps([{"id": "a", "question": "x"}, {"id": "a", "question": "y"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        cs.load_template(str(p))
    with pytest.raises(ValueError):
        cs.load_template("nope")


def test_gather_sources_link_file_notes_and_skips(tmp_path):
    f = tmp_path / "n.txt"
    f.write_text("A long enough note about the case that has plenty of words in it for the test.", encoding="utf-8")
    pages = {"https://example.com/a": "<html><script>x=1</script><p>" + SRC + "</p></html>"}
    sources, skipped = cs.gather_sources(["https://example.com/a", str(f), "pasted notes that are also long enough to count as text", "https://example.com/dead", "x"],
                                         fetch=lambda u: pages[u])
    assert [s["id"] for s in sources] == ["S1", "S2", "S3"]
    assert "x=1" not in sources[0]["text"] and "Acme" in sources[0]["text"]
    assert sources[1]["ref"] == "n.txt" and sources[2]["ref"] == "pasted notes"
    assert len(skipped) == 2


def test_unsupported_finds_numbers_and_names():
    assert cs.unsupported("Attackers reached 4,200 records.", SRC) == []
    assert cs.unsupported("They stole 9,000 records.", SRC) == ["9,000"]
    assert "Zorblax" in cs.unsupported("The group called Zorblax did it.", SRC)
    assert cs.unsupported("Acme was breached.", SRC) == []


def reply(narration, on_screen=("Stolen password",), cites=("S1",)):
    return json.dumps({"title": "Acme breach", "sections": [{"id": "what", "narration": narration, "on_screen": list(on_screen), "cites": list(cites)}]})


def test_write_script_drops_unsupported_sentences():
    template = cs.load_template("case")
    text = "Acme was breached in March 2021. Attackers stole 9,000 records. A stolen password was the way in."
    script = cs.write_script("Acme breach", template, [{"id": "S1", "ref": "r", "text": SRC}], lambda p: reply(text))
    assert script["verified"] is True
    assert script["sections"][0]["narration"] == "Acme was breached in March 2021. A stolen password was the way in."
    assert script["dropped"][0]["unsupported"] == ["9,000"]


def test_write_script_without_sources_is_unverified_and_keeps_text():
    script = cs.write_script("Acme breach", cs.load_template("case"), [], lambda p: reply("Attackers stole 9,000 records."))
    assert script["verified"] is False and script["dropped"] == []
    assert "No sources were given" in cs.build_prompt("t", cs.load_template("case"), [])


def test_write_script_rejects_bad_answers():
    template = cs.load_template("case")
    with pytest.raises(ValueError):
        cs.write_script("t", template, [], lambda p: "no json here")
    with pytest.raises(ValueError):
        cs.write_script("t", template, [{"id": "S1", "ref": "r", "text": SRC}], lambda p: reply("It cost 77 million dollars."))
