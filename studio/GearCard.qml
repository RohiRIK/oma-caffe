// My gear: pick a grinder and a machine by name (fuzzy autocomplete), then
// see the grinder's scale with every brew method mapped onto it, calibrate
// it to your own sweet spot, and read the machine's capabilities and tips.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

Card {
  id: card
  title: "🛠 My gear — recommendations follow your grinder & machine"

  readonly property var prof: s.gear || ({})
  readonly property var g: prof.grinder || null
  readonly property var m: prof.machine || null
  property var grinderHits: []
  property var machineHits: []

  function searchGear(kind, q) {
    if (!q || q.length < 2) {
      if (kind === "grinder") card.grinderHits = []; else card.machineHits = []
      return
    }
    s.json(["gear", "search", kind].concat(q.split(/\s+/)).concat(["--json"]), function(d) {
      if (kind === "grinder") card.grinderHits = d; else card.machineHits = d
    })
  }

  function pick(kind, item) {
    if (kind === "grinder") { card.grinderHits = []; grinderField.text = "" }
    else { card.machineHits = []; machineField.text = "" }
    s.act(["gear", "set", kind, item.id], "✨ " + item.name + " — got it!")
  }

  Row {
    width: parent.width
    spacing: Style.space(18)

    // ---------- grinder ----------
    Column {
      width: (parent.width - Style.space(18)) / 2
      spacing: Style.space(8)

      CText { s: card.s; text: "⚙️ Grinder"; font.bold: true; font.pixelSize: Style.font.title }
      TextField {
        id: grinderField
        width: parent.width
        placeholderText: card.g ? "Change grinder… (" + card.g.name + ")" : "Type your grinder: Comandante, Niche, DF64, Encore…"
        foreground: card.s.fg
        accent: card.s.accent
        onTextEdited: card.searchGear("grinder", text)
      }
      Repeater {
        model: card.grinderHits
        Button {
          required property var modelData
          width: parent.width
          leftAlign: true
          text: modelData.name + "   ·   " + modelData.kind + ", " + modelData.adjust + (modelData.espresso_capable ? "" : " · filter only")
          foreground: card.s.fg
          fontFamily: card.s.font
          onClicked: card.pick("grinder", modelData)
        }
      }

      Column {
        visible: !!card.g
        width: parent.width
        spacing: Style.space(6)
        CText { s: card.s; width: parent.width; text: card.g ? card.g.name : ""; font.bold: true; color: card.s.accent }
        CText {
          s: card.s; muted: true; width: parent.width; font.pixelSize: Style.font.bodySmall
          text: card.g ? card.g.kind + " · " + card.g.adjust + " · " + card.g.min + "–" + card.g.max + " " + card.g.unit
                         + (card.prof.offset ? " · calibrated " + (card.prof.offset > 0 ? "+" : "") + card.prof.offset : "") : ""
        }

        // The range map: each method's window on the grinder's scale.
        Repeater {
          model: card.prof.ranges || []
          Item {
            required property var modelData
            width: parent.width
            height: Style.space(22)
            CText { id: rl; s: card.s; width: 108; text: modelData.label; font.pixelSize: Style.font.bodySmall; anchors.verticalCenter: parent.verticalCenter }
            Rectangle {
              id: track
              x: rl.width + Style.space(6)
              width: parent.width - x - 64
              height: 8
              radius: 4
              anchors.verticalCenter: parent.verticalCenter
              color: card.s.line
              Rectangle {
                readonly property real span: Math.max(0.0001, card.g.max - card.g.min)
                x: track.width * (modelData.low - card.g.min) / span
                width: Math.max(6, track.width * (modelData.high - modelData.low) / span)
                height: parent.height
                radius: 4
                color: card.s.accent
              }
            }
            CText {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              s: card.s
              text: modelData.low + "–" + modelData.high
              font.pixelSize: Style.font.bodySmall
              color: card.s.accent
            }
          }
        }
        CText { s: card.s; muted: true; width: parent.width; visible: !!(card.g && card.g.notes); text: card.g ? "💡 " + card.g.notes : ""; font.pixelSize: Style.font.bodySmall }

        // Calibration.
        Flow {
          width: parent.width
          spacing: Style.space(8)
          CText { s: card.s; text: "My sweet spot for"; height: calVal.height; verticalAlignment: Text.AlignVCenter; font.pixelSize: Style.font.bodySmall }
          Dropdown {
            id: calCat
            width: 150
            showLabel: false
            value: (card.prof.ranges && card.prof.ranges.length) ? card.prof.ranges[0].category : "espresso"
            options: (card.prof.ranges || []).map(function(r) { return { value: r.category, label: r.label } })
            foreground: card.s.fg
            onChanged: function(v) { calCat.value = v }
          }
          CText { s: card.s; text: "is"; height: calVal.height; verticalAlignment: Text.AlignVCenter; font.pixelSize: Style.font.bodySmall }
          TextField { id: calVal; width: 70; placeholderText: "14"; foreground: card.s.fg; accent: card.s.accent }
          Button {
            text: "Calibrate"
            bordered: true
            foreground: card.s.fg
            fontFamily: card.s.font
            onClicked: { if (!calVal.text) return; card.s.act(["gear", "calibrate", calCat.value, calVal.text], "Calibrated 🎯 every range shifted"); calVal.text = "" }
          }
          Button {
            visible: !!card.prof.offset
            text: "Reset"
            foreground: card.s.dim
            fontFamily: card.s.font
            onClicked: card.s.act(["config", "set", "gear.offset", "0"], "Calibration reset")
          }
        }
      }
    }

    // ---------- machine ----------
    Column {
      width: (parent.width - Style.space(18)) / 2
      spacing: Style.space(8)

      CText { s: card.s; text: "☕ Espresso machine"; font.bold: true; font.pixelSize: Style.font.title }
      TextField {
        id: machineField
        width: parent.width
        placeholderText: card.m ? "Change machine… (" + card.m.name + ")" : "Type your machine: Gaggia, Bambino, Silvia, Flair…"
        foreground: card.s.fg
        accent: card.s.accent
        onTextEdited: card.searchGear("machine", text)
      }
      Repeater {
        model: card.machineHits
        Button {
          required property var modelData
          width: parent.width
          leftAlign: true
          text: modelData.name + "   ·   " + modelData.kind
          foreground: card.s.fg
          fontFamily: card.s.font
          onClicked: card.pick("machine", modelData)
        }
      }

      Text {
        text: customForm.visible ? "▾ Not listed? Describe your machine" : "▸ Not listed? Describe your machine"
        color: card.s.accent
        font.family: card.s.font
        font.pixelSize: Style.font.bodySmall
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: customForm.visible = !customForm.visible }
      }
      Column {
        id: customForm
        visible: false
        width: parent.width
        spacing: Style.space(6)
        property string kind: "heat exchanger"
        property string pressure: "fixed"
        property string preinfusion: "none"
        property bool e61: false
        TextField { id: cName; width: parent.width; placeholderText: "Name (e.g. Vibiemme Domobar)"; foreground: card.s.fg; accent: card.s.accent }
        Row {
          spacing: Style.space(6)
          Dropdown { width: 170; showLabel: false; value: customForm.kind; options: card.prof.machine_kinds || []; foreground: card.s.fg; onChanged: function(v) { customForm.kind = v } }
          Dropdown { width: 150; showLabel: false; value: customForm.pressure; options: [{ value: "fixed", label: "fixed pressure" }, { value: "profiling", label: "profiling" }, { value: "manual", label: "manual lever" }]; foreground: card.s.fg; onChanged: function(v) { customForm.pressure = v } }
        }
        Row {
          spacing: Style.space(6)
          Dropdown { width: 170; showLabel: false; value: customForm.preinfusion; options: [{ value: "none", label: "no pre-infusion" }, { value: "passive", label: "passive (E61)" }, { value: "auto", label: "automatic" }, { value: "adjustable", label: "adjustable" }, { value: "manual", label: "manual" }]; foreground: card.s.fg; onChanged: function(v) { customForm.preinfusion = v } }
          Button { text: "E61 group"; selected: customForm.e61; bordered: true; foreground: card.s.fg; fontFamily: card.s.font; onClicked: customForm.e61 = !customForm.e61 }
        }
        Row {
          spacing: Style.space(6)
          TextField { id: cPf; width: 80; placeholderText: "58 mm"; foreground: card.s.fg; accent: card.s.accent }
          TextField { id: cBasket; width: 80; placeholderText: "18 g"; foreground: card.s.fg; accent: card.s.accent }
          TextField { id: cTmin; width: 80; placeholderText: "min °C"; foreground: card.s.fg; accent: card.s.accent }
          TextField { id: cTmax; width: 80; placeholderText: "max °C"; foreground: card.s.fg; accent: card.s.accent }
        }
        CText { s: card.s; muted: true; width: parent.width; font.pixelSize: Style.font.caption; text: "Leave the °C fields empty if your machine has no PID / temperature setting." }
        Button {
          text: "Save my machine"
          iconText: "💾"
          bordered: true
          foreground: card.s.fg
          fontFamily: card.s.font
          onClicked: {
            var args = ["gear", "custom", "name=" + (cName.text || "My machine"), "kind=" + customForm.kind, "pressure=" + customForm.pressure,
                        "preinfusion=" + customForm.preinfusion, "e61=" + (customForm.e61 ? "1" : "0")]
            if (cPf.text) args.push("portafilter_mm=" + parseInt(cPf.text))
            if (cBasket.text) args.push("basket_g=" + parseFloat(cBasket.text))
            if (cTmin.text && cTmax.text) args.push("temp_min=" + parseFloat(cTmin.text), "temp_max=" + parseFloat(cTmax.text))
            customForm.visible = false
            card.s.act(args, "Saved " + (cName.text || "your machine") + " ☕")
          }
        }
      }

      Column {
        visible: !!card.m
        width: parent.width
        spacing: Style.space(8)
        CText { s: card.s; width: parent.width; text: card.m ? card.m.name : ""; font.bold: true; color: card.s.accent }
        Flow {
          width: parent.width
          spacing: Style.space(6)
          Repeater {
            model: card.m ? [
              "🔥 " + card.m.kind,
              "⭕ " + card.m.portafilter_mm + " mm",
              "⚖️ " + card.m.basket_g + " g basket",
              "🌡 " + (card.m.temp.adjustable ? card.m.temp.range[0] + "–" + card.m.temp.range[1] + " °C" : "fixed temp"),
              "📈 " + card.m.pressure.type + " pressure" + (card.m.pressure.type === "fixed" ? " (" + card.m.pressure.bar + " bar)" : ""),
              "💧 pre-infusion: " + card.m.preinfusion
            ].concat(card.m.pump ? ["⚙️ " + card.m.pump + " pump"] : []).concat(card.m.group ? ["🔩 " + card.m.group + " group"] : []) : []
            Rectangle {
              required property string modelData
              width: mt.implicitWidth + Style.space(16)
              height: mt.implicitHeight + Style.space(10)
              radius: height / 2
              color: card.s.wash
              border.color: card.s.line
              Text { id: mt; anchors.centerIn: parent; text: modelData; color: card.s.fg; font.family: card.s.font; font.pixelSize: Style.font.bodySmall }
            }
          }
        }
        Repeater {
          model: card.m ? card.m.tips : []
          CText { required property string modelData; s: card.s; width: parent.width; text: "💡 " + modelData; font.pixelSize: Style.font.bodySmall }
        }
        // Upgrades that fit this machine; fitting one changes the advice.
        CText { s: card.s; text: "🔧 Upgrades & mods you've fitted"; font.bold: true; topPadding: Style.space(6) }
        Flow {
          width: parent.width
          spacing: Style.space(6)
          Repeater {
            model: card.prof.upgrades || []
            Button {
              required property var modelData
              text: modelData.name
              iconText: modelData.icon
              selected: modelData.installed
              bordered: true
              tooltipText: modelData.desc
              foreground: card.s.fg
              fontFamily: card.s.font
              fontSize: Style.font.bodySmall
              onClicked: card.s.act(["gear", "upgrade", modelData.installed ? "remove" : "add", modelData.id],
                                    (modelData.installed ? "Removed " : "Fitted ") + modelData.name + (modelData.installed ? "" : " 🔧"))
            }
          }
        }
        Row {
          visible: (card.prof.upgrades || []).some(function(u) { return u.id === "precision-basket" && u.installed })
          spacing: Style.space(8)
          CText { s: card.s; text: "Basket size"; anchors.verticalCenter: parent.verticalCenter; font.pixelSize: Style.font.bodySmall }
          TextField { id: basketField; width: 80; text: card.prof.basket_g ? String(card.prof.basket_g) : ""; placeholderText: "20"; foreground: card.s.fg; accent: card.s.accent }
          CText { s: card.s; text: "g"; anchors.verticalCenter: parent.verticalCenter }
          Button { text: "Save"; enabled: basketField.text.trim() !== ""; bordered: true; foreground: card.s.fg; fontFamily: card.s.font; onClicked: card.s.act(["gear", "basket", basketField.text], "Basket: " + basketField.text + " g") }
        }

        Button {
          visible: !!(card.m && card.m.builtin_grinder) && !(card.g && card.g.id === card.m.builtin_grinder)
          text: "Use its built-in grinder"
          iconText: "⚙️"
          bordered: true
          foreground: card.s.fg
          fontFamily: card.s.font
          onClicked: card.s.act(["gear", "set", "grinder", card.m.builtin_grinder], "Built-in grinder selected")
        }
      }
    }
  }

  CText { s: card.s; muted: true; width: parent.width; text: card.prof.disclaimer || ""; font.pixelSize: Style.font.caption; font.italic: true }
}
