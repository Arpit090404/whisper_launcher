from voicelaunch.stt import clean_dictation

def test_dictation_cleanup_is_conservative():
    assert clean_dictation("um, this is a note") == "This is a note."
    assert clean_dictation("already punctuated!") == "Already punctuated!"
