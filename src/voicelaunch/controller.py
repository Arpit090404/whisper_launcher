"""The single owner of VoiceLaunch's command and dictation state machines."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
import os, subprocess, time
from urllib.parse import quote_plus
import keyboard
from PySide6.QtCore import QObject, QMimeData, QTimer, Signal
from PySide6.QtWidgets import QApplication
from .audio import Recorder
from .intents import ParseContext, parse
from .matching import best_match
from .actions import ActionResult
from .actions import apps, files, web


class Controller(QObject):
    command_done = Signal(object)
    dictation_done = Signal(str)
    hotkey_requested = Signal()
    dictation_requested = Signal()
    dictation_released = Signal()
    cancel_requested = Signal()
    recording_finished = Signal(bool)

    def __init__(self, pill, config, macros, app_index, reload_callback=None):
        super().__init__()
        self.pill, self.c, self.macros, self.index = pill, config, macros, app_index
        self.reload_callback = reload_callback
        self.state = "IDLE"
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.recorder = Recorder(config, self.recording_finished.emit)
        self.pill.level_source = lambda: self.recorder.rms
        self.hotkey = self.cancel = None
        self.dictation_hook = None
        self.last_hotkey = 0.0
        self.generation = 0
        self._process_command = lambda _: ActionResult(False, "Speech model unavailable")
        self._process_dictation = lambda _: ""
        self.command_done.connect(self._finish_command)
        self.dictation_done.connect(self._finish_dictation)
        self.hotkey_requested.connect(self.toggle_command)
        self.dictation_requested.connect(self.toggle_dictation)
        self.dictation_released.connect(self.finish_dictation_on_release)
        self.cancel_requested.connect(self.cancel_recording)
        self.recording_finished.connect(self.finish_recording)
        self.result_timer = QTimer(self)
        self.result_timer.setSingleShot(True)
        self.result_timer.timeout.connect(self.pill.fade_hide)

    def register(self):
        if self.hotkey:
            keyboard.remove_hotkey(self.hotkey)
        if self.dictation_hook:
            keyboard.unhook(self.dictation_hook)
            self.dictation_hook = None
        self.hotkey = keyboard.add_hotkey(self.c["hotkey"], self.hotkey_requested.emit, suppress=False)
        dictation_key = self.c["dictation_hotkey"].strip()
        if "+" in dictation_key:
            raise ValueError("dictation_hotkey must be one key (for example: f8)")
        # One low-level hook receives both transitions.  Registering press and
        # release separately can lose the key-up event when the press is suppressed.
        self.dictation_hook = keyboard.hook_key(
            dictation_key, self._on_dictation_key_event, suppress=True
        )

    def _on_dictation_key_event(self, event):
        """Forward F8 transitions to Qt's main thread without touching UI here."""
        if event.event_type == keyboard.KEY_DOWN:
            self.dictation_requested.emit()
        elif event.event_type == keyboard.KEY_UP:
            self.dictation_released.emit()
        return False

    def reload_config(self, show_result=True):
        try:
            if self.reload_callback: self.reload_callback()
            self.register()
            if show_result: self.result(True, "Config reloaded")
        except Exception:
            if show_result: self.result(False, "Invalid config")

    def _begin(self, mode: str):
        self.generation += 1
        self.pill.hide_standby()
        self.state = mode
        endpointing = self.c["endpointing"] if mode == "LISTENING" else {
            **self.c["endpointing"], **self.c["dictation"]
        }
        self.recorder.start(endpointing)
        self.cancel = keyboard.add_hotkey(self.c["cancel_key"], self.cancel_requested.emit, suppress=False)
        self.pill.show_mode("listening" if mode == "LISTENING" else "dictating")

    def toggle_command(self):
        if time.monotonic() - self.last_hotkey < 0.4: return
        self.last_hotkey = time.monotonic()
        try:
            if self.state == "IDLE": self._begin("LISTENING")
            elif self.state == "LISTENING": self.finish_recording(self.recorder.started)
        except Exception:
            self.result(False, "No microphone")

    def toggle_dictation(self):
        if time.monotonic() - self.last_hotkey < 0.4: return
        self.last_hotkey = time.monotonic()
        try:
            if self.state == "IDLE": self._begin("DICTATING")
        except Exception:
            self.result(False, "No microphone")

    def finish_dictation_on_release(self):
        """Push-to-talk: pressing begins capture; releasing submits it."""
        if self.state == "DICTATING":
            self.finish_recording(self.recorder.started)

    def cleanup_cancel(self):
        if self.cancel:
            keyboard.remove_hotkey(self.cancel)
            self.cancel = None

    def cancel_recording(self):
        if self.state not in ("LISTENING", "DICTATING"): return
        self.recorder.stop(); self.cleanup_cancel(); self.state = "IDLE"
        self.pill.fade_hide(); generation = self.generation
        QTimer.singleShot(180, lambda: self._return_idle(generation))

    def finish_recording(self, spoken: bool):
        if self.state not in ("LISTENING", "DICTATING"): return
        previous_state = self.state
        audio = self.recorder.stop(); self.cleanup_cancel()
        if not spoken:
            self.result(False, "Didn't catch that")
            return
        self.state = "PROCESSING"; self.pill.show_mode("processing")
        if previous_state == "DICTATING":
            future = self.executor.submit(self._process_dictation, audio)
            future.add_done_callback(lambda f: self.dictation_done.emit(f.result() if not f.exception() else ""))
        else:
            future = self.executor.submit(self._process_command, audio)
            future.add_done_callback(lambda f: self.command_done.emit(f.result() if not f.exception() else ActionResult(False, "Something went wrong")))

    def _finish_command(self, result: ActionResult):
        self.result(result.ok, result.message)

    def _copy_mime_data(self):
        original = QMimeData()
        source = QApplication.clipboard().mimeData()
        for fmt in source.formats(): original.setData(fmt, source.data(fmt))
        return original

    def _finish_dictation(self, text: str):
        if not text.strip():
            self.result(False, "Didn't catch that")
            return
        clipboard = QApplication.clipboard()
        previous = self._copy_mime_data()
        clipboard.setText(text)
        # Keyboard paste preserves the currently focused app and works in rich text fields.
        keyboard.send("ctrl+v")
        QTimer.singleShot(self.c["dictation"].get("restore_clipboard_ms", 180),
                          lambda: clipboard.setMimeData(previous))
        self.result(True, "Typed")

    def execute_text(self, text):
        triggers = {t: m["name"] for m in self.macros.get("macros", []) for t in m.get("triggers", [])}
        return self.execute(parse(text, ParseContext(triggers, self.c["sites"], self.c["app_aliases"])))

    def execute(self, intent):
        if intent.kind == "meta":
            if intent.meta == "refresh_apps":
                from .paths import DATA_DIR
                self.index.update(apps.build_index(DATA_DIR / "apps_cache.json")); return ActionResult(True, "Apps refreshed")
            self.reload_config(show_result=False); return ActionResult(True, "Config reloaded")
        if intent.kind == "macro":
            macro = next((m for m in self.macros.get("macros", []) if m.get("name") == intent.arg), None)
            if not macro: return ActionResult(False, "Macro not found")
            succeeded = False
            for step in macro.get("steps", []):
                try:
                    key, value = next(iter(step.items()))
                    if key == "open_url": web.open_url(value)
                    elif key == "search": web.google(value)
                    elif key == "open_file": os.startfile(value)
                    elif key == "run": subprocess.Popen(value, shell=False)
                    elif key == "wait": time.sleep(float(value))
                    elif key == "open_app":
                        hit = best_match(value, list(self.index), self.c["matching"]["app_min_score"])
                        if not hit: continue
                        apps.launch(self.index[hit[0]])
                    else: continue
                    succeeded = True
                except Exception: continue
            return ActionResult(succeeded, intent.arg.title() if succeeded else "Macro failed")
        if intent.kind == "web_search": web.google(intent.arg); return ActionResult(True, "Searching Google")
        if intent.kind == "fallback":
            hit = best_match(intent.arg, list(self.index), self.c["matching"]["fallback_app_min_score"])
            if hit: apps.launch(self.index[hit[0]]); return ActionResult(True, f"Opening {hit[0].title()}")
            path = files.search(intent.arg, False, self.c)
            if path: os.startfile(path); return ActionResult(True, f"Opening {os.path.basename(path)}")
            web.google(intent.arg); return ActionResult(True, "Searching Google")
        if intent.kind == "site_search": web.open_url(self.c["sites"][intent.site]["search"].format(q=quote_plus(intent.arg))); return ActionResult(True, f"Searching {intent.site.title()}")
        if intent.kind == "open":
            name = self.c["app_aliases"].get(intent.arg, intent.arg); hit = best_match(name, list(self.index), self.c["matching"]["app_min_score"])
            if hit: apps.launch(self.index[hit[0]]); return ActionResult(True, f"Opening {hit[0].title()}")
            if name in self.c["sites"]: web.open_url(self.c["sites"][name]["home"]); return ActionResult(True, f"Opening {name.title()}")
            path = files.search(name, False, self.c)
            if path: os.startfile(path); return ActionResult(True, f"Opening {os.path.basename(path)}")
            web.google(name); return ActionResult(True, "Searching Google")
        if intent.kind in ("find_file", "find_folder", "reveal"):
            path = files.search(intent.arg, intent.kind == "find_folder", self.c)
            if not path: web.google(intent.arg); return ActionResult(True, "Searching Google")
            if intent.kind == "reveal": files.reveal(path); return ActionResult(True, f"Showing {os.path.basename(path)}")
            os.startfile(path); return ActionResult(True, f"Opening {os.path.basename(path)}")
        return ActionResult(False, "Command not available")

    def result(self, ok, message):
        self.state = "RESULT"; self.pill.show_mode("result", message, not ok)
        self.result_timer.start(self.c["ui"]["result_display_ms"]); generation = self.generation
        QTimer.singleShot(self.c["ui"]["result_display_ms"] + 180, lambda: self._return_idle(generation))

    def _return_idle(self, generation):
        if generation != self.generation: return
        self.state = "IDLE"; self.pill.show_standby()
