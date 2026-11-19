import json

from engine.modes import animate


def test_defaults_add_the_animation_template_and_no_picture_behind_it():
    assert animate.defaults_for(None) == ["template=animation", "background=none"]
    assert animate.defaults_for(["theme=neon"]) == ["template=animation", "background=none", "theme=neon"]


def test_the_users_own_choices_win_on_the_command_line_and_in_a_settings_file(tmp_path):
    assert animate.defaults_for(["background=images", "template=explainer"]) == ["background=images", "template=explainer"]
    f = tmp_path / "s.json"
    f.write_text(json.dumps({"background": "images"}), encoding="utf-8")
    assert animate.defaults_for(["theme=neon"], str(f)) == ["template=animation", "theme=neon"]
    assert animate.defaults_for([], str(tmp_path / "missing.json")) == ["template=animation", "background=none"]


def test_run_hands_the_case_pipeline_the_animation_template(monkeypatch):
    seen = {}
    monkeypatch.setattr("engine.modes.case.run", lambda args, *a: seen.update(case=list(args.case), mode=getattr(args, "mode", None)))

    class Args:
        mode = "ANIMATE"
        case = ["draft"]
        case_file = None
    animate.run(Args())
    assert seen["case"] == ["template=animation", "background=none", "draft"] and seen["mode"] == "ANIMATE"


def test_the_mode_is_a_cli_choice_and_has_a_dispatch():
    import re
    from pathlib import Path
    main = (Path(__file__).resolve().parents[1] / "shortsflow" / "_main.py").read_text(encoding="utf-8")
    assert '"ANIMATE"' in main and "engine.modes.animate" in main
    assert re.search(r'"--mode".*?"ANIMATE"', main, re.S)


def test_an_animation_section_without_a_clip_is_reported():
    from engine.modes import case
    script = {"sections": [{"title": "The idea", "scene": "animation"}, {"title": "Facts", "scene": "counters"}]}
    assert case.missing_animations(script, [None, None]) == ["The idea"]
    assert case.missing_animations(script, [{"path": "x"}, None]) == []
    assert case.missing_animations(script, None) == []
