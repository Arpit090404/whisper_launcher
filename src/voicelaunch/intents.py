from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import re
from rapidfuzz import fuzz, process

@dataclass(frozen=True)
class Intent:
    kind: Literal["meta","macro","site_search","find_file","find_folder","reveal","open","web_search","fallback"]
    arg: str = ""; site: str = ""; meta: str = ""; raw: str = ""

@dataclass(frozen=True)
class ParseContext:
    macro_triggers: dict[str, str]
    sites: dict[str, dict]
    app_aliases: dict[str, str]

FILLERS = ("go ahead and", "i would like to", "i'd like to", "could you", "can you", "please", "okay", "hey", "ok")
def normalize(text: str, file_command: bool = False) -> str:
    value = re.sub(r"\s+", " ", text.lower().strip().rstrip(".!?,")).strip()
    while True:
        found = next((f for f in FILLERS if value == f or value.startswith(f + " ")), None)
        if not found: break
        value = value[len(found):].strip()
    value = re.sub(r"\s+please$", "", value).strip()
    return value.replace(" dot ", ".") if file_command else value

def parse(text: str, ctx: ParseContext) -> Intent:
    raw = normalize(text)
    if raw in {"refresh apps", "reload config"}: return Intent("meta", meta=raw.replace(" ", "_"), raw=raw)
    if ctx.macro_triggers:
        hit = process.extractOne(raw, list(ctx.macro_triggers), scorer=fuzz.WRatio, score_cutoff=90)
        if hit: return Intent("macro", arg=ctx.macro_triggers[hit[0]], raw=raw)
    names = []
    for key, data in ctx.sites.items(): names += [key] + data.get("aliases", [])
    if names:
        match = re.match(r"^(?:(?:search|find|look up|look for)\s*)?(.+?)\s+(?:on|in|at)\s+(.+)$", raw)
        if match:
            lookup = {n.lower(): key for key, d in ctx.sites.items() for n in [key] + d.get("aliases", [])}
            if match.group(2) in lookup: return Intent("site_search", match.group(1), lookup[match.group(2)], raw=raw)
    m = re.match(r"^(?:reveal|show)\s+(.+?)\s+in\s+(?:folder|explorer|file explorer)$", raw)
    if m: return Intent("reveal", m.group(1), raw=raw)
    m = re.match(r"^(?:find|open)\s+folder\s+(.+)$", raw)
    if m: return Intent("find_folder", m.group(1), raw=raw)
    m = re.match(r"^(?:(?:find|open|show)\s+)?file\s+(.+)$|^find\s+(.+)$", raw)
    if m: return Intent("find_file", normalize(m.group(1) or m.group(2), True), raw=raw)
    m = re.match(r"^(?:open|launch|start|run)\s+(.+)$", raw)
    if m: return Intent("open", m.group(1), raw=raw)
    m = re.match(r"^(?:search for|search|google|look up|chrome)\s+(.+)$", raw)
    if m: return Intent("web_search", m.group(1), raw=raw)
    return Intent("fallback", raw, raw=raw)
