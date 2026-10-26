// oma-caffe Studio -- the GUI for recipes, brewing, discovery, dial-in,
// beans, stats and settings, in its own window.
//
// Lives inside the plugin's overlay entry (Overlay.qml routes
// {"view":"studio"} payloads here). Every read and write goes through the
// oma-caffe CLI in async Processes, the same single source of truth the bar
// and the terminal use, so the three never disagree.

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "../Model.js" as Model

Item {
  id: s

  property string cli: ""
  property bool opened: false
  property bool closingFromHost: false
  property string page: "recipes"
  signal closed()

  // ---- shared data --------------------------------------------------------
  property var recipes: []
  property var status: ({})
  property var cfg: ({})
  property var drinks: []
  property var beansData: ({ beans: [], grinders: [] })
  property var shots: []
  property var gear: ({})
  readonly property string tagline: "Powered by caffeine and questionable life choices."
  property string selectedId: ""
  property var brewRecipe: null
  property string toastText: ""
  property string sandbox: ""   // self-test HOME; see SelfTest.qml

  readonly property var selected: {
    for (var i = 0; i < s.recipes.length; i++) if (s.recipes[i].id === s.selectedId) return s.recipes[i]
    return null
  }

  // ---- theme --------------------------------------------------------------
  readonly property color bg: Commons.Color.popups.background
  readonly property color fg: Commons.Color.popups.text
  readonly property color accent: Commons.Color.accent
  readonly property color urgent: Commons.Color.urgent
  readonly property color dim: Qt.rgba(fg.r, fg.g, fg.b, 0.64)
  readonly property color line: Qt.rgba(fg.r, fg.g, fg.b, 0.12)
  readonly property color wash: Qt.rgba(fg.r, fg.g, fg.b, 0.045)
  readonly property string font: Style.font.family

  // ---- lifecycle ----------------------------------------------------------
  function open(p) {
    p = p || {}
    if (p.page) s.page = p.page
    if (p.recipe) s.selectedId = p.recipe
    s.sandbox = p.selftest || ""
    s.opened = true
    s.reload(function() {
      if (p.page === "brew" && p.recipe) s.startBrew(p.recipe, p.dose)
      if (p.selftest) selfTest.start()
    })
    win.raise()
  }

  function close() {
    s.closingFromHost = true
    s.opened = false
    s.closingFromHost = false
  }

  // ---- CLI plumbing ---------------------------------------------------------
  // run(args, cb): cb(stdout, exitCode) once the command finishes.
  function run(args, cb) {
    var env = { "OMA_CAFFE_FROM_BAR": "1" }
    if (s.sandbox) env = { HOME: s.sandbox, XDG_CONFIG_HOME: s.sandbox + "/.config", XDG_DATA_HOME: s.sandbox + "/.local/share",
                           XDG_STATE_HOME: s.sandbox + "/.local/state", XDG_CACHE_HOME: s.sandbox + "/.cache", OMA_CAFFE_HEADLESS: "1" }
    var done = function(out, code) {
      if (code !== 0 && selfTest.running) selfTest.cliFailed(args, code)
      if (cb) cb(out, code)
    }
    var p = procComp.createObject(s, { command: [s.cli].concat(args), cb: done, environment: env })
    p.running = true
  }

  function json(args, cb) {
    s.run(args, function(out, code) {
      if (code !== 0) return
      try { cb(JSON.parse(out)) } catch (e) { console.warn("oma-caffe studio: bad JSON from", args.join(" ")) }
    })
  }

  // A write: run it, refresh what it touched, refresh the bar, toast.
  function act(args, message, after) {
    s.run(args, function(out, code) {
      if (code === 0 && message) s.toast(message)
      if (code !== 0) s.toast("Hmm, that didn't work (╥﹏╥)")
      s.reload(after ? function() { after(out) } : null)
    })
  }

  function reload(done) {
    var pending = 6
    function one() { if (--pending === 0 && done) done() }
    s.json(["lab", "list", "--json"], function(d) { s.recipes = d; if (!s.selectedId && d.length) s.selectedId = d[0].id; one() })
    s.json(["status", "--json"], function(d) { s.status = d; one() })
    s.json(["config", "show", "--json"], function(d) { s.cfg = d; one() })
    s.json(["drinks", "list", "--json"], function(d) { s.drinks = d; one() })
    s.json(["beans", "list", "--json"], function(d) { s.beansData = d; one() })
    s.json(["dial", "--list", "12", "--json"], function(d) { s.shots = d })
    s.json(["gear", "show", "--json"], function(d) { s.gear = d; one() })
    if (!s.sandbox) Quickshell.execDetached(["omarchy-shell", "-q", "rohirik.oma-caffe", "refresh"])
  }

  function toast(text) {
    s.toastText = text
    toastTimer.restart()
  }

  function startBrew(recipeId, dose) {
    var r = null
    for (var i = 0; i < s.recipes.length; i++) if (s.recipes[i].id === recipeId) r = s.recipes[i]
    if (!r) return
    s.brewRecipe = dose ? Model.scaleRecipe(r, Number(dose)) : r
    s.page = "brew"
    brewPage.reset()
  }

  Component {
    id: procComp
    Process {
      id: proc
      property var cb: null
      property string out: ""
      property bool streamDone: false
      property int exitCode: -1
      function finish() {
        if (!proc.streamDone || proc.exitCode < 0) return
        if (proc.cb) proc.cb(proc.out, proc.exitCode)
        proc.destroy()
      }
      stdout: StdioCollector {
        waitForEnd: true
        onStreamFinished: { proc.out = text; proc.streamDone = true; proc.finish() }
      }
      onExited: function(code) { proc.exitCode = code; proc.finish() }
    }
  }

  SelfTest { id: selfTest; s: s; root: pages }

  Timer { id: toastTimer; interval: 2600; onTriggered: s.toastText = "" }

  // ---- the window -----------------------------------------------------------
  FloatingWindow {
    id: win
    title: "oma-caffe Studio"
    visible: s.opened
    color: s.bg
    implicitWidth: 1180
    implicitHeight: 800
    minimumSize: Qt.size(900, 600)

    function raise() {
      Quickshell.execDetached([s.cli + "-float", "oma-caffe Studio", "1180", "800"])
    }

    onVisibleChanged: if (!visible && !s.closingFromHost) { s.opened = false; s.closed() }

    Row {
      anchors.fill: parent

      // ---------- sidebar ----------
      Rectangle {
        id: sidebar
        width: 220
        height: parent.height
        color: s.wash

        Column {
          anchors.fill: parent
          anchors.margins: Style.space(14)
          spacing: Style.space(4)

          Text {
            text: "☕ oma-caffe"
            color: s.fg
            font.family: s.font
            font.pixelSize: Style.font.title + 4
            font.bold: true
          }
          Text {
            text: s.status.level ? "Lv " + s.status.level.level + " · " + s.status.level.name : "Studio"
            color: s.accent
            font.family: s.font
            font.pixelSize: Style.font.bodySmall
            bottomPadding: Style.space(10)
          }

          Repeater {
            model: [
              { id: "recipes", icon: "📖", label: "Recipes" },
              { id: "brew", icon: "⏱", label: "Brew" },
              { id: "discover", icon: "🔍", label: "Discover" },
              { id: "dial", icon: "🎯", label: "Dial-in" },
              { id: "beans", icon: "🫘", label: "Beans" },
              { id: "stats", icon: "📊", label: "Stats" },
              { id: "wallpapers", icon: "🖼", label: "Wallpapers" },
              { id: "settings", icon: "⚙️", label: "Settings" }
            ]
            Rectangle {
              required property var modelData
              width: parent.width
              height: Style.space(38)
              radius: Style.cornerRadius
              color: s.page === modelData.id ? Qt.rgba(s.accent.r, s.accent.g, s.accent.b, 0.16)
                   : navMouse.containsMouse ? s.wash : "transparent"
              Row {
                anchors.verticalCenter: parent.verticalCenter
                x: Style.space(10)
                spacing: Style.space(10)
                Text { text: modelData.icon; font.pixelSize: Style.font.title }
                Text {
                  text: modelData.label
                  color: s.page === modelData.id ? s.accent : s.fg
                  font.family: s.font
                  font.pixelSize: Style.font.body + 1
                  font.bold: s.page === modelData.id
                }
              }
              MouseArea {
                id: navMouse
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: s.page = modelData.id
              }
            }
          }
        }

        // Today, at the foot of the sidebar.
        Column {
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.bottom: parent.bottom
          anchors.margins: Style.space(14)
          spacing: Style.space(2)
          Text {
            text: s.status.mood ? s.status.mood.face : ""
            color: s.accent
            font.family: s.font
            font.pixelSize: Style.font.title + 2
            font.bold: true
          }
          Text {
            text: (s.status.cups || 0) + " cups · " + (s.status.mg || 0) + " mg active"
            color: s.status.overLimit ? s.urgent : s.fg
            font.family: s.font
            font.pixelSize: Style.font.bodySmall
          }
          Text {
            width: parent.width
            topPadding: Style.space(8)
            text: "⚡ " + s.tagline
            color: s.accent
            font.family: s.font
            font.pixelSize: Style.font.caption
            font.bold: true
            wrapMode: Text.WordWrap
          }
          Text {
            width: parent.width
            text: s.status.pun || ""
            color: s.dim
            font.family: s.font
            font.pixelSize: Style.font.caption
            font.italic: true
            wrapMode: Text.WordWrap
          }
        }
      }

      // ---------- pages ----------
      Item {
        id: pages
        width: parent.width - sidebar.width
        height: parent.height

        RecipesPage { anchors.fill: parent; s: s; visible: s.page === "recipes" }
        BrewPage { id: brewPage; anchors.fill: parent; s: s; visible: s.page === "brew" }
        DiscoverPage { anchors.fill: parent; s: s; visible: s.page === "discover" }
        DialPage { anchors.fill: parent; s: s; visible: s.page === "dial" }
        BeansPage { anchors.fill: parent; s: s; visible: s.page === "beans" }
        StatsPage { anchors.fill: parent; s: s; visible: s.page === "stats" }
        WallpapersPage { anchors.fill: parent; s: s; visible: s.page === "wallpapers" }
        SettingsPage { anchors.fill: parent; s: s; visible: s.page === "settings" }

        // Toast.
        Rectangle {
          visible: s.toastText !== ""
          anchors.horizontalCenter: parent.horizontalCenter
          anchors.bottom: parent.bottom
          anchors.bottomMargin: Style.space(20)
          width: toastLabel.implicitWidth + Style.space(32)
          height: toastLabel.implicitHeight + Style.space(18)
          radius: height / 2
          color: s.accent
          Text {
            id: toastLabel
            anchors.centerIn: parent
            text: s.toastText
            color: s.bg
            font.family: s.font
            font.pixelSize: Style.font.body
            font.bold: true
          }
        }
      }
    }
  }
}
