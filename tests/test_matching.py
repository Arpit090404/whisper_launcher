from voicelaunch.matching import best_match
def test_fuzzy_match(): assert best_match("spotfy",["spotify"],75)[0]=="spotify"
