import json
import os
import subprocess
import sys

import mcp_server
from shortsflow import __version__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _talk(messages, cwd):
    """Send JSON-RPC lines to a fresh `python mcp_server.py` started from `cwd` and return the parsed replies."""
    payload = "".join(json.dumps(m) + "\n" for m in messages)
    out = subprocess.run([sys.executable, os.path.join(ROOT, "mcp_server.py")], input=payload, capture_output=True, text=True,
                         encoding="utf-8", cwd=cwd, timeout=60).stdout
    return [json.loads(line) for line in out.splitlines() if line.strip().startswith("{")]


def test_handshake_and_tool_list_work_from_any_working_directory(tmp_path):
    replies = _talk([
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ], cwd=str(tmp_path))
    by_id = {r["id"]: r for r in replies if "id" in r}
    info = by_id[1]["result"]["serverInfo"]
    assert info["version"] == __version__                     # not a stale hard-coded number
    tools = {t["name"] for t in by_id[2]["result"]["tools"]}
    assert tools == {"generate_short", "extract_clips", "generate_social_package", "get_render_status", "list_supported_modes",
                     "create_explainer", "dub_video", "list_videos", "publish_video"}
    assert all(t["inputSchema"]["type"] == "object" for t in by_id[2]["result"]["tools"])


def test_render_jobs_run_main_py_by_absolute_path_in_the_repo(monkeypatch, tmp_path):
    """AI tools start the server from arbitrary folders; `python main.py` must not depend on the caller's cwd."""
    seen = {}

    def fake_popen(cmd, **kwargs):
        seen["cmd"], seen["cwd"] = cmd, kwargs.get("cwd")
        raise RuntimeError("stop here")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mcp_server.subprocess, "Popen", fake_popen)
    mcp_server.run_main_command("job-test", ["--mode", "FACTS"])
    assert os.path.isabs(seen["cmd"][1]) and seen["cmd"][1].endswith("main.py") and os.path.exists(seen["cmd"][1])
    assert os.path.abspath(seen["cwd"]) == ROOT
    assert "--mode" in seen["cmd"] and "--skip_upload" in seen["cmd"]


def test_a_minimal_container_still_answers_introspection_and_explains_rendering(tmp_path):
    """Dockerfile.mcp only copies mcp_server.py and shortsflow/__init__.py: it must start, list the tools, and fail a render politely."""
    import shutil
    import time
    (tmp_path / "shortsflow").mkdir()
    shutil.copy(os.path.join(ROOT, "mcp_server.py"), tmp_path / "mcp_server.py")
    shutil.copy(os.path.join(ROOT, "shortsflow", "__init__.py"), tmp_path / "shortsflow" / "__init__.py")
    NL = chr(10)
    p = subprocess.Popen([sys.executable, "-I", "mcp_server.py"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, encoding="utf-8", cwd=str(tmp_path))

    def send(obj):
        p.stdin.write(json.dumps(obj) + NL)
        p.stdin.flush()

    def recv():
        end = time.time() + 30
        while time.time() < end:
            line = p.stdout.readline()
            if line.strip():
                return json.loads(line)
        raise AssertionError("no reply from the MCP server")

    try:
        send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                                                                              "clientInfo": {"name": "t", "version": "1"}}})
        assert recv()["result"]["serverInfo"]["version"] == __version__
        send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        assert len(recv()["result"]["tools"]) == 9
        send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "generate_short", "arguments": {"mode": "FACTS"}}})
        job_id = json.loads(recv()["result"]["content"][0]["text"])["job_id"]
        time.sleep(1.5)
        send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "get_render_status", "arguments": {"job_id": job_id}}})
        status = json.loads(recv()["result"]["content"][0]["text"])
        assert status["status"] == "failed" and "full ShortsFlow checkout" in status["error"]
    finally:
        p.terminate()


def _cli_choices():
    """{'--flag': set(choices)} read from the pipeline's argparse setup without importing it (it runs code on import)."""
    import ast
    tree = ast.parse(open(os.path.join(ROOT, "shortsflow", "_main.py"), encoding="utf-8").read())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument" and node.args:
            flag = node.args[0]
            for kw in node.keywords:
                if kw.arg == "choices" and isinstance(flag, ast.Constant) and isinstance(kw.value, (ast.List, ast.Tuple)):
                    found[flag.value] = {e.value for e in kw.value.elts if isinstance(e, ast.Constant)}
    return found


def test_every_option_the_schema_offers_is_accepted_by_the_pipeline():
    """The schema once offered edge-tts, gtts and chime, which main.py rejects, so a client following it got an error."""
    choices = _cli_choices()
    wanted = {"mode": "--mode", "vibe": "--vibe", "caption_style": "--caption_style", "tts_provider": "--tts_provider",
              "aspect_ratio": "--aspect_ratio", "sfx_preset": "--sfx_preset", "layout": "--layout"}
    checked = 0
    for tool in mcp_server.TOOLS_DEFINITIONS:
        for name, prop in tool["inputSchema"].get("properties", {}).items():
            if name in wanted and "enum" in prop:
                bad = set(prop["enum"]) - choices[wanted[name]]
                assert not bad, f"{tool['name']}.{name} offers {sorted(bad)} which {wanted[name]} does not accept"
                assert prop.get("default") in prop["enum"]
                checked += 1
    assert checked >= 8


def test_every_tool_and_parameter_is_described():
    for tool in mcp_server.TOOLS_DEFINITIONS:
        assert len(tool["description"]) >= 120, tool["name"]          # purpose, how it behaves, when to use the other tools
        for name, prop in tool["inputSchema"].get("properties", {}).items():
            assert prop.get("description"), f"{tool['name']}.{name} has no description"
        for name in tool["inputSchema"].get("required", []):
            assert name in tool["inputSchema"]["properties"]
    names = {t["name"] for t in mcp_server.TOOLS_DEFINITIONS}
    assert {"create_explainer", "dub_video", "list_videos", "publish_video"} <= names


def test_list_supported_modes_matches_the_schema():
    reply = mcp_server.handle_tool_call("list_supported_modes", {})
    info = json.loads(reply["content"][0]["text"])
    assert info["tts_providers"] == mcp_server.TTS_PROVIDERS and info["content_modes"] == mcp_server.CONTENT_MODES
    assert "edge-tts" not in info["tts_providers"] and "chime" not in info["sfx_presets"]


def test_the_explainer_dub_and_publish_lists_match_the_pipeline():
    from engine import case_options, publish
    assert mcp_server.EXPLAINER_TEMPLATES == list(case_options.TEMPLATES) and mcp_server.EXPLAINER_THEMES == list(case_options.THEMES)
    assert mcp_server.PUBLISH_PLATFORMS == list(publish.PLATFORMS) + ["youtube_direct"]


def _capture_job(monkeypatch):
    seen = {}
    monkeypatch.setattr(mcp_server, "run_main_command", lambda job_id, args: seen.update(args=args))
    monkeypatch.setattr(mcp_server.threading, "Thread", lambda target, args: type("T", (), {"start": lambda self: target(*args)})())
    return seen


def test_create_explainer_builds_the_case_command_and_asks_for_a_source(monkeypatch):
    seen = _capture_job(monkeypatch)
    bad = mcp_server.handle_tool_call("create_explainer", {"topic": "T"})
    assert bad["isError"] and "source" in bad["content"][0]["text"]
    ok = mcp_server.handle_tool_call("create_explainer", {"topic": "How X works", "sources": ["https://example.com/a"], "template": "postmortem",
                                                          "theme": "neon", "formats": "9:16", "draft": True})
    assert json.loads(ok["content"][0]["text"])["status"] == "processing"
    a = seen["args"]
    assert a[:4] == ["--mode", "CASE", "--prompt", "How X works"] and ["--sources", "https://example.com/a"] == a[4:6]
    assert "theme=neon" in a and "template=postmortem" in a and "formats=9:16" in a and "draft" in a
    mcp_server.handle_tool_call("create_explainer", {"topic": "Binary search", "kind": "animate"})
    assert seen["args"][:2] == ["--mode", "ANIMATE"] and "--sources" not in seen["args"]


def test_dub_video_needs_a_language_from_the_list(monkeypatch):
    seen = _capture_job(monkeypatch)
    assert mcp_server.handle_tool_call("dub_video", {"source_video": "a.mp4", "target_lang": "xx"})["isError"]
    mcp_server.handle_tool_call("dub_video", {"source_video": "a.mp4", "target_lang": "es", "dub_captions": True, "dub_voice": "male"})
    assert seen["args"] == ["--mode", "DUB", "--source_video", "a.mp4", "--target_lang", "es", "--dub_captions", "--dub_voice", "male"]


def test_publish_video_previews_by_default_and_refuses_paths_outside_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_server, "ROOT_DIR", str(tmp_path))
    folder = tmp_path / "sessions" / "case_a"
    folder.mkdir(parents=True)
    video = folder / "case_9x16.mp4"
    video.write_bytes(b"x" * 100)
    outside = tmp_path / "other.mp4"
    outside.write_bytes(b"x" * 100)
    assert mcp_server.handle_tool_call("publish_video", {"path": str(outside), "platforms": ["tiktok"]})["isError"]
    assert mcp_server.handle_tool_call("publish_video", {"path": str(video), "platforms": []})["isError"]
    calls = []
    from shortsflow import settings
    monkeypatch.setattr(settings, "publish_file", lambda path, *a, **k: calls.append(k) or (True, ["ok"]))
    out = json.loads(mcp_server.handle_tool_call("publish_video", {"path": str(video), "platforms": ["tiktok"]})["content"][0]["text"])
    assert out["dry_run"] is True and out["sent"] is False and calls[-1]["dry_run"] is True
    out = json.loads(mcp_server.handle_tool_call("publish_video", {"path": str(video), "platforms": ["tiktok"], "dry_run": False})["content"][0]["text"])
    assert out["dry_run"] is False and out["sent"] is True


def test_list_videos_reports_shape_and_where_it_was_published(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_server, "ROOT_DIR", str(tmp_path))
    folder = tmp_path / "sessions" / "case_a"
    folder.mkdir(parents=True)
    (folder / "case_9x16.mp4").write_bytes(b"x" * 60000)
    out = json.loads(mcp_server.handle_tool_call("list_videos", {"shape": "tall"})["content"][0]["text"])
    assert out["count"] == 1 and out["videos"][0]["shape"] == "tall" and out["videos"][0]["published_to"] == []
    assert json.loads(mcp_server.handle_tool_call("list_videos", {"shape": "wide"})["content"][0]["text"])["count"] == 0
