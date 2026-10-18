"""Small, always-visible, click-through listening standby indicator."""
import math, time
from PySide6.QtCore import Qt, QTimer, QPoint, QRectF
from PySide6.QtGui import QPainter, QColor, QCursor
from PySide6.QtWidgets import QWidget, QApplication
from ..winapi import harden_overlay

class StandbyWidget(QWidget):
    SIZE = 34
    def __init__(self, config: dict):
        flags = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint |
                 Qt.WindowType.Tool | Qt.WindowType.WindowTransparentForInput |
                 Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.NoDropShadowWindowHint)
        super().__init__(None, flags)
        self.config = config
        self.setFixedSize(self.SIZE, self.SIZE)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.phase = 0.0; self.last = time.monotonic()
        self.timer = QTimer(self); self.timer.setInterval(16); self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.timeout.connect(self._tick)
    def show_standby(self):
        if not self.config["ui"].get("show_standby_icon", True): return
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        # availableGeometry ends above the Windows taskbar; lift the indicator a
        # little further so it feels intentionally placed rather than docked.
        geo = screen.availableGeometry(); self.move(geo.center().x() - self.SIZE // 2, geo.bottom() - 87)
        self.show(); harden_overlay(int(self.winId())); self.timer.start()
    def _tick(self):
        now=time.monotonic(); self.phase += min(.05, now-self.last); self.last=now; self.update()
    def paintEvent(self, _):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # A compact version of the reference's flowing dotted sphere.
        center=self.SIZE/2; radius=12.5
        for row in range(9):
            y=-1+row/4
            for col in range(9):
                x=-1+col/4
                d=math.hypot(x,y)
                if d > 1: continue
                edge=math.sqrt(max(0,1-d*d))
                wobble=.18*math.sin(self.phase*2.4 + row*.8 + col*.55)
                px=center+x*radius*(.90+.13*edge)+wobble*edge
                py=center+y*radius
                alpha=int(55+175*edge)
                p.setPen(Qt.PenStyle.NoPen); p.setBrush(QColor(255,255,255,alpha))
                dot=1.35 if edge>.55 else 1.0
                p.drawEllipse(QRectF(px-dot/2,py-dot/2,dot,dot))
