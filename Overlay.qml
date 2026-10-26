// rohirik.oma-caffe overlay entry. The shell gives a plugin one overlay
// loader, so this routes summons: {"view":"studio", ...} opens the Studio
// window, anything else is a Coffee Time break. The loader stays alive
// until both are closed.

import QtQuick
import Quickshell
import "studio"

Item {
  id: root

  property var shell: null
  property var manifest: null
  readonly property bool opened: brk.opened || studio.opened
  readonly property string cli: Qt.resolvedUrl("bin/oma-caffe").toString().replace("file://", "")

  function open(payloadJson) {
    var p = ({})
    try { p = JSON.parse(payloadJson || "{}") } catch (e) { p = ({}) }
    if (p.view === "studio") studio.open(p)
    else brk.open(payloadJson)
  }

  // From the host (shell.hide): close everything.
  function close() {
    brk.close()
    studio.close()
  }

  function settle() {
    if (!brk.opened && !studio.opened && root.shell && typeof root.shell.hide === "function")
      root.shell.hide((root.manifest && root.manifest.id) || "rohirik.oma-caffe")
  }

  BreakOverlay {
    id: brk
    onDismissed: root.settle()
    onRecipeRequested: function(id) { studio.open({ page: "brew", recipe: id }) }
  }

  Studio {
    id: studio
    cli: root.cli
    onClosed: root.settle()
  }
}
