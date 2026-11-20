import json
import os

import pytest

from shortsflow import settings as st

SECRET = "sk-abcdef1234567890WXYZ"


@pytest.fixture(autouse=True)
def clean_environment():
    """set_key also sets the key in this process (the app needs no restart): leave the process environment as it was after every test."""
    saved = {n: os.environ.get(n) for n in st.KEY_NAMES}
    for n in st.KEY_NAMES:
        os.environ.pop(n, None)
    yield
    for n, v in saved.items():
        if v is None:
            os.environ.pop(n, None)
        else:
            os.environ[n] = v


def test_mask_shows_at_most_the_last_four_characters():
    assert st.mask(SECRET) == "••••WXYZ"
    assert st.mask("short") == "••••" and st.mask("") == ""
    assert SECRET not in st.mask(SECRET)


def test_placeholders_do_not_count_as_keys(tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=your_gemini_api_key_here\n# GROQ_API_KEY=real123456789012\nPEXELS_API_KEY=abc123456789xyz0\n", encoding="utf-8")
    assert st.read_env(str(env)) == {"PEXELS_API_KEY": "abc123456789xyz0"}
    rows = {r["env"]: r for r in st.key_rows(str(env), environ={})}
    assert not rows["GEMINI_API_KEY"]["set"] and not rows["GROQ_API_KEY"]["set"] and rows["PEXELS_API_KEY"]["set"]


def test_set_and_remove_a_key_and_the_page_text_never_holds_it(tmp_path):
    env, environ = str(tmp_path / ".env"), {}
    ok, _ = st.set_key(env, "GROQ_API_KEY", SECRET)
    assert ok and st.read_env(env)["GROQ_API_KEY"] == SECRET
    rows = st.key_rows(env, environ=environ)
    text = st.rows_markdown(rows)
    assert SECRET not in text and "••••WXYZ" in text and SECRET not in json.dumps(rows)
    environ["GROQ_API_KEY"] = SECRET
    ok, _ = st.remove_key(env, "GROQ_API_KEY", environ=environ)
    assert ok and "GROQ_API_KEY" not in st.read_env(env) and "GROQ_API_KEY" not in environ
    assert st.remove_key(env, "GROQ_API_KEY", environ=environ)[0] is False


def test_only_known_names_and_clean_values_are_accepted(tmp_path):
    env = str(tmp_path / ".env")
    assert st.set_key(env, "PATH", "x" * 20)[0] is False
    assert st.set_key(env, "GROQ_API_KEY", "")[0] is False
    assert st.set_key(env, "GROQ_API_KEY", "has a space")[0] is False
    assert st.remove_key(env, "PATH")[0] is False
    assert not os.path.exists(env)


def test_remove_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("A_NOTE=1\nPEXELS_API_KEY=abc123456789xyz0\nGROQ_API_KEY=gk123456789012345\n", encoding="utf-8")
    st.remove_key(str(env), "PEXELS_API_KEY", environ={})
    assert env.read_text(encoding="utf-8") == "A_NOTE=1\nGROQ_API_KEY=gk123456789012345\n"


def test_upload_profile_is_shown_in_full_but_the_key_is_masked(tmp_path):
    env = str(tmp_path / ".env")
    st.set_key(env, "UPLOAD_POST_USER", "my_profile")
    st.set_key(env, "UPLOAD_POST_API_KEY", SECRET)
    rows = {r["env"]: r for r in st.key_rows(env, environ={})}
    assert rows["UPLOAD_POST_USER"]["shown"] == "my_profile" and rows["UPLOAD_POST_API_KEY"]["shown"] == "••••WXYZ"


def test_prefs_default_off_round_trip_and_ignore_bad_platforms(tmp_path):
    home = str(tmp_path)
    assert st.load_prefs(home) == {"auto_publish": False, "platforms": [], "youtube_privacy": "private", "youtube_account": "1"}
    st.save_prefs(home, True, ["youtube", "nonsense", "tiktok"])
    assert st.load_prefs(home) == {"auto_publish": True, "platforms": ["youtube", "tiktok"], "youtube_privacy": "private", "youtube_account": "1"}
    (tmp_path / "settings.json").write_text("not json", encoding="utf-8")
    assert st.load_prefs(home)["auto_publish"] is False


def test_route_sends_each_shape_where_it_belongs():
    wide, tall = "/s/case_16x9.mp4", "/s/case_9x16.mp4"
    out = st.route([wide, tall], ["tiktok", "linkedin", "youtube"])
    assert out["tiktok"] == [tall] and out["linkedin"] == [wide] and out["youtube"] == [tall, wide]
    assert st.route([wide], ["tiktok"]) == {"tiktok": [wide]}        # the only shape made is better than nothing
    assert st.route([], ["tiktok"]) == {}


def test_publish_needs_a_key_and_profile_unless_it_is_a_preview(tmp_path):
    env = str(tmp_path / ".env")
    ok, lines = st.publish_videos(str(tmp_path), [str(tmp_path / "case_9x16.mp4")], "T", "D", ["tiktok"], env_path=env, environ={}, publisher=lambda *a: 1 / 0)
    assert not ok and "Upload-Post" in lines[0]


def test_publish_groups_platforms_and_reports_each_video(tmp_path):
    folder = str(tmp_path)
    wide, tall = os.path.join(folder, "case_16x9.mp4"), os.path.join(folder, "case_9x16.mp4")
    calls = []

    def fake(meta, plats, dry):
        calls.append((json.load(open(meta, encoding="utf-8")), list(plats), dry))
        return [{"file": i["file"], "ok": True, "dry_run": dry} for i in calls[-1][0]]
    ok, lines = st.publish_videos(folder, [wide, tall], "Title", "Desc", ["tiktok", "instagram", "linkedin"], dry_run=True, publisher=fake)
    assert ok and len(calls) == 2                                  # tiktok+instagram share the tall video, linkedin gets the wide one
    assert any("case_9x16.mp4 → tiktok, instagram" in ln and "preview only" in ln for ln in lines)
    assert any("case_16x9.mp4 → linkedin" in ln for ln in lines)
    assert calls[0][0][0]["title"] == "Title" and calls[0][0][0]["file"].endswith(".mp4")


def test_publish_reports_a_failure_and_an_exit_from_the_engine(tmp_path):
    folder = str(tmp_path)
    vid = os.path.join(folder, "case_9x16.mp4")
    ok, lines = st.publish_videos(folder, [vid], "T", "D", ["tiktok"], publisher=lambda m, p, d: [{"file": "case_9x16.mp4", "ok": False, "error": "quota"}])
    assert not ok and "quota" in lines[0]

    def exits(m, p, d):
        raise SystemExit("Set UPLOAD_POST_API_KEY")
    ok, lines = st.publish_videos(folder, [vid], "T", "D", ["tiktok"], publisher=exits)
    assert not ok and "UPLOAD_POST_API_KEY" in lines[0]


def _case_run(root, name, title="A title", mtime=None):
    folder = root / "sessions" / name
    folder.mkdir(parents=True)
    (folder / "script.json").write_text(json.dumps({"title": title, "sections": [{"narration": "First one. Second one. Third one."}]}), encoding="utf-8")
    for f in ("case_16x9.mp4", "case_9x16.mp4", "case_draft_16x9.mp4"):
        (folder / f).write_bytes(b"x")
        if mtime:
            os.utime(folder / f, (mtime, mtime))
    return folder


def test_list_runs_finds_case_and_clip_runs_newest_first_and_skips_drafts(tmp_path):
    older = _case_run(tmp_path, "case_old", "Old", mtime=1_000_000_000)
    clips = tmp_path / "sessions" / "extraction_1"
    clips.mkdir()
    (clips / "metadata.json").write_text("[]", encoding="utf-8")
    (tmp_path / "sessions" / "empty").mkdir()
    runs = st.list_runs(str(tmp_path))
    assert [r[2] for r in runs] == ["clips", "case"] and runs[1][1] == str(older) and "Old" in runs[1][0]


def test_publish_run_for_a_case_uses_its_title_and_skips_draft_videos(tmp_path):
    folder = _case_run(tmp_path, "case_1", "Gulab jamun")
    seen = []

    def fake(meta, plats, dry):
        items = json.load(open(meta, encoding="utf-8"))
        seen.append((items[0]["title"], items[0]["description"], [i["file"] for i in items]))
        return [{"file": i["file"], "ok": True} for i in items]
    ok, lines = st.publish_run(str(folder), "case", ["tiktok", "linkedin"], publisher=fake)
    assert ok and seen[0][0] == "Gulab jamun" and seen[0][1] == "First one. Second one."
    assert all("draft" not in f for s in seen for f in s[2])


def test_auto_publish_is_off_by_default_and_only_publishes_a_new_run(tmp_path):
    home = str(tmp_path)
    folder = _case_run(tmp_path, "case_1")
    called = []

    def fake(meta, plats, dry):
        called.append(plats)
        return [{"file": "case_9x16.mp4", "ok": True}]
    assert st.auto_publish(home, 0, publisher=fake) == [] and not called              # off
    st.save_prefs(home, True, ["tiktok"])
    st.set_key(str(tmp_path / ".env"), "UPLOAD_POST_API_KEY", SECRET)
    st.set_key(str(tmp_path / ".env"), "UPLOAD_POST_USER", "me")
    import time
    assert st.auto_publish(home, time.time() + 60, publisher=fake) == [] and not called  # nothing newer than `since`
    lines = st.auto_publish(home, 0, publisher=fake, environ={})
    assert called and lines[0] == "Auto-publish:" and "✅" in lines[1]
    assert os.path.isdir(folder)


def test_a_run_is_not_published_twice_to_the_same_platform_unless_asked(tmp_path):
    folder = _case_run(tmp_path, "case_1")
    calls = []

    def fake(meta, plats, dry):
        calls.append(list(plats))
        return [{"file": "case_9x16.mp4", "ok": True, "dry_run": dry}]
    ok, _ = st.publish_run(str(folder), "case", ["tiktok"], publisher=fake)
    assert ok and "tiktok" in st.published_to(str(folder))
    ok, lines = st.publish_run(str(folder), "case", ["tiktok"], publisher=fake)
    assert not ok and "Already published to tiktok" in lines[0] and len(calls) == 1
    ok, _ = st.publish_run(str(folder), "case", ["tiktok"], publisher=fake, again=True)
    assert ok and len(calls) == 2
    ok, _ = st.publish_run(str(folder), "case", ["tiktok"], publisher=fake, dry_run=True)       # a preview is always allowed and records nothing new
    assert ok


def test_a_failed_publish_is_not_recorded_and_auto_publish_skips_done_platforms(tmp_path):
    folder = _case_run(tmp_path, "case_1")
    bad = lambda m, p, d: [{"file": "case_9x16.mp4", "ok": False, "error": "quota"}]
    assert st.publish_run(str(folder), "case", ["tiktok"], publisher=bad)[0] is False and st.published_to(str(folder)) == {}
    home = str(tmp_path)
    st.save_prefs(home, True, ["tiktok"])
    st.set_key(str(tmp_path / ".env"), "UPLOAD_POST_API_KEY", SECRET)
    st.set_key(str(tmp_path / ".env"), "UPLOAD_POST_USER", "me")
    st.record_published(str(folder), ["tiktok"])
    lines = st.auto_publish(home, 0, publisher=lambda *a: 1 / 0)
    assert len(lines) == 1 and "already published" in lines[0]
