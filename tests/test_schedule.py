from datetime import datetime

from shortsflow import schedule as sc

NOW = datetime(2026, 11, 21, 12, 0)


def _video(tmp_path):
    f = tmp_path / "sessions" / "case_a" / "case_9x16.mp4"
    f.parent.mkdir(parents=True)
    f.write_bytes(b"x" * 100)
    return str(f)


def test_times_are_read_in_the_ways_people_type_them():
    assert sc.parse_when("2026-11-22 09:00", NOW) == datetime(2026, 11, 22, 9, 0)
    assert sc.parse_when("in 2h", NOW) == datetime(2026, 11, 21, 14, 0)
    assert sc.parse_when("+30m", NOW) == datetime(2026, 11, 21, 12, 30)
    assert sc.parse_when("18:30", NOW) == datetime(2026, 11, 21, 18, 30)
    assert sc.parse_when("09:00", NOW) == datetime(2026, 11, 22, 9, 0)       # already passed today: tomorrow
    assert sc.parse_when("soonish", NOW) is None and sc.parse_when("", NOW) is None and sc.parse_when("25:00", NOW) is None


def test_adding_checks_time_platforms_and_file(tmp_path):
    v = _video(tmp_path)
    home = str(tmp_path)
    assert not sc.add(home, v, "nonsense", "T", "d", "", ["tiktok"], now=NOW)[0]
    assert not sc.add(home, v, "2026-11-01 09:00", "T", "d", "", ["tiktok"], now=NOW)[0]
    assert not sc.add(home, v, "in 1h", "T", "d", "", [], now=NOW)[0]
    assert not sc.add(home, str(tmp_path / "gone.mp4"), "in 1h", "T", "d", "", ["tiktok"], now=NOW)[0]
    ok, msg, job = sc.add(home, v, "in 1h", "  My   title ", "d", "a, b", ["tiktok", "nope"], privacy="weird", account="2", now=NOW)
    assert ok and job["platforms"] == ["tiktok"] and job["privacy"] == "private" and job["title"] == "My title" and job["at"] == "2026-11-21 13:00"
    assert [j["id"] for j in sc.jobs(home)] == [job["id"]]


def test_only_what_is_due_is_sent_once_and_failures_are_kept(tmp_path):
    v = _video(tmp_path)
    home = str(tmp_path)
    a = sc.add(home, v, "in 1h", "A", "", "", ["tiktok"], now=NOW)[2]
    b = sc.add(home, v, "in 3h", "B", "", "", ["tiktok"], now=NOW)[2]
    sent = []

    def fake(path, title, desc, tags, platforms, **kw):
        sent.append(title)
        return (title != "A"), [f"result for {title}"]
    assert sc.run_due(home, now=datetime(2026, 11, 21, 12, 30), publish=fake) == []
    res = sc.run_due(home, now=datetime(2026, 11, 21, 13, 5), publish=fake)
    assert [r[0] for r in res] == [a["id"]] and sent == ["A"]
    assert sc.jobs(home)[0]["status"] == "failed" and "result for A" in sc.jobs(home)[0]["result"]
    assert sc.run_due(home, now=datetime(2026, 11, 21, 13, 6), publish=fake) == []         # a failed job is not retried by itself
    sc.run_due(home, now=datetime(2026, 11, 21, 16, 0), publish=fake)
    assert sent == ["A", "B"] and sc.jobs(home, "done")[0]["id"] == b["id"]


def test_cancel_and_a_crashing_publisher_do_not_break_the_queue(tmp_path):
    v = _video(tmp_path)
    home = str(tmp_path)
    a = sc.add(home, v, "in 1h", "A", "", "", ["tiktok"], now=NOW)[2]
    b = sc.add(home, v, "in 1h", "B", "", "", ["tiktok"], now=NOW)[2]
    assert sc.cancel(home, a["id"]) and not sc.cancel(home, a["id"])

    def boom(*a, **k):
        raise RuntimeError("network down")
    res = sc.run_due(home, now=datetime(2026, 11, 21, 14, 0), publish=boom)
    assert [r[0] for r in res] == [b["id"]] and not res[0][1] and "network down" in res[0][2]
    assert "cancelled" in sc.markdown(home) and "network down" in sc.markdown(home)
    assert sc.markdown(str(tmp_path / "empty")) == "Nothing is scheduled."
