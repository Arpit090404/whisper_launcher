import numpy as np

from voicelaunch.stt import clean_dictation, prepare_audio

def test_dictation_cleanup_is_conservative():
    assert clean_dictation("um, this is a note") == "This is a note."
    assert clean_dictation("already punctuated!") == "Already punctuated!"


def test_dictation_cleanup_only_changes_formatting():
    assert clean_dictation("i wrote this. then i sent it") == "I wrote this. Then I sent it."


def test_audio_preparation_trims_dead_air_with_padding():
    audio = np.zeros(16_000, dtype=np.float32)
    audio[8_000:8_320] = 0.1
    trimmed = prepare_audio(audio, 16_000, trim_threshold=0.01, padding_ms=100)
    assert 3_000 <= len(trimmed) <= 4_000
    assert np.max(np.abs(trimmed)) > 0.09
