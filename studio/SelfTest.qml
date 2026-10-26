// Dogfood self-test: visits every Studio page and fires every visible
// button's real click handler, a few passes deep so buttons revealed by
// earlier clicks (forms, confirms) get pressed too. Only runs when Studio is
// summoned with {"view":"studio","selftest":"<sandbox HOME>"}; Studio then
// points every CLI call at that sandbox, headless, so real data is untouched.
// Results go to the shell log ("oma-caffe selftest:") and <sandbox>/selftest.json.

import QtQuick
import Quickshell

Item {
  id: t
  property var s
  property Item root
  property bool running: false

  readonly property var pages: ["recipes", "brew", "discover", "dial", "beans", "stats", "wallpapers", "settings"]
  property int pageIdx: -1
  property int pass: 0
  property var queue: []
  property var pressed: ({})
  property var report: []
  property string current: ""
  property int failures: 0

  function log(m) { console.log("oma-caffe selftest: " + m) }

  function isButton(item) {
    return typeof item.rightClicked === "function" && item.bordered !== undefined && item.iconText !== undefined
  }

  function shown(item) {
    for (var p = item; p; p = p.parent) if (!p.visible) return false
    return item.enabled
  }

  function collect(item, out) {
    if (!item || !item.visible) return out
    if (t.isButton(item) && item.enabled) out.push(item)
    var kids = item.children || []
    for (var i = 0; i < kids.length; i++) t.collect(kids[i], out)
    if (item.contentItem && kids.indexOf(item.contentItem) === -1) t.collect(item.contentItem, out)
    return out
  }

  function label(b) { return ((b.iconText ? b.iconText + " " : "") + (b.text || b.tooltipText || "?")).trim() }

  function start() {
    t.running = true
    t.pageIdx = -1
    t.report = []
    t.failures = 0
    t.log("start")
    t.nextPage()
  }

  // Called by Studio when a CLI call exits non-zero during the run.
  function cliFailed(args, code) {
    t.failures++
    t.report.push({ page: t.pages[t.pageIdx], button: t.current, ok: false, error: args.join(" ") + " → exit " + code })
    t.log("FAIL " + t.pages[t.pageIdx] + " / " + t.current + ": " + args.join(" ") + " → exit " + code)
  }

  function nextPage() {
    t.pageIdx++
    if (t.pageIdx >= t.pages.length) return t.finish()
    t.pass = 0
    t.pressed = ({})
    t.s.page = t.pages[t.pageIdx]
    t.log("page " + t.s.page)
    settle.restart()
  }

  function scan() {
    var key = {}
    t.queue = t.collect(t.root, []).map(function(b) {
      var k = t.label(b)
      key[k] = (key[k] || 0) + 1
      return { b: b, k: k + "#" + key[k] }
    }).filter(function(e) { return !t.pressed[e.k] })
    if (!t.queue.length || t.pass >= 3) return t.nextPage()
    t.pass++
    clicker.restart()
  }

  function clickNext() {
    var page = t.pages[t.pageIdx]
    if (t.s.page !== page) t.s.page = page       // a button navigated away; come back
    while (t.queue.length) {
      var e = t.queue.shift()
      var b = e.b
      if (!b || !t.shown(b)) continue
      t.pressed[e.k] = true
      t.current = t.label(b)
      t.report.push({ page: page, button: t.current, ok: true })
      try { b.clicked() } catch (e) {
        t.failures++
        t.report.push({ page: page, button: t.current, ok: false, error: String(e) })
        t.log("FAIL " + page + " / " + t.current + ": " + e)
      }
      clicker.restart()
      return
    }
    settle.restart()                              // queue drained: rescan for revealed buttons
  }

  function finish() {
    t.running = false
    var clicks = t.report.filter(function(r) { return r.ok }).length
    t.log("done: " + clicks + " clicks, " + t.failures + " failures")
    Quickshell.execDetached(["sh", "-c", 'printf "%s\\n" "$1" > "$2"', "sh",
                             JSON.stringify({ clicks: clicks, failures: t.failures, report: t.report }),
                             t.s.sandbox + "/selftest.json"])
  }

  Timer { id: settle; interval: 1400; onTriggered: t.scan() }
  Timer { id: clicker; interval: 450; onTriggered: t.clickNext() }
}
