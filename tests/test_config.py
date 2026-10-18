from voicelaunch.config import deep_merge
def test_merge(): assert deep_merge({"a":{"b":1,"c":2}},{"a":{"b":3}})=={"a":{"b":3,"c":2}}
