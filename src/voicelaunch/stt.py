from __future__ import annotations
import re, time
import numpy as np
from faster_whisper import WhisperModel


def prepare_audio(audio: np.ndarray, sample_rate: int, trim_threshold: float = 0.0035,
                  padding_ms: int = 180) -> np.ndarray:
    """Remove capture dead-air while preserving a small amount around speech.

    This is deliberately an amplitude trim, not noise suppression or a second
    VAD model.  It reduces decoder work and cannot rewrite what was spoken.
    """
    samples = np.asarray(audio, dtype=np.float32).reshape(-1)
    if not len(samples):
        return samples
    # A small DC offset can make a quiet microphone look like speech.
    samples = samples - np.mean(samples, dtype=np.float32)
    window = max(1, sample_rate // 50)  # 20 ms: responsive without per-sample work.
    usable = len(samples) - (len(samples) % window)
    if not usable:
        return np.ascontiguousarray(samples)
    frames = samples[:usable].reshape(-1, window)
    # einsum reduces each frame directly, avoiding a second full-size audio
    # allocation while the user holds the dictation key.
    active = np.sqrt(np.einsum("ij,ij->i", frames, frames) / window) >= trim_threshold
    if not np.any(active):
        return np.ascontiguousarray(samples)
    first, last = np.flatnonzero(active)[[0, -1]]
    padding = int(sample_rate * padding_ms / 1000)
    start = max(0, first * window - padding)
    end = min(len(samples), (last + 1) * window + padding)
    return np.ascontiguousarray(samples[start:end])


class STT:
    def __init__(self, config, download_root): self.c=config; self.root=str(download_root); self.model=None
    def load(self):
        c=self.c["stt"]; self.model=WhisperModel(c["model"],device=c["device"],compute_type=c["compute_type"],cpu_threads=c["cpu_threads"],download_root=self.root)
        list(self.model.transcribe(np.zeros(16000,dtype=np.float32), language=c["language"], beam_size=1, vad_filter=True)[0])
    def transcribe(self, audio, prompt="", dictation=False):
        start=time.perf_counter(); c=self.c["stt"]
        audio = prepare_audio(
            audio,
            self.c["audio"]["sample_rate"],
            c.get("trim_rms_threshold", 0.0035),
            c.get("trim_padding_ms", 180),
        )
        if not len(audio): return "", 0.0
        vad_silence_ms = c.get(
            "dictation_vad_silence_ms" if dictation else "command_vad_silence_ms", 550 if dictation else 300
        )
        # Launcher commands are short and normally contain an app name, so a
        # single beam returns them sooner. Dictation keeps the configured
        # wider search for better word recovery.
        beam_size = c.get("dictation_beam_size" if dictation else "command_beam_size", c["beam_size"])
        segments,_=self.model.transcribe(
            audio, language=c["language"], beam_size=beam_size, vad_filter=True,
            # Dictation gets a longer VAD hangover so short pauses and quiet
            # connecting words are not split away. Commands finish sooner.
            vad_parameters={"min_silence_duration_ms": vad_silence_ms},
            condition_on_previous_text=dictation, initial_prompt=prompt[:600],
            temperature=0.0, compression_ratio_threshold=2.4,
            no_speech_threshold=c.get("no_speech_threshold", 0.62),
        )
        text=" ".join(s.text.strip() for s in segments).strip()
        return text,(time.perf_counter()-start)*1000

def clean_dictation(text: str) -> str:
    """Make a transcript easier to read without changing its wording."""
    value=re.sub(r"\s+", " ", text).strip()
    # Only strip a run of hesitation at the very beginning; fillers in the
    # middle may be intentional and must remain in the transcript.
    value=re.sub(r"^(?:(?:um|uh|erm|you know)[, ]+)+", "", value, flags=re.I)
    if not value: return ""
    value=re.sub(r"\bi\b", "I", value)
    value=re.sub(r"\s+([,.;:!?])", r"\1", value)
    value=value[0].upper()+value[1:]
    # Whisper normally supplies sentence boundaries.  This merely fixes the
    # capitalization after boundaries it already identified.
    value=re.sub(r"([.!?]\s+)([a-z])", lambda match: match.group(1)+match.group(2).upper(), value)
    return value if value[-1] in ".!?…:;" else value+"."
