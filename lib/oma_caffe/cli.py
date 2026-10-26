"""oma-caffe: one entry point for the bar, the overlay, the lab and you."""
import argparse
import json
import os
import shutil
import sys
import time

from . import (ambience, beans, breaks, config, desktop, dial, fun, gear, importer, paths, recipes,
               state, store, theme, ui, wallpapers)

TAGLINE = "Powered by caffeine and questionable life choices."

FROM_BAR = os.environ.get("OMA_CAFFE_FROM_BAR") == "1"


def _refresh():
    # The bar re-reads status itself after its own clicks.
    if not FROM_BAR:
        desktop.refresh_bar()


def _out(data, as_json):
    if as_json:
        print(json.dumps(data, ensure_ascii=False))
    elif isinstance(data, str):
        print(data)
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


# ---- handlers ------------------------------------------------------------------

def cmd_status(a):
    st = state.status()
    _out(st if a.json else st["tooltip"], a.json)


def cmd_log(a):
    cfg = config.load()
    if a.profile and a.profile not in cfg["profiles"]:
        sys.exit(f"oma-caffe: unknown drink {a.profile!r} (see `oma-caffe drinks`)")
    cup = state.log_cup(profile=a.profile, mg=a.mg, recipe_id=a.recipe)
    st = state.status()
    d = cfg["profiles"].get(cup["profile"], {})
    if not FROM_BAR:
        print(f"{d.get('icon', '☕')} +1 {d.get('label', cup['profile'])} ({cup['mg']:.0f} mg) · {st['cups']} today · "
              f"{st['mg']} mg active  {st['mood']['face']}\n   {st['pun']}")
    desktop.osd(f"{d.get('icon', '☕')}  {d.get('label', cup['profile'])} · {st['pun']}", icon="󰅶", duration=1400)
    if st["overLimit"]:
        desktop.notify("That's a lot of coffee", f"{st['mgToday']} mg logged today", urgency="normal")
    _refresh()


def cmd_undo(a):
    n = 0
    for _ in range(max(1, a.count)):
        if not state.undo_cup():
            break
        n += 1
    print(f"Undid {n} cup{'s' if n != 1 else ''}." if n else "Nothing to undo.")
    if n:
        desktop.osd(f"Undid {n} cup{'s' if n != 1 else ''}", icon="󰕌", duration=900)
    _refresh()


def cmd_cups(a):
    if a.action == "rm":
        gone = state.remove_cup(a.id)
        print("Removed." if gone else f"No cup {a.id!r} today.")
    elif a.action == "clear-today":
        n = 0
        while state.cups_today(state.load()) and state.undo_cup():
            n += 1
        print(f"Cleared {n} cups from today.")
    else:
        st = state.status()
        if a.json:
            _out(st["todayCups"], True)
            return
        for c in st["todayCups"]:
            print(f"{c['time']}  {c['icon']}  {c['label']:<20} {c['mg']:>4} mg   id {c['id']}")
        if not st["todayCups"]:
            print("No cups yet today. (╯°□°）╯︵ ┻━┻")
    if a.action != "list":
        _refresh()


def cmd_drinks(a):
    cfg = config.load()
    if a.action == "add":
        key = recipes.slug(a.name).replace("-", "")
        config.set_value(f"profiles.{key}.label", a.name)
        config.set_value(f"profiles.{key}.mg", str(a.mg))
        config.set_value(f"profiles.{key}.method", a.method)
        config.set_value(f"profiles.{key}.icon", a.icon)
        print(f"{a.icon} Added {a.name} ({a.mg} mg) as `{key}` — log it with: oma-caffe log --profile {key}")
        _refresh()
        return
    if a.action == "remove":
        def fn(data):
            return (data.get("profiles") or {}).pop(a.id, None)
        if store.update_json(paths.config_file(), {}, fn) is None:
            print("Only drinks you added can be removed.")
        else:
            print(f"Removed {a.id}.")
        _refresh()
        return
    if getattr(a, "json", False):
        builtin = config.defaults().get("profiles", {})
        _out([dict(d, id=k, custom=k not in builtin) for k, d in cfg["profiles"].items()], True)
        return
    by_method = {}
    for key, d in cfg["profiles"].items():
        by_method.setdefault(d.get("method", "Other"), []).append((key, d))
    for method, items in by_method.items():
        print(f"\n{method}")
        for key, d in items:
            print(f"  {d.get('icon', '☕')}  {d.get('label', key):<20} {d.get('mg', 0):>4} mg   {key}")


def cmd_stats(a):
    st = state.status()
    if a.json:
        _out({k: st[k] for k in ("stats", "level", "badges", "mood")}, True)
        return
    s, lv = st["stats"], st["level"]
    peak = max([w["cups"] for w in s["week"]] + [1])
    print(f"\n  {st['mood']['face']}  Lv {lv['level']} {lv['name']}" + (f"  ({lv['toNext']} cups to {lv['nextName']})" if lv["toNext"] else ""))
    print(f"  {'█' * int(lv['progress'] * 24)}{'░' * (24 - int(lv['progress'] * 24))}\n")
    for w in s["week"]:
        bar = "▇" * round(12 * w["cups"] / peak)
        print(f"  {w['day']}  {bar:<12} {w['cups']:>2} cups  {w['mg']:>5} mg" + ("  ← today" if w["today"] else ""))
    print(f"\n  🔥 streak {s['streak']}d · {s['weekCups']} cups this week ({s['avgPerDay']}/day) · {s['total']} all-time")
    print(f"  {s['topDrinkIcon']} favourite: {s['topDrink'] or '—'} · {s['drinksTried']} drinks · {s['methodsTried']} methods · peak {s['peakHour'] or '—'}")
    got = [b for b in st["badges"] if b["unlocked"]]
    print(f"\n  Badges {len(got)}/{len(st['badges'])}: " + " ".join(b["icon"] for b in got))


def cmd_badges(a):
    state.check_badges()
    for b in state.status()["badges"]:
        print(f"  {b['icon'] if b['unlocked'] else '🔒'}  {b['name']:<16} {b['desc']}")


def cmd_profile(a):
    cfg = config.load()
    if a.action in ("next", "prev"):
        name = state.cycle_profile(1 if a.action == "next" else -1)
    elif a.action == "set":
        name = state.set_profile(a.name)
    else:
        name = state.load()["profile"]
    label = cfg["profiles"].get(name, {}).get("label", name)
    if a.action != "show":
        desktop.osd(label, icon="󰅶", duration=900)
    print(label)
    _refresh()


def cmd_lock(a):
    cur = desktop.lock_active()
    want = {"toggle": not cur, "on": True, "off": False}.get(a.action)
    if want is not None:
        cur = desktop.set_lock(want)
        desktop.osd("Caffeine Lock on — staying awake" if cur else "Caffeine Lock off", icon="󰅶" if cur else "󰛊", duration=1200)
        _refresh()
    print("on" if cur else "off")


def cmd_menu(a):
    from . import lab
    if a.window:
        desktop.launch_tui("menu")
        return
    lab.quick_menu()


def cmd_lab(a):
    from . import lab, timer
    sub = a.sub
    if not sub:
        if a.window:
            cmd_studio(argparse.Namespace(page="recipes", recipe=None, dose=None))
            return
        lab.main()
        return
    if sub == "list":
        rs = recipes.all_recipes()
        if a.status:
            rs = [r for r in rs if r.get("status") == a.status]
        if a.json:
            _out(rs, True)
            return
        for r in rs:
            sc = recipes.score(r)
            print(f"{r['id']:<34} {recipes.STATUSES.get(r.get('status'), ''):<20} {r['name']}  —  {recipes.summary(r)}"
                  + (f"  {sc:.1f}★" if sc is not None else ""))
    elif sub == "show":
        r = _need(a.id)
        _out(r, True) if a.json else print(recipes.describe(r))
    elif sub == "scale":
        r = _need(a.id)
        s = recipes.scale_to_output(r, a.output) if a.output else recipes.scale(r, a.dose)
        _out(s, True) if a.json else print(recipes.describe(s))
    elif sub == "clone":
        tweaks = {k: v for k, v in (("grind", a.grind), ("temp_c", a.temp), ("dose_g", a.dose),
                                    ("yield_g", a.yield_g), ("water_ml", a.water)) if v is not None}
        child = recipes.clone(a.id, tweaks, a.name)
        print(f"{child['id']}  {child['name']}")
    elif sub == "rate":
        scores = {k: getattr(a, k) for k in recipes.SCORES}
        recipes.rate(a.id, scores, a.notes or "")
        r = recipes.get(a.id)
        print(f"Rated {r['name']}: now {recipes.score(r):.1f}★ over {len(r['ratings'])} brews")
        _refresh()
    elif sub == "status":
        recipes.set_status(a.id, a.status)
        print(f"{a.id} → {recipes.STATUSES[a.status]}")
        _refresh()
    elif sub == "research":
        hits = importer.research(" ".join(a.query))
        if a.json:
            _out(hits, True)
            return
        for h in hits:
            print(f"{'✓' if h['in_db'] else ' '} {h['id']:<30} {h['name']}  —  {recipes.summary(h)}  [{h.get('author', '')}]")
    elif sub == "adopt":
        r = importer.adopt(a.id)
        print(f"Added {r['id']}  {r['name']}")
    elif sub == "import":
        found = importer.from_source(a.source)
        if a.json:
            _out(found if a.dry_run else importer.import_recipes(found), True)
            return
        if a.dry_run:
            for r in found:
                print(recipes.describe(r) + "\n")
            return
        for r in importer.import_recipes(found):
            print(f"Imported {r['id']}  {r['name']}  —  {recipes.summary(r)}")
    elif sub == "feed":
        if a.action == "add":
            importer.add_feed(a.url)
            print(f"Added {a.url}")
        elif a.action == "remove":
            importer.remove_feed(a.url)
        elif a.action == "sync":
            for url, n, err in importer.sync_feeds():
                print(f"{url}: {n} recipes" + (f" (error: {err})" if err else ""))
        elif a.json:
            _out(importer.feeds().get("feeds", []), True)
        else:
            for f in importer.feeds().get("feeds", []):
                print(f"{f['url']}  {len(f.get('recipes', []))} recipes")
    elif sub == "brew":
        r = _need(a.id)
        if a.dose:
            r = recipes.scale(r, a.dose)
        if a.window:
            cmd_studio(argparse.Namespace(page="brew", recipe=r["id"], dose=a.dose))
            return
        lab.brew_flow(r) if sys.stdin.isatty() else timer.run(r)
    elif sub == "delete":
        print("deleted" if recipes.delete(a.id) else "not found")
    elif sub == "active":
        state.set_active_recipe(_need(a.id)["id"])
        print(f"active recipe: {a.id}")
        _refresh()


def _need(rid):
    r = recipes.get(rid)
    if not r:
        sys.exit(f"oma-caffe: no recipe {rid!r} (try `oma-caffe lab list`)")
    return r


def cmd_brew(a):
    a.sub = "brew"
    cmd_lab(a)


def cmd_dial(a):
    from . import lab
    if a.window:
        cmd_studio(argparse.Namespace(page="dial", recipe=None, dose=None))
        return
    if a.list:
        if a.json:
            _out(list(reversed(dial.recent(a.list))), True)
            return
        for r in dial.recent(a.list):
            print(dial.line(r))
        return
    if a.dose is None:
        if not sys.stdin.isatty():
            sys.exit("oma-caffe dial: pass --dose/--yield/--time, or run in a terminal")
        lab.dial_form()
        return
    if a.yield_g is None or a.time is None:
        sys.exit("oma-caffe dial: --dose needs --yield and --time")
    rec = dial.log({"dose_g": a.dose, "yield_g": a.yield_g, "time_s": a.time, "grind": a.grind,
                    "prep": a.prep.split(",") if a.prep else [], "taste": a.taste or "", "notes": a.notes or "",
                    "recipe": a.recipe})
    tips = dial.advise(a.dose, a.yield_g, a.time, a.taste or "", recipes.get(rec["recipe"] or ""), rec.get("grind"))
    if a.json:
        _out(dict(rec, tips=tips), True)
        return
    print(dial.line(rec))
    for tip in tips:
        print(f"  → {tip}")


def cmd_beans(a):
    if a.action == "add":
        b = beans.add_bean({"roaster": a.roaster, "name": a.name, "origin": a.origin, "process": a.process,
                            "roast_level": a.roast, "roast_date": a.roasted, "notes": a.notes, "grind_setting": a.grind})
        print(f"Added and activated {b['id']}")
    elif a.action == "use":
        beans.set_active(a.id)
        print(f"Active bean: {a.id}")
    elif a.action == "grind":
        beans.set_grind(a.setting)
        print(f"Grind: {a.setting}")
    elif a.action == "grinder":
        g = beans.set_grinder(a.name, a.burrs or "")
        print(f"Active grinder: {g['name']}")
    elif getattr(a, "json", False):
        _out(beans.load(), True)
        return
    else:
        data = beans.load()
        for b in data["beans"]:
            mark = "*" if b["id"] == data.get("active_bean") else " "
            print(f"{mark} {b['id']:<28} {beans.bean_label(b)}  {b.get('origin', '')}  grind {b.get('grind_setting') or '?'}")
        g = beans.active_grinder(data)
        print(f"\nGrinder: {g['name'] if g else 'none'}")
    if a.action != "list":
        _refresh()


def cmd_break(a):
    act = a.action
    if act == "now":
        breaks.show()
    elif act == "tick":
        print(breaks.tick())
    elif act == "snooze":
        until = breaks.snooze(a.minutes)
        print(f"Snoozed until {time.strftime('%H:%M', time.localtime(until))}")
    elif act == "skip":
        nxt = breaks.skip()
        print(f"Next break {time.strftime('%H:%M', time.localtime(nxt))}")
    elif act == "start":
        m = breaks.start_break(a.minutes, decaf=a.decaf)
        print(f"Break for {m} minutes")
    elif act == "pomodoro":
        nxt = breaks.schedule_next(a.minutes or 25, pomodoro=True)
        desktop.osd(f"Focus for {a.minutes or 25} min", icon="󰔛")
        print(f"Coffee break at {time.strftime('%H:%M', time.localtime(nxt))}")
    elif act == "payload":
        _out(breaks.payload(), True)
    elif act == "ascii":
        breaks.ascii_screen()
    elif act in ("enable", "disable"):
        config.set_value("breaks.enabled", "true" if act == "enable" else "false")
        print(f"breaks {act}d")
    else:
        s = state.load()["break"]
        cfg = config.load()["breaks"]
        print(f"enabled: {cfg['enabled']} · every {cfg['interval_min']} min · {cfg['active_from']}–{cfg['active_until']}")
        if s.get("next_due"):
            print(f"next: {time.strftime('%H:%M', time.localtime(s['next_due']))}" + (" (pomodoro)" if s.get("pomodoro") else ""))
    _refresh()


def cmd_tick(a):
    state.check_badges()
    switched = theme.sync()
    result = breaks.tick()
    print(f"break: {result}" + (f" · theme → {switched}" if switched else ""))


def cmd_theme(a):
    act = a.action
    if act in ("light", "dark", "cute"):
        light, dark = theme.names()
        name = {"light": light, "dark": dark, "cute": config.load()["theme"].get("cute", "strawberry-latte")}[act]
        theme.apply(name)
        print(name)
    elif act == "toggle":
        print(theme.toggle())
    elif act == "cycle":
        print(theme.cycle())
    elif act == "auto":
        on = a.value != "off"
        config.set_value("theme.auto", "true" if on else "false")
        print(f"Auto-Roast {'on' if on else 'off'}")
        if on:
            print(theme.sync(force=True) or "already roasted right")
    elif act == "sync":
        print(theme.sync() or "no change")
    else:
        cfg = config.load()["theme"]
        print(f"current: {desktop.current_theme()} · auto: {cfg['auto']} ({cfg['light_at']} light / {cfg['dark_at']} dark)"
              f" · wanted now: {theme.wanted_for()}")


def cmd_ambience(a):
    if a.action == "toggle":
        on = ambience.toggle()
    elif a.action == "on":
        on = ambience.start()
    elif a.action == "off":
        on = ambience.stop()
    else:
        on = ambience.running()
    if a.action != "status":
        desktop.osd("Cafe ambience on" if on else "Cafe ambience off", icon="󰎈", duration=900)
        _refresh()
    print("on" if on else "off")


def cmd_config(a):
    if a.action == "set":
        print(config.set_value(a.key, a.value))
    elif a.action == "get":
        _out(config.get_value(config.load(), a.key), False)
    elif a.action == "path":
        print(f"config: {paths.config_file()}\ndata:   {paths.data_dir()}")
    else:
        _out(config.load(), a.json)
    if a.action == "set":
        _refresh()


def cmd_cue(a):
    from . import timer
    step = {"label": a.label, "kind": a.kind}
    if a.target is not None:
        step["target_g"] = a.target
    timer.cue(step, a.progress, config.load(), final=a.final)


def cmd_studio(a):
    payload = {"view": "studio", "page": a.page}
    if a.recipe:
        payload["recipe"] = a.recipe
    if a.dose:
        payload["dose"] = a.dose
    if not desktop.summon_overlay(payload):
        sys.exit("oma-caffe: the Omarchy shell isn't running; try `oma-caffe lab` in a terminal")


def cmd_gear(a):
    act = a.action
    if act == "search":
        kind = "grinders" if a.kind == "grinder" else "machines"
        hits = gear.search(kind, " ".join(a.query))
        if a.json:
            _out(hits, True)
            return
        for h in hits:
            print(f"{h['id']:<36} {h['name']}")
    elif act == "set":
        item = gear.set_gear(a.kind, " ".join(a.query))
        print(f"{a.kind}: {item['name']}")
        _refresh()
    elif act == "clear":
        gear.clear(a.kind)
        print(f"{a.kind} cleared")
    elif act == "upgrade":
        if a.kind in ("add", "remove"):
            gear.toggle_upgrade(a.query[0], a.kind == "add")
            print(f"upgrade {a.query[0]} {'fitted' if a.kind == 'add' else 'removed'}")
        else:
            prof = gear.profile()
            for u in prof["upgrades"]:
                print(f"  [{'x' if u['installed'] else ' '}] {u['id']:<20} {u['icon']} {u['name']} — {u['desc']}")
            if not prof["upgrades"]:
                print("set your machine first (oma-caffe gear set machine <name>)")
    elif act == "basket":
        gear.set_basket(a.kind)
        print(f"basket: {a.kind or 'stock'} g")
    elif act == "custom":
        fields = dict(kv.split("=", 1) for kv in ([a.kind] if a.kind else []) + a.query if "=" in kv)
        fields["e61"] = fields.get("e61") in ("1", "true", "yes")
        m = gear.set_custom(fields)
        print(f"custom machine: {m['name']} ({m['kind']}, {m['portafilter_mm']} mm, {m['basket_g']:g} g)")
    elif act == "calibrate":
        off = gear.calibrate(a.kind, a.query[0])
        print(f"calibrated: ranges shifted by {off:+g}")
    elif act == "recommend":
        r = _need(a.kind)
        rec = gear.recommend(r)
        if a.json:
            _out(rec, True)
            return
        print(f"{r['name']} ({rec['categoryLabel']})")
        if rec["grind"]:
            print(f"  grind: {rec['grind']['grinder']} {rec['grind']['text']}")
        for w in rec["warnings"]:
            print(f"  ⚠ {w}")
        for t in rec["machine"]:
            print(f"  • {t['text']}")
    else:
        prof = gear.profile()
        if a.json:
            _out(prof, True)
            return
        g, m = prof["grinder"], prof["machine"]
        print(f"grinder: {g['name'] if g else '— (oma-caffe gear set grinder <name>)'}")
        for rg in prof.get("ranges", []):
            print(f"  {rg['label']:<16} {rg['low']:g}–{rg['high']:g} {g['unit']}")
        print(f"machine: {m['name'] if m else '— (oma-caffe gear set machine <name>)'}")
        if m and m.get("upgrades"):
            print(f"  upgrades: {', '.join(m['upgrades'])}")
        if m:
            t = m["temp"]
            print(f"  {m['kind']} · {m['portafilter_mm']} mm · {m['basket_g']} g basket · "
                  f"temp {'%g–%g°C' % tuple(t['range']) if t['adjustable'] else 'fixed'} · {m['pressure']['type']} pressure · "
                  f"pre-infusion {m['preinfusion']}")


def cmd_wallpapers(a):
    act = a.action
    if act == "thumbs":
        print(f"fetched {wallpapers.ensure_thumbs()} thumbnails")
    elif act == "add":
        for t in (a.theme or [desktop.current_theme()]):
            print(wallpapers.add(a.id, t))
    elif act == "remove":
        for t in (a.theme or [desktop.current_theme()]):
            print("removed" if wallpapers.remove(a.id, t) else f"{a.id} is bundled with {t} or not installed")
    elif act == "set":
        print(wallpapers.set_now(a.id))
    elif act == "build-defaults":
        wallpapers.build_defaults()
        print("rebuilt bundled theme wallpapers")
    else:
        items = wallpapers.listing()
        if a.json:
            _out(items, True)
            return
        for w in items:
            print(f"{w['id']:<22} {','.join(w['tags']):<16} {w['tone']:<5} {w['name']}" + (f"  [{', '.join(w['themes'])}]" if w["themes"] else ""))


def cmd_doctor(a):
    ok = True
    for tool in ("python3", "gum", "jq", "curl", "mpv", "notify-send", "omarchy-shell", "omarchy-theme-set", "hyprctl"):
        have = shutil.which(tool) is not None
        ok &= have or tool in ("jq", "fzf")
        print(f"{'✓' if have else '✗'} {tool}")
    print(f"{'✓' if theme.installed() else '✗'} themes linked into {paths.omarchy_themes_dir()}")
    print(f"✓ data in {paths.data_dir()}  · config in {paths.config_dir()}")
    plug = paths.omarchy_themes_dir().parent / "plugins" / desktop.PLUGIN_ID
    print(f"{'✓' if plug.exists() else '✗'} shell plugin at {plug}")
    sys.exit(0 if ok else 1)


# ---- parser ------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(prog="oma-caffe", description=f"Specialty coffee suite for Omarchy. ☕ {TAGLINE}")
    sp = p.add_subparsers(dest="cmd")

    s = sp.add_parser("status", help="today's cups, active caffeine and more")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_status)

    s = sp.add_parser("log", help="log +1 cup (bar left-click)")
    s.add_argument("--profile")
    s.add_argument("--mg", type=float)
    s.add_argument("--recipe")
    s.set_defaults(fn=cmd_log)

    s = sp.add_parser("undo", help="remove the last logged cup(s)")
    s.add_argument("count", type=int, nargs="?", default=1)
    s.set_defaults(fn=cmd_undo)

    s = sp.add_parser("cups", help="today's cups; remove any of them")
    s.add_argument("action", nargs="?", default="list", choices=["list", "rm", "clear-today"])
    s.add_argument("id", nargs="?")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_cups)

    s = sp.add_parser("drinks", help="the drink menu; add your own")
    dsp = s.add_subparsers(dest="action")
    x = dsp.add_parser("list")
    x.add_argument("--json", action="store_true")
    x = dsp.add_parser("add")
    x.add_argument("name")
    x.add_argument("--mg", type=float, required=True)
    x.add_argument("--method", default="Other")
    x.add_argument("--icon", default="☕")
    x = dsp.add_parser("remove")
    x.add_argument("id")
    s.set_defaults(fn=cmd_drinks, action="list")

    s = sp.add_parser("stats", help="week chart, streak, level and badges")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_stats)

    sp.add_parser("badges", help="achievements").set_defaults(fn=cmd_badges)

    s = sp.add_parser("profile", help="cycle or set the brew profile (bar scroll)")
    s.add_argument("action", nargs="?", default="show", choices=["next", "prev", "set", "show"])
    s.add_argument("name", nargs="?")
    s.set_defaults(fn=cmd_profile)

    s = sp.add_parser("lock", help="Caffeine Lock: hold off idle/sleep (bar right-click)")
    s.add_argument("action", nargs="?", default="status", choices=["toggle", "on", "off", "status"])
    s.set_defaults(fn=cmd_lock)

    s = sp.add_parser("menu", help="Quick Brew & Recipe Launcher (bar middle-click)")
    s.add_argument("--window", action="store_true", help="open in a floating terminal")
    s.set_defaults(fn=cmd_menu)

    s = sp.add_parser("lab", help="recipe researcher, aggregator and experiments")
    s.add_argument("--window", action="store_true")
    lsp = s.add_subparsers(dest="sub")
    x = lsp.add_parser("list")
    x.add_argument("--status", choices=list(recipes.STATUSES))
    x.add_argument("--json", action="store_true")
    x = lsp.add_parser("show")
    x.add_argument("id")
    x.add_argument("--json", action="store_true")
    x = lsp.add_parser("scale", help="rescale a recipe to a new dose (or --output)")
    x.add_argument("id")
    x.add_argument("dose", type=float, nargs="?")
    x.add_argument("--output", type=float, help="target yield/water instead of dose")
    x.add_argument("--json", action="store_true")
    x = lsp.add_parser("clone", help="branch a recipe into an experiment")
    x.add_argument("id")
    x.add_argument("--grind", help="e.g. -0.5, +2 or a new setting")
    x.add_argument("--temp", help="e.g. +2 or 94")
    x.add_argument("--dose", help="e.g. +2 or 20 (output scales)")
    x.add_argument("--yield", dest="yield_g")
    x.add_argument("--water")
    x.add_argument("--name")
    x = lsp.add_parser("rate", help="taste scorecard, 1-5 each")
    x.add_argument("id")
    for k in recipes.SCORES:
        x.add_argument(f"--{k}", type=int, choices=range(1, 6))
    x.add_argument("--notes")
    x = lsp.add_parser("status")
    x.add_argument("id")
    x.add_argument("status", choices=list(recipes.STATUSES))
    x = lsp.add_parser("research", help="search the curated library and feeds")
    x.add_argument("query", nargs="*")
    x.add_argument("--json", action="store_true")
    x = lsp.add_parser("adopt", help="copy a library recipe into yours")
    x.add_argument("id")
    x = lsp.add_parser("import", help="import from URL, file or text")
    x.add_argument("source")
    x.add_argument("--dry-run", action="store_true")
    x.add_argument("--json", action="store_true")
    x = lsp.add_parser("feed", help="community recipe feeds")
    x.add_argument("action", choices=["add", "remove", "sync", "list"])
    x.add_argument("url", nargs="?")
    x.add_argument("--json", action="store_true")
    x = lsp.add_parser("brew", help="guided brew timer")
    x.add_argument("id")
    x.add_argument("--dose", type=float)
    x.add_argument("--window", action="store_true")
    x = lsp.add_parser("delete")
    x.add_argument("id")
    x = lsp.add_parser("active", help="make a recipe the active one")
    x.add_argument("id")
    s.set_defaults(fn=cmd_lab)

    s = sp.add_parser("brew", help="shortcut for `lab brew`")
    s.add_argument("id")
    s.add_argument("--dose", type=float)
    s.add_argument("--window", action="store_true")
    s.set_defaults(fn=cmd_brew)

    s = sp.add_parser("dial", help="fast shot dial-in logger")
    s.add_argument("--window", action="store_true")
    s.add_argument("--list", type=int, nargs="?", const=10, metavar="N")
    s.add_argument("--dose", type=float)
    s.add_argument("--yield", dest="yield_g", type=float)
    s.add_argument("--time", type=float)
    s.add_argument("--grind")
    s.add_argument("--prep", help="comma-separated, e.g. WDT,Puck screen")
    s.add_argument("--taste", choices=dial.TASTES)
    s.add_argument("--notes")
    s.add_argument("--recipe")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_dial)

    s = sp.add_parser("beans", help="beans and grinders")
    bsp = s.add_subparsers(dest="action")
    x = bsp.add_parser("list")
    x.add_argument("--json", action="store_true")
    x = bsp.add_parser("add")
    for f in ("roaster", "name", "origin", "process", "roasted", "notes", "grind"):
        x.add_argument(f"--{f}", default="")
    x.add_argument("--roast", default="Medium", choices=recipes.ROASTS)
    x = bsp.add_parser("use")
    x.add_argument("id")
    x = bsp.add_parser("grind")
    x.add_argument("setting")
    x = bsp.add_parser("grinder")
    x.add_argument("name")
    x.add_argument("--burrs")
    s.set_defaults(fn=cmd_beans, action="list")

    s = sp.add_parser("break", help="Coffee Time break overlay")
    s.add_argument("action", nargs="?", default="status",
                   choices=["now", "tick", "snooze", "skip", "start", "pomodoro", "payload", "ascii", "status", "enable", "disable"])
    s.add_argument("minutes", type=int, nargs="?")
    s.add_argument("--decaf", action="store_true")
    s.set_defaults(fn=cmd_break)

    sp.add_parser("tick", help="minute heartbeat: Auto-Roast + break scheduler").set_defaults(fn=cmd_tick)

    s = sp.add_parser("theme", help="Crema Light / Ristretto Dark")
    s.add_argument("action", nargs="?", default="status", choices=["light", "dark", "cute", "toggle", "cycle", "auto", "sync", "status"])
    s.add_argument("value", nargs="?", choices=["on", "off"])
    s.set_defaults(fn=cmd_theme)

    s = sp.add_parser("ambience", help="lo-fi cafe ambience")
    s.add_argument("action", nargs="?", default="toggle", choices=["toggle", "on", "off", "status"])
    s.set_defaults(fn=cmd_ambience)

    s = sp.add_parser("config", help="show or change settings")
    s.add_argument("action", nargs="?", default="show", choices=["show", "get", "set", "path"])
    s.add_argument("key", nargs="?")
    s.add_argument("value", nargs="?")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_config)

    s = sp.add_parser("cue", help="fire one brew-step cue (sound / OSD / notification); used by Studio")
    s.add_argument("label")
    s.add_argument("--kind", default="pour")
    s.add_argument("--target", type=float)
    s.add_argument("--progress", type=float, default=0)
    s.add_argument("--final", action="store_true")
    s.set_defaults(fn=cmd_cue)

    s = sp.add_parser("studio", help="open the oma-caffe Studio window")
    s.add_argument("page", nargs="?", default="recipes",
                   choices=["recipes", "brew", "discover", "dial", "beans", "stats", "wallpapers", "settings"])
    s.add_argument("--recipe")
    s.add_argument("--dose", type=float)
    s.set_defaults(fn=cmd_studio)

    s = sp.add_parser("gear", help="your grinder and machine: ranges and recommendations")
    s.add_argument("action", nargs="?", default="show", choices=["show", "search", "set", "clear", "calibrate", "recommend", "upgrade", "basket", "custom"])
    s.add_argument("kind", nargs="?", help="grinder | machine (search/set/clear), a method (calibrate) or a recipe id (recommend)")
    s.add_argument("query", nargs="*")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_gear)

    s = sp.add_parser("wallpapers", help="the curated coffee photo & painting gallery")
    s.add_argument("action", nargs="?", default="list", choices=["list", "thumbs", "add", "remove", "set", "build-defaults"])
    s.add_argument("id", nargs="?")
    s.add_argument("--theme", action="append", choices=wallpapers.THEMES)
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_wallpapers)

    sp.add_parser("doctor", help="check dependencies and install").set_defaults(fn=cmd_doctor)
    return p


def main(argv=None):
    parser = build_parser()
    a = parser.parse_args(argv)
    if not getattr(a, "fn", None):
        parser.print_help()
        return 0
    if a.cmd == "lab" and a.sub == "scale" and a.dose is None and a.output is None:
        parser.error("lab scale needs a dose or --output")
    if a.cmd == "lab" and a.sub == "feed" and a.action in ("add", "remove") and not a.url:
        parser.error("feed add/remove needs a URL")
    if a.cmd == "gear" and a.action in ("search", "set", "clear") and a.kind not in ("grinder", "machine"):
        parser.error("gear search/set/clear needs grinder or machine")
    if a.cmd == "gear" and a.action == "upgrade" and a.kind in ("add", "remove") and not a.query:
        parser.error("gear upgrade add/remove needs an upgrade id (see `oma-caffe gear upgrade`)")
    if a.cmd == "gear" and a.action in ("set", "calibrate") and not a.query:
        parser.error("gear set needs a name; gear calibrate needs <method> <setting>")
    if a.cmd == "gear" and a.action == "recommend" and not a.kind:
        parser.error("gear recommend needs a recipe id")
    if a.cmd == "wallpapers" and a.action in ("add", "remove", "set") and not a.id:
        parser.error("wallpapers add/remove/set needs an id (see `oma-caffe wallpapers`)")
    if a.cmd == "cups" and a.action == "rm" and not a.id:
        parser.error("cups rm needs an id (see `oma-caffe cups`)")
    if a.cmd == "profile" and a.action == "set" and not a.name:
        parser.error("profile set needs a name")
    if a.cmd == "config" and a.action in ("get", "set") and not a.key:
        parser.error("config get/set needs a key")
    try:
        a.fn(a)
    except ui.Cancelled:
        return 130
    except (KeyError, ValueError) as exc:
        print(f"oma-caffe: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0
