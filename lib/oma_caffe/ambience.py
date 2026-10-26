"""Lo-fi cafe ambience through mpv (PipeWire handles the output).

With no source configured, mpv synthesises a soft cafe bed: low brown noise
for the room, with a slow tremolo standing in for murmur and the swell of a
steam wand. Point ambience.source at a file, a directory or a stream URL to
use a real recording instead (`oma-caffe config ambience.source ~/Music/cafe.ogg`).
"""
import os
import signal
import subprocess
from pathlib import Path

from . import config, state

SYNTH = ("av://lavfi:anoisesrc=color=brown:amplitude=0.05,lowpass=f=650,"
         "tremolo=f=0.12:d=0.5,aecho=0.6:0.4:60:0.25")


def _alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:
        return b"mpv" in Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False


def running(s=None):
    s = s or state.load()
    return _alive(int(s.get("ambience_pid") or 0))


def source_args(cfg):
    src = os.path.expanduser(str(cfg["ambience"].get("source") or ""))
    if not src:
        return [SYNTH]
    if os.path.isdir(src):
        return ["--shuffle", src]
    return [src]


def start():
    if running():
        return True
    cfg = config.load()
    argv = ["mpv", "--no-video", "--really-quiet", "--loop-playlist=inf", "--loop-file=inf",
            f"--volume={int(cfg['ambience'].get('volume', 35))}", "--title=oma-caffe-ambience",
            *source_args(cfg)]
    try:
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        return False

    def fn(s):
        s["ambience_pid"] = proc.pid
    state.update(fn)
    return True


def stop():
    s = state.load()
    pid = int(s.get("ambience_pid") or 0)
    if _alive(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
        except OSError:
            os.kill(pid, signal.SIGTERM)

    def fn(s):
        s["ambience_pid"] = 0
    state.update(fn)
    return False


def toggle():
    return stop() if running() else start()
