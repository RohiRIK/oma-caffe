// Recipes: search + filter on the left, the selected recipe on the right
// with a live dose slider (output and every pour rescale as you drag),
// brew / rate / experiment / status actions and the tasting history.

import QtQuick
import QtQuick.Controls
import Quickshell
import qs.Commons
import qs.Ui
import "../Model.js" as Model

Item {
  id: page
  property var s
  property string query: ""
  property string filter: "all"
  property real dose: 0
  property bool rating: false
  property bool experimenting: false
  property bool confirmDelete: false
  property var rec: null

  function loadRec() {
    page.rec = null
    if (!page.r) return
    var id = page.r.id
    page.s.json(["gear", "recommend", id, "--json"], function(d) { if (page.r && page.r.id === id) page.rec = d })
  }
  Connections {
    target: page.s
    function onGearChanged() { page.loadRec() }
  }

  readonly property var list: Model.filterRecipes(s.recipes, page.query, page.filter)
  readonly property var r: s.selected
  readonly property var scaled: r ? Model.scaleRecipe(r, page.dose > 0 ? page.dose : r.dose_g) : null

  onRChanged: {
    page.dose = r ? Number(r.dose_g || 0) : 0
    page.rating = false
    page.experimenting = false
    page.confirmDelete = false
    page.loadRec()
  }

  Row {
    anchors.fill: parent

    // ---------- list ----------
    Column {
      id: listCol
      width: 360
      height: parent.height
      padding: Style.space(16)
      spacing: Style.space(10)

      TextField {
        width: listCol.width - listCol.padding * 2
        placeholderText: "🔍  Search recipes, methods, authors…"
        foreground: page.s.fg
        accent: page.s.accent
        font.family: page.s.font
        onTextChanged: page.query = text
      }

      Row {
        spacing: Style.space(4)
        Repeater {
          model: [{ v: "all", l: "All" }, { v: "favorite", l: "⭐ Faves" }, { v: "testing", l: "🧪 Testing" }, { v: "to_try", l: "🆕 To Try" }]
          Button {
            required property var modelData
            text: modelData.l
            selected: page.filter === modelData.v
            foreground: page.s.fg
            fontFamily: page.s.font
            fontSize: Style.font.bodySmall
            onClicked: page.filter = modelData.v
          }
        }
      }

      ListView {
        id: listView
        width: listCol.width - listCol.padding * 2
        height: page.height - y - listCol.padding
        clip: true
        spacing: Style.space(4)
        model: page.list
        boundsBehavior: Flickable.StopAtBounds

        delegate: Rectangle {
          required property var modelData
          width: listView.width
          height: rowCol.implicitHeight + Style.space(16)
          radius: Style.cornerRadius + 2
          color: modelData.id === page.s.selectedId ? Qt.rgba(page.s.accent.r, page.s.accent.g, page.s.accent.b, 0.16)
               : rowMouse.containsMouse ? page.s.wash : "transparent"

          Row {
            x: Style.space(10)
            anchors.verticalCenter: parent.verticalCenter
            spacing: Style.space(10)
            Text { text: Model.methodIcon(modelData.method); font.pixelSize: Style.font.title + 6; anchors.verticalCenter: parent.verticalCenter }
            Column {
              id: rowCol
              width: listView.width - Style.space(60)
              spacing: 2
              Text {
                width: parent.width
                text: modelData.name + (modelData.parent ? "  ↳" : "")
                color: page.s.fg
                font.family: page.s.font
                font.pixelSize: Style.font.body
                font.bold: true
                elide: Text.ElideRight
              }
              Text {
                width: parent.width
                text: Model.summary(modelData)
                color: page.s.dim
                font.family: page.s.font
                font.pixelSize: Style.font.caption
                elide: Text.ElideRight
              }
              Text {
                text: (modelData.status === "favorite" ? "⭐ " : modelData.status === "testing" ? "🧪 " : "🆕 ")
                      + (Model.score(modelData) !== null ? "★ " + Model.score(modelData).toFixed(1) : Model.STATUS_LABELS[modelData.status])
                color: page.s.accent
                font.family: page.s.font
                font.pixelSize: Style.font.caption
              }
            }
          }
          MouseArea {
            id: rowMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: page.s.selectedId = modelData.id
          }
        }
      }
    }

    Rectangle { width: 1; height: parent.height; color: page.s.line }

    // ---------- detail ----------
    Flickable {
      width: parent.width - listCol.width - 1
      height: parent.height
      contentHeight: detail.implicitHeight + Style.space(40)
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      ScrollBar.vertical: ScrollBar {}

      Column {
        id: detail
        visible: !!page.r
        x: Style.space(28)
        y: Style.space(24)
        width: parent.width - Style.space(56)
        spacing: Style.space(16)

        // Title block.
        Row {
          spacing: Style.space(16)
          width: parent.width
          Text { text: page.r ? Model.methodIcon(page.r.method) : ""; font.pixelSize: 54 }
          Column {
            width: parent.width - 80
            spacing: Style.space(4)
            Text {
              width: parent.width
              text: page.r ? page.r.name : ""
              color: page.s.fg
              font.family: page.s.font
              font.pixelSize: Style.font.display
              font.bold: true
              wrapMode: Text.WordWrap
            }
            CText {
              s: page.s
              muted: true
              width: parent.width
              text: page.r ? [page.r.author ? "by " + page.r.author : "", page.r.roast_level + " roast", page.r.bean_profile].filter(function(x) { return x }).join("  ·  ") : ""
            }
            Text {
              visible: page.r && /^https?:/.test(page.r.source || "")
              text: "🔗 open source"
              color: page.s.accent
              font.family: page.s.font
              font.pixelSize: Style.font.bodySmall
              font.underline: true
              MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: Quickshell.execDetached(["xdg-open", page.r.source]) }
            }
          }
        }

        // Fact chips.
        Flow {
          width: parent.width
          spacing: Style.space(8)
          Repeater {
            model: page.scaled ? [
              "⚖️ " + page.scaled.dose_g + " g in",
              (page.scaled.yield_g ? "☕ " + page.scaled.yield_g + " g out" : "💧 " + page.scaled.water_ml + " g water"),
              "📐 " + (page.scaled.ratio || Model.ratioText(page.scaled.dose_g, Model.outputOf(page.scaled))),
              "🌡 " + (page.scaled.temp_c || "?") + " °C",
              "⚙️ " + (page.scaled.grind_setting || "grind ?"),
              "⏱ " + Model.clock(Model.totalTime(page.scaled))
            ] : []
            Rectangle {
              required property string modelData
              width: chipText.implicitWidth + Style.space(20)
              height: chipText.implicitHeight + Style.space(12)
              radius: height / 2
              color: page.s.wash
              border.color: page.s.line
              Text { id: chipText; anchors.centerIn: parent; text: modelData; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.body }
            }
          }
        }

        // Dose slider.
        Card {
          s: page.s
          width: parent.width
          title: "Dose — drag to rescale everything"
          CSlider {
            s: page.s
            width: parent.width
            label: page.scaled ? "→ " + Model.outputOf(page.scaled) + (page.scaled.yield_g ? " g out" : " g water")
                   + (page.scaled.caffeine_mg ? "  ·  ~" + page.scaled.caffeine_mg + " mg caffeine" : "") : ""
            suffix: " g"
            decimals: 1
            value: page.dose
            from: page.r ? Math.max(1, Math.round(page.r.dose_g * 0.4)) : 1
            to: page.r ? Math.round(page.r.dose_g * 2.5) : 2
            step: page.r && page.r.dose_g >= 50 ? 5 : 0.5
            onReleased: function(v) { page.dose = v }
          }
        }

        // Your gear.
        Card {
          s: page.s
          width: parent.width
          title: "🛠 On your gear"
          visible: !!page.rec
          CText {
            s: page.s
            width: parent.width
            visible: !(page.s.gear && (page.s.gear.grinder || page.s.gear.machine))
            muted: true
            text: "Tell me your grinder and machine in ⚙️ Settings → My gear and I'll give you exact settings for every recipe."
          }
          Row {
            visible: !!(page.rec && page.rec.grind)
            spacing: Style.space(12)
            Text { text: "⚙️"; font.pixelSize: 28; anchors.verticalCenter: parent.verticalCenter }
            Column {
              CText { s: page.s; text: page.rec && page.rec.grind ? page.rec.grind.grinder + " · " + page.rec.categoryLabel : ""; muted: true; font.pixelSize: Style.font.bodySmall }
              Text {
                text: page.rec && page.rec.grind ? "Start at " + page.rec.grind.start + " " + page.rec.grind.unit : ""
                color: page.s.accent
                font.family: page.s.font
                font.pixelSize: Style.font.title + 6
                font.bold: true
              }
              CText { s: page.s; muted: true; text: page.rec && page.rec.grind ? "window " + page.rec.grind.low + "–" + page.rec.grind.high + " " + page.rec.grind.unit : ""; font.pixelSize: Style.font.bodySmall }
            }
          }
          Repeater {
            model: page.rec ? page.rec.warnings : []
            CText { required property string modelData; s: page.s; width: parent.width; text: "⚠️ " + modelData; color: page.s.urgent }
          }
          Repeater {
            model: page.rec ? page.rec.machine : []
            Row {
              required property var modelData
              spacing: Style.space(10)
              width: parent.width
              CText {
                s: page.s
                width: parent.width - (scaleBtn.visible ? scaleBtn.width + Style.space(10) : 0)
                text: ({ dose: "⚖️", temp: "🌡", pressure: "📈", preinfusion: "💧", machine: "💡" }[modelData.kind] || "•") + "  " + modelData.text
              }
              Button {
                id: scaleBtn
                visible: modelData.kind === "dose"
                text: "Scale to " + modelData.dose + " g"
                bordered: true
                foreground: page.s.fg
                fontFamily: page.s.font
                onClicked: page.dose = modelData.dose
              }
            }
          }
        }

        // Steps.
        Card {
          s: page.s
          width: parent.width
          title: "Steps"
          Repeater {
            model: page.scaled ? page.scaled.steps : []
            Row {
              required property var modelData
              spacing: Style.space(14)
              Text { width: 54; text: Model.clock(modelData.at); color: page.s.accent; font.family: page.s.font; font.pixelSize: Style.font.body; font.bold: true }
              Text { text: Model.stepGlyph(modelData.kind); font.pixelSize: Style.font.body + 2 }
              Column {
                CText { s: page.s; text: Model.cueText(modelData) }
                CText { s: page.s; muted: true; visible: !!modelData.note; text: modelData.note || ""; font.pixelSize: Style.font.bodySmall }
              }
            }
          }
        }

        // Actions.
        Flow {
          width: parent.width
          spacing: Style.space(8)
          Button {
            text: "Brew this"
            iconText: "▶"
            bordered: true
            selected: true
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: {
              page.s.brewRecipe = page.scaled
              page.s.page = "brew"
            }
          }
          Button { text: "Rate"; iconText: "⭐"; bordered: true; selected: page.rating; foreground: page.s.fg; fontFamily: page.s.font; onClicked: page.rating = !page.rating }
          Button { text: "Experiment"; iconText: "🧪"; bordered: true; selected: page.experimenting; foreground: page.s.fg; fontFamily: page.s.font; onClicked: page.experimenting = !page.experimenting }
          Button {
            text: page.s.status.activeRecipe === (page.r ? page.r.name : "") ? "Active" : "Set active"
            iconText: "✓"
            bordered: true
            selected: page.s.status.activeRecipe === (page.r ? page.r.name : "")
            tooltipText: "Dial-in shots and logged cups link to the active recipe"
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: page.s.act(["lab", "active", page.r.id], "Active recipe set")
          }
          Repeater {
            model: [{ v: "to_try", l: "🆕 To Try" }, { v: "testing", l: "🧪 Testing" }, { v: "favorite", l: "⭐ Favorite" }]
            Button {
              required property var modelData
              text: modelData.l
              selected: page.r && page.r.status === modelData.v
              foreground: page.s.fg
              fontFamily: page.s.font
              onClicked: page.s.act(["lab", "status", page.r.id, modelData.v], "Marked " + modelData.l)
            }
          }
          Button {
            text: page.confirmDelete ? "Really delete?" : "Delete"
            iconText: "🗑"
            foreground: page.confirmDelete ? page.s.urgent : page.s.dim
            fontFamily: page.s.font
            onClicked: {
              if (!page.confirmDelete) { page.confirmDelete = true; return }
              var id = page.r.id
              page.s.selectedId = ""
              page.s.act(["lab", "delete", id], "Deleted")
            }
          }
        }

        // Rate card.
        Card {
          id: rateCard
          visible: page.rating
          s: page.s
          width: parent.width
          title: "Taste scorecard"
          property var scores: ({ acidity: 3, sweetness: 3, body: 3, bitterness: 3, overall: 3 })
          Repeater {
            model: ["acidity", "sweetness", "body", "bitterness", "overall"]
            Row {
              required property string modelData
              spacing: Style.space(16)
              CText { s: page.s; width: 110; text: modelData.charAt(0).toUpperCase() + modelData.slice(1); anchors.verticalCenter: parent.verticalCenter }
              Stars {
                s: page.s
                editable: true
                value: rateCard.scores[modelData]
                onPicked: function(v) { var x = Object.assign({}, rateCard.scores); x[modelData] = v; rateCard.scores = x }
              }
            }
          }
          TextField {
            id: notesField
            width: parent.width
            placeholderText: "Tasting notes — stone fruit, cocoa, a bit hollow…"
            foreground: page.s.fg
            accent: page.s.accent
            font.family: page.s.font
          }
          Button {
            text: "Save rating"
            iconText: "💾"
            bordered: true
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: {
              var sc = rateCard.scores
              var args = ["lab", "rate", page.r.id]
              for (var k in sc) args.push("--" + k, String(sc[k]))
              if (notesField.text) args.push("--notes", notesField.text)
              page.rating = false
              notesField.text = ""
              page.s.act(args, sc.overall >= 5 ? "5★! Mark it a favorite? 🌟" : "Rated ★" + sc.overall)
            }
          }
        }

        // Experiment card.
        Card {
          visible: page.experimenting
          s: page.s
          width: parent.width
          title: "Branch an experiment"
          CText { s: page.s; muted: true; width: parent.width; text: "Leave blank what you're not changing. Use +/- for relative tweaks (grind -0.5, temp +2) or a plain number for absolute." }
          Grid {
            columns: 2
            columnSpacing: Style.space(12)
            rowSpacing: Style.space(8)
            CText { s: page.s; text: "Grind" }
            TextField { id: exGrind; width: 220; placeholderText: page.r ? (page.r.grind_setting || "-0.5") : ""; foreground: page.s.fg; accent: page.s.accent }
            CText { s: page.s; text: "Temp °C" }
            TextField { id: exTemp; width: 220; placeholderText: "+2"; foreground: page.s.fg; accent: page.s.accent }
            CText { s: page.s; text: "Dose g" }
            TextField { id: exDose; width: 220; placeholderText: page.r ? String(page.r.dose_g) : ""; foreground: page.s.fg; accent: page.s.accent }
            CText { s: page.s; text: "Name" }
            TextField { id: exName; width: 220; placeholderText: "(auto)"; foreground: page.s.fg; accent: page.s.accent }
          }
          Button {
            text: "Create experiment"
            iconText: "🧪"
            bordered: true
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: {
              var args = ["lab", "clone", page.r.id]
              if (exGrind.text) args.push("--grind", exGrind.text)
              if (exTemp.text) args.push("--temp", exTemp.text)
              if (exDose.text) args.push("--dose", exDose.text)
              if (exName.text) args.push("--name", exName.text)
              page.experimenting = false
              page.s.act(args, "Experiment created 🧪", function(out) {
                var id = String(out).trim().split(/\s+/)[0]
                if (id) page.s.selectedId = id
              })
              exGrind.text = exTemp.text = exDose.text = exName.text = ""
            }
          }
        }

        // Tasting history.
        Card {
          visible: page.r && page.r.ratings && page.r.ratings.length > 0
          s: page.s
          width: parent.width
          title: "Tasting history"
          Repeater {
            model: page.r && page.r.ratings ? page.r.ratings.slice().reverse() : []
            Row {
              required property var modelData
              spacing: Style.space(12)
              Stars { s: page.s; value: modelData.overall || 0; size: Style.font.body + 2 }
              CText {
                s: page.s
                text: new Date(modelData.ts * 1000).toLocaleDateString(Qt.locale(), "d MMM") + "  ·  A" + (modelData.acidity || "-")
                      + " S" + (modelData.sweetness || "-") + " B" + (modelData.body || "-") + " Bi" + (modelData.bitterness || "-")
                      + (modelData.notes ? "  ·  " + modelData.notes : "")
              }
            }
          }
        }
      }

      CText {
        visible: !page.r
        s: page.s
        muted: true
        anchors.centerIn: parent
        text: "Pick a recipe on the left ☕"
      }
    }
  }
}
