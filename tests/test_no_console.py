"""Every program that starts helper processes turns on the no-console-window switch (Windows)."""
import os
import re
import subprocess

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENTRY_POINTS = ("shortsflow/_main.py", "webui.py", "gui_app.py", "mcp_server.py", "shortsflow/api/jobs.py")


@pytest.mark.parametrize("path", ENTRY_POINTS)
def test_entry_point_installs_the_no_console_switch(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        source = f.read()
    assert re.search(r"^\s*from engine import proc as _no_console$", source, re.M), path
    assert re.search(r"^\s*_no_console\.install\(\)", source, re.M), path


def test_install_adds_the_flag_to_every_popen(monkeypatch):
    from engine import proc
    seen = {}
    monkeypatch.setattr(subprocess.Popen, "__init__", lambda self, *a, **k: seen.update(k))
    monkeypatch.setattr(proc, "NO_WINDOW", 0x08000000)
    monkeypatch.setattr(proc, "_installed", False)
    proc.install()
    subprocess.Popen.__new__(subprocess.Popen).__init__(["x"])
    assert seen["creationflags"] == 0x08000000
