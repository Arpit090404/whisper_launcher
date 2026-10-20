"""Cassette's movable activity dashboard."""
from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QToolButton, QVBoxLayout, QWidget,
)

from ..assets import asset_path


class Dashboard(QWidget):
    """A regular native window, so it can be moved, minimized, and resized."""

    def __init__(self, history):
        super().__init__()
        self.history = history
        self.setWindowTitle("Cassette")
        self.resize(820, 650)
        self.setMinimumSize(640, 520)
        self.setStyleSheet("""
            Dashboard { background: #181818; color: #eeeeee; font-family: 'Segoe UI'; }
            QLabel { color: #ededed; }
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical { background: #555; min-height: 28px; border-radius: 3px; }
        """)
        self._build()
        self.refresh()

    def _build(self):
        page = QVBoxLayout(self)
        page.setContentsMargins(34, 28, 34, 28)
        page.setSpacing(0)

        eyebrow = QLabel("CASSETTE  /  ACTIVITY")
        eyebrow.setStyleSheet("color: #9a9a9a; font-size: 11px; font-weight: 700; letter-spacing: 1.2px;")
        page.addWidget(eyebrow)
        page.addSpacing(8)
        heading = QLabel("Your words, in flow.")
        heading.setStyleSheet("font-size: 27px; font-weight: 700; letter-spacing: -0.4px;")
        page.addWidget(heading)
        page.addSpacing(5)
        help_text = QLabel("Cassette keeps your recent dictation close at hand. Hold F8 to dictate.")
        help_text.setStyleSheet("color: #a8a8a8; font-size: 13px;")
        page.addWidget(help_text)
        page.addSpacing(24)

        overview = QHBoxLayout()
        overview.setSpacing(14)
        weekly_card = self._card()
        weekly_layout = QVBoxLayout(weekly_card)
        weekly_layout.setContentsMargins(20, 17, 20, 15)
        weekly_layout.setSpacing(0)
        weekly_title = QLabel("Weekly activity")
        weekly_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        weekly_layout.addWidget(weekly_title)
        weekly_layout.addSpacing(2)
        weekly_subtitle = QLabel("Words transcribed in the last seven days")
        weekly_subtitle.setStyleSheet("color: #929292; font-size: 12px;")
        weekly_layout.addWidget(weekly_subtitle)
        weekly_layout.addSpacing(15)
        self.bars = QHBoxLayout()
        self.bars.setContentsMargins(6, 0, 6, 0)
        self.bars.setSpacing(9)
        weekly_layout.addLayout(self.bars)
        overview.addWidget(weekly_card, 3)

        metrics_card = self._card()
        metrics_layout = QVBoxLayout(metrics_card)
        metrics_layout.setContentsMargins(20, 17, 20, 17)
        metrics_layout.setSpacing(0)
        self.word_metric = self._metric(metrics_layout, "TOTAL WORDS")
        self.wpm_metric = self._metric(metrics_layout, "AVERAGE WPM")
        self.streak_metric = self._metric(metrics_layout, "DAY STREAK", last=True)
        overview.addWidget(metrics_card, 2)
        page.addLayout(overview)
        page.addSpacing(25)

        history_header = QHBoxLayout()
        history_title = QLabel("Recent transcripts")
        history_title.setStyleSheet("font-size: 17px; font-weight: 700;")
        self.clear = QPushButton("Clear history")
        self.clear.setAccessibleName("Clear transcript history")
        self.clear.setFixedHeight(29)
        self.clear.setStyleSheet("QPushButton { background: #332525; color: #eb9696; border: 1px solid #603b3b; border-radius: 6px; padding: 0 11px; font-size: 12px; font-weight: 700; } QPushButton:hover { background: #482d2d; } QPushButton:disabled { color: #6e5252; border-color: #403333; }")
        self.clear.clicked.connect(self.clear_history)
        history_header.addWidget(history_title)
        history_header.addStretch()
        history_header.addWidget(self.clear)
        page.addLayout(history_header)
        page.addSpacing(10)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.history_body = QWidget()
        self.history_layout = QVBoxLayout(self.history_body)
        self.history_layout.setContentsMargins(0, 0, 0, 0)
        self.history_layout.setSpacing(7)
        self.scroll.setWidget(self.history_body)
        page.addWidget(self.scroll, 1)

    def _card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        card.setStyleSheet("QFrame#card { background: #202020; border: 1px solid #333333; border-radius: 13px; }")
        return card

    def _metric(self, layout: QVBoxLayout, label: str, last: bool = False) -> QLabel:
        value = QLabel("0")
        value.setStyleSheet("color: #f2f2f2; font-family: Georgia; font-size: 27px;")
        caption = QLabel(label)
        caption.setStyleSheet("color: #a0a0a0; font-size: 10px; font-weight: 700; letter-spacing: 0.8px;")
        layout.addWidget(value)
        layout.addWidget(caption)
        if not last:
            layout.addSpacing(12)
            divider = QFrame(); divider.setFrameShape(QFrame.Shape.HLine)
            divider.setStyleSheet("color: #363636;")
            layout.addWidget(divider)
            layout.addSpacing(10)
        return value

    def refresh(self):
        self._refresh_bars()
        summary = self.history.summary()
        self.word_metric.setText(f"{summary['total_words']:,}")
        self.wpm_metric.setText(str(summary["average_wpm"]) if summary["average_wpm"] else "—")
        self.streak_metric.setText(str(summary["streak"]))
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        entries = self.history.entries()
        self.clear.setEnabled(bool(entries))
        if not entries:
            empty = QLabel("Your transcriptions will appear here after you dictate.")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #828282; background: #202020; border: 1px dashed #3c3c3c; border-radius: 10px; padding: 26px;")
            self.history_layout.addWidget(empty)
        else:
            for entry in entries:
                self.history_layout.addWidget(self._entry(entry))
        self.history_layout.addStretch()

    def _refresh_bars(self):
        while self.bars.count():
            item = self.bars.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        weekly = self.history.weekly_word_counts()
        maximum = max((count for _, count in weekly), default=0)
        for day, count in weekly:
            column = QVBoxLayout(); column.setSpacing(6)
            column.setAlignment(Qt.AlignmentFlag.AlignBottom)
            bar = QFrame()
            bar.setFixedWidth(34)
            height = 5 if maximum == 0 else max(15, round(112 * count / maximum))
            bar.setFixedHeight(height)
            tone = "#e5e5e5" if day == weekly[-1][0] else "#5e5e5e"
            bar.setStyleSheet(f"background: {tone}; border-radius: 6px 6px 2px 2px;")
            weekday = QLabel(day.strftime("%a"))
            weekday.setAlignment(Qt.AlignmentFlag.AlignCenter)
            weekday.setStyleSheet("font-size: 11px; color: #aaa;")
            column.addWidget(bar, alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
            column.addWidget(weekday)
            wrapper = QWidget(); wrapper.setLayout(column)
            self.bars.addWidget(wrapper, 1)

    def _entry(self, entry: dict[str, object]) -> QWidget:
        text = str(entry.get("text", ""))
        pinned = bool(entry.get("pinned", False))
        row = QFrame(); row.setObjectName("historyItem")
        row.setStyleSheet("QFrame#historyItem { background: #1d1d1d; border: 1px solid #303030; border-radius: 10px; } QFrame#historyItem:hover { background: #232323; border-color: #484848; }")
        layout = QGridLayout(row)
        layout.setContentsMargins(15, 11, 8, 11)
        layout.setHorizontalSpacing(13); layout.setVerticalSpacing(2)
        time = QLabel(_formatted_time(entry.get("created_at")))
        time.setStyleSheet("color: #8e8e8e; font-size: 11px;")
        layout.addWidget(time, 0, 0, Qt.AlignmentFlag.AlignTop)
        transcript = QLabel(text)
        transcript.setWordWrap(True)
        transcript.setStyleSheet("color: #eeeeee; font-size: 13px; font-weight: 600;")
        layout.addWidget(transcript, 0, 1)
        if pinned:
            pinned_label = QLabel("PINNED")
            pinned_label.setStyleSheet("color: #ee8d8d; font-size: 9px; font-weight: 700; letter-spacing: 0.6px;")
            layout.addWidget(pinned_label, 1, 1)
        controls = QVBoxLayout(); controls.setContentsMargins(0, 0, 0, 0); controls.setSpacing(2)
        pin = self._icon_button("pin-svgrepo-com.svg", "Unpin transcription" if pinned else "Pin transcription", "#ef8b8b" if pinned else "#bcbcbc")
        pin.clicked.connect(lambda: self.toggle_pin(str(entry.get("id", ""))))
        copy = self._icon_button("copy-3-svgrepo-com.svg", "Copy transcription", "#c9c9c9")
        copy.clicked.connect(lambda: QGuiApplication.clipboard().setText(text))
        controls.addWidget(pin); controls.addWidget(copy)
        layout.addLayout(controls, 0, 2, 2, 1, Qt.AlignmentFlag.AlignTop)
        layout.setColumnStretch(1, 1)
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
        """The title-bar close button returns Cassette to the system tray."""
        event.ignore()
        self.hide()


def _formatted_time(value: object) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%I:%M %p").lstrip("0")
    except ValueError:
        return ""


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
