// Five stars; click to pick when editable.
import QtQuick
import qs.Commons

Row {
  id: stars
  property var s
  property int value: 0
  property bool editable: false
  property int size: Style.font.title + 4
  signal picked(int value)
  spacing: 2

  Repeater {
    model: 5
    Text {
      required property int index
      text: index < stars.value ? "★" : "☆"
      color: stars.s ? (index < stars.value ? stars.s.accent : stars.s.dim) : "gray"
      font.pixelSize: stars.size
      MouseArea {
        anchors.fill: parent
        enabled: stars.editable
        cursorShape: stars.editable ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: { stars.value = index + 1; stars.picked(index + 1) }
      }
    }
  }
}
