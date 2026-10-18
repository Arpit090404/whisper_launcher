from __future__ import annotations
import json, logging
from logging.handlers import RotatingFileHandler
from concurrent.futures import ThreadPoolExecutor
from PySide6.QtCore import QLockFile, QTimer
from PySide6.QtWidgets import QApplication
from .paths import ensure_dirs, DATA_DIR, LOG_DIR
from .config import load_config
from .actions.apps import build_index
from .controller import Controller
from .stt import STT
from .ui.pill import PillWidget
from .ui.standby import StandbyWidget
from .ui.tray import make_tray
def run():
    ensure_dirs(); logging.basicConfig(level=logging.INFO,handlers=[RotatingFileHandler(LOG_DIR/"voicelaunch.log",maxBytes=1_000_000,backupCount=3)])
    app=QApplication([]); lock=QLockFile(str(DATA_DIR/"lock"));
    if not lock.tryLock(10): return 0
    config,macros=load_config(); cache=DATA_DIR/"apps_cache.json"
    try: index=json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    except Exception: index={}
    def reload_live_config():
        new_config,new_macros=load_config()
        config.clear(); config.update(new_config)
        macros.clear(); macros.update(new_macros)
    pill=PillWidget(config); standby=StandbyWidget(config); controller=Controller(pill,standby,config,macros,index,reload_live_config); controller.register(); tray=make_tray(controller,app); standby.show_standby()
    stt=STT(config,DATA_DIR/"models")
    def loaded():
        try: stt.load(); tray.setToolTip("VoiceLaunch — ready")
        except Exception: logging.exception("Speech model failed to load"); tray.showMessage("VoiceLaunch","Could not download speech model. Check your internet and restart.")
    def process(audio):
        text,_=stt.transcribe(audio)
        return controller.execute_text(text) if text else __import__("voicelaunch.actions",fromlist=["ActionResult"]).ActionResult(False,"Didn't catch that")
    controller._process=process
    pool=ThreadPoolExecutor(max_workers=1); pool.submit(loaded); pool.submit(lambda: index.update(build_index(cache)))
    return app.exec()
