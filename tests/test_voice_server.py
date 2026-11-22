import ast

from engine import voice_server


def test_not_installed_in_an_empty_folder_and_the_message_says_how(tmp_path):
    assert not voice_server.installed(str(tmp_path))
    installed, running, message = voice_server.status(str(tmp_path), port=1)
    assert (installed, running) == (False, False) and "Install" in message


def test_installed_needs_the_python_the_server_script_and_the_ready_mark(tmp_path):
    p = voice_server.paths(str(tmp_path))
    for key in ("python", "server"):
        __import__("os").makedirs(__import__("os").path.dirname(p[key]), exist_ok=True)
        open(p[key], "w").close()
    assert not voice_server.installed(str(tmp_path))
    open(p["ready"], "w").close()
    assert voice_server.installed(str(tmp_path))


def test_the_server_script_is_valid_python_and_listens_on_this_pc_only():
    ast.parse(voice_server.SERVER_SOURCE)
    assert '("127.0.0.1", PORT)' in voice_server.SERVER_SOURCE and "0.0.0.0" not in voice_server.SERVER_SOURCE
    assert "sample_audio_b64" in voice_server.SERVER_SOURCE and "exaggeration" in voice_server.SERVER_SOURCE   # what engine.voiceover sends


def test_stop_does_nothing_without_a_pid_file_and_start_refuses_when_not_installed(tmp_path):
    assert voice_server.stop(str(tmp_path)) is False
    try:
        voice_server.start(str(tmp_path), port=1)
    except RuntimeError as e:
        assert "not installed" in str(e)
    else:
        raise AssertionError("start must refuse")


def test_the_cli_status_runs():
    assert voice_server.main(["status"]) == 0


def test_the_server_script_takes_a_port_or_the_check_flag(monkeypatch):
    for argv, port in ((["server.py"], 8080), (["server.py", "9001"], 9001), (["server.py", "--check"], 8080)):
        monkeypatch.setattr("sys.argv", argv)
        header = voice_server.SERVER_SOURCE.split("LOCK = ")[0]       # imports and the PORT line only
        scope = {}
        exec(compile(header, "server.py", "exec"), scope)
        assert scope["PORT"] == port


def test_the_server_script_picks_the_multilingual_model_for_other_languages():
    src = voice_server.SERVER_SOURCE
    ast.parse(src)
    assert "ChatterboxMultilingualTTS" in src and 'kwargs["language_id"] = language' in src and "model(language)" in src
