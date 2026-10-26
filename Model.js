// Pure helpers for BarWidget.qml and BreakOverlay.qml. No QML imports, so
// test/model.test.js can load this file in node.

var CUP_EMPTY = "󰛊"   // md-coffee-outline
var CUP_FULL = "󰅶"    // md-coffee

// Count label beside the cup: "3 · 142mg", or just "3" when showMg is off.
// Vertical bars stack the two values.
function countText(status, showMg, vertical) {
  var cups = status && status.cups !== undefined ? Number(status.cups) : 0
  // Studio → Settings → Bar can hide either half (or both: icon only).
  if (status && status.showMg === false) showMg = false
  var showCups = !(status && status.showCups === false)
  if (!showCups && !showMg) return ""
  if (!showCups) return status && status.mg !== undefined ? Math.round(Number(status.mg)) + "mg" : ""
  if (!showMg || !status || status.mg === undefined) return String(cups)
  var mg = Math.round(Number(status.mg))
  return vertical ? cups + "\n" + mg : cups + " · " + mg + "mg"
}

// Mouse-wheel deltas arrive in 120ths on wheels and in small fractions on
// touchpads; accumulate until a full notch before stepping the profile.
function wheelSteps(accumulated, delta) {
  var total = accumulated + delta
  var steps = 0
  while (total >= 120) { steps -= 1; total -= 120 }    // wheel up = previous
  while (total <= -120) { steps += 1; total += 120 }   // wheel down = next
  return { steps: steps, rest: total }
}

// Overlay key handling, shared so the mapping is testable.
function overlayAction(key, text) {
  var k = String(text || "").toLowerCase()
  if (key === "Return" || key === "Enter") return "enter"
  if (key === "Escape") return "skip"
  if (k === "r") return "recipe"
  if (k === "s") return "snooze"
  return ""
}

// Argument vector for each overlay action against the oma-caffe CLI.
function overlayCommand(action, cli, payload) {
  var p = payload || {}
  if (action === "enter") {
    var args = [cli, "break", "start", String(p.breakMin || 5)]
    if (p.mode === "decaf") args.push("--decaf")
    return args
  }
  if (action === "recipe" && p.recipe && p.recipe.id) return [cli, "brew", p.recipe.id, "--window"]
  if (action === "snooze") return [cli, "break", "snooze", String(p.snoozeMin || 15)]
  if (action === "skip") return [cli, "break", "skip"]
  return []
}

// Steam ribbon i at time t (seconds): x offsets for a wavy line rising from
// the cup, 0..1 progress up the ribbon -> horizontal sway in units of width.
function steamSway(i, t, progress) {
  var phase = t * 1.6 + i * 2.1
  return Math.sin(progress * 5.5 + phase) * (0.25 + progress * 0.75)
}

// Single-key shortcuts inside the café panel.
var PANEL_KEYS = { c: "cup", u: "undo", l: "lock", a: "ambience", t: "theme", b: "break", f: "focus", d: "dial", r: "lab" }

function panelKey(text) {
  return PANEL_KEYS[String(text || "").toLowerCase()] || ""
}

// Tallest day in the week chart, never 0 so bar heights stay finite.
function weekPeak(week) {
  var peak = 1
  for (var i = 0; i < (week || []).length; i++) peak = Math.max(peak, Number(week[i].cups || 0))
  return peak
}

function unlockedCount(badges) {
  var n = 0
  for (var i = 0; i < (badges || []).length; i++) if (badges[i].unlocked) n++
  return n
}

// ---- Studio helpers ---------------------------------------------------------

var METHOD_ICONS = { "Espresso": "☕", "V60": "🔻", "Chemex": "⏳", "AeroPress": "🧪", "Milk Drink": "🥛",
                     "Pour-Over": "🫖", "French Press": "🫙", "Moka Pot": "🌋", "Cold Brew": "🧊" }
var STATUS_LABELS = { to_try: "To Try", testing: "Testing", favorite: "Favorite" }
var STEP_GLYPHS = { pour: "💧", swirl: "🌀", stir: "🥄", press: "⬇️", stop: "⏹", wait: "⏳", preinfuse: "💧", shot: "☕" }

function methodIcon(method) { return METHOD_ICONS[method] || "☕" }
function stepGlyph(kind) { return STEP_GLYPHS[kind] || "•" }

function outputOf(r) { return (r && (r.yield_g || r.water_ml)) || 0 }

function round1(x) { return Math.round(x * 10) / 10 }

// Same rule as recipes.scale(): output, pour targets and caffeine follow the
// dose; timings stay put.
function scaleRecipe(r, dose) {
  if (!r) return null
  var out = JSON.parse(JSON.stringify(r))
  var old = Number(r.dose_g || 0)
  if (!(old > 0) || !(dose > 0)) return out
  var k = dose / old
  out.dose_g = round1(dose)
  if (out.yield_g) out.yield_g = Math.round(r.yield_g * k)
  if (out.water_ml) out.water_ml = Math.round(r.water_ml * k)
  if (out.caffeine_mg) out.caffeine_mg = Math.round(r.caffeine_mg * k)
  for (var i = 0; i < (out.steps || []).length; i++)
    if (out.steps[i].target_g !== undefined && out.steps[i].target_g !== null)
      out.steps[i].target_g = Math.round(r.steps[i].target_g * k)
  return out
}

function clock(sec) {
  sec = Math.max(0, Math.floor(sec))
  if (sec >= 3600) return Math.floor(sec / 3600) + "h" + ("0" + Math.floor((sec % 3600) / 60)).slice(-2)
  return Math.floor(sec / 60) + ":" + ("0" + (sec % 60)).slice(-2)
}

function totalTime(r) {
  var steps = (r && r.steps) || []
  if (!steps.length) return 0
  var last = steps[steps.length - 1]
  return last.kind === "stop" ? last.at : last.at + 30
}

function stepIndex(steps, elapsed) {
  var idx = -1
  for (var i = 0; i < (steps || []).length; i++) if (steps[i].at <= elapsed) idx = i
  return idx
}

function cueText(step) {
  if (!step) return ""
  return step.label + (step.target_g !== undefined && step.target_g !== null ? " → " + step.target_g + "g" : "")
}

function score(r) {
  var vals = []
  var ratings = (r && r.ratings) || []
  for (var i = 0; i < ratings.length; i++) {
    var x = ratings[i]
    if (x.overall !== undefined) vals.push(x.overall)
    else {
      var axes = [x.acidity, x.sweetness, x.body].filter(function(v) { return v !== undefined })
      if (axes.length) vals.push(axes.reduce(function(a, b) { return a + b }, 0) / axes.length)
    }
  }
  if (!vals.length) return null
  return vals.reduce(function(a, b) { return a + b }, 0) / vals.length
}

function summary(r) {
  if (!r) return ""
  var bits = [r.method]
  if (r.dose_g) bits.push(r.dose_g + "g in")
  var out = outputOf(r)
  if (out) bits.push(out + (r.yield_g ? "g out" : "g water"))
  if (r.ratio) bits.push(r.ratio)
  if (r.temp_c) bits.push(r.temp_c + "°C")
  return bits.join(" · ")
}

function filterRecipes(list, query, status) {
  var q = String(query || "").toLowerCase().split(/\s+/).filter(function(t) { return t })
  var order = { favorite: 0, testing: 1, to_try: 2 }
  return (list || []).filter(function(r) {
    if (status && status !== "all" && r.status !== status) return false
    var hay = [r.name, r.method, r.author, r.bean_profile, r.roast_level].concat(r.tags || []).join(" ").toLowerCase()
    return q.every(function(t) { return hay.indexOf(t) !== -1 })
  }).sort(function(a, b) {
    return (order[a.status] - order[b.status]) || String(a.name).localeCompare(String(b.name))
  })
}

function ratioText(dose, out) {
  if (!(dose > 0) || !(out > 0)) return ""
  return "1:" + round1(out / dose)
}
