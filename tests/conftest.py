import os
import sys

# Make `engine` importable when pytest runs from any directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture(autouse=True)
def _private_transcript_cache(tmp_path, monkeypatch):
    """Tests never read or write the real ~/.shortsflow cache."""
    monkeypatch.setenv("SHORTSFLOW_CACHE_DIR", str(tmp_path / "shortsflow-cache"))


@pytest.fixture(autouse=True)
def _private_home(tmp_path_factory, monkeypatch):
    """Tests never read or write the real home folder (~/.shortsflow: the icon library, the picture cache, the puzzle history, ...): two tests once wrote
    there and then failed on their second run. `~` points at an empty folder per test."""
    home = tmp_path_factory.mktemp("home")                 # beside the test's own folder, never inside it (some tests check that nothing else was written there)
    for name in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(name, str(home))
    monkeypatch.setenv("SHORTSFLOW_ICONS", str(home / "icons"))
    monkeypatch.setenv("SHORTSFLOW_CHARACTERS", str(home / "characters"))
    monkeypatch.setenv("SHORTSFLOW_STORY_OBJECTS", str(home / "story_objects"))
