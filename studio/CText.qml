// Body text in the studio palette.
import QtQuick
import qs.Commons

Text {
  property var s
  property bool muted: false
  color: s ? (muted ? s.dim : s.fg) : "gray"
  font.family: s ? s.font : ""
  font.pixelSize: Style.font.body
  wrapMode: Text.WordWrap
}
