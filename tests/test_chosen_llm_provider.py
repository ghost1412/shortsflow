"""A provider the user chose is the only one the prompt is sent to; only "auto" falls back."""
import pytest
import requests

from engine import script_gen

KEYS = ("GEMINI_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "HF_API_KEY")


@pytest.fixture
def sent(monkeypatch):
    """Every key set and every request failing: returns the list of (url, timeout) the prompt was sent to."""
    calls = []

    def post(url, **kw):
        calls.append((url, kw.get("timeout")))
        raise requests.exceptions.ConnectionError("down")

    for name in KEYS:
        monkeypatch.setenv(name, "k")
        monkeypatch.setattr(script_gen, name, "k", raising=False)
    for name in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "FORCE_OLLAMA"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(script_gen, "_GEMINI_COOLDOWN", {})
    monkeypatch.setattr(script_gen, "LOCAL_LLM_URL", "http://localhost:11434/api/chat")
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(script_gen.requests, "post", post)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return calls


@pytest.mark.parametrize("provider, host", [
    ("ollama", "localhost:11434"), ("gemini", "generativelanguage.googleapis.com"), ("openai", "api.openai.com"),
    ("anthropic", "api.anthropic.com"), ("deepseek", "api.deepseek.com"), ("groq", "api.groq.com"), ("openrouter", "openrouter.ai")])
def test_a_chosen_provider_that_fails_sends_the_prompt_nowhere_else(sent, monkeypatch, provider, host):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    with pytest.raises(RuntimeError, match="Nothing was sent to any other provider"):
        script_gen.get_llm_response("p")
    assert sent and all(host in url for url, _ in sent), sent


def test_a_chosen_provider_without_a_key_does_not_fall_back(sent, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.setattr(script_gen, "OPENAI_API_KEY", None)
    with pytest.raises(RuntimeError, match="openai"):
        script_gen.get_llm_response("p", provider="openai")
    assert sent == []


def test_your_own_server_is_the_only_place_a_custom_prompt_goes(sent, monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "http://localhost:1234/v1/chat/completions")
    with pytest.raises(RuntimeError):
        script_gen.get_llm_response("p", provider="custom")
    assert sent and all("localhost:1234" in url for url, _ in sent), sent


def test_the_chosen_local_model_gets_time_to_load_and_the_automatic_one_does_not_hold_the_chain(sent, monkeypatch):
    with pytest.raises(RuntimeError):
        script_gen.get_llm_response("p", provider="ollama", timeout=60)
    assert [t for _, t in sent] == [600]
    sent.clear()
    with pytest.raises(RuntimeError):
        script_gen.get_llm_response("p", timeout=60)
    assert [t for url, t in sent if "11434" in url] == [12]
    assert any("groq" in url for url, _ in sent) and any("huggingface" in url for url, _ in sent)      # automatic still falls back


def test_force_ollama_means_ollama_only(sent, monkeypatch):
    monkeypatch.setenv("FORCE_OLLAMA", "true")
    with pytest.raises(RuntimeError):
        script_gen.get_llm_response("p")
    assert sent and all("11434" in url for url, _ in sent), sent
