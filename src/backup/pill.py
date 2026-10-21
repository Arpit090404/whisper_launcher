"""Cassette's acrylic standby pill and active dot-sphere overlay."""
from __future__ import annotations

import math
import time

import numpy as np
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QLinearGradient, QPainter, QPainterPath, QRegion
from PySide6.QtWidgets import QApplication, QWidget

from ..audio import rms_to_level
from ..winapi import enable_acrylic, harden_overlay


# The overlay uses real size changes so its acrylic backdrop matches the visible form.
STANDBY_W, STANDBY_H = 48.0, 13.0
ACTIVE_SIZE = 75.0
ACTIVE_CORNER = 22.0
SPHERE_RADIUS = 23.5
N_DOTS = 320
TILT = 0.40
BACK_ALPHA = 0.16
ANCHOR_FROM_BOTTOM = 70

_MODES = {
    "hidden":     dict(width=STANDBY_W, height=STANDBY_H, sphere=0.0, opacity=0.0, spin=0.30),
    "standby":    dict(width=STANDBY_W, height=STANDBY_H, sphere=0.0, opacity=1.0, spin=0.30),
    "listening":  dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=0.55),
    "dictating":  dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=0.70),
    "processing": dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=2.40),
    "result":     dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=0.55),
}


def _fibonacci_sphere(count: int) -> np.ndarray:
    index = np.arange(count)
    y = 1.0 - 2.0 * (index + 0.5) / count
    radius = np.sqrt(1.0 - y * y)
    theta = math.pi * (3.0 - math.sqrt(5.0)) * index
    return np.stack([radius * np.cos(theta), y, radius * np.sin(theta)], axis=1)


_POINTS = _fibonacci_sphere(N_DOTS)


def _chase(current: float, target: float, rate: float, dt: float) -> float:
    return current + (target - current) * (1.0 - math.exp(-rate * dt))


class PillWidget(QWidget):
    """One click-through window that morphs between the two reference shapes."""

    def __init__(self, config: dict):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                 Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput |
                 Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)
        super().__init__(None, flags)
        self.config = config
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.resize(round(STANDBY_W), round(STANDBY_H))

        self.level_source = lambda: 0.0
        self.mode = "hidden"
        self.error = False
        self._standby_enabled = False
        self._last = time.monotonic()
        self._phase = 0.0
        self._angle = 0.0
        self._width, self._height = STANDBY_W, STANDBY_H
        self._opacity = 0.0
        self._sphere = 0.0
        self._spin = _MODES["standby"]["spin"]
        self._level = 0.0

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    def show_mode(self, mode: str, text: str = "", error: bool = False):
        """Show the active acrylic tile. Dictation and listening stay white."""
        if mode == "error":
            mode, error = "result", True
        if mode not in ("listening", "dictating", "processing", "result"):
            return
        self.error = error
        self._set_mode(mode)

    def show_standby(self):
        if not self.config.get("ui", {}).get("show_standby_icon", True):
            return
        self._standby_enabled = True
        if self.mode in ("hidden", "standby"):
            self._set_mode("standby")

    def hide_standby(self):
        self._standby_enabled = False
        if self.mode == "standby":
            self._set_mode("hidden")

    def fade_hide(self):
        self._set_mode("standby" if self._standby_enabled else "hidden")

    def _set_mode(self, mode: str):
        visible = self.isVisible()
        self.mode = mode
        if mode == "hidden" and not visible:
            return
        if not visible:
            self._width, self._height = STANDBY_W, STANDBY_H
            self._last = time.monotonic()
            self._place()
            self.show()
            harden_overlay(int(self.winId()))
            enable_acrylic(int(self.winId()), 0x302A2A2A)
        if not self.timer.isActive():
            self.timer.start()

    def _place(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geometry = screen.availableGeometry()
        width, height = round(self._width), round(self._height)
        self.setGeometry(geometry.center().x() - width // 2,
                         geometry.bottom() - ANCHOR_FROM_BOTTOM - height,
                         width, height)
        # Acrylic is applied to the full native window; mask it to the same
        # rounded outline we paint so it can never appear as a square block.
        corner = min(height / 2.0, ACTIVE_CORNER * (height / ACTIVE_SIZE))
        path = QPainterPath()
        path.addRoundedRect(0, 0, width, height, corner, corner)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last)
        self._last = now
        target = _MODES[self.mode]
        self._phase += dt
        level = rms_to_level(self.level_source()) if self.mode in ("listening", "dictating") else 0.0
        self._level = _chase(self._level, level, 25.0 if level > self._level else 8.0, dt)
        self._width = _chase(self._width, target["width"], 13.0, dt)
        self._height = _chase(self._height, target["height"], 13.0, dt)
        self._sphere = _chase(self._sphere, target["sphere"], 15.0, dt)
        self._opacity = _chase(self._opacity, target["opacity"], 18.0, dt)
        self._spin = _chase(self._spin, target["spin"], 4.0, dt)
        self._angle = (self._angle + self._spin * dt) % (2.0 * math.pi)
        self._place()

        if self.mode == "hidden" and self._opacity < 0.01:
            self._opacity = 0.0
            self.timer.stop()
            self.hide()
            return

        settled = (abs(self._width - target["width"]) < 0.1 and
                   abs(self._height - target["height"]) < 0.1 and
                   abs(self._sphere - target["sphere"]) < 0.01)
        interval = 33 if self.mode == "standby" and settled else 16
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.update()

    def paintEvent(self, _):
        if self._opacity <= 0.003:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        width, height = self.width(), self.height()
        corner = min(height / 2.0, ACTIVE_CORNER * (height / ACTIVE_SIZE))

        # Keep the tint thin enough for the native blur to show through. A
        # single filled shape also avoids accumulating opacity across layers.
        surface = QLinearGradient(0, 0, width, height)
        surface.setColorAt(0, QColor(48, 50, 54, int(34 * self._opacity)))
        surface.setColorAt(1, QColor(30, 32, 36, int(24 * self._opacity)))
        painter.setBrush(surface)
        painter.drawRoundedRect(0.5, 0.5, width - 1, height - 1, corner, corner)
        border = QColor(255, 255, 255, int(175 * self._opacity))
        painter.setPen(border)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(0.75, 0.75, width - 1.5, height - 1.5,
                                max(0, corner - 0.75), max(0, corner - 0.75))
        painter.setPen(Qt.PenStyle.NoPen)

        if self._sphere < 0.01:
            return
        center_x, center_y = width / 2.0, height / 2.0
        ca, sa = math.cos(self._angle), math.sin(self._angle)
        ct, st = math.cos(TILT), math.sin(TILT)
        px, py, pz = _POINTS[:, 0], _POINTS[:, 1], _POINTS[:, 2]
        x1 = px * ca + pz * sa
        z1 = -px * sa + pz * ca
        y2 = py * ct - z1 * st
        z2 = py * st + z1 * ct
        order = np.argsort(z2).tolist()
        radius = SPHERE_RADIUS * self._sphere * (1.0 + 0.12 * self._level)
        x1, y2, z2 = x1.tolist(), y2.tolist(), z2.tolist()
        for index in order:
            depth = (z2[index] + 1.0) * 0.5
            alpha = (BACK_ALPHA + (1.0 - BACK_ALPHA) * depth ** 1.4) * self._opacity * self._sphere
            pulse = 1.0 + 0.08 * self._level * math.sin(self._phase * 7.0 + index * 1.7)
            dot = (0.61 + 1.0 * depth) * self._sphere
            color = QColor("#FF6B63") if self.error else QColor("#FFFFFF")
            color.setAlpha(int(255 * alpha))
            painter.setBrush(color)
            painter.drawEllipse(QPointF(center_x + x1[index] * radius * pulse,
                                        center_y + y2[index] * radius * pulse), dot / 2, dot / 2)
