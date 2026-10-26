// rohirik.oma-caffe -- the full-screen "Coffee Time" break overlay.
//
// Summoned by `oma-caffe tick` (or `oma-caffe break now`) through
// `omarchy-shell shell summon rohirik.oma-caffe '<payload>'`. The payload
// carries the copy (it switches to "Hydrate or Decaf" after the cutoff hour)
// and the suggested recipe of the day. Covers the focused monitor with a
// translucent scrim (Hyprland blurs it via the oma-caffe layer rule), draws
// a big cup with rising steam, and maps Enter / R / S / Esc onto the CLI.

import QtQuick
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "Model.js" as Model

Item {
  id: root

  property bool opened: false
  signal dismissed()
  signal recipeRequested(string id)
  property var payload: ({})

  readonly property string cli: Qt.resolvedUrl("bin/oma-caffe").toString().replace("file://", "")
  readonly property bool decaf: payload.mode === "decaf"
  readonly property color background: Commons.Color.menu.background
  readonly property color foreground: Commons.Color.menu.text
  readonly property color accent: Commons.Color.accent
  readonly property color muted: Commons.Color.muted
  readonly property string fontFamily: Style.font.menuFamily
  property real t: 0

  function open(payloadJson) {
    var p = ({})
    try { p = JSON.parse(payloadJson || "{}") } catch (e) { p = ({}) }
    if (!p.headline) p.headline = "Time to dial in a shot"
    root.payload = p
    root.opened = true
    Qt.callLater(function() { keys.forceActiveFocus() })
  }

  function close() {
    root.opened = false
  }

  function dismiss() {
    root.opened = false
    root.dismissed()
  }

  function act(action) {
    if (action === "recipe" && root.payload.recipe && root.payload.recipe.id) {
      root.recipeRequested(root.payload.recipe.id)
      root.dismiss()
      return
    }
    var argv = Model.overlayCommand(action, root.cli, root.payload)
    if (argv.length === 0) return
    Quickshell.execDetached(argv)
    root.dismiss()
  }

  function focusedScreen() {
    var name = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
    var screens = Quickshell.screens
    for (var i = 0; i < screens.length; i++)
      if (screens[i].name === name) return screens[i]
    return screens.length > 0 ? screens[0] : null
  }

  PanelWindow {
    id: panel
    visible: root.opened
    screen: root.focusedScreen()
    anchors { top: true; bottom: true; left: true; right: true }
    color: "transparent"
    WlrLayershell.namespace: "oma-caffe-break"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive
    exclusionMode: ExclusionMode.Ignore

    Rectangle {
      id: scrim
      anchors.fill: parent
      color: Qt.rgba(root.background.r, root.background.g, root.background.b, 0.78)
      opacity: root.opened ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
    }

    // Clicking the backdrop is a skip, same as Esc.
    MouseArea {
      anchors.fill: parent
      onClicked: root.act("skip")
    }

    Item {
      id: keys
      anchors.fill: parent
      focus: true
      Keys.onPressed: function(event) {
        var name = event.key === Qt.Key_Return ? "Return"
          : event.key === Qt.Key_Enter ? "Enter"
          : event.key === Qt.Key_Escape ? "Escape" : ""
        var action = Model.overlayAction(name, event.text)
        if (action) {
          root.act(action)
          event.accepted = true
        }
      }
    }

    Timer {
      interval: 33
      running: root.opened
      repeat: true
      onTriggered: { root.t += 0.033; cupCanvas.requestPaint() }
    }

    Column {
      anchors.centerIn: parent
      spacing: Style.space(18)
      width: Math.min(parent.width - Style.space(64), Style.space(720))

      // ---- the big cup -------------------------------------------------
      Canvas {
        id: cupCanvas
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(panel.height * 0.36, Style.space(360))
        height: width
        renderStrategy: Canvas.Cooperative

        onPaint: {
          var ctx = getContext("2d")
          var w = width, h = height
          ctx.reset()
          var fg = root.foreground, acc = root.accent

          // Steam: three ribbons swaying and fading as they rise.
          for (var i = 0; i < 3; i++) {
            var baseX = w * (0.38 + i * 0.12)
            ctx.beginPath()
            for (var s = 0; s <= 24; s++) {
              var p = s / 24
              var y = h * 0.40 - p * h * 0.36
              var x = baseX + Model.steamSway(i, root.t, p) * w * 0.035
              if (s === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y)
            }
            var grad = ctx.createLinearGradient(0, h * 0.40, 0, h * 0.04)
            grad.addColorStop(0, Qt.rgba(fg.r, fg.g, fg.b, 0.55))
            grad.addColorStop(1, Qt.rgba(fg.r, fg.g, fg.b, 0))
            ctx.strokeStyle = grad
            ctx.lineWidth = Math.max(2, w * 0.014)
            ctx.lineCap = "round"
            ctx.stroke()
          }

          // Saucer.
          ctx.beginPath()
          ctx.ellipse(w * 0.12, h * 0.84, w * 0.76, h * 0.10)
          ctx.fillStyle = Qt.rgba(fg.r, fg.g, fg.b, 0.10)
          ctx.fill()
          ctx.lineWidth = Math.max(2, w * 0.012)
          ctx.strokeStyle = Qt.rgba(fg.r, fg.g, fg.b, 0.55)
          ctx.stroke()

          // Handle.
          ctx.beginPath()
          ctx.arc(w * 0.76, h * 0.60, w * 0.09, -Math.PI * 0.45, Math.PI * 0.45, false)
          ctx.lineWidth = Math.max(3, w * 0.035)
          ctx.strokeStyle = fg
          ctx.stroke()

          // Body: straight walls tapering into a rounded base.
          ctx.beginPath()
          ctx.moveTo(w * 0.24, h * 0.44)
          ctx.lineTo(w * 0.76, h * 0.44)
          ctx.bezierCurveTo(w * 0.76, h * 0.74, w * 0.68, h * 0.86, w * 0.50, h * 0.86)
          ctx.bezierCurveTo(w * 0.32, h * 0.86, w * 0.24, h * 0.74, w * 0.24, h * 0.44)
          ctx.closePath()
          ctx.fillStyle = fg
          ctx.fill()

          // Crema: an amber ellipse with a lighter heart.
          ctx.beginPath()
          ctx.ellipse(w * 0.255, h * 0.415, w * 0.49, h * 0.06)
          var crema = ctx.createRadialGradient(w * 0.5, h * 0.445, 1, w * 0.5, h * 0.445, w * 0.25)
          crema.addColorStop(0, Qt.lighter(acc, 1.35))
          crema.addColorStop(1, acc)
          ctx.fillStyle = crema
          ctx.fill()
          ctx.lineWidth = Math.max(2, w * 0.012)
          ctx.strokeStyle = fg
          ctx.stroke()
        }
      }

      // ---- copy --------------------------------------------------------
      Text {
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        text: root.payload.headline || ""
        color: root.decaf ? root.accent : root.foreground
        font.family: root.fontFamily
        font.pixelSize: Math.round(Style.font.display * 1.6)
        font.bold: true
        wrapMode: Text.WordWrap
      }

      Text {
        width: parent.width
        horizontalAlignment: Text.AlignHCenter
        text: root.payload.subline || ""
        color: root.foreground
        opacity: 0.85
        font.family: root.fontFamily
        font.pixelSize: Style.font.title
        wrapMode: Text.WordWrap
      }

      // ---- recipe of the day ------------------------------------------
      BorderSurface {
        id: card
        visible: !!root.payload.recipe
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width, Style.space(520))
        height: cardColumn.implicitHeight + Style.spacing.panelPadding * 2
        radius: Style.cornerRadius
        color: Qt.rgba(root.background.r, root.background.g, root.background.b, 0.92)
        borderSpec: Border.surfaceSpec("menu", "border", root.accent, Math.max(1, Style.space(2)))

        MouseArea { anchors.fill: parent; onClicked: root.act("recipe") }

        Column {
          id: cardColumn
          anchors.fill: parent
          anchors.margins: Style.spacing.panelPadding
          spacing: Style.space(4)

          Text {
            text: (root.decaf ? "Suggested (go easy): " : "Suggested Recipe of the Day: ") + (root.payload.recipe ? root.payload.recipe.name : "")
            color: root.accent
            font.family: root.fontFamily
            font.pixelSize: Style.font.title
            font.bold: true
            width: parent.width
            elide: Text.ElideRight
          }
          Text {
            text: root.payload.recipe ? root.payload.recipe.summary : ""
            color: root.foreground
            font.family: root.fontFamily
            font.pixelSize: Style.font.body
            width: parent.width
            elide: Text.ElideRight
          }
          Repeater {
            model: root.payload.recipe ? root.payload.recipe.steps : []
            Text {
              required property string modelData
              text: modelData
              color: root.foreground
              opacity: 0.8
              font.family: root.fontFamily
              font.pixelSize: Style.font.bodySmall
              width: cardColumn.width
              elide: Text.ElideRight
            }
          }
        }
      }

      // ---- actions -----------------------------------------------------
      Row {
        anchors.horizontalCenter: parent.horizontalCenter
        spacing: Style.space(10)

        Repeater {
          model: [
            { key: "Enter", label: root.payload.enterLabel || "Log Cup & Start Break", action: "enter" },
            { key: "R", label: "Try Suggested Recipe", action: "recipe" },
            { key: "S", label: "Snooze " + (root.payload.snoozeMin || 15) + "m", action: "snooze" },
            { key: "Esc", label: "Skip", action: "skip" }
          ]

          BorderSurface {
            id: chipCard
            required property var modelData
            visible: modelData.action !== "recipe" || !!root.payload.recipe
            width: chip.implicitWidth + Style.spacing.controlPaddingX * 2
            height: chip.implicitHeight + Style.spacing.controlPaddingY * 2
            radius: Style.cornerRadius
            color: chipMouse.containsMouse ? Qt.rgba(root.accent.r, root.accent.g, root.accent.b, 0.18) : "transparent"
            borderSpec: Border.surfaceSpec("menu", "border", root.foreground, 1)

            Text {
              id: chip
              anchors.centerIn: parent
              textFormat: Text.StyledText
              text: "<b>[" + modelData.key + "]</b> " + modelData.label
              color: root.foreground
              font.family: root.fontFamily
              font.pixelSize: Style.font.body
            }

            MouseArea {
              id: chipMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: root.act(chipCard.modelData.action)
            }
          }
        }
      }
    }
  }
}
