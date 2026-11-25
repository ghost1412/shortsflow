"""A short reel keeps its best moment (engine.analysis.reel_merge_cap / merge_segments), and a rate-limited Gemini model is skipped."""
from engine import analysis, script_gen


def moments():
    return [{"start": 2.5, "end": 45.5, "viral_score": 75, "final_score": 75, "hook_text": "first"},
            {"start": 45.5, "end": 89.1, "viral_score": 85, "final_score": 85, "hook_text": "second"},
            {"start": 92.3, "end": 119.8, "viral_score": 90, "final_score": 90, "hook_text": "best"}]


def test_three_neighbouring_moments_are_not_fused_before_the_reel_is_chosen():
    cap = analysis.reel_merge_cap(60)
    merged = analysis.merge_segments(moments(), min_gap=8.0, max_dur=cap, score_sensitive=True)
    assert len(merged) == 3
    picked = analysis.fit_to_target(merged, 60.0)
    assert any(h["hook_text"] == "best" and h["end"] == 119.8 for h in picked)         # whole, not trimmed away
    assert analysis.reel_merge_cap(240) == 60.0 and analysis.reel_merge_cap(None) == 150.0 and analysis.reel_merge_cap(3600) == 150.0


def test_a_joined_moment_is_named_after_its_best_part_and_invents_no_reason():
    one = analysis.merge_segments(moments(), min_gap=8.0, max_dur=150.0)[0]
    assert one["hook_text"] == "best" and one["final_score"] == 90 and not one.get("reason")


def test_a_rate_limited_gemini_model_is_skipped_at_once_and_on_the_next_call(monkeypatch):
    asked = []

    class Reply:
        def __init__(self, code):
            self.status_code = code

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"{self.status_code} error")

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "{}"}]}}]}

    def post(url, **kw):
        asked.append(url.split("/models/")[1].split(":")[0])
        return Reply(429 if asked[-1] == "gemini-3.6-flash" else 200)
    monkeypatch.setattr(script_gen, "_GEMINI_COOLDOWN", {})
    monkeypatch.setattr(script_gen, "GEMINI_API_KEY", "k")
    for name in ("FORCE_OLLAMA", "LLM_PROVIDER", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(script_gen.requests, "post", post)
    monkeypatch.setattr(script_gen.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("waited")))
    for _ in range(2):
        assert script_gen.get_llm_response("p", "s") == "{}"
    assert asked == ["gemini-3.6-flash", "gemini-flash-lite-latest", "gemini-flash-lite-latest"]
