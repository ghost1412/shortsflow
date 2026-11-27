"""narrator=voice_server borrows the local voice server: starts an installed one, stops only the one it started."""
import os

import pytest

from engine import voice_server as vs

LOCAL = vs.url()


@pytest.fixture
def fake(monkeypatch, tmp_path):
    state = {"installed": True, "running": False, "calls": [], "fail": False}

    def start(base=None, port=vs.DEFAULT_PORT, log=print):
        state["calls"].append("start")
        if state["fail"]:
            raise RuntimeError("did not answer in time")
        state["running"] = True

    def stop(base=None):
        state["calls"].append("stop")
        state["running"] = False
        return True
    monkeypatch.setattr(vs, "installed", lambda base=None: state["installed"])
    monkeypatch.setattr(vs, "running", lambda port=vs.DEFAULT_PORT: state["running"])
    monkeypatch.setattr(vs, "start", start)
    monkeypatch.setattr(vs, "stop", stop)
    monkeypatch.setattr(vs, "paths", lambda base=None: {"pid": str(tmp_path / "server.pid")})
    state["pid"] = tmp_path / "server.pid"
    return state


def test_it_is_started_for_the_job_and_stopped_after_also_when_the_job_fails(fake):
    with vs.while_needed(LOCAL) as started:
        assert started and fake["running"]
    assert fake["calls"] == ["start", "stop"] and not fake["running"]
    fake["calls"].clear()
    with pytest.raises(ValueError):
        with vs.while_needed("http://localhost:8080/"):
            raise ValueError("narration broke")
    assert fake["calls"] == ["start", "stop"]


@pytest.mark.parametrize("change, address", [({"running": True}, LOCAL), ({"installed": False}, LOCAL), ({}, "http://192.168.1.5:8080"), ({}, "http://127.0.0.1:9999")])
def test_a_running_server_a_missing_add_on_and_another_address_are_left_alone(fake, change, address):
    fake.update(change)
    with vs.while_needed(address) as started:
        assert not started
    assert fake["calls"] == []


def test_a_failed_start_stops_only_what_that_attempt_launched(fake):
    fake["fail"] = True
    fake["pid"].write_text("123")
    os.utime(fake["pid"], (1000, 1000))                       # an old pid file: the process it names may be anyone's by now
    with vs.while_needed(LOCAL) as started:
        assert not started
    assert fake["calls"] == ["start"]
    fake["calls"].clear()
    os.utime(fake["pid"])                                     # written by this attempt
    with vs.while_needed(LOCAL):
        pass
    assert fake["calls"] == ["start", "stop"]
