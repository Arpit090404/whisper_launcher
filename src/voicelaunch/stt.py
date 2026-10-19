from __future__ import annotations
import re, time
import numpy as np
from faster_whisper import WhisperModel
class STT:
    def __init__(self, config, download_root): self.c=config; self.root=str(download_root); self.model=None
    def load(self):
        c=self.c["stt"]; self.model=WhisperModel(c["model"],device=c["device"],compute_type=c["compute_type"],cpu_threads=c["cpu_threads"],download_root=self.root)
        list(self.model.transcribe(np.zeros(16000,dtype=np.float32), language=c["language"], beam_size=1, vad_filter=True)[0])
    def transcribe(self, audio, prompt="", dictation=False):
        start=time.perf_counter(); c=self.c["stt"]
        segments,_=self.model.transcribe(
            audio, language=c["language"], beam_size=c["beam_size"], vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 350},
            condition_on_previous_text=dictation, initial_prompt=prompt[:600],
            temperature=0.0, compression_ratio_threshold=2.4,
            no_speech_threshold=0.55,
        )
        text=" ".join(s.text.strip() for s in segments).strip()
        return text,(time.perf_counter()-start)*1000

def clean_dictation(text: str) -> str:
    """Conservative local cleanup: preserve words, repair only obvious speech noise."""
    value=re.sub(r"\s+", " ", text).strip()
    value=re.sub(r"^(?:(?:um|uh|erm|you know)[, ]+)+", "", value, flags=re.I)
    if not value: return ""
    value=value[0].upper()+value[1:]
    return value if value[-1] in ".!?…:;" else value+"."
