from __future__ import annotations
import math, threading, time
import numpy as np
import sounddevice as sd

def rms_to_level(rms: float) -> float:
    return min(1., max(0., (20*math.log10(rms+1e-6)+55)/35))

class Recorder:
    def __init__(self, config: dict, on_end):
        self.c=config; self.on_end=on_end; self.blocks=[]; self.rms=0.; self.running=False; self.started=False; self.started_at=0.; self.silent=0.; self.lock=threading.Lock(); self.stream=None
    def start(self, endpointing: dict | None = None):
        self.blocks=[]; self.rms=0.; self.running=True; self.started=False; self.started_at=time.monotonic(); self.silent=0.
        self.endpointing=endpointing or self.c["endpointing"]
        a=self.c["audio"]; self.stream=sd.InputStream(samplerate=a["sample_rate"],channels=1,dtype="float32",blocksize=a["block_samples"],device=a["input_device"],callback=self._callback); self.stream.start()
    def _callback(self, indata, frames, _time, status):
        if not self.running: return
        block=indata[:,0].copy(); rms=float(np.sqrt(np.mean(block*block)))
        with self.lock: self.blocks.append(block); self.rms=rms
        ep=self.endpointing; elapsed=time.monotonic()-self.started_at
        if rms>ep["rms_threshold"]: self.started=True; self.silent=0.
        elif self.started: self.silent+=frames/self.c["audio"]["sample_rate"]
        if (self.started and self.silent*1000>=ep["silence_ms"]) or elapsed>=ep["max_record_s"] or (not self.started and elapsed>=ep["no_speech_timeout_s"]): self.on_end(self.started)
    def stop(self) -> np.ndarray:
        self.running=False
        if self.stream: self.stream.stop(); self.stream.close(); self.stream=None
        with self.lock: return np.concatenate(self.blocks) if self.blocks else np.array([],dtype=np.float32)
