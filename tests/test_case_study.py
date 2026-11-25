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
    assert cs.spell_powers("2 × 10^7 cells") == "2 × 10⁷ cells"                              # any other power: real superscripts, never a caret
    assert cs.spell_powers("2 x 10^25 molecules per m^3 and 10^-5 fraction") == "2 x 10²⁵ molecules per m³ and 10⁻⁵ fraction"
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


def test_the_model_is_told_to_give_the_story_of_things_a_picture_with_short_names():
    from engine import case_study as cs
    prompt = cs.build_prompt("Topic", cs.TEMPLATES["explainer"] if hasattr(cs, "TEMPLATES") else cs.PRESETS["explainer"], [], "auto")
    assert "illustration" in prompt and "SHORT NAME" in prompt and "Most videos should have at least one" in prompt


def test_a_picture_section_needs_short_names_of_things_or_it_becomes_a_checklist():
    from engine import case_study as cs
    assert cs.fit_layout("illustration", ["Attacker", "Fake email", "Your credentials"]) == "illustration"
    assert cs.fit_layout("illustration", ["Only one"]) == "checklist"
    assert cs.fit_layout("illustration", ["Attacker", "Steals 3 million records every year"]) == "checklist"           # a number and a sentence
    assert cs.fit_layout("illustration", ["Attacker", "A very long label that is really a whole sentence"]) == "checklist"


def test_picture_names_are_short_things_the_narration_says():
    from engine import case_study as cs
    narration = "Researchers placed a thin film on a crystal base. A metal layer blocks the field."
    ask = lambda p: json.dumps({"names": ["Thin film", "Crystal base", "Metal layer"]})
    assert cs.picture_names_for("How", narration, "T", ask) == ["Thin film", "Crystal base", "Metal layer"]
    bad = lambda p: json.dumps({"names": ["The film is placed on a crystal and compressed", "3 layers", "Dragon"]})        # a sentence, a number, a thing never said
    assert cs.picture_names_for("How", narration, "T", bad) == []
    assert cs.picture_names_for("How", narration, "T", lambda p: "no json") == [] and cs.picture_names_for("How", narration, "T", lambda p: json.dumps({"names": "x"})) == []
    assert len(cs.picture_names_for("How", narration, "T", lambda p: json.dumps({"names": ["Thin film", "Film", "Crystal base", "Metal layer", "Field", "Layer"]}))) <= cs.MAX_ILLUSTRATION


def test_a_picture_section_with_sentence_labels_gets_names_asked_for_and_stays_a_picture():
    from engine import case_study as cs
    template = [{"id": "what", "title": "What it is", "question": "q", "scene": "illustration"}]
    calls = []

    def ask(prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return json.dumps({"title": "T", "hook": "A thin film changes the chip", "sections": [{"id": "what", "narration": "A thin film sits on a crystal base. A metal layer covers it.",
                                                            "on_screen": ["We have shown that the dead layer can be removed."], "scene": "illustration"}]})
        return json.dumps({"names": ["Thin film", "Crystal base", "Metal layer"]})
    script = cs.write_script("Topic", template, [], ask, "auto")
    sec = script["sections"][0]
    assert len(calls) == 2 and sec["scene"] == "illustration" and sec["on_screen"] == ["Thin film", "Crystal base", "Metal layer"]


def test_the_explainer_template_starts_with_a_picture_section():
    from engine import case_study as cs
    assert cs.PRESETS["explainer"][0]["scene"] == "illustration"


def test_two_pictures_may_follow_each_other_but_other_layouts_may_not():
    from engine import case_study as cs
    assert cs.pick_layout("diagram", "illustration", "illustration", "auto") == "illustration"
    assert cs.pick_layout("diagram", "checklist", "checklist", "auto") == "diagram"          # the old rule for the others


def test_the_prompt_keeps_diagrams_for_processes_and_publication_details_off_the_screen():
    from engine import case_study as cs
    prompt = cs.build_prompt("Topic", cs.PRESETS["explainer"], [{"id": "s1", "ref": "r", "text": "t"}], "auto")
    assert "Not for a list of parts" in prompt and "two pictures may follow each other" in prompt
    assert "Never use funding, grant numbers, journal names" in prompt
    assert "If they hold no numbers, say what it changes" in prompt


def test_a_json_wrapped_hook_is_read_and_a_stray_bracket_is_never_a_hook():
    from engine import case_study as cs
    assert cs.hook_line('{\n  "hook": "Rainbows are full circles, not arcs."\n}') == "Rainbows are full circles, not arcs."
    assert cs.hook_line('["A plain list answer is still a line."]') == "A plain list answer is still a line."
    assert cs.hook_line("Just the line.\nAnd an explanation.") == "Just the line." and cs.hook_line("") == "" and cs.hook_line("{}") == ""
    assert cs.check_hook("{")[0] == "" and cs.check_hook("[")[0] == "" and cs.check_hook("12 34")[0] == ""
    assert cs.check_hook("Rainbows are full circles, not arcs.")[0] == "Rainbows are full circles, not arcs."
    sections = [{"narration": "A long first sentence that goes on and on and on and on and on and on and on and on and on and on."}]
    reply = '{\n  "hook": "Every rainbow is really a full circle."\n}'
    assert cs.make_hook("", sections, None, lambda p: reply) == "Every rainbow is really a full circle."          # the model's answer to the second ask


def test_a_year_is_a_date_not_a_figure_for_a_counter():
    from engine import case_study as cs
    year = lambda x: cs.is_year(cs._NUMBER_LEAD.match(x))
    assert year("1672 year") and year("2013") and year("1999 AD") and year("1066 CE")
    assert not year("1,672 users") and not year("1500 servers") and not year("$2013") and not year("42 degrees") and not year("12345") and not year("999")
    assert cs.drop_years(["42 degrees", "7 colours", "1672 year"]) == ["42 degrees", "7 colours"]
    assert cs.drop_years(["2013", "1999"]) == ["2013", "1999"]                       # all years: left alone
    assert cs.fit_layout("counters", ["1672 year", "2013", "42 degrees"]) == "checklist"        # only one real figure is left
    assert cs.fit_layout("counters", ["66% of sites", "17 million servers", "1672 year"]) == "counters"


def test_the_script_leaves_a_year_off_the_counter_cards():
    from engine import case_study as cs
    template = [{"id": "why", "title": "Why", "question": "q", "scene": "counters"}]
    rows = [{"id": "why", "narration": "Rainbows bend light by 42 degrees and split it into 7 colours, as Newton showed in 1672.",
             "on_screen": ["42 degrees", "7 colours", "1672 year", "10 million viewers"], "scene": "counters"}]
    script = cs.write_script("T", template, [], lambda p: json.dumps({"title": "T", "hook": "Rainbows bend light by exactly 42 degrees", "sections": rows}), "auto")
    assert script["sections"][0]["scene"] == "counters" and "1672 year" not in script["sections"][0]["on_screen"]


def test_a_label_with_a_raw_exponent_is_left_off_the_counter_cards():
    from engine import case_study as cs
    assert cs.drop_unreadable(["2 x 10^25 molecules", "10^-5 fraction scattered", "1881 equations"]) == ["1881 equations"]
    assert cs.drop_unreadable(["10^3", "10^-5"]) == ["10^3", "10^-5"]                  # all of them: left alone
    assert cs.fit_layout("counters", cs.drop_unreadable(["2 x 10^25 molecules", "10^-5 fraction", "1881 equations"])) == "checklist"     # one real figure left


def test_the_length_option_sets_the_sentences_per_section():
    from engine import case_study as cs, case_options
    t = cs.PRESETS["explainer"]
    assert "<4-6 short spoken sentences" in cs.build_prompt("T", t, [], "auto")
    assert "<2-3 short spoken sentences" in cs.build_prompt("T", t, [], "auto", "short")
    assert "<6-8 short spoken sentences" in cs.build_prompt("T", t, [], "auto", "long")
    assert "<4-6 short spoken sentences" in cs.build_prompt("T", t, [], "auto", "nonsense")          # an unknown length is the standard one
    assert case_options.parse(["length=short"])["length"] == "short" and case_options.parse([])["length"] == "standard"


def test_the_explainers_last_section_is_about_remembering():
    from engine import case_study as cs
    assert cs.PRESETS["explainer"][-1]["title"] == "What to remember"


def test_a_year_followed_by_a_noun_is_still_a_year_but_a_counted_thing_is_not():
    from engine import case_study as cs
    year = lambda x: cs.is_year(cs._NUMBER_LEAD.match(x))
    assert year("1913 home invention") and year("1672 discovery") and year("2013 launch") and year("1066 CE") and year("1999")
    assert not year("1500 servers") and not year("1500 customers") and not year("1500 degrees") and not year("2000 patients") and not year("1500 years")
    assert cs.drop_years(["3-5 C optimal range", "50 percent supermarket energy", "1913 home invention"]) == ["3-5 C optimal range", "50 percent supermarket energy"]


def test_picture_labels_are_asked_to_be_things_you_can_see_not_ideas():
    from engine import case_study as cs
    prompt = cs.build_prompt("Topic", cs.PRESETS["explainer"], [], "auto")
    assert "could SEE and point at in a drawing" in prompt
    assert '"Heat transfer", "External environment" and "Vapor compression cycle" no' in prompt
    asked = []
    names = cs.picture_names_for("How", "A compressor pumps cold air through the door.", "T", lambda p: (asked.append(p), '{"names": ["Compressor", "Cold air"]}')[1])
    assert names == ["Compressor", "Cold air"]
    assert "point at in a drawing" in asked[0] and "not an idea or a process" in asked[0]


def test_a_section_whose_default_is_the_picture_keeps_it_whatever_the_model_chooses():
    from engine import case_study as cs
    for chosen in ("timeline", "quote", "checklist", "diagram", "flow", "counters", "illustration", None):
        assert cs.pick_layout("illustration", chosen, None, "auto") == "illustration"
    assert cs.pick_layout("diagram", "timeline", None, "auto") == "timeline"                       # the other defaults can still be changed by the model
    template = [{"id": "what", "title": "What it is", "question": "q", "scene": "illustration"}]
    calls = []

    def ask(prompt):
        calls.append(prompt)
        if len(calls) == 1:                                # the model answers with a timeline of dates for a section meant to be a picture
            return json.dumps({"title": "T", "hook": "Sunlight scatters in the air above you", "sections": [{"id": "what", "scene": "timeline",
                               "narration": "Sunlight hits tiny air molecules and blue light scatters most. Your eye sees that blue light from every direction.",
                               "on_screen": ["1506: Da Vinci", "1871: Rayleigh"]}]})
        return json.dumps({"names": ["Sunlight", "Air molecules", "Blue light"]})
    sec = cs.write_script("Sky", template, [], ask, "auto")["sections"][0]
    assert sec["scene"] == "illustration" and sec["on_screen"] == ["Sunlight", "Air molecules", "Blue light"]


def test_a_counters_section_with_no_readable_figures_becomes_a_checklist():
    from engine import case_study as cs
    assert cs.bad_counter_label("10^-5 fraction scattered") and cs.bad_counter_label("1913 home invention") and not cs.bad_counter_label("42 degrees")
    template = [{"id": "why", "title": "Why", "question": "q", "scene": "counters"}]

    def script_with(labels):
        rows = [{"id": "why", "narration": "Some words about the sky and its blue light and how far it goes.", "on_screen": labels, "scene": "counters"}]
        return cs.write_script("T", template, [], lambda p: json.dumps({"title": "T", "hook": "The sky is blue for a reason", "sections": rows}), "auto")["sections"][0]
    every_bad = script_with(["2 x 10^25 molecules per cubic meter", "10^-5 fraction scattered", "5.1 x 10^-31 m^2 cross section"])
    assert every_bad["scene"] == "checklist" and len(every_bad["on_screen"]) == 3                              # shown as plain lines, not as big cards
    one_good = script_with(["42 degrees", "10^-5 fraction scattered", "1913 home invention"])
    assert one_good["scene"] == "checklist" and one_good["on_screen"] == ["42 degrees"]                         # only one real figure is left
    two_good = script_with(["42 degrees", "10 million viewers", "10^-5 fraction scattered"])
    assert two_good["scene"] == "counters" and two_good["on_screen"] == ["42 degrees", "10 million viewers"]


def test_exponents_in_either_form_are_unreadable_and_a_spoken_label_is_told_from_an_unspoken_one():
    assert cs.has_power("10^-5 fraction") and cs.has_power("10⁻⁵ fraction") and not cs.has_power("42 degrees")
    assert cs.bad_counter_label("10⁻⁵ fraction") and cs.drop_unreadable(["10⁻⁵ fraction", "42 degrees"]) == ["42 degrees"]
    assert cs.label_spoken("Water droplets", "Sunlight hits a water droplet.") and not cs.label_spoken("Dragon", "A fridge keeps food cold.")


def test_a_section_thinned_by_the_source_check_is_refilled_with_checked_sentences():
    src = "Compressors move heat. Fridges use refrigerant. The coil is cold."
    calls = []

    def ask(prompt):
        calls.append(prompt)
        return '{"narration": "Compressors move heat. Fridges use refrigerant. The coil is cold. It was invented in 1913."}' if "more narration" in prompt else ""
    out = cs.refill_narration("How", "Compressors move heat.", "fridge", src, ask)
    assert "refrigerant" in out and "1913" not in out and len(out.split()) > 3
    assert cs.refill_narration("How", "Compressors move heat.", "fridge", src, lambda p: "nonsense") == "Compressors move heat."


def test_ideas_are_told_from_things_for_picture_labels():
    for idea in ("Individual liberty", "Court action", "Mechanical digestion", "Latin terms", "Heat transfer", "3 layers", "The film is placed on a crystal"):
        assert cs.abstract_label(idea), idea
    for thing in ("Compressor", "Hall of Mirrors", "Fermentation tank", "Law book", "Station", "Sorted array", "Government building", "Document", "Target value", "City"):
        assert not cs.abstract_label(thing), thing


def _one(scene, labels, narration, reply="", source=""):
    """The one section write_script makes of these labels, and the prompts it asked; `reply` answers every ask after the first."""
    asked = []

    def ask(prompt):
        asked.append(prompt)
        if len(asked) == 1:
            return json.dumps({"title": "T", "hook": "A short line to open", "sections": [{"id": "x", "narration": narration, "scene": scene, "on_screen": labels}]})
        return reply
    sources = [{"id": "S1", "ref": "r", "text": source}] if source else []
    return cs.write_script("Topic", [{"id": "x", "title": "X", "question": "q", "scene": scene}], sources, ask)["sections"][0], asked


def test_a_picture_with_idea_labels_gets_names_of_things_only_when_that_is_better():
    said = "A judge in a court orders a prisoner out of the jail. Court action protects individual liberty."
    sec, asked = _one("illustration", ["Court action", "Individual liberty", "Prisoner"], said, json.dumps({"names": ["Judge", "Prisoner", "Jail"]}))
    assert sec["on_screen"] == ["Judge", "Prisoner", "Jail"] and len(asked) == 2
    for useless in ("no json", json.dumps({"names": ["Liberty", "Action"]})):
        sec, _ = _one("illustration", ["Court action", "Judge", "Prisoner"], said, useless)
        assert sec["scene"] == "illustration" and sec["on_screen"] == ["Court action", "Judge", "Prisoner"]
    assert len(_one("illustration", ["Judge", "Prisoner"], said)[1]) == 1                    # good labels cost no extra call


def test_checklist_lines_are_short_said_and_supported_or_nothing():
    said = "Prices rise over time. Each unit of currency buys fewer goods. Central banks raise interest rates by 2 percent."

    def lines(*x):
        return lambda prompt: json.dumps({"lines": list(x)})
    assert cs.checklist_lines_for("Why", said, "T", lines("Prices rise", "Banks raise rates 2 percent")) == ["Prices rise", "Banks raise rates 2 percent"]
    assert cs.checklist_lines_for("Why", said, "T", lines("Prices rose 54 percent", "Dragons breathe fire", "A very long line about prices that is really a sentence")) == []
    assert cs.checklist_lines_for("Why", said, "T", lambda p: "no json") == []
    assert cs.checklist_lines_for("Why", said, "T", lines("Prices rise", "The Zorblax currency"), "Prices rise over time.") == []       # a name the sources lack


def test_counters_without_figures_become_takeaway_lines_or_a_timeline_when_every_label_is_a_date():
    said = "Critics called it harsh. Others called it lenient. Germany signed after talks."
    good = json.dumps({"lines": ["Critics called it harsh", "Others called it lenient"]})
    for labels in (["1 treaty signed", "2 opposing critics"], ["1919 treaty", "1933 election"]):      # counted things, and two dates
        sec, _ = _one("counters", labels, said, good)
        assert sec["scene"] == "checklist" and sec["on_screen"] == ["Critics called it harsh", "Others called it lenient"]
    sec, asked = _one("counters", ["1166 Assize", "1215 Magna Carta", "1679 Act"], said, good)
    assert sec["scene"] == "timeline" and len(sec["on_screen"]) == 3 and len(asked) == 1
    sec, _ = _one("counters", ["833,997 percent inflation", "150 years", "Purchasing power erodes"], said)
    assert sec["scene"] == "counters" and sec["on_screen"] == ["833,997 percent inflation", "150 years"]


def test_a_label_whose_figure_was_cut_from_the_narration_is_cut_too():
    cut = [("It takes 54 hours at Zorblax.", ["Zorblax"])]
    assert cs.cut_labels(["54 hours to settle", "2 times more gas"], "Some yeasts make twice the gas.", cut) == ["2 times more gas"]
    assert cs.cut_labels(["54 hours to settle"], "It settles in 54 hours.", cut) == ["54 hours to settle"]
    assert cs.cut_labels(["54 hours to settle"], "No figure here.", []) == ["54 hours to settle"]


def test_a_thin_section_is_refilled_also_when_nothing_was_cut():
    text = "Chewing more raises gut hormones. Slow eating lowers hunger. " * 5
    more = json.dumps({"narration": text})
    sec, asked = _one("checklist", ["Chew more", "Eat slowly"], "Chewing more raises gut hormones.", more, text)
    assert len(sec["narration"].split()) >= 35 and len(asked) == 2
    assert len(_one("checklist", ["Chew more"], "Chewing more raises gut hormones.", more)[1]) == 1          # no sources: nothing to check new sentences against


def test_unit_names_match_their_signs_and_an_era_makes_a_date():
    assert cs.unsupported("It takes 54 hours at 81 degrees Fahrenheit.", "about 54 hours at 81 °F") == []
    assert cs.unsupported("It takes 54 hours at 27 degrees Celsius.", "54 hours at 27\u00a0°C (81\u00a0°F)") == []
    assert cs.unsupported("It is 81 degrees Fahrenheit.", "81 degrees") == ["Fahrenheit"]
    assert cs.bad_counter_label("3700 BC: oldest bread") and cs.bad_counter_label("800 AD siege")
    assert not cs.bad_counter_label("150 years of yeast") and not cs.bad_counter_label("30 ad campaigns")


def test_the_prompt_asks_for_layouts_by_kind_and_no_invented_causes():
    prompt = cs.build_prompt("Topic", cs.PRESETS["explainer"], [{"id": "s1", "ref": "r", "text": "t"}], "auto")
    assert "dated events in order" in prompt and "Never pick counters" in prompt and "ONLY when the sources state that very cause" in prompt
    assert "then, that's why" not in prompt and "never open a section by restating its question" in prompt
