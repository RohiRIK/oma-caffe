// Beans: the shelf (switch the active bag, set its grind), add a bag, and
// name your grinder.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

Flickable {
  id: page
  property var s
  readonly property var data: s.beansData || ({ beans: [], grinders: [] })
  readonly property var grinder: {
    var g = page.data.grinders || []
    for (var i = 0; i < g.length; i++) if (g[i].id === page.data.active_grinder) return g[i]
    return g.length ? g[0] : null
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

    Text { text: "🫘 Beans & grinder"; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.display; font.bold: true }

    Grid {
      width: parent.width
      columns: Math.max(1, Math.floor(width / 380))
      columnSpacing: Style.space(12)
      rowSpacing: Style.space(12)
      Repeater {
        model: page.data.beans || []
        Card {
          id: beanCard
          required property var modelData
          readonly property bool active: modelData.id === page.data.active_bean
          s: page.s
          width: (col.width - Style.space(12) * (parent.columns - 1)) / parent.columns
          border.color: active ? page.s.accent : page.s.line
          border.width: active ? 2 : 1
          CText { s: page.s; width: parent.width; text: (beanCard.active ? "⭐ " : "") + (modelData.roaster || "") + " — " + (modelData.name || ""); font.bold: true; font.pixelSize: Style.font.title }
          CText { s: page.s; muted: true; width: parent.width; text: [modelData.origin, modelData.process, modelData.roast_level + " roast", modelData.roast_date ? "roasted " + modelData.roast_date : ""].filter(function(x) { return x }).join(" · ") }
          CText { s: page.s; muted: true; width: parent.width; visible: !!modelData.notes; text: "👅 " + (modelData.notes || "") }
          Row {
            spacing: Style.space(8)
            CText { s: page.s; text: "Grind"; anchors.verticalCenter: parent.verticalCenter }
            TextField { id: g; width: 110; text: modelData.grind_setting || ""; foreground: page.s.fg; accent: page.s.accent }
            Button {
              text: "Save"
              visible: beanCard.active
              foreground: page.s.fg
              fontFamily: page.s.font
              enabled: g.text.trim() !== ""
              onClicked: page.s.act(["beans", "grind", g.text.trim()], "Grind saved")
            }
            Button {
              text: beanCard.active ? "In the hopper" : "Use this bag"
              enabled: !beanCard.active
              bordered: true
              foreground: page.s.fg
              fontFamily: page.s.font
              onClicked: page.s.act(["beans", "use", modelData.id], "Now brewing " + modelData.name)
            }
          }
        }
      }
    }

    Card {
      s: page.s
      width: parent.width
      title: "New bag"
      Grid {
        columns: 4
        columnSpacing: Style.space(10)
        rowSpacing: Style.space(10)
        TextField { id: roaster; width: 220; placeholderText: "Roaster"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: name; width: 220; placeholderText: "Coffee name"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: origin; width: 220; placeholderText: "Origin (Ethiopia Guji)"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: process; width: 220; placeholderText: "Process (washed, natural…)"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: roasted; width: 220; placeholderText: "Roast date (2026-10-20)"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: tasting; width: 220; placeholderText: "Tasting notes"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: grindNew; width: 220; placeholderText: "Starting grind"; foreground: page.s.fg; accent: page.s.accent }
        Dropdown { id: roast; width: 220; showLabel: false; value: "Medium"; options: ["Light", "Medium", "Dark"]; foreground: page.s.fg; onChanged: function(v) { roast.value = v } }
      }
      Button {
        text: "Add & use this bag"
        iconText: "＋"
        bordered: true
        foreground: page.s.fg
        fontFamily: page.s.font
        onClicked: {
          if (!name.text && !roaster.text) { page.s.toast("Give it a name first"); return }
          page.s.act(["beans", "add", "--roaster", roaster.text, "--name", name.text, "--origin", origin.text, "--process", process.text,
                      "--roasted", roasted.text, "--notes", tasting.text, "--grind", grindNew.text, "--roast", roast.value],
                     "New bag in the hopper 🫘", function() { roaster.text = name.text = origin.text = process.text = roasted.text = tasting.text = grindNew.text = "" })
        }
      }
    }

    Card {
      s: page.s
      width: parent.width
      title: "Grinder"
      Row {
        spacing: Style.space(10)
        TextField { id: gname; width: 240; text: page.grinder ? page.grinder.name : ""; placeholderText: "DF64, Niche, Comandante…"; foreground: page.s.fg; accent: page.s.accent }
        TextField { id: burrs; width: 240; text: page.grinder ? (page.grinder.burrs || "") : ""; placeholderText: "Burrs (SSP MP)"; foreground: page.s.fg; accent: page.s.accent }
        Button {
          text: "Save grinder"
          bordered: true
          foreground: page.s.fg
          fontFamily: page.s.font
          enabled: gname.text.trim() !== ""
          onClicked: page.s.act(["beans", "grinder", gname.text.trim()].concat(burrs.text ? ["--burrs", burrs.text] : []), "Grinder saved ⚙️")
        }
      }
    }
  }
}
