// Settings: every knob in config.json as a slider, toggle or field, plus the
// drink menu editor. Each change is one `oma-caffe config set` call.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

Flickable {
  id: page
  property var s
  readonly property var c: s.cfg || ({})
  readonly property var b: c.breaks || ({})
  readonly property var t: c.theme || ({})
  readonly property var am: c.ambience || ({})
  readonly property var cues: c.cues || ({})

  function set(key, value, label) {
    page.s.act(["config", "set", key, String(value)], label || "Saved ✓")
  }

  contentHeight: col.implicitHeight + Style.space(48)
  clip: true
  boundsBehavior: Flickable.StopAtBounds
  ScrollBar.vertical: ScrollBar {}

  Column {
    id: col
    x: Style.space(28)
    y: Style.space(24)
    width: page.width - Style.space(56)
    spacing: Style.space(18)

    Text { text: "⚙️ Settings"; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.display; font.bold: true }
    CText { s: page.s; muted: true; text: page.s.tagline; font.italic: true }

    GearCard { s: page.s; width: parent.width }

    Row {
      width: parent.width
      spacing: Style.space(18)

      Column {
        width: (parent.width - Style.space(18)) / 2
        spacing: Style.space(18)

        Card {
          s: page.s
          width: parent.width
          title: "☕ Caffeine"
          CSlider { s: page.s; width: parent.width; label: "Half-life"; suffix: " h"; decimals: 1; value: page.c.half_life_hours || 5; from: 2; to: 9; step: 0.5; onReleased: function(v) { page.set("half_life_hours", v) } }
          CSlider { s: page.s; width: parent.width; label: "Daily guide"; suffix: " mg"; value: page.c.daily_limit_mg || 400; from: 100; to: 800; step: 25; onReleased: function(v) { page.set("daily_limit_mg", Math.round(v)) } }
          CSlider { s: page.s; width: parent.width; label: "Decaf cutoff (hour)"; suffix: ":00"; value: page.c.cutoff_hour || 16; from: 10; to: 23; step: 1; onReleased: function(v) { page.set("cutoff_hour", Math.round(v)) } }
        }

        Card {
          s: page.s
          width: parent.width
          title: "🧭 Bar"
          Repeater {
            model: [{ k: "show_cups", l: "Show today's cup count", v: page.s.status.showCups },
                    { k: "show_mg", l: "Show active caffeine (mg)", v: page.s.status.showMg }]
            Row {
              required property var modelData
              spacing: Style.space(12)
              ToggleSwitch {
                checked: modelData.v !== false
                foreground: page.s.fg
                accent: page.s.accent
                onToggled: page.set("bar." + modelData.k, !checked, !checked ? "Shown on the bar" : "Hidden from the bar")
              }
              CText { s: page.s; text: modelData.l; anchors.verticalCenter: parent.verticalCenter }
            }
          }
          CText { s: page.s; muted: true; width: parent.width; font.pixelSize: Style.font.caption; text: "Turn both off for an icon-only cup. Details stay in the tooltip and the panel." }
        }

        Card {
          s: page.s
          width: parent.width
          title: "🎨 Theme"
          Flow {
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: [{ v: "light", l: "☀️ Crema Light", n: "crema-light" }, { v: "dark", l: "🌙 Ristretto Dark", n: "ristretto-dark" }, { v: "cute", l: "🍓 Strawberry Latte", n: "strawberry-latte" }]
              Button {
                required property var modelData
                text: modelData.l
                selected: page.s.status.theme === modelData.n
                bordered: true
                foreground: page.s.fg
                fontFamily: page.s.font
                onClicked: page.s.act(["theme", modelData.v], "Roasting " + modelData.l + "…")
              }
            }
          }
          Row {
            spacing: Style.space(12)
            ToggleSwitch {
              checked: page.t.auto === true
              foreground: page.s.fg
              accent: page.s.accent
              onToggled: page.s.act(["theme", "auto", checked ? "off" : "on"], checked ? "Auto-Roast off" : "Auto-Roast on 🌗")
            }
            CText { s: page.s; text: "Auto-Roast: light by day, dark by night"; anchors.verticalCenter: parent.verticalCenter }
          }
          Row {
            spacing: Style.space(10)
            CText { s: page.s; text: "☀️ at"; anchors.verticalCenter: parent.verticalCenter }
            TextField { width: 90; text: page.t.light_at || "07:00"; foreground: page.s.fg; accent: page.s.accent; onEditingFinished: if (text !== page.t.light_at) page.set("theme.light_at", text) }
            CText { s: page.s; text: "🌙 at"; anchors.verticalCenter: parent.verticalCenter }
            TextField { width: 90; text: page.t.dark_at || "18:30"; foreground: page.s.fg; accent: page.s.accent; onEditingFinished: if (text !== page.t.dark_at) page.set("theme.dark_at", text) }
          }
        }

        Card {
          s: page.s
          width: parent.width
          title: "🎧 Café ambience"
          Row {
            spacing: Style.space(8)
            Button {
              text: page.s.status.ambience ? "Stop" : "Play"
              iconText: page.s.status.ambience ? "⏹" : "▶"
              bordered: true
              selected: page.s.status.ambience === true
              foreground: page.s.fg
              fontFamily: page.s.font
              onClicked: page.s.act(["ambience", "toggle"], "")
            }
          }
          CSlider { s: page.s; width: parent.width; label: "Volume"; suffix: "%"; value: page.am.volume || 35; from: 0; to: 100; step: 5; onReleased: function(v) { page.set("ambience.volume", Math.round(v)) } }
          TextField {
            width: parent.width
            text: page.am.source || ""
            placeholderText: "Your own audio: file, folder or stream URL (blank = synthesized café)"
            foreground: page.s.fg
            accent: page.s.accent
            onEditingFinished: if (text !== (page.am.source || "")) page.set("ambience.source", text)
          }
        }
      }

      Column {
        width: (parent.width - Style.space(18)) / 2
        spacing: Style.space(18)

        Card {
          s: page.s
          width: parent.width
          title: "⏰ Coffee Time breaks"
          Row {
            spacing: Style.space(12)
            ToggleSwitch { checked: page.b.enabled === true; foreground: page.s.fg; accent: page.s.accent; onToggled: page.set("breaks.enabled", !checked, checked ? "Breaks paused" : "Breaks on ☕") }
            CText { s: page.s; text: "Remind me to take coffee breaks"; anchors.verticalCenter: parent.verticalCenter }
          }
          CSlider { s: page.s; width: parent.width; label: "Every"; suffix: " min"; value: page.b.interval_min || 90; from: 20; to: 180; step: 5; onReleased: function(v) { page.set("breaks.interval_min", Math.round(v)) } }
          CSlider { s: page.s; width: parent.width; label: "Break length"; suffix: " min"; value: page.b.break_min || 5; from: 1; to: 20; step: 1; onReleased: function(v) { page.set("breaks.break_min", Math.round(v)) } }
          CSlider { s: page.s; width: parent.width; label: "Snooze"; suffix: " min"; value: page.b.snooze_min || 15; from: 5; to: 60; step: 5; onReleased: function(v) { page.set("breaks.snooze_min", Math.round(v)) } }
          Row {
            spacing: Style.space(10)
            CText { s: page.s; text: "Between"; anchors.verticalCenter: parent.verticalCenter }
            TextField { width: 90; text: page.b.active_from || "09:00"; foreground: page.s.fg; accent: page.s.accent; onEditingFinished: if (text !== page.b.active_from) page.set("breaks.active_from", text) }
            CText { s: page.s; text: "and"; anchors.verticalCenter: parent.verticalCenter }
            TextField { width: 90; text: page.b.active_until || "19:00"; foreground: page.s.fg; accent: page.s.accent; onEditingFinished: if (text !== page.b.active_until) page.set("breaks.active_until", text) }
          }
          Row {
            spacing: Style.space(8)
            Button { text: "Break now"; iconText: "☕"; bordered: true; foreground: page.s.fg; fontFamily: page.s.font; onClicked: page.s.act(["break", "now"], "") }
            Button { text: "Focus 25"; iconText: "🍅"; bordered: true; foreground: page.s.fg; fontFamily: page.s.font; onClicked: page.s.act(["break", "pomodoro", "25"], "Focus! Coffee in 25 min 🍅") }
          }
        }

        Card {
          s: page.s
          width: parent.width
          title: "🔔 Brew cues"
          Repeater {
            model: [{ k: "sound", l: "Chime on every step" }, { k: "osd", l: "On-screen display" }, { k: "notify", l: "Notifications for pours and stops" }]
            Row {
              required property var modelData
              spacing: Style.space(12)
              ToggleSwitch {
                checked: page.cues[modelData.k] !== false
                foreground: page.s.fg
                accent: page.s.accent
                onToggled: page.set("cues." + modelData.k, !checked)
              }
              CText { s: page.s; text: modelData.l; anchors.verticalCenter: parent.verticalCenter }
            }
          }
        }
      }
    }

    // Drink menu editor.
    Card {
      s: page.s
      width: parent.width
      title: "🧋 Drink menu"
      Flow {
        width: parent.width
        spacing: Style.space(6)
        Repeater {
          model: page.s.drinks || []
          Rectangle {
            required property var modelData
            width: drinkRow.implicitWidth + Style.space(18)
            height: drinkRow.implicitHeight + Style.space(12)
            radius: height / 2
            color: modelData.custom ? Qt.rgba(page.s.accent.r, page.s.accent.g, page.s.accent.b, 0.14) : page.s.wash
            border.color: page.s.line
            Row {
              id: drinkRow
              anchors.centerIn: parent
              spacing: Style.space(6)
              Text { text: modelData.icon; font.pixelSize: Style.font.body + 2 }
              CText { s: page.s; text: modelData.label + "  " + modelData.mg + " mg" }
              Text {
                visible: modelData.custom
                text: "✕"
                color: page.s.urgent
                font.pixelSize: Style.font.body
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: page.s.act(["drinks", "remove", modelData.id], "Removed " + modelData.label) }
              }
            }
          }
        }
      }
      Row {
        spacing: Style.space(8)
        TextField { id: dIcon; width: 60; placeholderText: "🌾"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: dName; width: 220; placeholderText: "New drink (Oat Cortado)"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: dMg; width: 100; placeholderText: "mg"; inputMethodHints: Qt.ImhDigitsOnly; foreground: page.s.fg; accent: page.s.accent }
        Dropdown {
          id: dMethod
          width: 180
          showLabel: false
          value: "Milk Drink"
          options: ["Espresso", "Milk Drink", "Pour-Over", "Immersion", "Cold Brew", "Moka Pot", "Tea", "Can", "Other"]
          foreground: page.s.fg
          onChanged: function(v) { dMethod.value = v }
        }
        Button {
          text: "Add drink"
          iconText: "＋"
          bordered: true
          foreground: page.s.fg
          fontFamily: page.s.font
          onClicked: {
            if (!dName.text || !dMg.text) { page.s.toast("Name and mg, please ☕"); return }
            page.s.act(["drinks", "add", dName.text, "--mg", dMg.text, "--method", dMethod.value, "--icon", dIcon.text || "☕"],
                       "Added " + dName.text + " to the menu 🎉", function() { dName.text = dMg.text = dIcon.text = "" })
          }
        }
      }
    }
  }
}
