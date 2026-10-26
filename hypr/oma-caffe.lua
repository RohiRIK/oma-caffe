-- oma-caffe: blur behind the Coffee Time break overlay.
-- (oma-caffe's terminal windows use the TUI.float app-id, which Omarchy
-- already floats.) Installed by oma-caffe/install.sh; uninstall.sh removes
-- the require line from ~/.config/hypr/hyprland.lua.

hl.layer_rule({ match = { namespace = "oma-caffe-break" }, blur = true, ignore_alpha = 0.2 })
