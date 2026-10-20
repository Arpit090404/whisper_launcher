from datetime import date, datetime

from voicelaunch.history import TranscriptHistory


def test_weekly_word_counts_are_grouped_by_day(tmp_path):
    history = TranscriptHistory(tmp_path / "history.json")
    history.add("one two", datetime(2026, 10, 18, 8, 0))
    history.add("three", datetime(2026, 10, 20, 9, 0))
    weekly = dict(history.weekly_word_counts(date(2026, 10, 20)))
    assert weekly[date(2026, 10, 18)] == 2
    assert weekly[date(2026, 10, 20)] == 1


def test_clear_removes_all_transcripts(tmp_path):
    history = TranscriptHistory(tmp_path / "history.json")
    history.add("keep this private")
    history.clear()
    assert history.entries() == []


def test_pinned_entries_are_kept_at_the_top(tmp_path):
    history = TranscriptHistory(tmp_path / "history.json")
    history.add("first")
    first_id = history.entries()[0]["id"]
    history.add("second")
    history.toggle_pin(first_id)
    entries = history.entries()
    assert entries[0]["text"] == "first"
    assert entries[0]["pinned"] is True


def test_summary_includes_words_wpm_and_streak(tmp_path):
    history = TranscriptHistory(tmp_path / "history.json")
    history.add("one two three", datetime(2026, 10, 19, 9, 0), duration_seconds=30)
    history.add("four five", datetime(2026, 10, 20, 9, 0), duration_seconds=30)
    assert history.summary(date(2026, 10, 20)) == {
        "total_words": 5,
        "average_wpm": 5,
        "streak": 2,
    }
