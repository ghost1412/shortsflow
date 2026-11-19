"""AGENTS.md is read by every agent that works on the repo: keep its facts true."""
import os
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
SECRET_FILES = {"client_secrets_drive.json", "token_drive.json"}          # named as things never to commit; they are not in the repo


def test_every_file_it_names_exists():
    named = set(re.findall(r"`([A-Za-z0-9_./\-]+\.(?:py|tsx|ts|md|yml|json|txt|bat|sh))`", AGENTS)) - SECRET_FILES
    missing = sorted(p for p in named if not (ROOT / p).exists())
    assert not missing, f"AGENTS.md names files that do not exist: {missing}"


def test_the_python_version_it_states_matches_the_package():
    minimum = re.search(r">=\s*(\d+\.\d+)", tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["requires-python"]).group(1)
    stated = re.search(r"\*\*Python\*\*: `(\d+\.\d+)\+`", AGENTS)
    assert stated and stated.group(1) == minimum, f"AGENTS.md says Python {stated and stated.group(1)}+, pyproject needs {minimum}+"


# Modes that were already undocumented in the README, docs/FEATURES.md and AGENTS.md when this test was written (2026-11-19). It is known debt: a NEW
# mode may not join this list (document it), and a mode that gets documented must be removed from it, so the list only shrinks.
UNDOCUMENTED_MODES = {"ARTICLE", "AUTO", "BIBLE", "CHALLENGE", "FILTER", "FIND_IT", "FUNNY_EXPLAINER", "GUESS_SOUND", "HORROR", "JWST", "MUSIC", "NEWS_SERIOUS",
                      "ODD_ONE_OUT", "PODCAST", "QUOTE", "REDDIT", "RIDDLE", "SPLIT_SCREEN", "TEACH", "TRAILER_MISSED", "TREND", "TRIVIA", "TRUE_CRIME", "UGC"}


def test_every_new_cli_mode_is_documented_and_the_known_gaps_only_shrink():
    main = (ROOT / "shortsflow" / "_main.py").read_text(encoding="utf-8")
    modes = re.findall(r'"([A-Z_0-9]+)"', re.search(r'"--mode".*?choices=\[(.*?)\]', main, re.S).group(1))
    docs = AGENTS + (ROOT / "docs" / "FEATURES.md").read_text(encoding="utf-8") + (ROOT / "README.md").read_text(encoding="utf-8")
    undocumented = {m for m in modes if not re.search(r"\b%s\b" % m, docs)}
    assert not (undocumented - UNDOCUMENTED_MODES), f"new modes with no documentation (add them to README, docs/FEATURES.md or AGENTS.md): {sorted(undocumented - UNDOCUMENTED_MODES)}"
    assert not (UNDOCUMENTED_MODES - undocumented), f"these modes are documented now: remove them from UNDOCUMENTED_MODES: {sorted(UNDOCUMENTED_MODES - undocumented)}"


def test_the_llm_fallback_order_it_states_is_the_order_the_code_tries():
    code = (ROOT / "engine" / "script_gen.py").read_text(encoding="utf-8")
    start = code.index("def get_llm_response(")
    body = code[start:start + 40000]
    positions = {name: body.find(marker) for name, marker in (
        ("Gemini", "Gemini API Fallback Chain"), ("DeepSeek", "# 3. DeepSeek"), ("OpenAI", "# 4. OpenAI"), ("Ollama", "# 5. Local LLM"),
        ("HuggingFace", "# 6. HuggingFace"))}
    assert all(p > 0 for p in positions.values()), positions
    order = sorted(positions, key=positions.get)
    stated = [n for n in ("Gemini", "DeepSeek", "OpenAI", "Ollama", "Groq", "HuggingFace") if n in AGENTS.split("fallback order")[1][:300]]
    assert [n for n in stated if n in positions] == order
