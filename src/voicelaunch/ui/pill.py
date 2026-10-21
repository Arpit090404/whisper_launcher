"""Cassette's translucent standby pill and active dot-sphere overlay."""
from __future__ import annotations

import math
import time

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QCursor, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QWidget

from ..audio import rms_to_level
from ..winapi import harden_overlay


# Compact, Wispr-Flow-like sizing: a hairline pill at rest, a small orb when active.
STANDBY_W, STANDBY_H = 36.0, 9.0
ACTIVE_SIZE = 54.0
ACTIVE_CORNER = 20.0
SPHERE_RADIUS = 16.5
N_DOTS = 240
TILT = 0.40
BACK_ALPHA = 0.14
ANCHOR_FROM_BOTTOM = 44

_MODES = {
    "hidden":     dict(width=STANDBY_W, height=STANDBY_H, sphere=0.0, opacity=0.0, spin=0.30),
    "standby":    dict(width=STANDBY_W, height=STANDBY_H, sphere=0.0, opacity=1.0, spin=0.30),
    "listening":  dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=0.55),
    "dictating":  dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=0.70),
    "processing": dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=2.40),
    "result":     dict(width=ACTIVE_SIZE, height=ACTIVE_SIZE, sphere=1.0, opacity=1.0, spin=0.55),
}

# Per-property settle times (seconds). Critically damped: eases in and out, no overshoot.
_SIZE_TIME = 0.11
_SPHERE_TIME = 0.10
_SPIN_TIME = 0.25


def _fibonacci_sphere(count: int) -> np.ndarray:
    index = np.arange(count)
    y = 1.0 - 2.0 * (index + 0.5) / count
    radius = np.sqrt(1.0 - y * y)
    theta = math.pi * (3.0 - math.sqrt(5.0)) * index
    return np.stack([radius * np.cos(theta), y, radius * np.sin(theta)], axis=1)


_POINTS = _fibonacci_sphere(N_DOTS)
_SHIMMER = np.arange(N_DOTS) * 1.7


def _chase(current: float, target: float, rate: float, dt: float) -> float:
    return current + (target - current) * (1.0 - math.exp(-rate * dt))


class _Smooth:
    """Critically damped spring: starts and stops gently instead of snapping."""

    __slots__ = ("value", "vel")

    def __init__(self, value: float):
        self.value = value
        self.vel = 0.0

    def update(self, target: float, smooth_time: float, dt: float) -> float:
        omega = 2.0 / smooth_time
        x = omega * dt
        decay = 1.0 / (1.0 + x + 0.48 * x * x + 0.235 * x * x * x)
        change = self.value - target
        temp = (self.vel + omega * change) * dt
        self.vel = (self.vel - omega * temp) * decay
        self.value = target + (change + temp) * decay
        return self.value


def _corner(height: float) -> float:
    return min(height / 2.0, ACTIVE_CORNER)


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
        self._w = _Smooth(STANDBY_W)
        self._h = _Smooth(STANDBY_H)
        self._s = _Smooth(0.0)
        self._sp = _Smooth(_MODES["standby"]["spin"])
        self._width, self._height = STANDBY_W, STANDBY_H
        self._sphere = 0.0
        self._spin = _MODES["standby"]["spin"]
        self._opacity = 0.0
        self._level = 0.0
        self._geom = None            # last applied (x, y, w, h)
        self._avail = None           # cached screen geometry
        self._win_opacity = -1.0

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    # ---- public API -------------------------------------------------------------

    def show_mode(self, mode: str, text: str = "", error: bool = False):
        """Show the active translucent tile. Dictation and listening stay white."""
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

    # ---- internals --------------------------------------------------------------

    def _set_mode(self, mode: str):
        visible = self.isVisible()
        self.mode = mode
        if mode == "hidden" and not visible:
            return
        if not visible:
            self._reset_motion()
            self._last = time.monotonic()
            self._refresh_screen()
            self._place(force=True)
            self.setWindowOpacity(0.0)
            self._win_opacity = 0.0
            self.show()
            harden_overlay(int(self.winId()))
        if not self.timer.isActive():
            self.timer.start()

    def _reset_motion(self):
        self._w.value, self._w.vel = STANDBY_W, 0.0
        self._h.value, self._h.vel = STANDBY_H, 0.0
        self._s.value, self._s.vel = 0.0, 0.0
        self._width, self._height, self._sphere = STANDBY_W, STANDBY_H, 0.0
        self._geom = None

    def _refresh_screen(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self._avail = screen.availableGeometry()

    def _place(self, force: bool = False):
        if self._avail is None:
            self._refresh_screen()
        # Snap to even pixels so the centre never wobbles by half a pixel mid-morph.
        width = max(2, int(round(self._width / 2.0)) * 2)
        height = max(2, int(round(self._height / 2.0)) * 2)
        x = self._avail.center().x() - width // 2
        y = self._avail.bottom() - ANCHOR_FROM_BOTTOM - height
        geom = (x, y, width, height)
        if geom == self._geom and not force:
            return
        self._geom = geom
        self.setGeometry(x, y, width, height)

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last)
        self._last = now
        target = _MODES[self.mode]
        self._phase += dt

        listening = self.mode in ("listening", "dictating")
        level = rms_to_level(self.level_source()) if listening else 0.0
        self._level = _chase(self._level, level, 18.0 if level > self._level else 6.0, dt)

        self._width = self._w.update(target["width"], _SIZE_TIME, dt)
        self._height = self._h.update(target["height"], _SIZE_TIME, dt)
        self._sphere = self._s.update(target["sphere"], _SPHERE_TIME, dt)
        self._spin = self._sp.update(target["spin"], _SPIN_TIME, dt)
        self._opacity = _chase(self._opacity, target["opacity"], 20.0, dt)
        self._angle = (self._angle + self._spin * dt) % (2.0 * math.pi)

        # Fade the entire window so its translucent surface and content stay in sync.
        win_opacity = round(max(0.0, min(1.0, self._opacity)), 2)
        if win_opacity != self._win_opacity:
            self._win_opacity = win_opacity
            self.setWindowOpacity(win_opacity)

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
        corner = _corner(height)

        shape = QPainterPath()
        shape.addRoundedRect(QRectF(0.25, 0.25, width - 0.5, height - 0.5), corner, corner)
        painter.fillPath(shape, QColor(0, 0, 0, 184))
        painter.setPen(QColor(255, 255, 255, int(58 * self._opacity)))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(shape)
        painter.setPen(Qt.PenStyle.NoPen)

        if self._sphere < 0.01:
            return

        cx, cy = width / 2.0, height / 2.0
        ca, sa = math.cos(self._angle), math.sin(self._angle)
        ct, st = math.cos(TILT), math.sin(TILT)
        px, py, pz = _POINTS[:, 0], _POINTS[:, 1], _POINTS[:, 2]
        x1 = px * ca + pz * sa
        z1 = -px * sa + pz * ca
        y2 = py * ct - z1 * st
        z2 = py * st + z1 * ct
        order = np.argsort(z2)

        # Gentle idle breathing plus a smoothed level swell (no per-dot jitter).
        breathe = 1.0 + 0.015 * math.sin(self._phase * 1.6)
        radius = SPHERE_RADIUS * self._sphere * breathe * (1.0 + 0.10 * self._level)
        shimmer = 1.0 + 0.035 * self._level * np.sin(self._phase * 6.0 + _SHIMMER)

        depth = (z2 + 1.0) * 0.5
        alpha = (BACK_ALPHA + (1.0 - BACK_ALPHA) * depth ** 1.4) * self._opacity * self._sphere
        size = (0.46 + 0.78 * depth) * self._sphere
        xs = (cx + x1 * radius * shimmer).tolist()
        ys = (cy + y2 * radius * shimmer).tolist()
        alpha_l, size_l = alpha.tolist(), size.tolist()

        # One brush, per-dot opacity: far cheaper than building a QColor per dot.
        painter.setBrush(QColor("#FF6B63") if self.error else QColor("#FFFFFF"))
        for i in order.tolist():
            painter.setOpacity(alpha_l[i])
            r = size_l[i] / 2.0
            painter.drawEllipse(QPointF(xs[i], ys[i]), r, r)
