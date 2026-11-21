import json

import pytest

from engine import case_study as cs

SRC = "In March 2021 the Acme payment portal was breached. Attackers used a stolen password and reached 4,200 customer records."


def test_presets_have_known_scenes_and_the_story_presets_have_four_sections():
    for name, sections in cs.PRESETS.items():
        assert len(sections) == (1 if name == "animation" else 4), name
        assert all(s["scene"] in cs.SCENES for s in sections), name


def test_the_animation_preset_is_one_animated_section_with_a_long_narration():
    (section,) = cs.load_template("animation")
    assert section["scene"] == "animation" and section["sentences"] == "10-14"
    prompt = cs.build_prompt("T", [section], [], "auto")
    assert "Narration length: 10-14 short sentences" in prompt and "layout is animation" in prompt
    assert cs.pick_layout("animation", "chart", None) == "animation"                  # the model may not swap the animation for a card scene


def test_a_template_file_may_ask_for_a_narration_length(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps([{"id": "a", "question": "Why?", "sentences": "6-8"}, {"id": "b", "question": "How?", "sentences": "lots"}]), encoding="utf-8")
    sections = cs.load_template(str(f))
    assert sections[0]["sentences"] == "6-8" and "sentences" not in sections[1]


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


def test_gather_sources_keeps_the_paragraphs_not_the_page_furniture():
    page = ("<html><nav>Home About Contact Login Subscribe Cookies</nav>" + "".join(f"<p>Paragraph {i} " + "word " * 30 + "</p>" for i in range(5))
            + "<footer>Terms Privacy</footer></html>")
    sources, _ = cs.gather_sources(["https://example.com/x"], fetch=lambda u: page)
    assert "Paragraph 3" in sources[0]["text"] and "Subscribe" not in sources[0]["text"] and "Privacy" not in sources[0]["text"]


def test_step_numbers_are_not_claims():
    assert cs.unsupported("Step 2: Hit by sandstorm winds", SRC) == []
    assert cs.unsupported("Phase 3: spread", SRC) == []
    assert cs.unsupported("Step 2: stole 9,000 records", SRC) == ["9,000"]      # a real figure is still checked


BASE = {"title": "Old title", "verified": True, "sources": [{"id": "S1", "ref": "r"}],
        "sections": [{"id": "what", "title": "What happened", "scene": "timeline", "narration": "First sentence. Second one.", "on_screen": ["A", "B"],
                      "cites": ["S1"], "footage": ["server room", "keyboard"]},
                     {"id": "how", "title": "How", "scene": "flow", "narration": "It worked like this.", "on_screen": ["Step 1"], "cites": [], "footage": "one phrase"}]}


def test_script_text_round_trips_and_keeps_what_is_not_edited():
    text = cs.script_to_text(BASE)
    assert text.startswith("TITLE: Old title") and "== 1. What happened [timeline]" in text and "FOOTAGE: server room; keyboard" in text
    back = cs.script_from_text(text, BASE)
    assert back["sections"][0]["narration"] == "First sentence. Second one." and back["sections"][0]["on_screen"] == ["A", "B"]
    assert back["sections"][0]["cites"] == ["S1"] and back["sources"] == BASE["sources"] and back["verified"] is True and back["edited"] is True
    assert back["sections"][1]["footage"] == ["one phrase"]


def test_script_text_edits_apply_and_a_deleted_block_drops_the_section():
    text = cs.script_to_text(BASE).replace("Old title", "New title").replace("First sentence.", "Changed sentence.").replace("- B", "- B changed")
    text = text.replace("[flow]", "[quote]").replace("FOOTAGE: server room; keyboard", "FOOTAGE: cables; night city; ")
    out = cs.script_from_text(text, BASE)
    assert out["title"] == "New title" and out["sections"][0]["narration"].startswith("Changed sentence.") and out["sections"][0]["on_screen"] == ["A", "B changed"]
    assert out["sections"][0]["footage"] == ["cables", "night city"] and out["sections"][1]["scene"] == "quote"
    only_second = text[text.index("== 2."):]
    dropped = cs.script_from_text("TITLE: T\n\n" + only_second, BASE)
    assert [s["id"] for s in dropped["sections"]] == ["how"]


def test_script_text_errors_are_plain():
    import pytest
    with pytest.raises(ValueError):
        cs.script_from_text("TITLE: T\n", BASE)                                   # nothing left
    with pytest.raises(ValueError):
        cs.script_from_text("TITLE: T\n== 9. Nope [flow]\nNARRATION:\nx\nLABELS:\n", BASE)          # a number with no section
    with pytest.raises(ValueError):
        cs.script_from_text("TITLE: T\n== 1. Empty [flow]\nNARRATION:\n\nLABELS:\n- a\n", BASE)     # no narration


def test_pick_layout_rules():
    assert cs.pick_layout("timeline", "compare", None) == "compare"
    assert cs.pick_layout("timeline", "compare", "compare") == "timeline"            # not the same twice in a row
    assert cs.pick_layout("timeline", "compare", None, layouts="template") == "timeline"
    assert cs.pick_layout("terminal", "chart", None) == "terminal" and cs.pick_layout("equation", "quote", None) == "equation"
    assert cs.pick_layout("flow", "nonsense", None) == "flow" and cs.pick_layout("flow", None, None) == "flow"
    assert cs.pick_layout("flow", "terminal", None) == "flow"                         # terminal and formula are never picked by the model
    assert cs.pick_layout("chart", "chart", "chart") == "chart"                       # the default is already the same: nothing better to use


def test_the_prompt_offers_the_layouts_and_explains_the_label_formats():
    text = cs.build_prompt("T", cs.load_template("case"), [], "auto")
    for name in cs.AUTO_LAYOUTS:
        assert f"  {name}:" in text
    assert "'left | right'" in text and "'Name: number'" in text and "do not use the same layout for two sections in a row" in text
    assert "Default layout:" in text
    fixed = cs.build_prompt("T", cs.load_template("case"), [], "template")
    assert "Scene kind:" in fixed and "Pick the layout" not in fixed


def test_write_script_takes_the_models_layouts_and_never_repeats_one():
    template = cs.load_template("case")
    rows = [{"id": s["id"], "narration": "A sentence about it.", "on_screen": ["One"], "scene": "compare"} for s in template]
    reply = json.dumps({"title": "T", "sections": rows})
    script = cs.write_script("T", template, [], lambda p: reply)
    scenes = [s["scene"] for s in script["sections"]]
    assert scenes[0] == "compare" and all(a != b for a, b in zip(scenes, scenes[1:]))
    with_diagram = json.dumps({"title": "T", "sections": [dict(r, diagram="flowchart LR\n A[One] --> B[Two]") for r in rows]})
    fixed = cs.write_script("T", template, [], lambda p: with_diagram, layouts="template", check_diagram=lambda c: (True, ""))
    assert [s["scene"] for s in fixed["sections"]] == [t["scene"] for t in template]
    no_code = cs.write_script("T", template, [], lambda p: reply, layouts="template", check_diagram=lambda c: (True, ""))
    assert [s["scene"] for s in no_code["sections"]] == ["timeline", "flow", "counters", "checklist"]       # a diagram section without code falls back to the flow


def test_counters_without_numbers_become_a_checklist():
    from engine import case_study as cs
    assert cs.fit_layout("counters", ["Binary reward in {0,1}", "Max horizon H"]) == "checklist"
    assert cs.fit_layout("counters", ["Binary reward", "Budget"], previous="checklist") == "timeline"
    assert cs.fit_layout("counters", ["300,000 computers", "$4 billion lost", "150 countries"]) == "counters"
    assert cs.fit_layout("flow", ["a"]) == "flow"


def test_prompt_asks_for_outcomes_not_setup():
    from engine import case_study as cs
    prompt = cs.build_prompt("T", cs.load_template("case"), [{"id": "S1", "ref": "x", "text": "t"}])
    assert "the outcomes" in prompt and "not how the work was set up" in prompt


def test_parse_reply_repairs_doubled_quotes_from_a_small_model():
    from engine import case_study as cs
    bad = '{"title": "T", "sections": [{"id": "a", "on_screen": [""Imagine an agent. What will it do?""], "cites": []}]}'
    assert cs.parse_reply(bad)["sections"][0]["on_screen"] == ["Imagine an agent. What will it do?"]
    multi = '{"sections": [{"id": "a", "on_screen": [\n  ""First line"",\n  "Second"\n]}]}'
    assert cs.parse_reply(multi)["sections"][0]["on_screen"] == ["First line", "Second"]
    assert cs.parse_reply("no json here") is None


def test_parse_reply_repairs_a_string_doubled_at_one_end_only():
    from engine import case_study as cs
    for line in ('[""Open only."]', '["Close only.""]', '[""Both.""]'):
        out = cs.parse_reply('{"sections": [{"id": "a", "on_screen": %s, "cites": []}]}' % line)
        assert out and out["sections"][0]["on_screen"][0].rstrip(".") in ("Open only", "Close only", "Both")
    assert cs.parse_reply('{"sections": [{"id": "a", "on_screen": [""], "cites": []}]}')["sections"][0]["on_screen"] == [""]


def test_checklist_keeps_three_rows_and_the_prompt_bans_author_lists():
    import json
    from engine import case_study as cs
    t = cs.load_template("case")
    rows = [{"id": x["id"], "narration": "A sentence about it.", "on_screen": ["a", "b", "c", "d", "e"], "scene": "checklist"} for x in t]
    script = cs.write_script("T", t, [], lambda p: json.dumps({"title": "T", "sections": rows}), layouts="template")
    assert all(len(s["on_screen"]) <= 3 for s in script["sections"] if s["scene"] == "checklist")
    assert "never read out a list of author names" in cs.build_prompt("T", t, [])


def test_powers_of_ten_in_labels_are_spelled_as_words():
    from engine import case_study as cs
    assert cs.spell_powers("3 × 10^9 cycles between errors") == "3 billion cycles between errors"
    assert cs.spell_powers("1.5 x 10^6 users") == "1.5 million users"
    assert cs.spell_powers("2 × 10^7 cells") == "2 × 10^7 cells"
    assert cs.spell_powers("300,000 computers") == "300,000 computers"


def test_recipe_template_and_counter_cap():
    import json
    from engine import case_study as cs
    t = cs.load_template("recipe")
    assert [s["scene"] for s in t] == ["quote", "flow", "counters", "checklist"]
    rows = [{"id": s["id"], "narration": "A sentence about it.", "on_screen": ["10 a", "20 b", "30 c", "40 d", "50 e", "60 f"], "scene": s["scene"]} for s in t]
    script = cs.write_script("T", t, [], lambda p: json.dumps({"title": "T", "sections": rows}))
    counters = [s for s in script["sections"] if s["scene"] == "counters"]
    assert counters and all(len(s["on_screen"]) <= cs.MAX_COUNTERS for s in counters)


def test_the_prompt_asks_for_a_hook_and_the_script_keeps_a_supported_one():
    import json
    from engine import case_study as cs
    t = cs.load_template("case")
    assert "HOOK:" in cs.build_prompt("T", t, []) and '"hook"' in cs.build_prompt("T", t, [])
    rows = [{"id": s["id"], "narration": "A sentence.", "on_screen": ["a"], "scene": s["scene"]} for s in t]
    src = [{"id": "S1", "ref": "x", "text": "The bug existed since 2013 in Log4j and put millions of servers at risk."}]
    good = json.dumps({"title": "T", "hook": "One logging bug put millions of servers at risk", "sections": rows})
    assert cs.write_script("T", t, src, lambda p: good)["hook"] == "One logging bug put millions of servers at risk"
    bad = json.dumps({"title": "T", "hook": "It cost 99 billion dollars", "sections": rows})       # a figure no source holds
    assert cs.write_script("T", t, src, lambda p: bad)["hook"] == "A sentence."                     # never the unsupported figure: the narration's first sentence
    assert cs.write_script("T", t, [], lambda p: good)["hook"] != ""                                # no sources: nothing to check against
    assert cs.write_script("T", t, src, lambda p: json.dumps({"title": "T", "sections": rows}))["hook"] == "A sentence."


def test_the_hook_is_editable_in_the_review_text():
    from engine import case_study as cs
    base = {"title": "T", "hook": "Old hook", "sections": [{"id": "a", "title": "A", "scene": "quote", "narration": "n", "on_screen": [], "footage": []}], "sources": []}
    text = cs.script_to_text(base)
    assert "HOOK: Old hook" in text
    assert cs.script_from_text(text.replace("HOOK: Old hook", "HOOK: A better, sharper hook"), base)["hook"] == "A better, sharper hook"
    assert cs.script_from_text(text.replace("HOOK: Old hook\n", ""), base)["hook"] == "Old hook"          # a deleted line keeps the saved hook


def test_number_cards_need_real_figures_not_counts_or_a_numbered_list():
    from engine.case_study import fit_layout
    assert fit_layout("counters", ["1 Law: Uruguay Law 18600", "2 Algorithms: RSA and ElGamal"]) == "checklist"      # a numbered list
    assert fit_layout("counters", ["3 vulnerabilities fixed", "2 patches released"]) == "checklist"                    # small counts
    assert fit_layout("counters", ["66% of sites affected", "17 million servers", "2.3x faster"]) == "counters"
    assert fit_layout("counters", ["$4.5 million cost", "500,000 records"]) == "counters"
    assert fit_layout("counters", ["4 million users", "2 billion devices"]) == "counters"                              # small numbers with a unit
    assert fit_layout("counters", ["1 Law", "2 Rules"], previous="checklist") == "timeline"


def test_the_hook_is_checked_retried_and_falls_back_with_a_reason(capsys):
    from engine import case_study as cs
    src = "OpenSSL had a bug in 2014. It leaked memory from 17 percent of servers."
    secs = [{"narration": "In 2014 a bug in OpenSSL leaked memory. It hit many servers."}]
    assert cs.check_hook("A bug in OpenSSL leaked memory in 2014.", src)[0]
    assert "2019" in cs.check_hook("In 2019 everything broke.", src)[1]
    assert "words" in cs.check_hook(" ".join(["word"] * 20), src)[1]
    assert cs.make_hook("A 2014 OpenSSL bug leaked memory.", secs, src, lambda p: "x") == "A 2014 OpenSSL bug leaked memory."
    asked = []
    hook = cs.make_hook("In 2019 it broke", secs, src, lambda p: asked.append(p) or "17 percent of servers leaked memory.")
    assert hook == "17 percent of servers leaked memory." and "2019" in capsys.readouterr().out and "OpenSSL" in asked[0]
    hook = cs.make_hook("", secs, src, lambda p: "In 2021 it broke")                 # the retry is unsupported too: the first sentence
    assert hook == "In 2014 a bug in OpenSSL leaked memory."
    def busy(p):
        raise RuntimeError("503")
    assert cs.make_hook("", [{"narration": " ".join(["long"] * 30) + "."}], src, busy) == ""
    assert "No hook" in capsys.readouterr().out
