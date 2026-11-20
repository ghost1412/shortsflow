import json
import os

import pytest

from shortsflow import settings as st

CLIENT = {"installed": {"client_id": "abc.apps.googleusercontent.com", "client_secret": "s3cr3t-value", "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token", "redirect_uris": ["http://localhost"]}}
TOKEN = {"token": "t", "refresh_token": "r", "client_id": "abc", "client_secret": "s", "token_uri": "https://oauth2.googleapis.com/token", "scopes": st.YOUTUBE_SCOPES}


class FakeUploader:
    def __init__(self, ok=True, video_id="vid123"):
        self.ok, self.video_id, self.calls = ok, video_id, []

    def authenticate(self):
        return self.ok

    def upload_video(self, path, title, description, tags, privacy="public"):
        self.calls.append({"path": os.path.basename(path), "title": title, "description": description, "tags": tags, "privacy": privacy})
        return self.video_id


def _connected(home, account="1"):
    st.save_client_secrets(home, account, json.dumps(CLIENT))
    _, token = st.youtube_paths(home, account)
    with open(token, "w", encoding="utf-8") as f:
        json.dump(TOKEN, f)


def _case_run(root, name="case_1", title="Heartbleed"):
    folder = root / "sessions" / name
    folder.mkdir(parents=True)
    (folder / "script.json").write_text(json.dumps({"title": title, "sections": [{"narration": "First one. Second one. Third one."}]}), encoding="utf-8")
    for f in ("case_16x9.mp4", "case_9x16.mp4", "case_draft_16x9.mp4"):
        (folder / f).write_bytes(b"x")
    return folder


def test_account_slots_use_the_file_names_the_uploader_uses(tmp_path):
    home = str(tmp_path)
    assert [os.path.basename(p) for p in st.youtube_paths(home)] == ["client_secrets.json", "token.json"]
    assert [os.path.basename(p) for p in st.youtube_paths(home, "2")] == ["client_secrets_2.json", "token_2.json"]
    assert [os.path.basename(p) for p in st.youtube_paths(home, "../x/Y")] == ["client_secrets_xy.json", "token_xy.json"]          # nothing can climb out of the folder
    assert st.clean_account("") == "1" and st.clean_account(None) == "1"


def test_only_a_desktop_app_client_file_is_accepted(tmp_path):
    home = str(tmp_path)
    ok, msg = st.save_client_secrets(home, "1", json.dumps(CLIENT).encode("utf-8"))
    assert ok and "Connect YouTube" in msg and json.load(open(st.youtube_paths(home)[0]))["installed"]["client_id"].startswith("abc")
    assert st.save_client_secrets(home, "1", "not json")[0] is False
    web = {"web": CLIENT["installed"]}
    ok, msg = st.save_client_secrets(home, "2", json.dumps(web))
    assert not ok and "Desktop app" in msg and not os.path.exists(st.youtube_paths(home, "2")[0])
    assert st.save_client_secrets(home, "2", json.dumps({"installed": {"client_id": "x"}}))[0] is False
    assert st.save_client_secrets(home, "2", json.dumps([1, 2]))[0] is False


def test_connect_saves_the_token_and_status_follows(tmp_path):
    home = str(tmp_path)
    assert st.connect_youtube(home, "1")[0] is False                                     # no client file yet
    st.save_client_secrets(home, "1", json.dumps(CLIENT))
    assert st.youtube_status(home) == {"secrets": True, "connected": False}
    assert "not connected" in st.youtube_status_markdown(home)
    ok, msg = st.connect_youtube(home, "1", run_flow=lambda path: json.dumps(TOKEN))
    assert ok and st.youtube_status(home)["connected"] and "✅ connected" in st.youtube_status_markdown(home)

    def cancelled(path):
        raise RuntimeError("the window was closed")
    st.disconnect_youtube(home, "1")
    ok, msg = st.connect_youtube(home, "1", run_flow=cancelled)
    assert not ok and "did not finish" in msg and not st.youtube_status(home)["connected"]


def test_a_broken_token_does_not_count_as_connected_and_disconnect_forgets_only_the_token(tmp_path):
    home = str(tmp_path)
    _connected(home)
    secrets, token = st.youtube_paths(home)
    open(token, "w").write("garbage")
    assert st.youtube_status(home)["connected"] is False
    json.dump(TOKEN, open(token, "w"))
    assert st.disconnect_youtube(home, "1") == (True, "Disconnected. The client file is kept.")
    assert os.path.isfile(secrets) and not os.path.exists(token)
    assert st.disconnect_youtube(home, "1")[0] is False


def test_preferences_keep_the_youtube_choices_and_allow_the_direct_route(tmp_path):
    home = str(tmp_path)
    prefs = st.save_prefs(home, True, ["youtube_direct", "tiktok", "nope"], youtube_privacy="unlisted", youtube_account="2")
    assert prefs == {"auto_publish": True, "platforms": ["youtube_direct", "tiktok"], "youtube_privacy": "unlisted", "youtube_account": "2"}
    assert st.load_prefs(home) == prefs
    again = st.save_prefs(home, False, ["youtube_direct"])                                # a setting left out keeps its saved value
    assert again["youtube_privacy"] == "unlisted" and again["youtube_account"] == "2"
    bad = st.save_prefs(home, False, [], youtube_privacy="public-ish", youtube_account="")
    assert bad["youtube_privacy"] == "unlisted"                                          # an invalid privacy keeps the saved one
    (tmp_path / "settings.json").write_text(json.dumps({"youtube_privacy": "weird", "youtube_account": "!!"}), encoding="utf-8")
    assert st.load_prefs(home)["youtube_privacy"] == "private" and st.load_prefs(home)["youtube_account"] == "1"


def test_a_preview_needs_no_sign_in_and_shows_the_tall_version_and_privacy(tmp_path):
    folder = _case_run(tmp_path)
    ok, lines = st.publish_direct(str(folder), "case", "unlisted", "1", str(tmp_path), dry_run=True)
    assert ok and len(lines) == 1 and "case_9x16.mp4" in lines[0] and "unlisted" in lines[0] and "preview only" in lines[0]


def test_a_case_video_goes_up_once_as_a_short_with_the_chosen_privacy(tmp_path):
    folder = _case_run(tmp_path)
    _connected(str(tmp_path))
    up = FakeUploader()
    ok, lines = st.publish_direct(str(folder), "case", "unlisted", "1", str(tmp_path), uploader=up)
    assert ok and len(up.calls) == 1 and up.calls[0]["path"] == "case_9x16.mp4" and up.calls[0]["privacy"] == "unlisted"
    assert up.calls[0]["title"] == "Heartbleed" and up.calls[0]["description"].endswith("#Shorts")
    assert "https://youtu.be/vid123" in lines[0]
    wide_only = _case_run(tmp_path, "case_2")
    os.remove(wide_only / "case_9x16.mp4")
    up2 = FakeUploader()
    st.publish_direct(str(wide_only), "case", "private", "1", str(tmp_path), uploader=up2)
    assert up2.calls[0]["path"] == "case_16x9.mp4" and "#Shorts" not in up2.calls[0]["description"]       # a wide video is not labelled a Short
    assert st.publish_direct(str(folder), "case", "weird", "1", str(tmp_path), uploader=FakeUploader())[0]    # an unknown privacy becomes private
    up3 = FakeUploader()
    st.publish_direct(str(folder), "case", "weird", "1", str(tmp_path), uploader=up3)
    assert up3.calls[0]["privacy"] == "private"


def test_clips_go_up_one_by_one_with_their_own_titles(tmp_path):
    folder = tmp_path / "sessions" / "extraction_1"
    folder.mkdir(parents=True)
    for n in ("a.mp4", "b.mp4"):
        (folder / n).write_bytes(b"x")
    (folder / "metadata.json").write_text(json.dumps([{"file": "a.mp4", "title": "Clip A", "description": "d1", "tags": ["#one", "two"]},
                                                      {"file": "b.mp4", "title": "Clip B", "description": "d2", "tags": []},
                                                      {"file": "missing.mp4", "title": "C"}]), encoding="utf-8")
    _connected(str(tmp_path))
    up = FakeUploader()
    ok, lines = st.publish_direct(str(folder), "clips", "private", "1", str(tmp_path), uploader=up)
    assert ok and [c["title"] for c in up.calls] == ["Clip A", "Clip B"] and up.calls[0]["tags"] == ["one", "two"] and len(lines) == 2


def test_failures_say_what_to_do_and_never_open_a_browser(tmp_path):
    folder = _case_run(tmp_path)
    ok, lines = st.publish_direct(str(folder), "case", "private", "1", str(tmp_path), uploader=FakeUploader())
    assert not ok and "Connect YouTube" in lines[0]                                      # not connected: told so, and the fake was never asked to sign in
    _connected(str(tmp_path))
    ok, lines = st.publish_direct(str(folder), "case", "private", "1", str(tmp_path), uploader=FakeUploader(ok=False))
    assert not ok and "no longer works" in lines[0]
    ok, lines = st.publish_direct(str(folder), "case", "private", "1", str(tmp_path), uploader=FakeUploader(video_id=None))
    assert not ok and "did not return a video id" in lines[0]
    assert st.publish_direct(str(folder), "case", "private", "1", None, uploader=FakeUploader())[0] is False


def test_the_direct_route_and_upload_post_are_sent_separately_and_only_what_went_out_is_remembered(tmp_path):
    folder = _case_run(tmp_path)
    _connected(str(tmp_path))
    up = FakeUploader()
    sent = []

    def fake_publisher(meta, plats, dry):
        sent.append(list(plats))
        return [{"file": "case_9x16.mp4", "ok": False, "error": "quota"}]
    ok, lines = st.publish_run(str(folder), "case", ["youtube_direct", "tiktok"], publisher=fake_publisher, again=True,
                               direct={"home": str(tmp_path), "privacy": "private", "account": "1", "uploader": up})
    assert not ok and sent == [["tiktok"]] and len(up.calls) == 1 and any("quota" in ln for ln in lines) and any("youtu.be" in ln for ln in lines)
    assert set(st.published_to(str(folder))) == {"youtube_direct"}                       # tiktok failed: not remembered; youtube went out: remembered
    ok, lines = st.publish_run(str(folder), "case", ["youtube_direct"], direct={"home": str(tmp_path), "uploader": up})
    assert not ok and "Already published to youtube_direct" in lines[0] and len(up.calls) == 1
    assert st.publish_run(str(folder), "case", [], direct=None)[0] is False


def test_a_direct_only_selection_does_not_need_the_upload_post_key(tmp_path, monkeypatch):
    for name in st.KEY_NAMES:
        monkeypatch.delenv(name, raising=False)
    folder = _case_run(tmp_path)
    _connected(str(tmp_path))
    up = FakeUploader()
    ok, lines = st.publish_run(str(folder), "case", ["youtube_direct"], env_path=str(tmp_path / ".env"), environ={}, again=True,
                               direct={"home": str(tmp_path), "uploader": up})
    assert ok and len(up.calls) == 1


def test_auto_publish_uses_the_saved_youtube_choices(tmp_path):
    home = str(tmp_path)
    folder = _case_run(tmp_path)
    st.save_prefs(home, True, ["youtube_direct"], youtube_privacy="unlisted", youtube_account="1")
    lines = st.auto_publish(home, 0)                                                     # not connected: a clear message, nothing uploaded, no browser
    assert lines[0] == "Auto-publish:" and any("Connect YouTube" in ln for ln in lines)
    assert st.published_to(str(folder)) == {}
