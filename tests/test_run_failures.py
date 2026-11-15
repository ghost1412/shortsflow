from engine.friendly_errors import explain_run_failure


def test_common_failures_are_explained():
    assert "FFmpeg" in explain_run_failure("FileNotFoundError: ffmpeg not found")
    assert "Node.js" in explain_run_failure("'node' is not recognized as an internal or external command")
    assert "graphics card" in explain_run_failure("OpenEncodeSessionEx failed: out of encoder sessions")
    assert "disk is full" in explain_run_failure("OSError: [Errno 28] No space left on device")
    assert "downloaded" in explain_run_failure("ERROR: Video unavailable")


def test_unknown_or_empty_log_gives_nothing():
    assert explain_run_failure("all fine, 3 clips") is None
    assert explain_run_failure(None) is None
