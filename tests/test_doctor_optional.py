"""doctor fails only for what clipping needs; the rest is marked optional."""
from shortsflow import cli, workspace


def rows(**missing):
    labels = ["FFmpeg", "Clipping extras (Whisper, OpenCV)", "Node.js (Remotion captions)", "PEXELS_API_KEY (stock footage)"]
    return [(label, label not in missing.get("names", ()), "do something") for label in labels]


def test_optional_items_do_not_look_like_a_failed_install(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workspace, "doctor", lambda home: rows(names=("Node.js (Remotion captions)", "PEXELS_API_KEY (stock footage)")))
    assert cli._doctor(str(tmp_path)) == 0
    out = capsys.readouterr().out
    assert "FIX" not in out and "optional  Node.js" in out and "Ready to clip. The 2 optional item(s)" in out


def test_a_missing_required_item_still_fails_and_says_so(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(workspace, "doctor", lambda home: rows(names=("FFmpeg",)))
    assert cli._doctor(str(tmp_path)) == 1
    assert "FIX       FFmpeg" in capsys.readouterr().out


def test_the_required_names_are_real_doctor_rows(tmp_path):
    assert set(workspace.REQUIRED) <= {label for label, _, _ in workspace.doctor(str(tmp_path))}
