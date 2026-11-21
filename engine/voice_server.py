"""Optional local voice-cloning server for `--mode VOICEOVER` (Chatterbox, run on this PC).

An add-on: nothing here runs unless it was installed with `python -m engine.voice_server install` (or the "Set up" button on the Voice-over
card). That builds a private Python 3.10-3.12 environment with PyTorch and Chatterbox in one folder, `~/.shortsflow/voice_server` (or
SHORTSFLOW_VOICE_SERVER), apart from ShortsFlow's own packages: about 2.5 GB of PyTorch plus about 3 GB of model files. The server then listens on
127.0.0.1 only (default port 8080), so the script and your voice sample never leave this PC.

    python -m engine.voice_server install | start | stop | status

Only clone your own voice, or the voice of someone who agreed.
"""
import json
import os
import subprocess
import sys
import time

DEFAULT_PORT = 8080
TORCH = ["torch==2.6.0", "torchaudio==2.6.0", "--index-url", "https://download.pytorch.org/whl/cu124"]
PACKAGES = ["chatterbox-tts"]

SERVER_SOURCE = r'''
import base64, hashlib, json, os, sys, tempfile, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 8080
LOCK = threading.Lock()
MODEL = {}


def model():
    if "m" not in MODEL:
        import torch
        from chatterbox.tts import ChatterboxTTS
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print("loading the voice model on", device, flush=True)
        MODEL["m"], MODEL["device"] = ChatterboxTTS.from_pretrained(device=device), device
    return MODEL["m"]


def sample_file(b64):
    raw = base64.b64decode(b64)
    path = os.path.join(tempfile.gettempdir(), "sf_voice_" + hashlib.sha1(raw).hexdigest()[:16] + ".wav")
    if not os.path.exists(path):
        with open(path, "wb") as f:
            f.write(raw)
    return path


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, kind="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._send(200, json.dumps({"ok": True, "loaded": "m" in MODEL}).encode())

    def do_POST(self):
        try:
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            text = (data.get("input") or data.get("text") or "").strip()
            if not text:
                return self._send(400, b'{"error": "no text"}')
            kwargs = {"exaggeration": float(data.get("exaggeration", 0.5)), "cfg_weight": 0.5}
            if data.get("sample_audio_b64"):
                kwargs["audio_prompt_path"] = sample_file(data["sample_audio_b64"])
            import io
            import torchaudio
            with LOCK:
                m = model()
                wav = m.generate(text, **kwargs)
                buf = io.BytesIO()
                torchaudio.save(buf, wav.cpu(), m.sr, format="wav")
            self._send(200, buf.getvalue(), "audio/wav")
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode())


if __name__ == "__main__":
    if "--check" in sys.argv:
        model()
        print("model ready", flush=True)
        sys.exit(0)
    print("voice server on 127.0.0.1:%d" % PORT, flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
'''


def home():
    return os.environ.get("SHORTSFLOW_VOICE_SERVER") or os.path.join(os.path.expanduser("~"), ".shortsflow", "voice_server")


def paths(base=None):
    base = base or home()
    py = os.path.join(base, "env", "Scripts", "python.exe") if os.name == "nt" else os.path.join(base, "env", "bin", "python")
    return {"base": base, "python": py, "server": os.path.join(base, "server.py"), "ready": os.path.join(base, "installed.ok"),
            "pid": os.path.join(base, "server.pid"), "log": os.path.join(base, "server.log")}


def installed(base=None):
    p = paths(base)
    return os.path.isfile(p["python"]) and os.path.isfile(p["server"]) and os.path.isfile(p["ready"])


def url(port=DEFAULT_PORT):
    return f"http://127.0.0.1:{port}"


def running(port=DEFAULT_PORT):
    """True when something answers on the server's port."""
    import urllib.request
    try:
        with urllib.request.urlopen(url(port), timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def status(base=None, port=DEFAULT_PORT):
    """(installed, running, one plain sentence)."""
    inst, run = installed(base), running(port)
    if run:
        return inst, True, f"The voice server is running on this PC (port {port})."
    if inst:
        return True, False, "Installed, not running. It starts by itself when you make a voice-over (the first one also loads the model)."
    return False, False, "Not installed. Press 'Install' once: about 5.5 GB of downloads (PyTorch and the voice model), then it runs locally."


def _find_python():
    """The command of a Python 3.10-3.12 (Chatterbox does not support newer ones), through the `py` launcher on Windows."""
    import shutil
    if os.name == "nt" and shutil.which("py"):
        for v in ("3.11", "3.12", "3.10"):
            if subprocess.run(["py", f"-{v}", "-c", "pass"], capture_output=True).returncode == 0:
                return ["py", f"-{v}"]
    for name in ("python3.11", "python3.12", "python3.10"):
        if shutil.which(name):
            return [name]
    return None


def _run(cmd, log, cwd=None):
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    for line in proc.stdout:
        if line.strip():
            log(line.rstrip()[:300])
    if proc.wait() != 0:
        raise RuntimeError(f"A setup step failed: {' '.join(cmd[:4])} ... (exit {proc.returncode}). The lines above say why.")


def install(base=None, log=print):
    p = paths(base)
    if installed(base):
        log(f"[Log] Already installed in {p['base']}.")
        return p
    py = _find_python()
    if not py:
        raise RuntimeError("The voice server needs Python 3.10, 3.11 or 3.12 next to your Python (install it from python.org).")
    os.makedirs(p["base"], exist_ok=True)
    if not os.path.isfile(p["python"]):
        _run(py + ["-m", "venv", os.path.join(p["base"], "env")], log)
    log("[Log] Installing PyTorch (about 2.5 GB)...")
    _run([p["python"], "-m", "pip", "install", "--upgrade", "pip"], log)
    _run([p["python"], "-m", "pip", "install", *TORCH], log)
    log("[Log] Installing Chatterbox...")
    _run([p["python"], "-m", "pip", "install", *PACKAGES], log)
    with open(p["server"], "w", encoding="utf-8") as f:
        f.write(SERVER_SOURCE)
    log("[Log] Downloading and loading the voice model (about 3 GB) to check it works...")
    _run([p["python"], p["server"], "--check"], log)
    with open(p["ready"], "w", encoding="utf-8") as f:
        f.write("ok")
    log(f"[Success] The voice server is installed in {p['base']}.")
    return p


def start(base=None, port=DEFAULT_PORT, log=print):
    """Start the server in the background (it keeps running after this process ends). Returns its url."""
    if running(port):
        return url(port)
    if not installed(base):
        raise RuntimeError("The voice server is not installed. Press 'Install' on the Voice-over card, or run `python -m engine.voice_server install`.")
    p = paths(base)
    flags = (subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS) if os.name == "nt" else 0
    with open(p["log"], "ab") as out:
        proc = subprocess.Popen([p["python"], p["server"], str(port)], stdout=out, stderr=subprocess.STDOUT, creationflags=flags,
                                **({"start_new_session": True} if os.name != "nt" else {}))
    with open(p["pid"], "w", encoding="utf-8") as f:
        f.write(str(proc.pid))
    log("[Log] Starting the voice server...")
    for _ in range(60):
        if running(port):
            return url(port)
        if proc.poll() is not None:
            raise RuntimeError(f"The voice server stopped at start-up. See {p['log']}.")
        time.sleep(1)
    raise RuntimeError(f"The voice server did not answer in time. See {p['log']}.")


def stop(base=None):
    """Stop the server this module started (the exact process in its pid file, nothing else). True when one was stopped."""
    p = paths(base)
    try:
        with open(p["pid"], "r", encoding="utf-8") as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return False
    if os.name == "nt":
        res = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
        ok = res.returncode == 0
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
            ok = True
        except OSError:
            ok = False
    try:
        os.remove(p["pid"])
    except OSError:
        pass
    return ok


def ensure_running(port=DEFAULT_PORT, log=print):
    """The server's url when the add-on is installed (started if needed), else None."""
    if running(port):
        return url(port)
    if installed():
        return start(port=port, log=log)
    return None


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    cmd = argv[0] if argv else "status"
    try:
        if cmd == "install":
            install()
        elif cmd == "start":
            print(f"[Success] Running at {start()}")
        elif cmd == "stop":
            print("[Success] Stopped." if stop() else "[Log] Nothing of ours was running.")
        else:
            print(json.dumps(dict(zip(("installed", "running", "message"), status())), indent=2))
    except RuntimeError as e:
        print(f"[Error] {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
