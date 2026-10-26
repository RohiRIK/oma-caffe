// Wallpapers: the curated gallery of coffee photos and paintings. Filter by
// mood, click one to preview, set it now or add it to any theme's rotation.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui

Item {
  id: page
  property var s
  property var items: []
  property string filter: "all"
  property string selectedId: ""
  property bool busy: false

  readonly property var themes: [{ id: "crema-light", label: "☀️ Crema Light" }, { id: "ristretto-dark", label: "🌙 Ristretto Dark" }, { id: "strawberry-latte", label: "🍓 Strawberry Latte" }]
  readonly property var shown: page.items.filter(function(w) {
    if (page.filter === "all") return true
    if (page.filter === "dark" || page.filter === "light") return w.tone === page.filter
    return w.tags.indexOf(page.filter) !== -1
  })
  readonly property var sel: {
    for (var i = 0; i < page.items.length; i++) if (page.items[i].id === page.selectedId) return page.items[i]
    return null
  }

  function load() {
    page.s.json(["wallpapers", "list", "--json"], function(d) {
      page.items = d
      if (d.some(function(w) { return !w.thumb })) page.s.run(["wallpapers", "thumbs"], function() { page.load() })
    })
  }

  function op(args, busyText, doneText) {
    page.busy = true
    page.s.toast(busyText)
    page.s.run(args, function(out, code) {
      page.busy = false
      page.s.toast(code === 0 ? doneText : "Couldn't fetch that one (｡•́︿•̀｡)")
      page.load()
    })
  }

  onVisibleChanged: if (visible) load()

  Column {
    anchors.fill: parent
    anchors.margins: Style.space(24)
    spacing: Style.space(14)

    Row {
      spacing: Style.space(14)
      Text { text: "🖼 Wallpapers"; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.display; font.bold: true }
      CText { s: page.s; muted: true; text: page.items.length + " curated photos & paintings · public domain, CC0 & CC BY-SA, credited"; anchors.bottom: parent.bottom; bottomPadding: 6 }
    }

    Row {
      spacing: Style.space(4)
      Repeater {
        model: [{ v: "all", l: "All" }, { v: "art", l: "🎨 Art" }, { v: "minimal", l: "◻️ Minimal" }, { v: "cozy", l: "🕯 Cozy" },
                { v: "latte", l: "☕ Latte" }, { v: "dark", l: "🌙 Dark" }, { v: "light", l: "☀️ Light" }]
        Button {
          required property var modelData
          text: modelData.l
          selected: page.filter === modelData.v
          foreground: page.s.fg
          fontFamily: page.s.font
          onClicked: page.filter = modelData.v
        }
      }
    }

    // Selected wallpaper: preview + actions.
    Rectangle {
      visible: !!page.sel
      width: parent.width
      height: visible ? 196 : 0
      radius: Style.cornerRadius + 4
      color: page.s.wash
      border.color: page.s.line
      Row {
        anchors.fill: parent
        anchors.margins: Style.space(14)
        spacing: Style.space(18)
        Image {
          width: 300
          height: 168
          source: page.sel && page.sel.thumb ? "file://" + page.sel.thumb : ""
          fillMode: Image.PreserveAspectCrop
          asynchronous: true
        }
        Column {
          width: parent.width - 320
          spacing: Style.space(8)
          Text { width: parent.width; text: page.sel ? page.sel.name : ""; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.title + 4; font.bold: true; elide: Text.ElideRight }
          CText { s: page.s; muted: true; width: parent.width; text: page.sel ? (page.sel.artist || "unknown") + " · " + page.sel.license + " · " + page.sel.width + "px" : ""; font.pixelSize: Style.font.bodySmall }
          Button {
            text: page.busy ? "Working…" : "Set as wallpaper now"
            iconText: "🖼"
            enabled: !page.busy
            bordered: true
            selected: true
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: page.op(["wallpapers", "set", page.sel.id], "Downloading in full quality…", "Enjoy the view ☕")
          }
          Flow {
            width: parent.width
            spacing: Style.space(6)
            Repeater {
              model: page.themes
              Button {
                required property var modelData
                readonly property bool has: page.sel && page.sel.themes.indexOf(modelData.id) !== -1
                text: (has ? "✓ " : "＋ ") + modelData.label
                selected: has
                enabled: !page.busy
                tooltipText: has ? "In this theme's rotation — click to remove (bundled ones stay)" : "Add to this theme's background rotation"
                foreground: page.s.fg
                fontFamily: page.s.font
                fontSize: Style.font.bodySmall
                onClicked: has ? page.op(["wallpapers", "remove", page.sel.id, "--theme", modelData.id], "Removing…", "Removed from " + modelData.label)
                               : page.op(["wallpapers", "add", page.sel.id, "--theme", modelData.id], "Downloading in full quality…", "Added to " + modelData.label + " ✨")
              }
            }
          }
        }
      }
    }

    GridView {
      id: grid
      width: parent.width
      height: parent.height - y
      clip: true
      cellWidth: Math.floor(width / Math.max(1, Math.floor(width / 250)))
      cellHeight: cellWidth * 9 / 16 + 34
      model: page.shown
      boundsBehavior: Flickable.StopAtBounds
      ScrollBar.vertical: ScrollBar {}

      delegate: Item {
        required property var modelData
        width: grid.cellWidth
        height: grid.cellHeight
        Rectangle {
          anchors.fill: parent
          anchors.margins: 5
          radius: Style.cornerRadius + 2
          color: page.s.wash
          border.color: modelData.id === page.selectedId ? page.s.accent : (tileMouse.containsMouse ? page.s.dim : page.s.line)
          border.width: modelData.id === page.selectedId ? 3 : 1
          clip: true
          Image {
            id: thumb
            x: 3; y: 3
            width: parent.width - 6
            height: width * 9 / 16
            source: modelData.thumb ? "file://" + modelData.thumb : ""
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            Text { anchors.centerIn: parent; visible: thumb.status !== Image.Ready; text: "☕"; font.pixelSize: 28; opacity: 0.4 }
            Rectangle {
              visible: modelData.themes.length > 0
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.margins: 6
              width: badgeText.implicitWidth + 12
              height: badgeText.implicitHeight + 6
              radius: height / 2
              color: page.s.accent
              Text { id: badgeText; anchors.centerIn: parent; text: "✓ " + modelData.themes.length; color: page.s.bg; font.pixelSize: Style.font.caption; font.bold: true }
            }
          }
          Text {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 8
            text: modelData.name
            color: page.s.fg
            font.family: page.s.font
            font.pixelSize: Style.font.bodySmall
            elide: Text.ElideRight
          }
        }
        MouseArea {
          id: tileMouse
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: page.selectedId = modelData.id
          onDoubleClicked: page.op(["wallpapers", "set", modelData.id], "Downloading in full quality…", "Enjoy the view ☕")
        }
      }
    }
  }
}
