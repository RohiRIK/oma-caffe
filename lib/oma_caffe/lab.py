"""`oma-caffe lab`, the quick-brew launcher and the dial-in form (interactive)."""
from . import ambience, beans, breaks, desktop, dial, importer, recipes, state, theme, timer, ui
from .recipes import STATUSES

STATUS_GLYPH = {"to_try": "󰐕", "testing": "󰙨", "favorite": "󰓎"}


def recipe_label(r):
    sc = recipes.score(r)
    star = f"  {sc:.1f}★" if sc is not None else ""
    branch = "  ↳" if r.get("parent") else ""
    return f"{STATUS_GLYPH.get(r.get('status'), '·')} {r['name']}{branch}  —  {recipes.summary(r)}{star}"


def pick_recipe(header, pool=None):
    pool = pool if pool is not None else recipes.all_recipes()
    order = {"favorite": 0, "testing": 1, "to_try": 2}
    pool = sorted(pool, key=lambda r: (order.get(r.get("status"), 3), r["method"], r["name"]))
    return ui.filter(header, [(r["id"], recipe_label(r)) for r in pool])


# ---- top level ---------------------------------------------------------------

def main():
    while True:
        ui.clear()
        rs = recipes.all_recipes()
        counts = {k: sum(1 for r in rs if r.get("status") == k) for k in STATUSES}
        top = recipes.top_rated(rs)
        ui.title("󰅶  oma-caffe lab",
                 f"{len(rs)} recipes · {counts['to_try']} to try · {counts['testing']} testing · {counts['favorite']} favorites"
                 + (f"\nTop rated: {top['name']}" if top else ""))
        try:
            action = ui.choose("What are we brewing?", [
                ("browse", "󰆘  Browse & brew my recipes"),
                ("favorites", "󰓎  Dialed-in favorites"),
                ("experiments", "󰙨  Experiments & scorecards"),
                ("research", "󰍉  Research library (championship & classic recipes)"),
                ("import", "󰇚  Import from URL, file or pasted text"),
                ("feeds", "󰑫  Community feeds"),
                ("dial", "󰔛  Log a dial-in shot"),
                ("quit", "󰈆  Quit"),
            ])
        except ui.Cancelled:
            return
        try:
            if action == "quit":
                return
            if action == "browse":
                recipe_menu(pick_recipe("Pick a recipe"))
            elif action == "favorites":
                favs = [r for r in recipes.all_recipes() if r.get("status") == "favorite"]
                if not favs:
                    ui.warn("No favorites yet — rate brews and mark the winners.")
                    ui.input("Enter to continue")
                else:
                    recipe_menu(pick_recipe("Favorites", favs))
            elif action == "experiments":
                experiments()
            elif action == "research":
                research()
            elif action == "import":
                import_flow()
            elif action == "feeds":
                feeds_flow()
            elif action == "dial":
                dial_form()
        except ui.Cancelled:
            continue


def recipe_menu(recipe_id):
    while True:
        r = recipes.get(recipe_id)
        if not r:
            return
        ui.clear()
        print(recipes.describe(r) + "\n")
        try:
            action = ui.choose("Action", [
                ("brew", "󰔛  Brew now (guided timer)"),
                ("brew-scaled", "󰞯  Brew with a different dose (auto-scale)"),
                ("scale", "󰄨  Preview scaling"),
                ("clone", "󰙨  Clone into an experiment (tweak grind / temp / dose)"),
                ("rate", "󰓎  Rate a brew (taste scorecard)"),
                ("status", "󰑓  Set status (To Try / Testing / Favorite)"),
                ("active", "󰄬  Make this my active recipe"),
                ("delete", "󰆴  Delete"),
                ("back", "󰁍  Back"),
            ])
        except ui.Cancelled:
            return
        if action == "back":
            return
        if action == "brew":
            brew_flow(r)
        elif action == "brew-scaled":
            dose = ui.number("New dose (g):", r.get("dose_g"), 1, 2000)
            brew_flow(recipes.scale(r, dose))
        elif action == "scale":
            dose = ui.number("Dose (g):", r.get("dose_g"), 1, 2000)
            s = recipes.scale(r, dose)
            print("\n" + recipes.describe(s) + "\n")
            ui.input("Enter to continue")
        elif action == "clone":
            clone_flow(r)
        elif action == "rate":
            rate_flow(r)
        elif action == "status":
            st = ui.choose("Status", [(k, f"{STATUS_GLYPH[k]}  {v}") for k, v in STATUSES.items()])
            recipes.set_status(r["id"], st)
        elif action == "active":
            state.set_active_recipe(r["id"])
            desktop.refresh_bar()
        elif action == "delete":
            if ui.confirm(f"Delete {r['name']}?", default=False):
                recipes.delete(r["id"])
                return


def brew_flow(r):
    print(f"\n{recipes.describe(r)}\n")
    print("Tare your scale and get your water ready.")
    try:
        ui.input("Press Enter to start the timer", "")
    except ui.Cancelled:
        return
    state.set_active_recipe(r["id"])
    finished = timer.run(r)
    if not finished:
        return
    try:
        if ui.confirm("Log this cup?"):
            prof = {"Espresso": "espresso", "Milk Drink": "espresso", "AeroPress": "aeropress",
                    "Cold Brew": "coldbrew"}.get(r.get("method"), "pourover")
            state.log_cup(profile=prof, mg=r.get("caffeine_mg"), recipe_id=r["id"])
            desktop.refresh_bar()
        if ui.confirm("Score this brew now?"):
            rate_flow(r)
    except ui.Cancelled:
        pass


def clone_flow(r):
    tweaks = {}
    fields = ui.multi("What are you changing?", [
        ("grind", f"Grind (now: {r.get('grind_setting') or '—'})"),
        ("temp_c", f"Water temp (now: {r.get('temp_c')}°C)"),
        ("dose_g", f"Dose (now: {r.get('dose_g')}g — output scales with it)"),
        ("yield_g" if r.get("yield_g") else "water_ml", f"Output (now: {recipes.output_g(r)}g)"),
    ])
    if not fields:
        return
    for f in fields:
        hint = {"grind": "e.g. -0.5 or +2 clicks, or a new setting", "temp_c": "e.g. +2 or 94"}.get(f, "e.g. +1 or an absolute value")
        tweaks[f] = ui.input(f"{f} change:", placeholder=hint)
    child = recipes.clone(r["id"], tweaks)
    print(f"\nCreated experiment {child['name']} ({child['id']}).")
    if ui.confirm("Brew it now?"):
        brew_flow(child)


def rate_flow(r):
    print(f"\nScorecard for {r['name']} (1 = low, 5 = high)")
    scores = {}
    for key in ("acidity", "sweetness", "body", "bitterness", "overall"):
        scores[key] = ui.stars(key.capitalize())
    notes = ui.input("Tasting notes:", placeholder="stone fruit, cocoa, a bit hollow…")
    recipes.rate(r["id"], scores, notes)
    if scores["overall"] >= 5 and r.get("status") != "favorite" and ui.confirm("A 5★ brew — mark as Dialed-In Favorite?"):
        recipes.set_status(r["id"], "favorite")
    desktop.refresh_bar()


def experiments():
    rs = recipes.all_recipes()
    by_parent = {}
    for r in rs:
        if r.get("parent"):
            by_parent.setdefault(r["parent"], []).append(r)
    if not by_parent:
        ui.warn("No experiments yet — open a recipe and choose Clone into an experiment.")
        ui.input("Enter to continue")
        return
    lines = []
    options = []
    for pid, kids in by_parent.items():
        parent = recipes.get(pid)
        if not parent:
            continue
        ps = recipes.score(parent)
        lines.append(f"{parent['name']}  {f'{ps:.1f}★' if ps is not None else 'unrated'}")
        options.append((parent["id"], recipe_label(parent)))
        best = max(kids + [parent], key=lambda x: recipes.score(x) or 0)
        for k in kids:
            ks = recipes.score(k)
            crown = "  ← best" if k is best and ks else ""
            lines.append(f"   ↳ {k['name']}  {f'{ks:.1f}★' if ks is not None else 'unrated'}{crown}")
            options.append((k["id"], "   ↳ " + recipe_label(k)))
    print("\n".join(lines) + "\n")
    pick = ui.choose("Open", options + [("back", "󰁍  Back")])
    if pick != "back":
        recipe_menu(pick)


def research():
    q = ui.input("Search the library:", placeholder="aeropress, hoffmann, iced, light roast… (blank = all)")
    hits = importer.research(q)
    if not hits:
        ui.warn("Nothing matched. Try `Import` with a URL to pull a recipe from the web.")
        ui.input("Enter to continue")
        return
    pick = ui.filter("Library results (✓ = already in your recipes)",
                     [(h["id"], ("✓ " if h["in_db"] else "  ") + f"{h['name']} — {recipes.summary(h)} · {h.get('author', '')}") for h in hits])
    item = next(h for h in hits if h["id"] == pick)
    print("\n" + recipes.describe(recipes.normalize(item)) + "\n")
    if ui.confirm("Add to your recipes (To Try)?"):
        added = importer.adopt(pick)
        print(f"Added {added['name']}.")
        if ui.confirm("Brew it now?"):
            brew_flow(added)


def import_flow():
    src = ui.input("URL, file path, or 'paste':", placeholder="https://… or ~/recipe.json")
    if src.strip().lower() == "paste":
        src = ui.write("Paste the recipe text", "0:00 - Bloom to 50g …")
    try:
        found = importer.from_source(src.strip())
    except Exception as exc:
        ui.warn(str(exc))
        ui.input("Enter to continue")
        return
    for r in found:
        print("\n" + recipes.describe(r))
    if ui.confirm(f"Import {len(found)} recipe(s) into To Try?"):
        added = importer.import_recipes(found)
        print("Imported: " + ", ".join(a["name"] for a in added))
        print("Tip: check dose/water/steps — free-text imports leave unknowns blank.")
        ui.input("Enter to continue")


def feeds_flow():
    data = importer.feeds()
    options = [("add", "󰐕  Add a feed URL (JSON in oma-caffe or schema.org format)"), ("sync", "󰑓  Sync all feeds")]
    options += [(f"rm:{f['url']}", f"󰆴  Remove {f['url']} ({len(f.get('recipes', []))} recipes)") for f in data.get("feeds", [])]
    action = ui.choose("Community feeds", options + [("back", "󰁍  Back")])
    if action == "add":
        importer.add_feed(ui.input("Feed URL:"))
        action = "sync"
    if action == "sync":
        for url, n, err in importer.sync_feeds():
            print(f"{url}: {n} recipes" + (f" (error: {err})" if err else ""))
        ui.input("Enter to continue")
    elif action.startswith("rm:"):
        importer.remove_feed(action[3:])


# ---- dial-in ------------------------------------------------------------------

def dial_form():
    s = state.load()
    b = beans.load()
    bean = beans.active_bean(b)
    active = recipes.get(s.get("active_recipe") or "") or None
    ui.title("󰔛  Dial-in", f"Bean: {beans.bean_label(bean)} · Recipe: {active['name'] if active else 'none'}")
    if not ui.confirm("Same bean?", default=True):
        roaster = ui.input("Roaster:")
        name = ui.input("Bean name:")
        origin = ui.input("Origin / process:", placeholder="Ethiopia Guji, natural")
        roast = ui.choose("Roast level", [(x, x) for x in recipes.ROASTS])
        bean = beans.add_bean({"roaster": roaster, "name": name, "origin": origin, "roast_level": roast})
    if not active:
        espresso = [r for r in recipes.all_recipes() if r.get("method") in ("Espresso", "Milk Drink")]
        if espresso and ui.confirm("Link this shot to a recipe?"):
            active = recipes.get(pick_recipe("Recipe", espresso))
            state.set_active_recipe(active["id"])
    grind = ui.input("Grind setting:", bean.get("grind_setting", "") if bean else "")
    dose = ui.number("Dose in (g):", (active or {}).get("dose_g") or 18, 1, 100)
    out = ui.number("Yield out (g):", (active or {}).get("yield_g") or dose * 2, 1, 500)
    secs = ui.number("Extraction time (s):", 28, 1, 300)
    prep = ui.multi("Puck prep", [(p, p) for p in dial.PREP])
    taste = ui.choose("How did it taste?", [(t, t.capitalize()) for t in dial.TASTES])
    notes = ui.input("Notes:", placeholder="channeling at 10s, blonding early…")
    rec = dial.log({"recipe": (active or {}).get("id"), "grind": grind, "dose_g": dose, "yield_g": out,
                    "time_s": secs, "prep": prep, "taste": taste, "notes": notes})
    print(f"\nLogged {rec['dose_g']:g}g → {rec['yield_g']:g}g in {rec['time_s']:g}s ({rec['ratio']}, {rec['flow_gps']} g/s)")
    for tip in dial.advise(dose, out, secs, taste, active, grind):
        print(f"  → {tip}")
    if taste == "balanced" and active and active.get("status") != "favorite" and ui.confirm("Mark the recipe as Dialed-In Favorite?"):
        recipes.set_status(active["id"], "favorite")
    if ui.confirm("Log it as a cup too?", default=True):
        state.log_cup(recipe_id=(active or {}).get("id"))
    desktop.refresh_bar()
    ui.input("Enter to close", "")


# ---- quick brew launcher (bar middle-click) -------------------------------------

def quick_menu():
    st = state.status()
    ui.title("󰅶  Quick Brew", st["tooltip"].split("\n\n")[0])
    rs = recipes.all_recipes()
    favs = [r for r in rs if r.get("status") == "favorite"]
    sug = recipes.suggestion_of_the_day(recipes=rs)
    options = []
    if sug:
        options.append((f"r:{sug['id']}", f"󰃭  Recipe of the day: {sug['name']} — {recipes.summary(sug)}"))
    options += [(f"r:{r['id']}", f"󰓎  {r['name']} — {recipes.summary(r)}") for r in favs[:6]]
    options += [
        ("all", "󰆘  All recipes…"),
        ("dial", "󰔛  Log a dial-in shot"),
        ("lab", "󰙨  Open the lab"),
        ("ambience", f"󰎈  Cafe ambience: {'ON — turn off' if st['ambience'] else 'off — turn on'}"),
        ("theme", "󰔎  Toggle Crema Light / Ristretto Dark"),
        ("break", "󰾪  Coffee break now"),
        ("undo", "󰕌  Undo last cup"),
    ]
    try:
        action = ui.choose("Brew & tools", options, height=16)
        if action.startswith("r:"):
            r = recipes.get(action[2:])
            if r and not ui.confirm(f"Brew at {r['dose_g']:g}g?", default=True):
                r = recipes.scale(r, ui.number("Dose (g):", r["dose_g"], 1, 2000))
            brew_flow(r)
        elif action == "all":
            recipe_menu(pick_recipe("Pick a recipe"))
        elif action == "dial":
            dial_form()
        elif action == "lab":
            main()
        elif action == "ambience":
            ambience.toggle()
        elif action == "theme":
            if not theme.installed():
                ui.warn("Themes not installed — run install.sh")
            else:
                print(f"Switching to {theme.toggle()}…")
        elif action == "break":
            breaks.show()
        elif action == "undo":
            state.undo_cup()
        desktop.refresh_bar()
    except ui.Cancelled:
        return
