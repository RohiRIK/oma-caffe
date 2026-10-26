// Stats: barista level, the week as a chart, totals and every badge.

import QtQuick
import QtQuick.Controls
import qs.Commons
import qs.Ui
import "../Model.js" as Model

Flickable {
  id: page
  property var s
  readonly property var st: s.status.stats || ({ week: [] })
  readonly property var lv: s.status.level || ({ level: 1, name: "", progress: 0 })

  contentHeight: col.implicitHeight + Style.space(48)
  clip: true
  boundsBehavior: Flickable.StopAtBounds
  ScrollBar.vertical: ScrollBar {}

  Column {
    id: col
    x: Style.space(28)
    y: Style.space(24)
    width: page.width - Style.space(56)
    spacing: Style.space(18)

    Row {
      spacing: Style.space(18)
      Text { text: page.s.status.mood ? page.s.status.mood.face : ""; color: page.s.accent; font.family: page.s.font; font.pixelSize: 40; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
      Column {
        spacing: 4
        Text { text: "Lv " + page.lv.level + " · " + page.lv.name; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.display; font.bold: true }
        CText { s: page.s; muted: true; text: page.lv.toNext ? page.lv.toNext + " cups to " + page.lv.nextName : "Max level — legend status ✨" }
      }
    }
    Rectangle {
      width: parent.width
      height: 12
      radius: 6
      color: page.s.line
      Rectangle { width: parent.width * (page.lv.progress || 0); height: parent.height; radius: 6; color: page.s.accent }
    }

    Grid {
      width: parent.width
      columns: 4
      columnSpacing: Style.space(12)
      rowSpacing: Style.space(12)
      Repeater {
        model: [
          { k: "🔥", v: (page.st.streak || 0) + " days", l: "streak" },
          { k: "☕", v: page.st.weekCups || 0, l: "cups this week" },
          { k: "📈", v: page.st.avgPerDay || 0, l: "per day" },
          { k: "🏆", v: page.st.total || 0, l: "all-time cups" },
          { k: page.st.topDrinkIcon || "☕", v: page.st.topDrink || "—", l: "favourite drink" },
          { k: "🧭", v: page.st.drinksTried || 0, l: "drinks tried" },
          { k: "⚗️", v: page.st.methodsTried || 0, l: "methods" },
          { k: "⏰", v: page.st.peakHour || "—", l: "peak hour" }
        ]
        Card {
          required property var modelData
          s: page.s
          width: (col.width - Style.space(12) * 3) / 4
          Text { text: modelData.k; font.pixelSize: 26 }
          Text { text: String(modelData.v); color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.title + 4; font.bold: true; elide: Text.ElideRight; width: parent.width }
          CText { s: page.s; muted: true; text: modelData.l; font.pixelSize: Style.font.caption }
        }
      }
    }

    Card {
      s: page.s
      width: parent.width
      title: "This week"
      Row {
        id: chart
        width: parent.width
        height: 220
        spacing: Style.space(14)
        readonly property int peak: Model.weekPeak(page.st.week)
        Repeater {
          model: page.st.week || []
          Column {
            required property var modelData
            width: (chart.width - chart.spacing * 6) / 7
            height: chart.height
            spacing: 4
            Item {
              width: parent.width
              height: parent.height - 44
              Rectangle {
                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width * 0.6
                height: Math.max(modelData.cups > 0 ? 6 : 2, parent.height * modelData.cups / chart.peak)
                radius: 6
                color: modelData.today ? page.s.accent : Qt.rgba(page.s.fg.r, page.s.fg.g, page.s.fg.b, 0.3)
                Behavior on height { NumberAnimation { duration: 500; easing.type: Easing.OutBack } }
              }
            }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.cups + " · " + modelData.mg + "mg"; color: page.s.fg; font.family: page.s.font; font.pixelSize: Style.font.caption }
            Text { anchors.horizontalCenter: parent.horizontalCenter; text: modelData.day; color: modelData.today ? page.s.accent : page.s.dim; font.family: page.s.font; font.pixelSize: Style.font.body; font.bold: modelData.today }
          }
        }
      }
    }

    Card {
      s: page.s
      width: parent.width
      title: "Achievements " + Model.unlockedCount(page.s.status.badges) + " / " + (page.s.status.badges || []).length
      Grid {
        width: parent.width
        columns: 2
        columnSpacing: Style.space(16)
        rowSpacing: Style.space(10)
        Repeater {
          model: page.s.status.badges || []
          Row {
            required property var modelData
            width: (col.width - Style.space(48)) / 2
            spacing: Style.space(12)
            opacity: modelData.unlocked ? 1 : 0.45
            Text { text: modelData.unlocked ? modelData.icon : "🔒"; font.pixelSize: 30 }
            Column {
              CText { s: page.s; text: modelData.name; font.bold: true }
              CText { s: page.s; muted: true; text: modelData.desc; font.pixelSize: Style.font.bodySmall }
            }
          }
        }
      }
    }
  }
}
