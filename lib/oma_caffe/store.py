"""JSON files that several processes touch at once.

The bar fires a click per mouse event, the break timer ticks every minute and
the lab may be open in a terminal, so every read-modify-write takes an
exclusive flock on a sidecar lock file and lands with an atomic rename. A
reader never sees half a file and two writers never lose each other's update.
"""
import contextlib
import fcntl
import json
import os
import tempfile
from pathlib import Path


def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        return default() if callable(default) else default
    except (json.JSONDecodeError, OSError):
        # A corrupt file is kept for inspection rather than silently replaced.
        path = Path(path)
        if path.exists():
            path.replace(path.with_suffix(path.suffix + ".corrupt"))
        return default() if callable(default) else default


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name("." + path.name + ".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def update_json(path, default, mutate):
    """Apply mutate(data) under the lock; returns whatever mutate returns."""
    with locked(path):
        data = read_json(path, default)
        result = mutate(data)
        write_json(path, data)
        return result


def append_jsonl(path, record):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with locked(path), open(path, "a", encoding="utf-8") as fh:
        fh.write(line)


def read_jsonl(path, limit=None):
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
    except FileNotFoundError:
        return []
    if limit:
        lines = lines[-limit:]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def rewrite_jsonl(path, keep):
    """Drop records for which keep(record) is false, atomically, under the lock."""
    path = Path(path)
    with locked(path):
        records = read_jsonl(path)
        kept = [r for r in records if keep(r)]
        if len(kept) == len(records):
            return 0
        fd, tmp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for r in kept:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, path)
        return len(records) - len(kept)
