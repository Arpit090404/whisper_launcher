from __future__ import annotations
from copy import deepcopy
from pathlib import Path
import shutil, sys, yaml
from .paths import CONFIG_DIR, ensure_dirs

# PyInstaller exposes bundled data in _MEIPASS (the _internal folder for an
# onedir build).  In development, resources live at the repository root.
PACKAGE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
DEFAULT_PATH = PACKAGE_ROOT / "config" / "default_config.yaml"
MACROS_EXAMPLE = PACKAGE_ROOT / "config" / "macros.example.yaml"

def deep_merge(base: dict, override: dict) -> dict:
    result = deepcopy(base)
    for key, value in override.items():
        result[key] = deep_merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
    return result

def _read(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def bootstrap_config() -> tuple[Path, Path]:
    ensure_dirs(); config, macros = CONFIG_DIR / "config.yaml", CONFIG_DIR / "macros.yaml"
    if not config.exists(): shutil.copyfile(DEFAULT_PATH, config)
    if not macros.exists(): shutil.copyfile(MACROS_EXAMPLE, macros)
    return config, macros

def load_config() -> tuple[dict, dict]:
    config, macros = bootstrap_config()
    defaults = _read(DEFAULT_PATH)
    user = _read(config)
    if not isinstance(user, dict): raise ValueError("config.yaml must contain a YAML mapping")
    macros_data = _read(macros)
    if not isinstance(macros_data, dict): raise ValueError("macros.yaml must contain a YAML mapping")
    return deep_merge(defaults, user), macros_data
