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


def run(*args, **kwargs):
    return subprocess.run(*args, **_flags(kwargs))


def Popen(*args, **kwargs):  # noqa: N802 (same name as subprocess.Popen)
    return subprocess.Popen(*args, **_flags(kwargs))


def check_output(*args, **kwargs):
    return subprocess.check_output(*args, **_flags(kwargs))


def call(*args, **kwargs):
    return subprocess.call(*args, **_flags(kwargs))
