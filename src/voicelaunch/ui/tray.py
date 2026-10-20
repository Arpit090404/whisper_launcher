"""Cassette's system-tray integration and compact activity window."""
from __future__ import annotations

import os
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ..assets import asset_path
from ..paths import CONFIG_DIR
from .dashboard import Dashboard

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "Cassette"


def make_tray(controller, app, history):
    icon = QIcon(str(asset_path("wispr-launcher-logo.png")))
    app.setApplicationName("Cassette")
    app.setWindowIcon(icon)
    dashboard = Dashboard(history)
    tray = QSystemTrayIcon(icon, app)
    tray.setToolTip("Cassette — ready")
    menu = QMenu()
    status = menu.addAction("Ready")
    status.setEnabled(False)
    pause = menu.addAction("Pause hotkey")
    pause.setCheckable(True)
    pause.toggled.connect(lambda checked: keyboard_remove(controller) if checked else controller.register())
    menu.addSeparator()
    refresh = menu.addAction("Refresh app index")
    refresh.triggered.connect(controller.refresh_app_index)
    reload_action = menu.addAction("Reload config")
    reload_action.triggered.connect(controller.reload_config)
    open_config = menu.addAction("Open config folder")
    open_config.triggered.connect(lambda: os.startfile(str(CONFIG_DIR)))
    open_history = menu.addAction("Open history")
    open_history.triggered.connect(lambda: show_dashboard(dashboard))
    start = menu.addAction("Start with Windows")
    start.setCheckable(True)
    start.setChecked(starts_with_windows())
    start.toggled.connect(set_start_with_windows)
    menu.addSeparator()
    quit_action = menu.addAction("Quit Cassette")
    quit_action.triggered.connect(app.quit)
    tray.setContextMenu(menu)
    tray.activated.connect(lambda reason: show_dashboard(dashboard) if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    tray.show()
    tray.dashboard = dashboard  # retain the top-level window
    return tray


def show_dashboard(dashboard: Dashboard) -> None:
    dashboard.refresh()
    dashboard.show()
    dashboard.raise_()
    dashboard.activateWindow()


def keyboard_remove(controller) -> None:
    import keyboard
    if controller.hotkey:
        keyboard.remove_hotkey(controller.hotkey)
        controller.hotkey = None
    if controller.dictation_hook:
        keyboard.unhook(controller.dictation_hook)
        controller.dictation_hook = None


def starts_with_windows() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, RUN_VALUE)
        return True
    except (FileNotFoundError, OSError):
        return False


def set_start_with_windows(enabled: bool) -> None:
    """Register the frozen executable (or Python module while developing)."""
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            if enabled:
                command = f'"{sys.executable}"' if getattr(sys, "frozen", False) else f'"{sys.executable}" -m voicelaunch'
                winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
            else:
                try:
                    winreg.DeleteValue(key, RUN_VALUE)
                except FileNotFoundError:
                    pass
    except OSError:
        pass
