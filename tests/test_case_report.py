"""The decisions report and the contact sheet of a case run (engine/case_report.py)."""
import json
import os

from engine import case_report as cr

SCRIPT = {"title": "How a Rainbow Forms", "hook": "Can a rainbow really last for nearly nine hours?", "verified": True, "sources": [{"id": "S1", "ref": "https://example.org/rainbow"}],
          "dropped": [{"section": "what", "sentence": "x", "unsupported": "y"}],
          "sections": [{"id": "what", "title": "What it is", "scene": "illustration", "mood": "excited", "narration": "Water drops bend sunlight into colours.",
                        "on_screen": ["Water drops", "Sunlight"], "footage": ["rain cloud"]},
                       {"id": "how", "title": "How it works", "scene": "illustration", "mood": "calm", "narration": "One two three.", "on_screen": ["Windmill", "Eye"]},
                       {"id": "why", "title": "Why it matters", "scene": "checklist", "narration": "Words.", "on_screen": ["Look away from the sun"]}]}


def test_the_report_says_what_was_chosen_and_where_each_icon_came_from(tmp_path, monkeypatch):
    monkeypatch.setenv("SHORTSFLOW_ICONS", str(tmp_path))
    (tmp_path / "windmill.v2.svg").write_text("<g/>", encoding="utf-8")
    art = {"16:9": [{"kinds": {"Water drops": "planet", "Sunlight": "sun"}}, {"kinds": {"Windmill": "windmill", "Eye": "eye"}}, None]}
    text = cr.build(SCRIPT, {"template": "explainer", "theme": "dark", "formats": "16:9", "narrator": "voice_server", "length": "short", "avatar": "nora"}, art,
                    [{"aspect": "16:9", "file": "x/case_16x9.mp4", "draft": True}], None, ["What it is: the first word is timed 12.0 s in."])
    assert "# How a Rainbow Forms" in text and "Can a rainbow really last for nearly nine hours?" in text
    assert "1 sentence(s) were removed" in text and "voice voice_server" in text and "presenter nora" in text and "length short" in text
    assert "## 1. What it is: a picture that explains" in text and "narrator mood: excited" in text
    assert "Water drops -> planet (built in); Sunlight -> sun (built in)" in text
    assert "Windmill -> windmill (drawn by the model, saved in the icon library); Eye -> eye (built in)" in text
    assert "## 3. Why it matters: a checklist" in text and "background ideas: rain cloud" in text
    assert "## Narration timing warnings" in text and "case_16x9.mp4 (draft)" in text


def test_a_picture_section_without_a_picture_says_it_became_a_checklist():
    text = cr.build(SCRIPT, {}, {"16:9": [None, None, None]})
    assert text.count("the picture could not be made, so this section shows its labels as a checklist") == 2
    assert "not recorded" in cr.build(SCRIPT, {}, {"16:9": [{"kinds": {}}, {"kinds": {}}, None]})              # an older picture plan has no icons recorded


def test_the_contact_sheet_asks_ffmpeg_for_a_grid_of_evenly_spaced_frames(tmp_path):
    seen = []

    class Done:
        def __init__(self, out="", code=0):
            self.stdout, self.returncode = out, code

    def run(cmd, **kw):
        seen.append(cmd)
        if cmd[0] == "ffprobe":
            return Done("1920,1080\n90.0\n")
        (tmp_path / "sheet.png").write_bytes(b"png")
        return Done()
    out = cr.contact_sheet("v.mp4", str(tmp_path / "sheet.png"), frames=8, cols=4, run=run)
    assert out == str(tmp_path / "sheet.png")
    vf = seen[1][seen[1].index("-vf") + 1]
    assert "fps=1/10.000" in vf and "scale=480" in vf and "tile=4x2" in vf                                      # 90 s / 9 = one frame every 10 s
    seen.clear()
    cr.contact_sheet("tall.mp4", str(tmp_path / "t.png"), run=lambda cmd, **kw: (seen.append(cmd), Done("1080,1920\n60.0\n"))[1])
    assert "scale=270" in seen[1][seen[1].index("-vf") + 1]                                                       # a tall video gets narrower frames
    assert cr.contact_sheet("v.mp4", str(tmp_path / "no.png"), run=lambda cmd, **kw: 1 / 0) is None             # a problem is never raised
    assert cr.contact_sheet("v.mp4", str(tmp_path / "no2.png"), run=lambda cmd, **kw: Done("1920,1080\n0\n")) is None


def test_write_puts_the_report_and_a_sheet_per_video_in_the_folder_and_never_raises(tmp_path):
    sheet = lambda video, out: (open(out, "wb").write(b"png"), out)[1]
    written = cr.write(str(tmp_path), SCRIPT, {}, {}, [{"aspect": "9:16", "file": "a.mp4"}, {"aspect": "16:9", "file": "b.mp4"}], sheet=sheet)
    assert sorted(os.path.basename(p) for p in written) == ["contact_16x9.png", "contact_9x16.png", "decisions.md"]
    assert "How a Rainbow Forms" in (tmp_path / "decisions.md").read_text(encoding="utf-8")
    assert cr.write(str(tmp_path / "missing" / "deeper"), SCRIPT, {}, {}, [], sheet=sheet) == []                  # a folder that is not there: nothing written, no error


def test_the_report_does_not_claim_a_failed_picture_when_it_has_no_picture_details():
    assert "could not be made" not in cr.build(SCRIPT, {}, None) and "could not be made" not in cr.build(SCRIPT, {}, {})
