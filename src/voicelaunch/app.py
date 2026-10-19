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
from .stt import clean_dictation
from .ui.pill import PillWidget
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
    pill=PillWidget(config); controller=Controller(pill,config,macros,index,reload_live_config); controller.register(); tray=make_tray(controller,app); pill.show_standby()
    stt=STT(config,DATA_DIR/"models")
    def loaded():
        try: stt.load(); tray.setToolTip("VoiceLaunch — ready")
        except Exception: logging.exception("Speech model failed to load"); tray.showMessage("VoiceLaunch","Could not download speech model. Check your internet and restart.")
    def command_prompt():
        apps_prompt=", ".join(list(index)[:40])
        macro_prompt=", ".join(trigger for m in macros.get("macros",[]) for trigger in m.get("triggers",[]))
        site_prompt=", ".join(config["sites"])
        return f"Open {apps_prompt}. {macro_prompt}. {site_prompt}."[:600]
    def process(audio):
        text,_=stt.transcribe(audio, command_prompt())
        return controller.execute_text(text) if text else __import__("voicelaunch.actions",fromlist=["ActionResult"]).ActionResult(False,"Didn't catch that")
    def dictate(audio):
        text,_=stt.transcribe(audio, config["dictation"]["initial_prompt"], dictation=True)
        return clean_dictation(text)
    controller._process=process
    controller._process_command=process
    controller._process_dictation=dictate
    pool=ThreadPoolExecutor(max_workers=1); pool.submit(loaded); pool.submit(lambda: index.update(build_index(cache)))
    return app.exec()
