"""Persistent transcript history and weekly word-count summaries."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from uuid import uuid4


class TranscriptHistory:
    """Keep a small, local-only record of completed dictations."""

    def __init__(self, path: Path, limit: int = 200):
        self.path = path
        self.limit = limit

    def entries(self) -> list[dict[str, str]]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, list):
                return []
            entries = [entry for entry in value if isinstance(entry, dict)]
            changed = len(entries) != len(value)
            for entry in entries:
                if not entry.get("id"):
                    entry["id"] = uuid4().hex
                    changed = True
                if "pinned" not in entry:
                    entry["pinned"] = False
                    changed = True
            if changed:
                self._write(entries)
            return sorted(entries, key=lambda entry: not entry.get("pinned", False))
        except (OSError, json.JSONDecodeError):
            return []

    def add(self, text: str, created_at: datetime | None = None, duration_seconds: float | None = None) -> None:
        text = text.strip()
        if not text:
            return
        entries = self.entries()
        word_count = len(text.split())
        entry = {
            "id": uuid4().hex,
            "text": text,
            "created_at": (created_at or datetime.now()).isoformat(timespec="seconds"),
            "pinned": False,
        }
        if duration_seconds and duration_seconds > 0:
            entry["wpm"] = round(word_count * 60 / duration_seconds)
        entries.insert(0, entry)
        self._write(entries[:self.limit])

    def clear(self) -> None:
        self._write([])

    def toggle_pin(self, entry_id: str) -> None:
        entries = self.entries()
        for entry in entries:
            if entry.get("id") == entry_id:
                entry["pinned"] = not entry.get("pinned", False)
                self._write(entries)
                return

    def weekly_word_counts(self, today: date | None = None) -> list[tuple[date, int]]:
        today = today or date.today()
        days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
        counts = {day: 0 for day in days}
        for entry in self.entries():
            try:
                created = datetime.fromisoformat(entry["created_at"]).date()
            except (KeyError, TypeError, ValueError):
                continue
            if created in counts:
                counts[created] += len(entry.get("text", "").split())
        return [(day, counts[day]) for day in days]

    def summary(self, today: date | None = None) -> dict[str, int]:
        """Return dashboard metrics derived entirely from local history."""
        today = today or date.today()
        entries = self.entries()
        total_words = sum(len(entry.get("text", "").split()) for entry in entries)
        wpm_samples = [entry["wpm"] for entry in entries if isinstance(entry.get("wpm"), (int, float))]
        active_days = set()
        for entry in entries:
            try:
                active_days.add(datetime.fromisoformat(entry["created_at"]).date())
            except (KeyError, TypeError, ValueError):
                continue
        streak = 0
        day = today
        while day in active_days:
            streak += 1
            day -= timedelta(days=1)
        return {
            "total_words": total_words,
            "average_wpm": round(sum(wpm_samples) / len(wpm_samples)) if wpm_samples else 0,
            "streak": streak,
        }

    def _write(self, entries: list[dict[str, str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)
