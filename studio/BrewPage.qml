// Brew: the guided timer as a big progress ring. Each step fires a cue
// (chime + OSD + notification via `oma-caffe cue`). Space pauses, N skips,
// R restarts. When it finishes: log the cup and rate it.

import QtQuick
import QtQuick.Controls
import Quickshell
import qs.Commons
import qs.Ui
import "../Model.js" as Model

Item {
  id: page
  property var s
  readonly property var r: s.brewRecipe
  readonly property var steps: r ? (r.steps || []) : []
  readonly property int total: Model.totalTime(r)
  readonly property bool long: total > 3600

  property bool running: false
  property real banked: 0           // seconds accumulated before the last resume
  property real startedAt: 0        // ms timestamp of the last resume
  property real elapsed: 0
  property int fired: -1            // last step index whose cue fired
  property bool done: false
  property bool logged: false

  readonly property int idx: Model.stepIndex(steps, elapsed)
  readonly property var current: idx >= 0 ? steps[idx] : null
  readonly property var next: idx + 1 < steps.length ? steps[idx + 1] : null

  function reset() {
    page.running = false
    page.banked = 0
    page.elapsed = 0
    page.fired = -1
    page.done = false
    page.logged = false
  }

  function toggle() {
    if (page.done) { reset(); return }
    if (page.running) {
      page.banked = page.elapsed
      page.running = false
    } else {
      page.startedAt = Date.now()
      page.running = true
    }
  }

  function skip() {
    if (!page.next) return
    page.banked = page.next.at
    page.startedAt = Date.now()
    page.elapsed = page.banked
    tick()
  }

  function tick() {
    if (page.running) page.elapsed = page.banked + (Date.now() - page.startedAt) / 1000
    while (page.fired < page.idx) {
      page.fired++
      var st = page.steps[page.fired]
      var final = page.fired === page.steps.length - 1 && st.kind === "stop"
      var args = ["cue", st.label, "--kind", st.kind || "pour", "--progress", String(Math.min(100, 100 * page.elapsed / Math.max(1, page.total)))]
      if (st.target_g !== undefined && st.target_g !== null) args.push("--target", String(st.target_g))
      if (final) args.push("--final")
      page.s.run(args)
    }
    if (page.elapsed >= page.total && page.total > 0 && !page.done) {
      page.done = true
      page.running = false
      page.elapsed = page.total
    }
    ring.requestPaint()
  }

  Timer { interval: 100; running: page.running; repeat: true; onTriggered: page.tick() }

  focus: visible
  Keys.onPressed: function(e) {
    if (e.key === Qt.Key_Space) { page.toggle(); e.accepted = true }
    else if (e.text === "n") { page.skip(); e.accepted = true }
    else if (e.text === "r") { page.reset(); e.accepted = true }
  }

  // ---------- nothing chosen ----------
  Column {
    visible: !page.r
    anchors.centerIn: parent
    spacing: Style.space(14)
    width: 520
    Text { anchors.horizontalCenter: parent.horizontalCenter; text: "⏱"; font.pixelSize: 64 }
    CText { s: page.s; width: parent.width; horizontalAlignment: Text.AlignHCenter; text: "Pick something to brew" ; font.pixelSize: Style.font.title + 4 }
    Repeater {
      model: (page.s.recipes || []).filter(function(x) { return x.status === "favorite" || x.status === "testing" }).slice(0, 5)
              .concat((page.s.recipes || []).filter(function(x) { return x.status === "to_try" }).slice(0, 3))
      Button {
        required property var modelData
        width: 520
        leftAlign: true
        iconText: Model.methodIcon(modelData.method)
        text: modelData.name + "   ·   " + Model.summary(modelData)
        foreground: page.s.fg
        fontFamily: page.s.font
        onClicked: { page.s.brewRecipe = modelData; page.reset() }
      }
    }
  }

  // ---------- the timer ----------
  Row {
    visible: !!page.r
    anchors.fill: parent
    anchors.margins: Style.space(28)
    spacing: Style.space(36)

    Column {
      width: 420
      spacing: Style.space(18)

      Text {
        width: parent.width
        text: page.r ? Model.methodIcon(page.r.method) + "  " + page.r.name : ""
        color: page.s.fg
        font.family: page.s.font
        font.pixelSize: Style.font.title + 6
        font.bold: true
        wrapMode: Text.WordWrap
      }
      CText { s: page.s; muted: true; width: parent.width; text: page.r ? Model.summary(page.r) + "  ·  grind " + (page.r.grind_setting || "?") : "" }

      Canvas {
        id: ring
        width: 380
        height: 380
        anchors.horizontalCenter: parent.horizontalCenter
        onPaint: {
          var ctx = getContext("2d")
          ctx.reset()
          var c = width / 2, rad = width / 2 - 18
          ctx.lineCap = "round"
          ctx.lineWidth = 22
          ctx.strokeStyle = page.s.line
          ctx.beginPath(); ctx.arc(c, c, rad, 0, Math.PI * 2); ctx.stroke()
          // Step ticks.
          ctx.lineWidth = 4
          for (var i = 0; i < page.steps.length; i++) {
            var a = -Math.PI / 2 + Math.PI * 2 * page.steps[i].at / Math.max(1, page.total)
            ctx.strokeStyle = i <= page.idx ? page.s.accent : page.s.dim
            ctx.beginPath()
            ctx.moveTo(c + Math.cos(a) * (rad - 18), c + Math.sin(a) * (rad - 18))
            ctx.lineTo(c + Math.cos(a) * (rad + 18), c + Math.sin(a) * (rad + 18))
            ctx.stroke()
          }
          var frac = Math.min(1, page.elapsed / Math.max(1, page.total))
          if (frac > 0) {
            ctx.lineWidth = 22
            ctx.strokeStyle = page.s.accent
            ctx.beginPath(); ctx.arc(c, c, rad, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * frac); ctx.stroke()
          }
        }

        Column {
          anchors.centerIn: parent
          spacing: Style.space(4)
          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: page.done ? "☕" : Model.clock(page.elapsed)
            color: page.s.fg
            font.family: page.s.font
            font.pixelSize: 72
            font.bold: true
          }
          Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: page.done ? "Enjoy!" : "of " + Model.clock(page.total)
            color: page.s.dim
            font.family: page.s.font
            font.pixelSize: Style.font.title
          }
        }
      }

      Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Style.space(10)
        Button {
          text: page.done ? "Again" : page.running ? "Pause" : (page.elapsed > 0 ? "Resume" : "Start")
          iconText: page.running ? "⏸" : "▶"
          bordered: true
          selected: true
          foreground: page.s.fg
          fontFamily: page.s.font
          fontSize: Style.font.title
          visible: !page.long
          onClicked: page.toggle()
        }
        Button { text: "Skip"; iconText: "⏭"; bordered: true; visible: !page.long && !page.done; foreground: page.s.fg; fontFamily: page.s.font; fontSize: Style.font.title; onClicked: page.skip() }
        Button { text: "Reset"; iconText: "↺"; bordered: true; visible: !page.long; foreground: page.s.fg; fontFamily: page.s.font; fontSize: Style.font.title; onClicked: page.reset() }
        Button {
          visible: page.long
          text: "Schedule step reminders"
          iconText: "🔔"
          bordered: true
          foreground: page.s.fg
          fontFamily: page.s.font
          onClicked: page.s.act(["lab", "brew", page.r.id], "Reminders set for every step 🔔")
        }
      }
      CText { s: page.s; muted: true; width: parent.width; horizontalAlignment: Text.AlignHCenter; visible: !page.long; text: "space pause · n skip · r reset"; font.pixelSize: Style.font.caption }
    }

    // Right: now / next / steps / finish.
    Column {
      width: parent.width - 420 - Style.space(36)
      spacing: Style.space(16)

      Card {
        s: page.s
        width: parent.width
        title: page.done ? "Done" : "Now"
        Text {
          width: parent.width
          text: page.done ? "Brew complete! " + (page.s.status.pun || "") : page.current ? Model.stepGlyph(page.current.kind) + "  " + page.current.label : (page.running ? "" : "Tare your scale, then Start")
          color: page.s.fg
          font.family: page.s.font
          font.pixelSize: Style.font.display
          font.bold: true
          wrapMode: Text.WordWrap
        }
        Text {
          visible: !page.done && page.current && page.current.target_g !== undefined && page.current.target_g !== null
          text: page.current ? "→ " + page.current.target_g + " g" : ""
          color: page.s.accent
          font.family: page.s.font
          font.pixelSize: 56
          font.bold: true
        }
        CText { s: page.s; muted: true; width: parent.width; visible: !page.done && page.current && !!page.current.note; text: page.current ? (page.current.note || "") : "" }
      }

      Card {
        s: page.s
        width: parent.width
        visible: !page.done && !!page.next
        title: "Next"
        Row {
          spacing: Style.space(12)
          Text {
            text: page.next ? Model.clock(Math.max(0, page.next.at - page.elapsed)) : ""
            color: page.s.accent
            font.family: page.s.font
            font.pixelSize: Style.font.display
            font.bold: true
          }
          CText { s: page.s; anchors.verticalCenter: parent.verticalCenter; text: page.next ? Model.stepGlyph(page.next.kind) + "  " + Model.cueText(page.next) : ""; font.pixelSize: Style.font.title }
        }
      }

      Card {
        s: page.s
        width: parent.width
        visible: page.done
        title: "Nice brew!"
        Row {
          spacing: Style.space(8)
          Button {
            text: page.logged ? "Logged ✓" : "Log this cup"
            iconText: "☕"
            bordered: true
            selected: !page.logged
            enabled: !page.logged
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: {
              var args = ["log", "--recipe", page.r.id]
              if (page.r.caffeine_mg) args.push("--mg", String(page.r.caffeine_mg))
              page.logged = true
              page.s.act(args, "Logged! " + (page.s.status.pun || ""))
            }
          }
          Button {
            text: "Rate it"
            iconText: "⭐"
            bordered: true
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: { page.s.selectedId = page.r.id.replace(/-scaled$/, ""); page.s.page = "recipes" }
          }
        }
      }

      Card {
        s: page.s
        width: parent.width
        title: "Steps"
        Repeater {
          model: page.steps
          Row {
            required property var modelData
            required property int index
            spacing: Style.space(12)
            opacity: index < page.idx ? 0.55 : 1
            Text {
              width: 22
              text: index < page.idx || page.done ? "✓" : index === page.idx ? "▶" : "·"
              color: index <= page.idx ? page.s.accent : page.s.dim
              font.pixelSize: Style.font.body + 2
              font.bold: true
            }
            Text { width: 54; text: Model.clock(modelData.at); color: page.s.accent; font.family: page.s.font; font.pixelSize: Style.font.body }
            Text { text: Model.stepGlyph(modelData.kind); font.pixelSize: Style.font.body + 2 }
            CText { s: page.s; text: Model.cueText(modelData); font.bold: index === page.idx }
          }
        }
      }
    }
  }
}
