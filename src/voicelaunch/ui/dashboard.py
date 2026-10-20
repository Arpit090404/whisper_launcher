"""Compact Cassette activity window opened from the system tray."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QSize, Qt, Signal
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from ..assets import asset_path


class Dashboard(QWidget):
    closed = Signal()

    def __init__(self, history):
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.history = history
        self.setWindowTitle("Cassette")
        self.setFixedSize(482, 589)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("""
            Dashboard { background: #282828; border-radius: 10px; color: #d5d5d5; font-family: 'Segoe UI'; }
            QLabel { color: #bdbdbd; } QPushButton, QToolButton { font-family: 'Segoe UI'; }
        """)
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(19, 14, 19, 18)
        layout.setSpacing(0)

        header = QHBoxLayout()
        title = QLabel("Cassette")
        title.setStyleSheet("color: #f2f2f2; font-size: 20px; font-weight: 700;")
        close = QToolButton()
        close.setText("×")
        close.setAccessibleName("Close Cassette")
        close.setFixedSize(32, 32)
        close.setStyleSheet("QToolButton { color: #eee; font-size: 40px; font-weight: 200; border: none; } QToolButton:hover { color: #fff; }")
        close.clicked.connect(self.hide)
        header.addWidget(title); header.addStretch(); header.addWidget(close)
        layout.addLayout(header)
        layout.addSpacing(27)

        stats = QLabel("Weekly stats")
        stats.setStyleSheet("font-size: 16px; font-weight: 700;")
        layout.addWidget(stats)
        layout.addSpacing(13)
        self.bars = QHBoxLayout()
        self.bars.setContentsMargins(56, 0, 45, 0)
        self.bars.setSpacing(14)
        layout.addLayout(self.bars)
        layout.addSpacing(20)

        rule = QFrame(); rule.setFrameShape(QFrame.Shape.HLine)
        rule.setStyleSheet("color: #737373;")
        layout.addWidget(rule)
        layout.addSpacing(11)

        history_header = QHBoxLayout()
        label = QLabel("History")
        label.setStyleSheet("font-size: 16px; font-weight: 700;")
        self.clear = QPushButton("Clear")
        self.clear.setAccessibleName("Clear transcript history")
        self.clear.setFixedSize(58, 22)
        self.clear.setStyleSheet("QPushButton { background: #ee8585; color: #813a3a; border: none; border-radius: 7px; font-size: 13px; font-weight: 700; } QPushButton:hover { background: #f39797; }")
        self.clear.clicked.connect(self.clear_history)
        history_header.addWidget(label); history_header.addStretch(); history_header.addWidget(self.clear)
        layout.addLayout(history_header)
        layout.addSpacing(7)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("QScrollArea { background: transparent; } QScrollBar:vertical { width: 5px; background: transparent; } QScrollBar::handle:vertical { background: #626262; border-radius: 2px; }")
        self.history_body = QWidget()
        self.history_layout = QVBoxLayout(self.history_body)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(7)
        self.scroll.setWidget(self.history_body)
        layout.addWidget(self.scroll, 1)

    def refresh(self):
        self._refresh_bars()
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        entries = self.history.entries()
        self.clear.setEnabled(bool(entries))
        if not entries:
            empty = QLabel("Your transcriptions will appear here.")
            empty.setStyleSheet("color: #8c8c8c; font-size: 13px;")
            self.history_layout.addWidget(empty)
        else:
            for entry in entries:
                self.history_layout.addWidget(self._entry(entry))
        self.history_layout.addStretch()

    def _refresh_bars(self):
        while self.bars.count():
            item = self.bars.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        weekly = self.history.weekly_word_counts()
        maximum = max((count for _, count in weekly), default=0)
        for day, count in weekly:
            column = QVBoxLayout(); column.setSpacing(5)
            column.setAlignment(Qt.AlignmentFlag.AlignBottom)
            bar = QFrame(); bar.setFixedWidth(35)
            height = 3 if maximum == 0 else max(14, round(126 * count / maximum))
            bar.setFixedHeight(height)
            tone = "#d5d5d5" if day == weekly[-1][0] else "#555555"
            bar.setStyleSheet(f"background: {tone}; border-radius: 7px 7px 0 0;")
            weekday = QLabel(day.strftime("%a")); weekday.setAlignment(Qt.AlignmentFlag.AlignCenter)
            weekday.setStyleSheet("font-size: 12px; color: #c9c9c9;")
            column.addWidget(bar, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            column.addWidget(weekday)
            wrapper = QWidget(); wrapper.setLayout(column)
            self.bars.addWidget(wrapper)

    def _entry(self, entry: dict[str, object]) -> QWidget:
        text = entry.get("text", "")
        pinned = entry.get("pinned", False)
        row = QFrame(); row.setObjectName("historyItem")
        row.setStyleSheet("QFrame#historyItem { background: #303030; border-radius: 8px; } QFrame#historyItem:hover { background: #363636; }")
        layout = QHBoxLayout(row)
        layout.setContentsMargins(10, 7, 6, 7); layout.setSpacing(5)
        transcript = QLabel(text)
        transcript.setWordWrap(True)
        transcript.setStyleSheet("color: #c1c1c1; font-size: 13px; font-weight: 600;")
        controls = QVBoxLayout(); controls.setContentsMargins(0, 0, 0, 0); controls.setSpacing(1)
        pin = self._icon_button("pin-svgrepo-com.svg", "Unpin transcription" if pinned else "Pin transcription", "#ef8b8b" if pinned else "#bcbcbc")
        pin.clicked.connect(lambda: self.toggle_pin(entry.get("id", "")))
        copy = self._icon_button("copy-3-svgrepo-com.svg", "Copy transcription", "#c9c9c9")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(text))
        controls.addWidget(pin); controls.addWidget(copy)
        layout.addWidget(transcript, 1); layout.addLayout(controls, 0)
        return row

    def _icon_button(self, asset_name: str, accessible_name: str, color: str) -> QToolButton:
        button = QToolButton()
        button.setAccessibleName(accessible_name)
        button.setIcon(_tinted_icon(asset_name, color))
        button.setIconSize(QSize(17, 17))
        button.setFixedSize(29, 25)
        button.setStyleSheet("QToolButton { border: none; border-radius: 5px; } QToolButton:hover { background: #484848; }")
        return button

    def toggle_pin(self, entry_id: str):
        if entry_id:
            self.history.toggle_pin(entry_id)
            self.refresh()

    def clear_history(self):
        self.history.clear()
        self.refresh()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        self.closed.emit()


def _tinted_icon(asset_name: str, color: str) -> QIcon:
    source = asset_path(asset_name).read_text(encoding="utf-8")
    for original in ("#000000", "#1C274C"):
        source = source.replace(original, color)
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    pixmap = QPixmap(20, 20)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)
