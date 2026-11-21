"""Optional realistic presenter: a photo of a face talks with the narration (SadTalker, run locally on the GPU).

It is an add-on: nothing here runs unless it was installed with `python -m engine.talking_head install`, which puts SadTalker, its own Python
(3.10 to 3.12, through the `py` launcher) and its model files (about 2.5 GB, plus about 2.5 GB of PyTorch) in one folder,
`~/.shortsflow/talking_head` (or SHORTSFLOW_TALKING_HEAD), apart from ShortsFlow's own packages. Everything runs on this PC: the photo and the
voice never leave it. A video takes GPU minutes (roughly the narration's length, or more on a small card).

Only use your own face, or the face of someone who agreed: a talking face of another person can be used to fake them.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request

REPO = "https://github.com/OpenTalker/SadTalker.git"
TORCH = ["torch==2.2.2", "torchvision==0.17.2", "torchaudio==2.2.2", "--index-url", "https://download.pytorch.org/whl/cu121"]
PACKAGES = ["numpy==1.26.4", "face_alignment==1.4.1", "imageio==2.34.0", "imageio-ffmpeg==0.4.9", "librosa==0.10.1", "numba==0.59.1",
            "resampy==0.4.3", "pydub==0.25.1", "scipy==1.11.4", "kornia==0.6.8", "tqdm", "yacs==0.1.8", "pyyaml", "joblib==1.3.2",
            "scikit-image==0.22.0", "basicsr==1.4.2", "facexlib==0.3.0", "gfpgan==1.3.8", "safetensors", "opencv-python==4.9.0.80"]
_REL = "https://github.com/OpenTalker/SadTalker/releases/download/v0.0.2-rc/"
MODELS = {
    "checkpoints/mapping_00109-model.pth.tar": _REL + "mapping_00109-model.pth.tar",
    "checkpoints/mapping_00229-model.pth.tar": _REL + "mapping_00229-model.pth.tar",
    "checkpoints/SadTalker_V0.0.2_256.safetensors": _REL + "SadTalker_V0.0.2_256.safetensors",
    "gfpgan/weights/alignment_WFLW_4HG.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/alignment_WFLW_4HG.pth",
    "gfpgan/weights/detection_Resnet50_Final.pth": "https://github.com/xinntao/facexlib/releases/download/v0.1.0/detection_Resnet50_Final.pth",
    "gfpgan/weights/GFPGANv1.4.pth": "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
    "gfpgan/weights/parsing_parsenet.pth": "https://github.com/xinntao/facexlib/releases/download/v0.2.2/parsing_parsenet.pth",
}


def home():
    return os.environ.get("SHORTSFLOW_TALKING_HEAD") or os.path.join(os.path.expanduser("~"), ".shortsflow", "talking_head")


def paths(base=None):
    base = base or home()
    py = os.path.join(base, "env", "Scripts", "python.exe") if os.name == "nt" else os.path.join(base, "env", "bin", "python")
    return {"base": base, "repo": os.path.join(base, "SadTalker"), "python": py, "cache": os.path.join(base, "cache")}


def installed(base=None):
    """True when SadTalker, its Python and every model file are in place."""
    p = paths(base)
    return (os.path.isfile(p["python"]) and os.path.isfile(os.path.join(p["repo"], "inference.py"))
            and all(os.path.isfile(os.path.join(p["repo"], rel)) for rel in MODELS))


def status(base=None):
    if installed(base):
        return True, f"Installed in {paths(base)['base']}."
    return False, "Not installed. Run `python -m engine.talking_head install` (about 5 GB, needs an NVIDIA GPU)."


def _find_python():
    """A Python 3.10-3.12 to build SadTalker's own environment (its packages do not support newer ones). A Python that lives inside a CI
    runner's tool cache is skipped: the add-on would break when the cache is cleaned."""
    if os.name == "nt" and shutil.which("py"):
        for v in ("3.12", "3.11", "3.10"):
            r = subprocess.run(["py", f"-{v}", "-c", "import sys; print(sys.executable)"], capture_output=True, text=True)
            if r.returncode == 0 and "_tool" not in r.stdout and "actions-runner" not in r.stdout:
                return ["py", f"-{v}"]
    for name in ("python3.12", "python3.11", "python3.10"):
        if shutil.which(name):
            return [name]
    return None


def _run(cmd, log, cwd=None):
    log("$ " + " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    tail = []
    for line in proc.stdout:
        tail = (tail + [line.rstrip()])[-30:]
        if any(k in line for k in ("Successfully", "ERROR", "error:", "Downloading", "Cloning")):
            log("  " + line.rstrip()[:200])
    if proc.wait() != 0:
        raise RuntimeError(f"Failed: {' '.join(cmd[:4])}...\n" + "\n".join(tail[-12:]))


def _download(url, dest, log):
    if os.path.isfile(dest) and os.path.getsize(dest) > 1000:
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    log(f"Downloading {os.path.basename(dest)} ...")
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "shortsflow-installer"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    os.replace(tmp, dest)


# Small fixes so SadTalker runs with the package versions above (it was written for older ones). Each is (file, old, new).
PATCHES = [
    ("src/utils/audio.py", "return librosa.filters.mel(hp.sample_rate, hp.n_fft, n_mels=hp.num_mels,",
     "return librosa.filters.mel(sr=hp.sample_rate, n_fft=hp.n_fft, n_mels=hp.num_mels,"),
    ("src/face3d/util/preprocess.py", "trans_params = np.array([w0, h0, s, t[0], t[1]])",
     "trans_params = np.array([w0, h0, s, t[0][0], t[1][0]])"),
    ("src/face3d/util/my_awing_arch.py", "preds = preds.astype(np.float, copy=False)", "preds = preds.astype(float, copy=False)"),
]


def _patch(repo, log):
    for rel, old, new in PATCHES:
        path = os.path.join(repo, rel)
        if not os.path.isfile(path):
            continue
        text = open(path, encoding="utf-8").read()
        if old in text:
            open(path, "w", encoding="utf-8").write(text.replace(old, new))
            log(f"Patched {rel}")
    # basicsr imports a torchvision module that newer torchvision renamed
    import glob
    for deg in glob.glob(os.path.join(os.path.dirname(repo), "env", "**", "basicsr", "data", "degradations.py"), recursive=True):
        text = open(deg, encoding="utf-8").read()
        if "functional_tensor import" in text:
            open(deg, "w", encoding="utf-8").write(text.replace("torchvision.transforms.functional_tensor import", "torchvision.transforms.functional import"))
            log("Patched basicsr for torchvision")


def install(base=None, log=print):
    """Install SadTalker with its own Python and its model files. Safe to run again: finished steps are skipped."""
    p = paths(base)
    os.makedirs(p["base"], exist_ok=True)
    if not shutil.which("git"):
        raise RuntimeError("git is needed to fetch SadTalker.")
    if not os.path.isfile(os.path.join(p["repo"], "inference.py")):
        _run(["git", "clone", "--depth", "1", REPO, p["repo"]], log)
    if not os.path.isfile(p["python"]):
        py = _find_python()
        if not py:
            raise RuntimeError("SadTalker needs Python 3.10 or 3.11 next to your Python (install it from python.org).")
        _run(py + ["-m", "venv", os.path.join(p["base"], "env")], log)
    _run([p["python"], "-m", "pip", "install", "--upgrade", "pip", "wheel", "setuptools<70"], log)
    _run([p["python"], "-m", "pip", "install", *TORCH], log)
    _run([p["python"], "-m", "pip", "install", *PACKAGES], log)
    for rel, url in MODELS.items():
        _download(url, os.path.join(p["repo"], rel), log)
    _patch(p["repo"], log)
    ok = installed(base)
    log("Done: the realistic presenter is ready." if ok else "Something is still missing; run install again.")
    return ok


def _key(photo, audio):
    h = hashlib.sha1()
    for f in (photo, audio):
        with open(f, "rb") as fh:
            h.update(hashlib.sha1(fh.read()).digest())
    return h.hexdigest()[:16]


def make(photo, audio, out_path, base=None, log=print, enhance=True, run=None):
    """A video of the face in `photo` saying `audio` (head moves kept small), written to out_path. Cached by photo and audio. Returns out_path."""
    p = paths(base)
    if not installed(base):
        raise RuntimeError(status(base)[1])
    for f in (photo, audio):
        if not os.path.isfile(f):
            raise RuntimeError(f"Missing file: {f}")
    os.makedirs(p["cache"], exist_ok=True)
    cached = os.path.join(p["cache"], _key(photo, audio) + ".mp4")
    if not os.path.isfile(cached):
        work = os.path.join(p["cache"], "work_" + _key(photo, audio))
        os.makedirs(work, exist_ok=True)
        wav = os.path.join(work, "voice.wav")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", audio, "-ac", "1", "-ar", "16000", wav], check=True)
        cmd = [p["python"], "inference.py", "--driven_audio", wav, "--source_image", os.path.abspath(photo), "--result_dir", work,
               "--preprocess", "crop", "--still", "--size", "256", "--expression_scale", "1.0", "--batch_size", "2"]
        if enhance:
            cmd += ["--enhancer", "gfpgan"]
        log("[Log] Talking head: drawing the photo talking (GPU, this takes a while)...")
        (run or _run)(cmd, log, cwd=p["repo"])
        made = sorted((os.path.join(dp, f) for dp, _, fs in os.walk(work) for f in fs if f.endswith(".mp4")), key=os.path.getmtime)
        if not made:
            raise RuntimeError("SadTalker made no video (see the lines above).")
        shutil.copy(made[-1], cached)
        shutil.rmtree(work, ignore_errors=True)           # its own scratch files (frames, wav); only the finished video is kept
    shutil.copy(cached, out_path)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "install":
        sys.exit(0 if install() else 1)
    if len(sys.argv) > 1 and sys.argv[1] == "status":
        print(status()[1])
        sys.exit(0)
    if len(sys.argv) == 5 and sys.argv[1] == "make":
        print(make(sys.argv[2], sys.argv[3], sys.argv[4]))
        sys.exit(0)
    print("python -m engine.talking_head install | status | make PHOTO AUDIO OUT.mp4")
    sys.exit(2)
