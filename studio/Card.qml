// A soft panel with an optional small-caps title.
import QtQuick
import qs.Commons

Rectangle {
  id: card
  property var s
  property string title: ""
  default property alias content: col.data
  readonly property int pad: Style.space(16)

  radius: Style.cornerRadius + 4
  color: s ? s.wash : "transparent"
  border.color: s ? s.line : "transparent"
  border.width: 1
  implicitHeight: col.implicitHeight + pad * 2

  Column {
    id: col
    x: card.pad
    y: card.pad
    width: card.width - card.pad * 2
    spacing: Style.space(10)

    Text {
      visible: card.title !== ""
      text: card.title.toUpperCase()
      color: card.s ? card.s.dim : "gray"
      font.family: card.s ? card.s.font : ""
      font.pixelSize: Style.font.caption
      font.bold: true
      font.letterSpacing: 1.3
    }
  }
}
