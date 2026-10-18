from rapidfuzz import fuzz, process

def best_match(query: str, choices: list[str] | tuple[str, ...], cutoff: int = 0):
    if not query or not choices: return None
    return process.extractOne(query.lower(), [x.lower() for x in choices], scorer=fuzz.WRatio, score_cutoff=cutoff)

def rank_paths(query: str, paths: list[str], home: str) -> list[tuple[str, float]]:
    import os
    scored = [(p, fuzz.WRatio(query.lower(), os.path.splitext(os.path.basename(p))[0].lower())) for p in paths]
    return sorted(scored, key=lambda x: (-x[1], not x[0].lower().startswith(home.lower()), len(x[0])))
