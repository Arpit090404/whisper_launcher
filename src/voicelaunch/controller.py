from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os, time, keyboard, subprocess
from urllib.parse import quote_plus
from PySide6.QtCore import QObject, Signal, QTimer
from .audio import Recorder
from .intents import ParseContext, parse
from .matching import best_match
from .actions import ActionResult
from .actions import apps, files, web

class Controller(QObject):
    worker_done=Signal(object)
    hotkey_requested=Signal()
    cancel_requested=Signal()
    recording_finished=Signal(bool)
    def __init__(self, pill, standby, config, macros, app_index, reload_callback=None):
        super().__init__(); self.pill,self.standby,self.c,self.macros,self.index=pill,standby,config,macros,app_index; self.reload_callback=reload_callback; self.state="IDLE"; self.executor=ThreadPoolExecutor(max_workers=1); self.recorder=Recorder(config, self.recording_finished.emit); self.pill.level_source=lambda:self.recorder.rms; self.last_hotkey=0; self.hotkey=None; self.cancel=None; self.visual_generation=0
        self.worker_done.connect(self._finish); self.hotkey_requested.connect(self.toggle); self.cancel_requested.connect(self.cancel_recording); self.recording_finished.connect(self.finish_recording)
        self.result_timer=QTimer(self); self.result_timer.setSingleShot(True); self.result_timer.timeout.connect(self.pill.fade_hide)
    def register(self):
        if self.hotkey: keyboard.remove_hotkey(self.hotkey)
        self.hotkey=keyboard.add_hotkey(self.c["hotkey"],self.hotkey_pressed,suppress=False)
    def reload_config(self, show_result=True):
        """Apply edited YAML and replace the global hotkey without a restart."""
        try:
            if self.reload_callback: self.reload_callback()
            self.register()
            if show_result: self.result(True,"Config reloaded")
        except Exception:
            if show_result: self.result(False,"Invalid config")
    def hotkey_pressed(self): self.hotkey_requested.emit()
    def toggle(self):
        if time.monotonic()-self.last_hotkey<.4:return
        self.last_hotkey=time.monotonic()
        if self.state=="IDLE":
            try: self.visual_generation+=1; self.standby.hide(); self.standby.timer.stop(); self.state="LISTENING"; self.recorder.start(); self.cancel=keyboard.add_hotkey(self.c["cancel_key"],self.cancel_requested.emit,suppress=False); self.pill.show_mode("listening")
            except Exception: self.result(False,"No microphone")
        elif self.state=="LISTENING": self.finish_recording(self.recorder.started)
    def cancel_recording(self):
        if self.state=="LISTENING":
            self.recorder.stop(); self.cleanup_cancel(); self.state="IDLE"; self.pill.fade_hide()
            generation=self.visual_generation; QTimer.singleShot(160,lambda: self._show_standby(generation))
    def cleanup_cancel(self):
        if self.cancel: keyboard.remove_hotkey(self.cancel); self.cancel=None
    def finish_recording(self, spoken):
        if self.state!="LISTENING": return
        audio=self.recorder.stop(); self.cleanup_cancel()
        if not spoken: self.result(False,"Didn't catch that"); return
        self.state="PROCESSING"; self.pill.show_mode("processing"); self.executor.submit(self._process,audio).add_done_callback(lambda f:self.worker_done.emit(f.result() if not f.exception() else ActionResult(False,"Something went wrong")))
    def _process(self,audio):
        # STT injection is delayed until app wiring; keeping controller responsive if unavailable.
        return ActionResult(False,"Speech model unavailable")
    def execute_text(self,text):
        triggers={t:m["name"] for m in self.macros.get("macros",[]) for t in m.get("triggers",[])}; intent=parse(text,ParseContext(triggers,self.c["sites"],self.c["app_aliases"])); return self.execute(intent)
    def execute(self,intent):
        if intent.kind == "meta":
            if intent.meta == "refresh_apps":
                from .paths import DATA_DIR
                self.index.update(apps.build_index(DATA_DIR / "apps_cache.json")); return ActionResult(True,"Apps refreshed")
            self.reload_config(show_result=False); return ActionResult(True,"Config reloaded")
        if intent.kind == "macro":
            macro=next((m for m in self.macros.get("macros",[]) if m.get("name")==intent.arg),None)
            if not macro: return ActionResult(False,"Macro not found")
            succeeded=False
            for step in macro.get("steps",[]):
                try:
                    key,value=next(iter(step.items()))
                    if key=="open_url": web.open_url(value)
                    elif key=="search": web.google(value)
                    elif key=="open_file": os.startfile(value)
                    elif key=="run": subprocess.Popen(value,shell=False)
                    elif key=="wait": time.sleep(float(value))
                    elif key=="open_app":
                        hit=best_match(value,list(self.index),self.c["matching"]["app_min_score"])
                        if not hit: continue
                        apps.launch(self.index[hit[0]])
                    else: continue
                    succeeded=True
                except Exception: continue
            return ActionResult(succeeded, intent.arg.title() if succeeded else "Macro failed")
        if intent.kind == "web_search": web.google(intent.arg); return ActionResult(True,"Searching Google")
        if intent.kind == "fallback":
            app_hit=best_match(intent.arg,list(self.index),self.c["matching"]["fallback_app_min_score"])
            if app_hit:
                apps.launch(self.index[app_hit[0]]); return ActionResult(True,f"Opening {app_hit[0].title()}")
            path=files.search(intent.arg,False,self.c)
            if path:
                os.startfile(path); return ActionResult(True,f"Opening {os.path.basename(path)}")
            web.google(intent.arg); return ActionResult(True,"Searching Google")
        if intent.kind=="site_search": web.open_url(self.c["sites"][intent.site]["search"].format(q=quote_plus(intent.arg))); return ActionResult(True,f"Searching {intent.site.title()}")
        if intent.kind=="open":
            name=self.c["app_aliases"].get(intent.arg,intent.arg); match=best_match(name,list(self.index),self.c["matching"]["app_min_score"])
            if match: apps.launch(self.index[match[0]]); return ActionResult(True,f"Opening {match[0].title()}")
            if name in self.c["sites"]: web.open_url(self.c["sites"][name]["home"]); return ActionResult(True,f"Opening {name.title()}")
            path=files.search(name,False,self.c)
            if path: os.startfile(path); return ActionResult(True,f"Opening {os.path.basename(path)}")
            web.google(name); return ActionResult(True,"Searching Google")
        if intent.kind in ("find_file","find_folder","reveal"):
            path=files.search(intent.arg,intent.kind=="find_folder",self.c)
            if not path:
                web.google(intent.arg)
                return ActionResult(True,"Searching Google")
            if intent.kind=="reveal": files.reveal(path); return ActionResult(True,f"Showing {os.path.basename(path)}")
            os.startfile(path); return ActionResult(True,f"Opening {os.path.basename(path)}")
        return ActionResult(False,"Command not available")
    def _finish(self,result): self.result(result.ok,result.message)
    def result(self,ok,msg):
        self.state="RESULT"; self.pill.show_mode("result",msg,not ok); self.result_timer.start(self.c["ui"]["result_display_ms"])
        generation=self.visual_generation
        QTimer.singleShot(self.c["ui"]["result_display_ms"]+160,lambda: self._to_idle(generation))
    def _to_idle(self,generation):
        if generation != self.visual_generation: return
        self.state="IDLE"; self._show_standby(generation)
    def _show_standby(self,generation):
        if generation == self.visual_generation and self.state == "IDLE": self.standby.show_standby()
