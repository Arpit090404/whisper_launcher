from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from ..assets import asset_path
def make_tray(controller, app):
    icon=QIcon(str(asset_path("wispr-launcher-logo.png")))
    app.setWindowIcon(icon)
    tray=QSystemTrayIcon(icon,app); tray.setToolTip("VoiceLaunch — ready"); menu=QMenu(); status=menu.addAction("Ready"); status.setEnabled(False); pause=menu.addAction("Pause hotkey"); pause.setCheckable(True); pause.toggled.connect(lambda checked: keyboard_remove(controller) if checked else controller.register()); menu.addSeparator(); menu.addAction("Refresh app index"); reload_action=menu.addAction("Reload config"); reload_action.triggered.connect(lambda: controller.reload_config()); menu.addAction("Open config folder"); menu.addAction("Open history log"); start=menu.addAction("Start with Windows"); start.setCheckable(True); menu.addSeparator(); quit_action=menu.addAction("Quit"); quit_action.triggered.connect(app.quit); tray.setContextMenu(menu); tray.show(); return tray
def keyboard_remove(c):
    import keyboard
    if c.hotkey: keyboard.remove_hotkey(c.hotkey); c.hotkey=None
