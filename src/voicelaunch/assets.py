"""Resolve tracked visual assets in source and frozen builds."""
from pathlib import Path
import sys

def asset_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return root / "assets" / name
