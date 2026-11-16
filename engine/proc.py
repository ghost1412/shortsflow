"""Run helper programs (FFmpeg and friends) without a console window flashing up on Windows.

`run`, `Popen`, `check_output` and `call` are `subprocess` with `creationflags=CREATE_NO_WINDOW` added on Windows; on other systems
they are exactly `subprocess`. A caller that passes its own `creationflags` keeps them (the window flag is added to them).
"""
import os
import subprocess

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0


def _flags(kwargs):
    if NO_WINDOW:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | NO_WINDOW
    return kwargs


_DETACHED, _NEW_CONSOLE = 0x00000008, 0x00000010


def with_no_window(kwargs):
    """kwargs with CREATE_NO_WINDOW added (Windows only), unless the caller asked for a detached process or its own console."""
    if NO_WINDOW:
        flags = kwargs.get("creationflags", 0) or 0
        if not flags & (_DETACHED | _NEW_CONSOLE):
            kwargs["creationflags"] = flags | NO_WINDOW
    return kwargs


_installed = False


def install():
    """Make every program started through `subprocess` in this process (FFmpeg, Node, yt-dlp, Whisper helpers, ... also inside other
    libraries) start without a console window on Windows. Safe to call more than once; does nothing on other systems."""
    global _installed
    if _installed or not NO_WINDOW:
        return
    original = subprocess.Popen.__init__

    def init(self, *args, **kwargs):
        original(self, *args, **with_no_window(kwargs))
    subprocess.Popen.__init__ = init
    _installed = True


def run(*args, **kwargs):
    return subprocess.run(*args, **_flags(kwargs))


def Popen(*args, **kwargs):  # noqa: N802 (same name as subprocess.Popen)
    return subprocess.Popen(*args, **_flags(kwargs))


def check_output(*args, **kwargs):
    return subprocess.check_output(*args, **_flags(kwargs))


def call(*args, **kwargs):
    return subprocess.call(*args, **_flags(kwargs))
