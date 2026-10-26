"""Caffeine kinetics: first-order elimination with a configurable half-life.

    active(t) = sum(mg_i * 0.5 ** ((t - t_i) / half_life))

Absorption is treated as instant, which slightly overstates the first 30-45
minutes after a cup and is accurate thereafter — the right bias for a
"should I have another?" readout.
"""
import math

SLEEP_SAFE_MG = 50


def active_mg(cups, now, half_life_h=5.0):
    hl = max(0.1, float(half_life_h)) * 3600
    total = 0.0
    for cup in cups:
        dt = now - float(cup.get("ts", now))
        if dt < 0:
            continue
        total += float(cup.get("mg", 0)) * 0.5 ** (dt / hl)
    return total


def hours_until(mg_now, threshold, half_life_h=5.0):
    """Hours until the active level decays below threshold (0 if already)."""
    if mg_now <= threshold or threshold <= 0:
        return 0.0
    return float(half_life_h) * math.log2(mg_now / threshold)


def prune(cups, now, keep_h=48):
    """Cups older than keep_h contribute <0.2% at a 5h half-life; drop them."""
    cutoff = now - keep_h * 3600
    return [c for c in cups if float(c.get("ts", 0)) >= cutoff]
