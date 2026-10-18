"""The one and only overlay window: standby orb -> listening -> processing -> result.

Why this exists: the old design used two windows (standby orb + pill) and restarted a
fade/grow animation on every state change, so animations stacked and overlapped.

Now there is ONE window, ONE timer and ONE render loop. Every visual property (radius,
opacity, spin speed, text, error tint) simply chases a target value with exponential
smoothing.  A new state only re-aims the same sphere, so nothing can overlap and nothing
restarts from zero.
"""
from __future__ import annotations
import math, time
import numpy as np
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF
from PySide6.QtGui import QColor, QCursor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication, QWidget
from .theme import WHITE, ERROR
from ..audio import rms_to_level
from ..winapi import harden_overlay

# ---------------------------------------------------------------- look (tweak here)
SPHERE_RADIUS = 19.0      # active sphere (listening / processing / result). Was 38 -> 50% smaller
STANDBY_RADIUS = 12.5     # small idle orb
N_DOTS = 320              # dots over the WHOLE sphere (front + back)
TILT = 0.40               # radians the globe is tilted toward the viewer
BACK_ALPHA = 0.16         # brightness of dots on the far side (0..1)
STANDBY_OPACITY = 0.85

# ---------------------------------------------------------------- window layout
WIN_W, WIN_H = 300, 104
CENTER_Y = 40             # sphere centre inside the window
ANCHOR_FROM_BOTTOM = 70   # sphere centre sits this far above the work-area bottom
TEXT_GAP = 14             # gap between sphere and result text

# mode -> target values the animation chases
_MODES = {
    "hidden":     dict(radius=STANDBY_RADIUS, opacity=0.0,             spin=0.35, text=0.0),
    "standby":    dict(radius=STANDBY_RADIUS, opacity=STANDBY_OPACITY, spin=0.35, text=0.0),
    "listening":  dict(radius=SPHERE_RADIUS,  opacity=1.0,             spin=0.55, text=0.0),
    "processing": dict(radius=SPHERE_RADIUS,  opacity=1.0,             spin=2.40, text=0.0),
    "result":     dict(radius=SPHERE_RADIUS,  opacity=1.0,             spin=0.55, text=1.0),
}


def _fibonacci_sphere(n: int) -> np.ndarray:
    """n points spread evenly over the full unit sphere (both hemispheres)."""
    k = np.arange(n)
    y = 1.0 - 2.0 * (k + 0.5) / n
    r = np.sqrt(1.0 - y * y)
    theta = math.pi * (3.0 - math.sqrt(5.0)) * k        # golden angle
    return np.stack([r * np.cos(theta), y, r * np.sin(theta)], axis=1)


_POINTS = _fibonacci_sphere(N_DOTS)


def _chase(cur: float, target: float, rate: float, dt: float) -> float:
    """Frame-rate independent exponential approach."""
    return cur + (target - cur) * (1.0 - math.exp(-rate * dt))


class PillWidget(QWidget):
    def __init__(self, config: dict):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                 Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput |
                 Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)
        super().__init__(None, flags)
        self.config = config
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedSize(WIN_W, WIN_H)

        self.level_source = lambda: 0.0          # set by the controller (mic RMS)
        self.mode = "hidden"
        self.error = False
        self.text = ""
        self._standby_enabled = False

        self._last = time.monotonic()
        self._phase = 0.0
        self._angle = 0.0
        self._radius = STANDBY_RADIUS
        self._opacity = 0.0
        self._spin = _MODES["standby"]["spin"]
        self._text_alpha = 0.0
        self._tint = 0.0
        self._level = 0.0

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------ public API
    def show_mode(self, mode: str, text: str = "", error: bool = False):
        """listening | processing | result (| error, same as result with error=True)."""
        if mode == "error":
            mode, error = "result", True
        if mode not in ("listening", "processing", "result"):
            return
        self.error = error
        if mode == "result":
            self.text = text
        self._set_mode(mode)

    def show_standby(self):
        """Show the small idle orb. Never interrupts an active session."""
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
        """Session over: glide the SAME sphere back to the standby orb (or fade out)."""
        self._set_mode("standby" if self._standby_enabled else "hidden")

    # ------------------------------------------------------------------ internals
    def _set_mode(self, mode: str):
        was_visible = self.isVisible()
        self.mode = mode
        if mode == "hidden" and not was_visible:
            return
        if not was_visible or mode == "listening":
            self._place()
        if not was_visible:
            self._radius = STANDBY_RADIUS            # new sphere grows out of the orb
            self._last = time.monotonic()
            self.show()
            harden_overlay(int(self.winId()))
        if not self.timer.isActive():
            self.timer.start()

    def _place(self):
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        geo = screen.availableGeometry()
        self.move(geo.center().x() - WIN_W // 2, geo.bottom() - ANCHOR_FROM_BOTTOM - CENTER_Y)

    def _tick(self):
        now = time.monotonic()
        dt = min(0.05, now - self._last)
        self._last = now
        goal = _MODES[self.mode]
        self._phase += dt

        want = rms_to_level(self.level_source()) if self.mode == "listening" else 0.0
        self._level = _chase(self._level, want, 25.0 if want > self._level else 8.0, dt)
        self._radius = _chase(self._radius, goal["radius"], 12.0, dt)
        self._opacity = _chase(self._opacity, goal["opacity"],
                               20.0 if goal["opacity"] > self._opacity else 14.0, dt)
        self._spin = _chase(self._spin, goal["spin"], 4.0, dt)
        self._text_alpha = _chase(self._text_alpha, goal["text"], 14.0, dt)
        self._tint = _chase(self._tint, 1.0 if self.error else 0.0, 14.0, dt)
        self._angle = (self._angle + self._spin * dt) % (2.0 * math.pi)

        if self.mode == "hidden" and self._opacity < 0.01:
            self._opacity = 0.0
            self.timer.stop()
            self.hide()
            return

        settled = (abs(self._radius - goal["radius"]) < 0.05 and
                   abs(self._opacity - goal["opacity"]) < 0.005 and
                   abs(self._text_alpha - goal["text"]) < 0.01)
        interval = 33 if (self.mode == "standby" and settled) else 16   # idle orb: 30 fps is plenty
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)
        self.update()

    def _rgb(self):
        w, e = QColor(WHITE), QColor(ERROR)
        t = self._tint
        return (int(w.red() + (e.red() - w.red()) * t),
                int(w.green() + (e.green() - w.green()) * t),
                int(w.blue() + (e.blue() - w.blue()) * t))

    def paintEvent(self, _):
        if self._opacity <= 0.003:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        cr, cg, cb = self._rgb()
        cx, cy = WIN_W / 2.0, float(CENTER_Y)

        # Rotate the FULL sphere around its vertical axis, tilt it a little, project.
        ca, sa = math.cos(self._angle), math.sin(self._angle)
        ct, st = math.cos(TILT), math.sin(TILT)
        px, py, pz = _POINTS[:, 0], _POINTS[:, 1], _POINTS[:, 2]
        x1 = px * ca + pz * sa
        z1 = -px * sa + pz * ca
        y2 = py * ct - z1 * st
        z2 = py * st + z1 * ct                       # +1 = facing the viewer, -1 = far side
        order = np.argsort(z2).tolist()              # paint far side first, near side on top
        x1, y2, z2 = x1.tolist(), y2.tolist(), z2.tolist()

        radius = self._radius * (1.0 + 0.12 * self._level)       # mic level makes it breathe
        size_k = 0.55 + 0.45 * (self._radius / SPHERE_RADIUS)    # orb dots a bit smaller
        lvl, ph = self._level, self._phase
        for i in order:
            depth = (z2[i] + 1.0) * 0.5
            alpha = (BACK_ALPHA + (1.0 - BACK_ALPHA) * depth ** 1.4) * self._opacity
            r = radius * (1.0 + 0.08 * lvl * math.sin(ph * 7.0 + i * 1.7))
            d = (0.8 + 1.3 * depth) * size_k
            p.setBrush(QColor(cr, cg, cb, int(255 * alpha)))
            p.drawEllipse(QPointF(cx + x1[i] * r, cy + y2[i] * r), d / 2, d / 2)

        if self._text_alpha > 0.01 and self.text:
            f = self.font()
            f.setFamilies(["Segoe UI Variable Text", "Segoe UI"])
            f.setPixelSize(13)
            f.setWeight(QFont.Weight.DemiBold)
            p.setFont(f)
            shown = QFontMetrics(f).elidedText(self.text, Qt.TextElideMode.ElideMiddle, WIN_W - 24)
            a = int(255 * 0.92 * self._text_alpha * self._opacity)
            p.setPen(QColor(cr, cg, cb, a))
            p.drawText(QRectF(0, CENTER_Y + SPHERE_RADIUS + TEXT_GAP, WIN_W, 22),
                       Qt.AlignmentFlag.AlignCenter, shown)
