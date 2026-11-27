"""A Gemini model out of quota is not asked again and again: a long story run made the same four tries dozens of times."""
import pytest
import requests

from engine import script_gen


class Reply:
    def __init__(self, text):
        self.status_code, self.text = 429, text

    def raise_for_status(self):
        raise requests.exceptions.HTTPError("429 Too Many Requests")


@pytest.fixture
def gemini(monkeypatch):
    calls, state = [], {"body": "PerDay", "now": 1000.0}

    def post(url, **kw):
        calls.append(url.split("/models/")[1].split(":")[0] if "/models/" in url else url)
        return Reply(state["body"])
    monkeypatch.setattr(script_gen, "_GEMINI_COOLDOWN", {})
    monkeypatch.setattr(script_gen, "GEMINI_API_KEY", "k")
    for name in ("DEEPSEEK_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY", "HF_API_KEY"):
        monkeypatch.setattr(script_gen, name, None, raising=False)
        monkeypatch.delenv(name, raising=False)
    for name in ("LLM_PROVIDER", "LLM_MODEL", "FORCE_OLLAMA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(script_gen, "LOCAL_LLM_URL", "")
    monkeypatch.setattr(script_gen.requests, "post", post)
    monkeypatch.setattr(script_gen.time, "sleep", lambda s: None)
    monkeypatch.setattr(script_gen.time, "time", lambda: state["now"])
    return calls, state


def ask():
    with pytest.raises(RuntimeError):
        script_gen.get_llm_response("p", "s")


def test_each_spent_model_is_asked_once_and_then_not_at_all_for_an_hour(gemini):
    calls, state = gemini
    ask()
    assert len(calls) == len(set(calls)) == 4
    calls.clear()
    state["now"] += 120
    ask()
    assert calls == []
    state["now"] += 3600
    ask()
    assert len(calls) == 4


def test_a_model_limited_through_every_try_rests_longer_than_a_minute(gemini):
    calls, state = gemini
    state["body"] = "per minute"
    ask()
    assert calls.count("gemini-pro-latest") == 4 and script_gen._GEMINI_COOLDOWN["gemini-pro-latest"] == 1600.0
    calls.clear()
    state["now"] += 90
    ask()
    assert "gemini-pro-latest" not in calls and calls
