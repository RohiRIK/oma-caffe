"""Terminal UI primitives: gum first, fzf second, plain prompts last.

gum picks up the active Omarchy theme from the GUM_* environment (exported
by `omarchy-restart-gum`), so Crema Light / Ristretto Dark style these menus
without any colour code here.
"""
import builtins
import os
import shutil
import subprocess
import sys

GUM = shutil.which("gum")
FZF = shutil.which("fzf")
_DELIM = "\x1f"


class Cancelled(Exception):
    pass


def _gum(args, stdin=None):
    proc = subprocess.run([GUM, *args], input=stdin, stdout=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise Cancelled()
    return proc.stdout.rstrip("\n")


def choose(header, options, height=14):
    """options: list of (value, label). Returns the chosen value."""
    if not options:
        raise Cancelled()
    labels = [label for _, label in options]
    if GUM:
        lines = "\n".join(f"{label}{_DELIM}{i}" for i, label in enumerate(labels))
        idx = _gum(["choose", "--header", header, "--height", str(height), "--label-delimiter", _DELIM], lines)
        return options[int(idx)][0]
    if FZF:
        lines = "\n".join(f"{i}\t{label}" for i, label in enumerate(labels))
        proc = subprocess.run([FZF, "--with-nth=2..", "--delimiter=\t", "--header", header, "--height=60%", "--reverse"],
                              input=lines, stdout=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise Cancelled()
        return options[int(proc.stdout.split("\t", 1)[0])][0]
    print(header)
    for i, label in enumerate(labels, 1):
        print(f"  {i:>2}. {label}")
    raw = _plain("> ")
    if not raw.isdigit() or not 1 <= int(raw) <= len(options):
        raise Cancelled()
    return options[int(raw) - 1][0]


def filter(header, options):
    """Fuzzy pick from (value, label) pairs."""
    if GUM:
        proc = subprocess.run([GUM, "filter", "--header", header, "--placeholder", "type to search…", "--height", "16"],
                              input="\n".join(label for _, label in options), stdout=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            raise Cancelled()
        picked = proc.stdout.rstrip("\n")
        for value, label in options:
            if label == picked:
                return value
        raise Cancelled()
    return choose(header, options)


def input(prompt, default="", placeholder=""):
    if GUM:
        args = ["input", "--prompt", f"{prompt} ", "--width", "60"]
        if default != "":
            args += ["--value", str(default)]
        if placeholder:
            args += ["--placeholder", placeholder]
        return _gum(args)
    raw = _plain(f"{prompt} [{default}] " if default != "" else f"{prompt} ")
    return raw or str(default)


def number(prompt, default=None, lo=None, hi=None):
    while True:
        raw = input(prompt, "" if default is None else f"{default:g}" if isinstance(default, (int, float)) else default)
        if raw.strip() == "" and default is None:
            return None
        try:
            val = float(raw)
        except ValueError:
            warn("Enter a number")
            continue
        if (lo is not None and val < lo) or (hi is not None and val > hi):
            warn(f"Between {lo:g} and {hi:g}")
            continue
        return int(val) if val == int(val) else val


def stars(prompt):
    return choose(prompt, [(i, "★" * i + "☆" * (5 - i) + f"  {i}") for i in (5, 4, 3, 2, 1)], height=7)


def confirm(prompt, default=True):
    if GUM:
        args = ["confirm", prompt] + ([] if default else ["--default=false"])
        return subprocess.run([GUM, *args]).returncode == 0
    raw = _plain(f"{prompt} [{'Y/n' if default else 'y/N'}] ").lower()
    return default if not raw else raw.startswith("y")


def multi(header, options):
    if GUM:
        lines = "\n".join(label for _, label in options)
        out = _gum(["choose", "--no-limit", "--header", header], lines)
        picked = set(out.splitlines())
        return [v for v, label in options if label in picked]
    print(header + " (comma-separated numbers)")
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    raw = _plain("> ")
    idx = {int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()}
    return [v for i, (v, _) in enumerate(options, 1) if i in idx]


def write(prompt, placeholder=""):
    if GUM:
        return _gum(["write", "--header", prompt, "--placeholder", placeholder, "--width", "70", "--height", "6"])
    return _plain(f"{prompt}: ")


def pager(text):
    if GUM and sys.stdout.isatty():
        subprocess.run([GUM, "pager", "--soft-wrap"], input=text, text=True)
    else:
        print(text)


def title(text, sub=""):
    if GUM:
        subprocess.run([GUM, "style", "--border", "rounded", "--padding", "0 2", "--margin", "1 0 0 0", "--bold", text]
                       + ([sub] if sub else []))
    else:
        print(f"\n== {text} ==")
        if sub:
            print(sub)


def info(text):
    print(text)


def warn(text):
    print(f"\033[33m{text}\033[0m" if sys.stdout.isatty() else text, file=sys.stderr)


def spin(text, fn):
    """Run fn() while showing a spinner (gum's spinner needs a command, so print)."""
    if sys.stdout.isatty():
        print(f"… {text}", flush=True)
    return fn()


def _plain(prompt):
    try:
        return builtins.input(prompt)
    except EOFError:
        raise Cancelled()


def clear():
    if sys.stdout.isatty() and os.environ.get("TERM", "dumb") != "dumb":
        print("\033[2J\033[H", end="")
