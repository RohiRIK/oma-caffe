// Discover: the curated library + feeds, URL/text import with preview, and
// community feed management.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "../Model.js" as Model

Flickable {
  id: page
  property var s
  property var hits: []
  property var preview: []
  property var feeds: []
  property bool searched: false

  contentHeight: col.implicitHeight + Style.space(48)
  clip: true
  boundsBehavior: Flickable.StopAtBounds
  ScrollBar.vertical: ScrollBar {}

  function search(q) {
    page.s.json(["lab", "research"].concat(q ? q.split(/\s+/) : []).concat(["--json"]), function(d) { page.hits = d; page.searched = true })
  }
  function loadFeeds() { page.s.json(["lab", "feed", "list", "--json"], function(d) { page.feeds = d }) }

  onVisibleChanged: if (visible) { if (!page.searched) search(""); loadFeeds() }

  Column {
    id: col
    x: Style.space(28)
    y: Style.space(24)
    width: page.width - Style.space(56)
    spacing: Style.space(18)

    Text { text: "🔍 Discover"; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.display; font.bold: true }
    CText { s: page.s; muted: true; width: parent.width; text: "Championship and classic recipes, your community feeds, or anything on the web. Added recipes land in To Try." }

    Row {
      spacing: Style.space(8)
      TextField {
        id: q
        width: 460
        placeholderText: "aeropress, hoffmann, iced, light roast…"
        foreground: page.s.fg
        accent: page.s.accent
        onAccepted: page.search(text)
      }
      Button { text: "Search"; iconText: "🔍"; bordered: true; foreground: page.s.fg; fontFamily: page.s.font; onClicked: page.search(q.text) }
    }

    Grid {
      width: parent.width
      columns: Math.max(1, Math.floor(width / 360))
      columnSpacing: Style.space(12)
      rowSpacing: Style.space(12)
      Repeater {
        model: page.hits
        Card {
          required property var modelData
          s: page.s
          width: (col.width - Style.space(12) * (parent.columns - 1)) / parent.columns
          Row {
            spacing: Style.space(10)
            width: parent.width
            Text { text: Model.methodIcon(modelData.method); font.pixelSize: 34 }
            Column {
              width: parent.width - 50
              spacing: 2
              CText { s: page.s; width: parent.width; text: modelData.name; font.bold: true; font.pixelSize: Style.font.title }
              CText { s: page.s; muted: true; width: parent.width; text: Model.summary(modelData); font.pixelSize: Style.font.bodySmall }
              CText { s: page.s; muted: true; width: parent.width; text: modelData.author || ""; font.pixelSize: Style.font.caption; elide: Text.ElideRight; maximumLineCount: 1 }
            }
          }
          Button {
            text: modelData.in_db ? "In your recipes ✓" : "Add to my recipes"
            iconText: modelData.in_db ? "" : "＋"
            enabled: !modelData.in_db
            bordered: true
            foreground: page.s.fg
            fontFamily: page.s.font
            onClicked: page.s.act(["lab", "adopt", modelData.id], "Added " + modelData.name + " ☕", function() { page.search(q.text) })
          }
        }
      }
    }

    Card {
      s: page.s
      width: parent.width
      title: "Import from the web"
      CText { s: page.s; muted: true; width: parent.width; text: "Paste a recipe URL (blogs with schema.org recipes work best), a path to a .json file, or the recipe text itself — '0:45 - pour to 150g' lines become timed steps." }
      TextArea {
        id: src
        width: parent.width
        height: 110
        wrapMode: TextEdit.Wrap
        placeholderText: "https://…  or paste the recipe"
        color: page.s.fg
        font.family: page.s.font
        background: Rectangle { color: page.s.wash; border.color: page.s.line; radius: Style.cornerRadius }
      }
      Row {
        spacing: Style.space(8)
        Button {
          text: "Preview"
          iconText: "👀"
          bordered: true
          foreground: page.s.fg
          fontFamily: page.s.font
          enabled: src.text.trim() !== ""
          onClicked: page.s.run(["lab", "import", src.text.trim(), "--dry-run", "--json"], function(out, code) {
            if (code !== 0) { page.preview = []; page.s.toast("No recipe found there (｡•́︿•̀｡)"); return }
            try { page.preview = JSON.parse(out) } catch (e) { page.preview = [] }
          })
        }
        Button {
          text: "Import " + (page.preview.length || "")
          iconText: "⬇"
          bordered: true
          enabled: page.preview.length > 0
          foreground: page.s.fg
          fontFamily: page.s.font
          onClicked: page.s.act(["lab", "import", src.text.trim(), "--json"], "Imported " + page.preview.length + " recipe(s) 🎉", function() { page.preview = []; src.text = "" })
        }
      }
      Repeater {
        model: page.preview
        CText { required property var modelData; s: page.s; width: parent.width; text: "• " + modelData.name + " — " + Model.summary(modelData) + " · " + (modelData.steps || []).length + " steps" }
      }
    }

    Card {
      s: page.s
      width: parent.width
      title: "Community feeds"
      CText { s: page.s; muted: true; width: parent.width; text: "A feed is any URL serving oma-caffe JSON or schema.org recipes. Synced recipes show up in the search above." }
      Repeater {
        model: page.feeds
        Row {
          required property var modelData
          spacing: Style.space(10)
          CText { s: page.s; text: modelData.url + "  (" + (modelData.recipes || []).length + " recipes)"; anchors.verticalCenter: parent.verticalCenter }
          Button { text: "Remove"; foreground: page.s.dim; fontFamily: page.s.font; onClicked: page.s.act(["lab", "feed", "remove", modelData.url], "Feed removed", page.loadFeeds) }
        }
      }
      Row {
        spacing: Style.space(8)
        TextField { id: feedUrl; width: 420; placeholderText: "https://example.com/recipes.json"; foreground: page.s.fg; accent: page.s.accent }
        Button {
          text: "Add"
          iconText: "＋"
          bordered: true
          foreground: page.s.fg
          fontFamily: page.s.font
          onClicked: { if (!feedUrl.text) return; page.s.act(["lab", "feed", "add", feedUrl.text], "Feed added", function() { feedUrl.text = ""; page.loadFeeds() }) }
        }
        Button { text: "Sync all"; iconText: "🔄"; bordered: true; foreground: page.s.fg; fontFamily: page.s.font; onClicked: page.s.act(["lab", "feed", "sync"], "Feeds synced", function() { page.loadFeeds(); page.search(q.text) }) }
      }
    }
  }
}
