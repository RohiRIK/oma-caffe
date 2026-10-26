// Dial-in: sliders for dose / yield / time with live ratio and flow, puck
// prep and taste chips, then advice for the next shot. Recent shots on the
// right.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "../Model.js" as Model

Row {
  id: page
  property var s
  property real dose: 18
  property real out: 36
  property real secs: 28
  property var prep: []
  property string taste: "balanced"
  property var tips: []
  property string recipeId: ""

  readonly property var espresso: (s.recipes || []).filter(function(r) { return r.method === "Espresso" || r.method === "Milk Drink" })
  readonly property var bean: {
    var b = s.beansData || {}
    var list = b.beans || []
    for (var i = 0; i < list.length; i++) if (list[i].id === b.active_bean) return list[i]
    return list.length ? list[0] : null
  }

  function pickRecipe(id) {
    page.recipeId = id
    for (var i = 0; i < page.espresso.length; i++) if (page.espresso[i].id === id) {
      page.dose = page.espresso[i].dose_g || 18
      page.out = page.espresso[i].yield_g || page.dose * 2
    }
  }

  spacing: 0

  Flickable {
    width: parent.width * 0.58
    height: parent.height
    contentHeight: form.implicitHeight + Style.space(48)
    clip: true
    boundsBehavior: Flickable.StopAtBounds

    Column {
      id: form
      x: Style.space(28)
      y: Style.space(24)
      width: parent.width - Style.space(56)
      spacing: Style.space(16)

      Text { text: "🎯 Dial-in"; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.display; font.bold: true }
      CText { s: page.s; muted: true; width: parent.width; text: "Bean: " + (page.s.status.bean || "—") + "  ·  " + (page.s.status.grind || "") }

      Card {
        s: page.s
        width: parent.width
        title: "The shot"
        Dropdown {
          width: parent.width
          label: "Recipe"
          value: page.recipeId
          options: [{ value: "", label: "— none —" }].concat(page.espresso.map(function(r) { return { value: r.id, label: r.name } }))
          foreground: page.s.fg
          onChanged: function(v) { page.pickRecipe(v) }
        }
        Row {
          spacing: Style.space(10)
          CText { s: page.s; text: "Grind"; anchors.verticalCenter: parent.verticalCenter }
          TextField { id: grind; width: 160; text: page.bean ? (page.bean.grind_setting || "") : ""; foreground: page.s.fg; accent: page.s.accent }
        }
        CSlider { s: page.s; width: parent.width; label: "Dose in"; suffix: " g"; decimals: 1; value: page.dose; from: 7; to: 25; step: 0.1; onReleased: function(v) { page.dose = v } }
        CSlider { s: page.s; width: parent.width; label: "Yield out"; suffix: " g"; decimals: 1; value: page.out; from: 10; to: 100; step: 0.5; onReleased: function(v) { page.out = v } }
        CSlider { s: page.s; width: parent.width; label: "Time"; suffix: " s"; value: page.secs; from: 5; to: 60; step: 1; onReleased: function(v) { page.secs = v } }
        Row {
          spacing: Style.space(24)
          CText { s: page.s; text: "📐 " + Model.ratioText(page.dose, page.out); font.pixelSize: Style.font.title; font.bold: true }
          CText { s: page.s; text: "💧 " + (page.out / Math.max(1, page.secs)).toFixed(1) + " g/s"; font.pixelSize: Style.font.title; font.bold: true }
        }
      }

      Card {
        s: page.s
        width: parent.width
        title: "Puck prep"
        Flow {
          width: parent.width
          spacing: Style.space(6)
          Repeater {
            model: ["WDT", "Puck screen", "RDT (spritz)", "Paper filter", "Leveler", "Calibrated tamp", "Dosing cup shake"]
            Button {
              required property string modelData
              text: modelData
              selected: page.prep.indexOf(modelData) !== -1
              bordered: true
              foreground: page.s.fg
              fontFamily: page.s.font
              onClicked: {
                var p = page.prep.slice()
                var i = p.indexOf(modelData)
                if (i === -1) p.push(modelData); else p.splice(i, 1)
                page.prep = p
              }
            }
          }
        }
      }

      Card {
        s: page.s
        width: parent.width
        title: "How did it taste?"
        Flow {
          width: parent.width
          spacing: Style.space(6)
          Repeater {
            model: [{ v: "sour", l: "🍋 Sour" }, { v: "balanced", l: "😋 Balanced" }, { v: "bitter", l: "🫠 Bitter" }, { v: "thin", l: "💧 Thin" }, { v: "astringent", l: "😖 Astringent" }]
            Button {
              required property var modelData
              text: modelData.l
              selected: page.taste === modelData.v
              bordered: true
              foreground: page.s.fg
              fontFamily: page.s.font
              onClicked: page.taste = modelData.v
            }
          }
        }
        TextField { id: notes; width: parent.width; placeholderText: "Notes — channeling at 10s, blonding early…"; foreground: page.s.fg; accent: page.s.accent }
      }

      Row {
        spacing: Style.space(8)
        Button {
          text: "Log shot"
          iconText: "💾"
          bordered: true
          selected: true
          foreground: page.s.fg
          fontFamily: page.s.font
          fontSize: Style.font.title
          onClicked: {
            var args = ["dial", "--dose", String(page.dose), "--yield", String(page.out), "--time", String(page.secs),
                        "--taste", page.taste, "--json"]
            if (grind.text) args.push("--grind", grind.text)
            if (page.prep.length) args.push("--prep", page.prep.join(","))
            if (notes.text) args.push("--notes", notes.text)
            if (page.recipeId) args.push("--recipe", page.recipeId)
            page.s.run(args, function(o, code) {
              if (code !== 0) { page.s.toast("Couldn't log that shot"); return }
              try { page.tips = JSON.parse(o).tips || [] } catch (e) { page.tips = [] }
              notes.text = ""
              page.s.toast("Shot logged 🎯")
              page.s.reload()
            })
          }
        }
        Button {
          text: "Also log as a cup"
          iconText: "☕"
          bordered: true
          foreground: page.s.fg
          fontFamily: page.s.font
          onClicked: page.s.act(page.recipeId ? ["log", "--recipe", page.recipeId] : ["log"], "+1 cup ☕")
        }
      }

      Card {
        s: page.s
        width: parent.width
        visible: page.tips.length > 0
        title: "Next shot"
        Repeater {
          model: page.tips
          CText { required property string modelData; s: page.s; width: parent.width; text: "→ " + modelData; font.pixelSize: Style.font.title }
        }
      }
    }
  }

  Rectangle { width: 1; height: parent.height; color: page.s.line }

  Flickable {
    width: parent.width * 0.42 - 1
    height: parent.height
    contentHeight: recent.implicitHeight + Style.space(48)
    clip: true
    Column {
      id: recent
      x: Style.space(20)
      y: Style.space(28)
      width: parent.width - Style.space(40)
      spacing: Style.space(10)
      Text { text: "RECENT SHOTS"; color: page.s.dim; font.family: page.s.font; font.pixelSize: Style.font.caption; font.bold: true; font.letterSpacing: 1.3 }
      CText { s: page.s; muted: true; visible: !(page.s.shots && page.s.shots.length); text: "No shots yet. Pull one and log it!" }
      Repeater {
        model: page.s.shots || []
        Card {
          required property var modelData
          s: page.s
          width: parent.width
          CText {
            s: page.s
            width: parent.width
            text: modelData.dose_g + " g → " + modelData.yield_g + " g in " + modelData.time_s + " s   " + (modelData.ratio || "")
            font.bold: true
          }
          CText {
            s: page.s
            muted: true
            width: parent.width
            font.pixelSize: Style.font.bodySmall
            text: new Date(modelData.ts * 1000).toLocaleString(Qt.locale(), "d MMM HH:mm") + " · grind " + (modelData.grind || "?")
                  + (modelData.taste ? " · " + modelData.taste : "") + (modelData.notes ? " · " + modelData.notes : "")
          }
        }
      }
    }
  }
}
