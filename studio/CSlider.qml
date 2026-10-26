// A labelled slider in the studio palette: label left, live value right.
import QtQuick
import qs.Commons
import qs.Ui

Column {
  id: sl
  property var s
  property string label: ""
  property string suffix: ""
  property real value: 0
  property real from: 0
  property real to: 1
  property real step: 1
  property int decimals: 0
  signal released(real value)
  spacing: Style.space(4)

  Item {
    width: parent.width
    height: lbl.implicitHeight
    Text { id: lbl; text: sl.label; color: sl.s.fg; font.family: sl.s.font; font.pixelSize: Style.font.body }
    Text {
      anchors.right: parent.right
      text: Number(slider.liveValue).toFixed(sl.decimals) + sl.suffix
      color: sl.s.accent
      font.family: sl.s.font
      font.pixelSize: Style.font.body
      font.bold: true
    }
  }
  PanelSlider {
    id: slider
    width: parent.width
    value: sl.value
    minimum: sl.from
    maximum: sl.to
    step: sl.step
    trackColor: sl.s.line
    fillColor: sl.s.accent
    knobColor: sl.s.accent
    onReleased: function(v) { sl.released(v) }
  }
}
