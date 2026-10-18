from voicelaunch.intents import parse, ParseContext, normalize
CTX=ParseContext({"work mode":"work mode"},{"youtube":{},"github":{},"maps":{}},{})
def p(text): return parse(text,CTX)
def test_examples():
    assert p("open spotify").kind=="open"
    assert p("please launch vs code").arg=="vs code"
    assert p("open file main dot py").arg=="main.py"
    assert p("find folder projects").kind=="find_folder"
    assert p("show invoice in folder").kind=="reveal"
    assert p("search best mechanical keyboards").kind=="web_search"
    assert (p("lofi beats on youtube").kind,p("lofi beats on youtube").site)==("site_search","youtube")
    assert p("work mode").kind=="macro"
    assert p("refresh apps").meta=="refresh_apps"
    assert p("what is the capital of france").kind=="fallback"
def test_normalize(): assert normalize("  Can you please OPEN Spotify! ")=="open spotify"
