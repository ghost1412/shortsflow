"""Titles for several clips are asked for at once; a local model answers one at a time, so the others must not time out in the queue."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from engine import script_gen


def test_requests_to_the_local_model_take_turns(monkeypatch):
    busy, overlaps, guard = [], [], threading.Lock()

    class Answer:
        text = ""

        def raise_for_status(self):
            pass

        def json(self):
            return {"message": {"content": "ok"}}

    def post(url, *a, **k):
        assert url == script_gen.LOCAL_LLM_URL
        with guard:
            overlaps.append(len(busy))
            busy.append(1)
        time.sleep(0.05)
        with guard:
            busy.pop()
        return Answer()
    monkeypatch.setattr("requests.post", post)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("FORCE_OLLAMA", raising=False)
    with ThreadPoolExecutor(3) as pool:
        got = list(pool.map(lambda _: script_gen.get_llm_response("hello", provider="ollama"), range(3)))
    assert got == ["ok"] * 3 and overlaps == [0, 0, 0]
