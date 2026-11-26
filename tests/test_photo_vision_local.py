"""With SHORTSFLOW_VISION=ollama the photos of a photo reel are not sent anywhere but the local model."""
import pytest
import requests
from PIL import Image

from engine import script_gen, visual_context


@pytest.fixture
def sent(monkeypatch, tmp_path):
    calls = []

    def post(url, **kw):
        calls.append(url)
        raise requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(script_gen, "GEMINI_API_KEY", "k", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    monkeypatch.delenv("LOCAL_LLM_URL", raising=False)
    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(script_gen.requests, "post", post)
    monkeypatch.setattr(visual_context, "pick_vision_model", lambda *a, **k: "gemma3:12b")
    photo = tmp_path / "a.jpg"
    Image.new("RGB", (64, 64), "red").save(photo)
    return calls, [str(photo)]


def test_local_pictures_means_no_photo_leaves_the_pc(sent, monkeypatch):
    calls, photos = sent
    monkeypatch.setenv("SHORTSFLOW_VISION", "ollama")
    result = script_gen.analyze_photo_story_with_vision(photos)
    assert result["ordered_indices"] == [0]
    assert calls and all(url.startswith("http://localhost:11434") for url in calls), calls


def test_automatic_still_asks_gemini_first(sent, monkeypatch):
    calls, photos = sent
    monkeypatch.delenv("SHORTSFLOW_VISION", raising=False)
    script_gen.analyze_photo_story_with_vision(photos)
    assert "generativelanguage" in calls[0]
