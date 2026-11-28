"""An unusable answer from the model on this PC is asked again at once; a busy or rate-limited cloud model is given time."""
from engine import story_objects as so


def test_a_local_model_that_gave_nothing_usable_is_asked_again_after_a_short_wait(monkeypatch):
    waits = []
    monkeypatch.setattr(so.time, "sleep", waits.append)
    assert so.patiently(lambda: None, "x", local=lambda: True) is None
    assert waits and all(w == so.LOCAL_WAIT for w in waits) and len(waits) == so.BUSY_TRIES - 1


def test_a_cloud_answer_that_is_empty_still_waits_the_long_time(monkeypatch):
    waits = []
    monkeypatch.setattr(so.time, "sleep", waits.append)
    so.patiently(lambda: None, "x", local=lambda: False)
    so.patiently(lambda: None, "x")
    assert waits and all(w == so.BUSY_WAIT for w in waits)


def test_an_error_always_waits_the_long_time_even_from_the_local_model(monkeypatch):
    waits = []
    monkeypatch.setattr(so.time, "sleep", waits.append)

    def boom():
        raise RuntimeError("429 Too Many Requests")
    so.patiently(boom, "x", local=lambda: True)
    assert waits and all(w == so.BUSY_WAIT for w in waits)


def test_a_usable_answer_is_returned_at_once(monkeypatch):
    monkeypatch.setattr(so.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("must not wait")))
    assert so.patiently(lambda: [1], "x", local=lambda: True) == [1]
