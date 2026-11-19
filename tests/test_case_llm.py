import pytest

from engine import case_llm


def _fakes():
    calls = []

    def cloud(p, s):
        calls.append("cloud")
        raise RuntimeError("429 rate limit")

    def local(p, s):
        calls.append("local")
        return "local answer"
    return calls, cloud, local


def test_auto_falls_back_and_skips_cloud_during_cooldown():
    calls, cloud, local = _fakes()
    now = [0.0]
    ask = case_llm.make_ask("sys", "auto", cloud=cloud, local=local, log=lambda m: None, clock=lambda: now[0])
    assert ask("a") == "local answer"
    assert ask("b") == "local answer"
    assert calls == ["cloud", "local", "local"]
    now[0] = case_llm.COOLDOWN + 1
    ask("c")
    assert calls[-2:] == ["cloud", "local"]


def test_auto_uses_cloud_when_it_answers_and_on_empty_falls_back():
    ask = case_llm.make_ask("s", "auto", cloud=lambda p, s: "cloud answer", local=lambda p, s: "x", log=lambda m: None)
    assert ask("a") == "cloud answer"
    ask = case_llm.make_ask("s", "auto", cloud=lambda p, s: "  ", local=lambda p, s: "x", log=lambda m: None)
    assert ask("a") == "x"


def test_local_mode_never_calls_cloud_and_cloud_mode_never_local():
    calls, cloud, local = _fakes()
    assert case_llm.make_ask("s", "local", cloud=cloud, local=local)("a") == "local answer"
    assert calls == ["local"]
    calls.clear()
    with pytest.raises(RuntimeError):
        case_llm.make_ask("s", "cloud", cloud=cloud, local=local)("a")
    assert calls == ["cloud"]


def test_local_chat_reads_the_reply_and_reports_failures():
    class R:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data
    seen = {}

    def post(url, json, timeout):
        seen.update(json=json, timeout=timeout)
        return R({"message": {"content": "hi"}})
    assert case_llm.local_chat("p", "s", model="m", url="u", post=post) == "hi"
    assert seen["json"]["model"] == "m" and seen["json"]["stream"] is False and seen["timeout"] >= 300
    with pytest.raises(RuntimeError):
        case_llm.local_chat("p", post=lambda *a, **k: R({"message": {"content": ""}}))

    def boom(*a, **k):
        raise ConnectionError("refused")
    with pytest.raises(RuntimeError, match="did not answer"):
        case_llm.local_chat("p", post=boom)
