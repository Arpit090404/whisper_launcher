from pathlib import Path
from platformdirs import user_config_dir, user_data_dir

CONFIG_DIR = Path(user_config_dir("Cassette", appauthor=False, roaming=True))
DATA_DIR = Path(user_data_dir("Cassette", appauthor=False, roaming=False))
LOG_DIR = DATA_DIR / "logs"

def ensure_dirs() -> None:
    for path in (CONFIG_DIR, DATA_DIR, LOG_DIR, DATA_DIR / "models"):
        path.mkdir(parents=True, exist_ok=True)
