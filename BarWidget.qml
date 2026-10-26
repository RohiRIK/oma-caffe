// rohirik.oma-caffe -- cups today and active caffeine, on the bar, with a
// popup café panel behind it.
//
// Left click opens the panel: kawaii mood, barista level, caffeine gauge,
// quick actions, today's cups with
// undo/remove, a week chart and streak, achievements and the recipe of the
// day. Middle click logs a cup of the current drink (the cup fills, then
// steams), right click toggles Caffeine Lock (Omarchy's stay-awake) and the
// wheel walks the brew profiles. All state lives in the oma-caffe CLI: this
// file renders its JSON and fires commands through async Processes, so
// nothing here can stall the bar.

import QtQuick
import QtQuick.Controls
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Ui
import "Model.js" as Model

Panel {
  id: root
  moduleName: "rohirik.oma-caffe"
  manageIpc: false

  readonly property string cli: Qt.resolvedUrl("bin/oma-caffe").toString().replace("file://", "")
  readonly property bool showMg: setting("showMg", true) !== false
  readonly property int refreshIntervalSec: Math.max(10, Number(setting("refreshIntervalSec", 30)))
  readonly property bool vertical: bar ? bar.vertical : false

  property var status: ({})
  property bool pouring: false
  property real wheelRest: 0
  property int pendingProfileSteps: 0
  property var queue: []

  readonly property bool locked: status.lock === true
  readonly property color foreground: bar ? bar.barForeground : Color.foreground
  readonly property color dim: Qt.darker(root.foreground, 1.45)
  readonly property color accent: Color.accent
  readonly property color urgent: bar ? bar.urgent : Color.urgent
  readonly property string fontFamily: bar ? bar.fontFamily : Style.font.family
  readonly property bool steaming: locked || pouring
  readonly property var stats: status.stats || ({ week: [] })
  readonly property var level: status.level || ({ level: 1, name: "", progress: 0 })

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  // ---- behaviour ----------------------------------------------------------

  function refresh() {
    if (statusProc.running) return
    statusProc.running = true
  }

  // Panel actions run one at a time, in click order.
  function cmd(args) {
    var q = root.queue.slice()
    q.push(args)
    root.queue = q
    pump()
  }

  function pump() {
    if (actionProc.running || root.queue.length === 0) return
    var q = root.queue.slice()
    actionProc.command = [root.cli].concat(q.shift())
    root.queue = q
    actionProc.running = true
  }

  function window(args) {
    Quickshell.execDetached([root.cli].concat(args))
    root.close()
  }

  function logCup(profile) {
    var next = Object.assign({}, root.status)
    next.cups = Number(next.cups || 0) + 1
    root.status = next
    pourAnim.restart()
    cmd(profile ? ["log", "--profile", profile] : ["log"])
  }

  function toggleLock() {
    var next = Object.assign({}, root.status)
    next.lock = !root.locked
    root.status = next
    cmd(["lock", "toggle"])
  }

  function stepProfile(steps) {
    if (steps === 0) return
    if (profileProc.running) {
      root.pendingProfileSteps += steps
      return
    }
    profileProc.command = [root.cli, "profile", steps > 0 ? "next" : "prev"]
    profileProc.running = true
    root.pendingProfileSteps += steps > 0 ? steps - 1 : steps + 1
  }

  onOpenedChanged: if (root.opened) root.refresh()
  Component.onCompleted: refresh()

  // ---- bar button ---------------------------------------------------------

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: ""
    labelVisible: false
    hasVisualContent: true
    fixedWidth: root.vertical ? -1 : content.implicitWidth + scaledHorizontalMargin * 2
    fixedHeight: root.vertical ? content.implicitHeight + scaledVerticalPadding * 2 : -1
    tooltipText: root.opened ? "" : (root.status.tooltip || "oma-caffe")

    onPressed: function(mouseButton) {
      if (mouseButton === Qt.LeftButton) root.toggle()
      else if (mouseButton === Qt.MiddleButton) root.logCup("")
      else if (mouseButton === Qt.RightButton) root.toggleLock()
    }

    onWheelMoved: function(delta) {
      var r = Model.wheelSteps(root.wheelRest, delta)
      root.wheelRest = r.rest
      root.stepProfile(r.steps)
    }

    Grid {
      id: content
      anchors.centerIn: parent
      columns: root.vertical ? 1 : 2
      columnSpacing: Style.space(5)
      rowSpacing: Style.space(2)
      horizontalItemAlignment: Grid.AlignHCenter
      verticalItemAlignment: Grid.AlignVCenter

      // An outline cup with a filled copy clipped from the bottom, so
      // `fill` pours it from empty to full.
      Item {
        id: cup
        property real fill: root.locked ? 1 : 0
        implicitWidth: outline.implicitWidth
        implicitHeight: outline.implicitHeight

        Behavior on fill {
          enabled: !pourAnim.running
          NumberAnimation { duration: 260; easing.type: Easing.OutCubic }
        }

        Text {
          id: outline
          text: Model.CUP_EMPTY
          color: root.locked || root.opened ? root.accent : root.foreground
          font.family: root.fontFamily
          font.pixelSize: Style.font.icon
          renderType: Text.NativeRendering
        }

        Item {
          anchors.bottom: parent.bottom
          width: parent.width
          height: parent.height * cup.fill
          clip: true

          Text {
            anchors.bottom: parent.bottom
            text: Model.CUP_FULL
            color: outline.color
            font: outline.font
            renderType: Text.NativeRendering
          }
        }

        Repeater {
          model: 2
          Text {
            id: wisp
            required property int index
            text: "~"
            color: outline.color
            font.family: root.fontFamily
            font.pixelSize: Math.max(7, Math.round(Style.font.icon * 0.5))
            rotation: 90
            x: cup.width * (0.22 + index * 0.3)
            y: -height * 0.2
            opacity: 0
            visible: root.steaming

            SequentialAnimation {
              running: root.steaming
              loops: Animation.Infinite
              PauseAnimation { duration: wisp.index * 550 }
              ParallelAnimation {
                NumberAnimation { target: wisp; property: "y"; from: -wisp.height * 0.15; to: -wisp.height * 0.75; duration: 1100; easing.type: Easing.OutSine }
                SequentialAnimation {
                  NumberAnimation { target: wisp; property: "opacity"; from: 0; to: 0.8; duration: 300 }
                  NumberAnimation { target: wisp; property: "opacity"; to: 0; duration: 800 }
                }
              }
            }
          }
        }
      }

      Text {
        visible: text !== ""
        text: Model.countText(root.status, root.showMg, root.vertical)
        color: root.status.overLimit ? root.urgent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.body
        horizontalAlignment: Text.AlignHCenter
        renderType: Text.NativeRendering
      }
    }
  }

  SequentialAnimation {
    id: pourAnim
    ScriptAction { script: { root.pouring = true; cup.fill = 0 } }
    NumberAnimation { target: cup; property: "fill"; to: 1; duration: 520; easing.type: Easing.InOutQuad }
    PauseAnimation { duration: 1400 }
    ScriptAction { script: { root.pouring = false; cup.fill = Qt.binding(function() { return root.locked ? 1 : 0 }) } }
  }

  // ---- the café panel -----------------------------------------------------

  KeyboardPanel {
    id: panel
    anchorItem: button
    owner: root
    bar: root.bar
    open: root.opened
    focusTarget: keyCatcher
    contentWidth: panel.fittedContentWidth(Style.space(470))
    contentHeight: panel.fittedContentHeight(column.implicitHeight)

    PanelKeyCatcher {
      id: keyCatcher
      anchors.fill: parent
      onCloseRequested: root.close()
      onTabRequested: function(direction) { root.switchPanel(direction) }
      onTextKey: function(t) {
        var a = Model.panelKey(t)
        if (a === "cup") root.logCup("")
        else if (a === "undo") root.cmd(["undo"])
        else if (a === "lock") root.toggleLock()
        else if (a === "ambience") root.cmd(["ambience", "toggle"])
        else if (a === "theme") root.cmd(["theme", "cycle"])
        else if (a === "break") root.window(["break", "now"])
        else if (a === "focus") root.cmd(["break", "pomodoro", "25"])
        else if (a === "dial") root.window(["studio", "dial"])
        else if (a === "lab") root.window(["studio", "recipes"])
        else if (a === "settings") root.window(["studio", "settings"])
      }

      Flickable {
        anchors.fill: parent
        contentWidth: width
        contentHeight: column.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds

        Column {
          id: column
          width: parent.width
          spacing: Style.space(12)

          // ---------- hero: mood, level, pun ----------
          Item {
            width: parent.width
            implicitHeight: Math.max(face.implicitHeight, heroText.implicitHeight)

            Text {
              id: face
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              text: root.status.mood ? root.status.mood.face : "(˘ᵕ˘)"
              color: root.accent
              font.family: root.fontFamily
              font.pixelSize: Math.round(Style.font.title * 1.45)
              font.bold: true

              SequentialAnimation on scale {
                running: root.opened
                loops: Animation.Infinite
                NumberAnimation { to: 1.08; duration: 900; easing.type: Easing.InOutSine }
                NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
              }
            }

            Column {
              id: heroText
              anchors.left: face.right
              anchors.leftMargin: Style.space(14)
              anchors.right: heroActions.left
              anchors.rightMargin: Style.space(6)
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(2)

              Text {
                width: parent.width
                text: "Lv " + root.level.level + " · " + root.level.name
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.title
                font.bold: true
                elide: Text.ElideRight
              }
              Text {
                width: parent.width
                text: (Number(root.status.cups || 0) + " CUPS TODAY · " + Number(root.status.mg || 0) + " MG ACTIVE · "
                       + (root.status.mood ? root.status.mood.name.toUpperCase() : ""))
                color: root.status.overLimit ? root.urgent : root.dim
                font.family: root.fontFamily
                font.pixelSize: Style.font.caption
                font.bold: true
                font.letterSpacing: 1.1
                elide: Text.ElideRight
              }
              Text {
                width: parent.width
                text: root.status.pun || ""
                color: root.foreground
                font.family: root.fontFamily
                font.pixelSize: Style.font.bodySmall
                font.italic: true
                elide: Text.ElideRight
              }
            }

            Row {
              id: heroActions
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              spacing: Style.space(2)

              PanelActionButton {
                iconText: "󰕌"
                tooltipText: "Undo last cup (u)"
                foreground: root.foreground
                fontFamily: root.fontFamily
                enabled: Number(root.status.cups || 0) > 0
                onClicked: root.cmd(["undo"])
              }
              PanelActionButton {
                iconText: "󰙨"
                tooltipText: "Open oma-caffe Studio: recipes (r)"
                foreground: root.foreground
                fontFamily: root.fontFamily
                onClicked: root.window(["studio", "recipes"])
              }
              PanelActionButton {
                iconText: "󰒓"
                tooltipText: "Settings (s)"
                foreground: root.foreground
                fontFamily: root.fontFamily
                onClicked: root.window(["studio", "settings"])
              }
            }
          }

          // ---------- meters ----------
          Meter {
            width: parent.width
            label: "Barista XP"
            value: root.level.progress || 0
            detail: root.level.toNext ? root.level.toNext + " cups to " + root.level.nextName : "max level ✨"
            fillColor: root.accent
          }
          Meter {
            width: parent.width
            label: "Caffeine"
            value: Math.min(1, Number(root.status.mg || 0) / Math.max(1, Number(root.status.dailyLimit || 400)))
            detail: Number(root.status.mg || 0) + " / " + (root.status.dailyLimit || 400) + " mg"
                    + (root.status.sleepSafeAt ? " · sleep-safe " + root.status.sleepSafeAt : " · sleep-safe now")
            fillColor: root.status.overLimit ? root.urgent : root.accent
          }

          // ---------- quick actions ----------
          Flow {
            width: parent.width
            spacing: Style.space(6)

            Button {
              text: "+1 " + (root.status.profileLabel || "cup")
              iconText: root.status.profileIcon || "☕"
              bordered: true
              tooltipText: "Log one (c) · middle-click the bar does this too"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.logCup("")
            }
            Button {
              text: root.locked ? "Lock on" : "Lock"
              iconText: root.locked ? "󰅶" : "󰛊"
              selected: root.locked
              bordered: true
              tooltipText: "Caffeine Lock: keep the screen awake (l)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.toggleLock()
            }
            Button {
              text: "Ambience"
              iconText: "󰎈"
              selected: root.status.ambience === true
              bordered: true
              tooltipText: "Lo-fi café murmur (a)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.cmd(["ambience", "toggle"])
            }
            Button {
              text: "Theme"
              iconText: "󰔎"
              bordered: true
              tooltipText: "Crema Light → Ristretto Dark → Strawberry Latte (t)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.cmd(["theme", "cycle"])
            }
            Button {
              text: "Focus 25"
              iconText: "󰔛"
              bordered: true
              tooltipText: "Pomodoro: coffee break in 25 minutes (f)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.cmd(["break", "pomodoro", "25"])
            }
            Button {
              text: "Break"
              iconText: "󰾪"
              bordered: true
              tooltipText: "Coffee Time, right now (b)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.window(["break", "now"])
            }
            Button {
              text: "Dial-in"
              iconText: "󰄨"
              bordered: true
              tooltipText: "Log a shot: dose, yield, time, taste (d)"
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.window(["studio", "dial"])
            }
          }

          // ---------- today ----------
          PanelSectionHeader {
            width: parent.width
            text: "TODAY"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }
          Text {
            visible: !(root.status.todayCups && root.status.todayCups.length)
            text: "No cups yet — (╯°□°）╯︵ ┻━┻  go make one!"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
          }
          Column {
            width: parent.width
            spacing: Style.space(1)

            Repeater {
              model: (root.status.todayCups || []).slice(0, 6)
              Item {
                required property var modelData
                width: parent.width
                height: Math.max(cupRow.implicitHeight, rm.height)

                Row {
                  id: cupRow
                  anchors.verticalCenter: parent.verticalCenter
                  spacing: Style.space(10)
                  Text { text: modelData.time; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.body }
                  Text { text: modelData.icon; font.pixelSize: Style.font.body }
                  Text { text: modelData.label; color: root.foreground; font.family: root.fontFamily; font.pixelSize: Style.font.body }
                  Text { text: modelData.mg + " mg"; color: root.dim; font.family: root.fontFamily; font.pixelSize: Style.font.body }
                }
                PanelActionButton {
                  id: rm
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  iconText: "󰅖"
                  fontSize: Style.font.body
                  tooltipText: "Remove this cup"
                  foreground: root.foreground
                  fontFamily: root.fontFamily
                  onClicked: root.cmd(["cups", "rm", modelData.id])
                }
              }
            }
          }
          Text {
            visible: (root.status.todayCups || []).length > 6
            text: "+" + ((root.status.todayCups || []).length - 6) + " more · oma-caffe cups"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          // ---------- week ----------
          PanelSectionHeader {
            width: parent.width
            text: "THIS WEEK"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }
          Row {
            id: weekRow
            width: parent.width
            height: Style.space(84)
            spacing: Style.space(6)
            readonly property int peak: Model.weekPeak(root.stats.week)

            Repeater {
              model: root.stats.week || []
              Column {
                required property var modelData
                width: (weekRow.width - weekRow.spacing * 6) / 7
                height: weekRow.height
                spacing: Style.space(2)

                Item {
                  width: parent.width
                  height: parent.height - dayLabel.height - countLabel.height - Style.space(4)
                  Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: parent.width * 0.62
                    height: Math.max(modelData.cups > 0 ? Style.space(4) : 1, parent.height * modelData.cups / weekRow.peak)
                    radius: Style.space(3)
                    color: modelData.today ? root.accent : Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.35)
                    Behavior on height { NumberAnimation { duration: 400; easing.type: Easing.OutBack } }
                  }
                }
                Text {
                  id: countLabel
                  anchors.horizontalCenter: parent.horizontalCenter
                  text: modelData.cups
                  color: root.foreground
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                }
                Text {
                  id: dayLabel
                  anchors.horizontalCenter: parent.horizontalCenter
                  text: modelData.day
                  color: modelData.today ? root.accent : root.dim
                  font.family: root.fontFamily
                  font.pixelSize: Style.font.caption
                  font.bold: modelData.today
                }
              }
            }
          }
          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: "🔥 " + (root.stats.streak || 0) + "-day streak · " + (root.stats.weekCups || 0) + " cups this week ("
                  + (root.stats.avgPerDay || 0) + "/day) · " + (root.stats.topDrinkIcon || "☕") + " fav " + (root.stats.topDrink || "—")
                  + " · " + (root.stats.drinksTried || 0) + " drinks, " + (root.stats.methodsTried || 0) + " methods tried"
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.bodySmall
          }

          // ---------- badges ----------
          PanelSectionHeader {
            width: parent.width
            text: "ACHIEVEMENTS " + Model.unlockedCount(root.status.badges) + "/" + (root.status.badges || []).length
            foreground: root.foreground
            fontFamily: root.fontFamily
          }
          Flow {
            width: parent.width
            spacing: Style.space(6)

            Repeater {
              model: root.status.badges || []
              Text {
                id: badge
                required property var modelData
                text: modelData.unlocked ? modelData.icon : "🔒"
                opacity: modelData.unlocked ? 1 : 0.35
                font.pixelSize: Math.round(Style.font.title * 1.3)

                MouseArea {
                  id: badgeMouse
                  anchors.fill: parent
                  hoverEnabled: true
                }
                PanelToolTip {
                  visible: badgeMouse.containsMouse
                  text: badge.modelData.name + " — " + badge.modelData.desc
                }
              }
            }
          }

          // ---------- recipes ----------
          PanelSectionHeader {
            width: parent.width
            text: "RECIPE OF THE DAY"
            foreground: root.foreground
            fontFamily: root.fontFamily
          }
          Button {
            visible: !!root.status.suggestion
            width: parent.width
            leftAlign: true
            iconText: "󰃭"
            text: root.status.suggestion ? root.status.suggestion.name : ""
            tooltipText: root.status.suggestion ? root.status.suggestion.summary + " — open in Studio" : ""
            foreground: root.foreground
            fontFamily: root.fontFamily
            onClicked: root.window(["studio", "recipes", "--recipe", root.status.suggestion.id])
          }
          Repeater {
            model: root.status.favorites || []
            Button {
              required property var modelData
              width: column.width
              leftAlign: true
              iconText: "󰓎"
              text: modelData.name + (modelData.score !== null ? "  " + modelData.score + "★" : "")
              tooltipText: modelData.summary
              foreground: root.foreground
              fontFamily: root.fontFamily
              onClicked: root.window(["studio", "recipes", "--recipe", modelData.id])
            }
          }

          // ---------- footer ----------
          Text {
            width: parent.width
            wrapMode: Text.WordWrap
            text: "󰆘 " + (root.status.bean || "") + " · " + (root.status.grind || "")
                  + (root.status.nextBreakText ? "   ·   󰾪 next break " + root.status.nextBreakText : "")
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
          }
          Text {
            width: parent.width
            text: "⚡ Powered by caffeine and questionable life choices.\nc cup · u undo · l lock · a ambience · t theme · f focus · b break · d dial · r recipes · s settings"
            color: root.dim
            font.family: root.fontFamily
            font.pixelSize: Style.font.caption
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
          }
        }
      }
    }
  }

  // A labelled progress track.
  component Meter: Column {
    id: meter
    property string label: ""
    property string detail: ""
    property real value: 0
    property color fillColor: root.accent
    spacing: Style.space(3)

    Item {
      width: parent.width
      height: meterLabel.implicitHeight
      Text {
        id: meterLabel
        text: meter.label.toUpperCase()
        color: root.dim
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
        font.bold: true
        font.letterSpacing: 1.1
      }
      Text {
        anchors.right: parent.right
        text: meter.detail
        color: root.foreground
        font.family: root.fontFamily
        font.pixelSize: Style.font.caption
      }
    }
    Rectangle {
      width: parent.width
      height: Style.space(6)
      radius: height / 2
      color: Qt.rgba(root.foreground.r, root.foreground.g, root.foreground.b, 0.12)
      Rectangle {
        width: parent.width * Math.max(0, Math.min(1, meter.value))
        height: parent.height
        radius: parent.radius
        color: meter.fillColor
        Behavior on width { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }
      }
    }
  }

  // ---- processes ----------------------------------------------------------

  Process {
    id: statusProc
    command: [root.cli, "status", "--json"]
    running: false
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        try {
          root.status = JSON.parse(text)
        } catch (e) {
          // Keep the last good status; the next tick tries again.
        }
      }
    }
  }

  Process {
    id: actionProc
    environment: ({ "OMA_CAFFE_FROM_BAR": "1" })
    onExited: {
      if (root.queue.length > 0) root.pump()
      else root.broadcast("refresh")
    }
  }

  Process {
    id: profileProc
    environment: ({ "OMA_CAFFE_FROM_BAR": "1" })
    onExited: {
      var pending = root.pendingProfileSteps
      root.pendingProfileSteps = 0
      if (pending !== 0) root.stepProfile(pending)
      else root.broadcast("refresh")
    }
  }

  Timer {
    interval: root.refreshIntervalSec * 1000
    running: true
    repeat: true
    onTriggered: root.refresh()
  }

  // Same relay as BarWidget.broadcast(): an IPC target reaches one instance,
  // and there is one bar per monitor.
  function broadcast(method) {
    var items = bar && typeof bar.moduleWidgets === "function" ? bar.moduleWidgets(moduleName) : [root]
    for (var i = 0; i < items.length; i++)
      if (items[i] && typeof items[i][method] === "function") items[i][method]()
  }

  // `oma-caffe` calls refresh after CLI changes; toggle opens the panel from
  // a keybinding: omarchy-shell rohirik.oma-caffe toggle
  IpcHandler {
    target: "rohirik.oma-caffe"

    function refresh(): void { root.broadcast("refresh") }
    function toggle(): void { root.toggle() }
    function open(): void { root.open() }
    function close(): void { root.close() }
  }
}
