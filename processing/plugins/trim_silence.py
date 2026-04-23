from __future__ import annotations

import logging
import threading

import numpy as np
import torch

from ..base import AudioData, AudioPlugin

logger = logging.getLogger(__name__)

_VAD_SR = 16_000  # silero-vad requires 16 kHz input

_lock = threading.Lock()
_model = None


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from silero_vad import load_silero_vad

                _model = load_silero_vad()
                logger.info("Silero VAD model loaded.")
    return _model


class TrimSilencePlugin(AudioPlugin):
    name = "trim_silence"

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.threshold = float(params.get("threshold", 0.5))
        self.min_silence_duration_ms = int(params.get("min_silence_duration_ms", 100))

    def process(self, audio: AudioData) -> AudioData:
        from silero_vad import get_speech_timestamps
        import librosa

        arr, sr = audio

        # Silero VAD requires 16 kHz mono float32
        if sr != _VAD_SR:
            arr_16k = librosa.resample(arr, orig_sr=sr, target_sr=_VAD_SR).astype(np.float32)
        else:
            arr_16k = arr

        model = _get_model()
        timestamps = get_speech_timestamps(
            torch.from_numpy(arr_16k),
            model,
            sampling_rate=_VAD_SR,
            threshold=self.threshold,
            min_silence_duration_ms=self.min_silence_duration_ms,
        )

        if not timestamps:
            logger.warning("trim_silence: no speech detected — audio returned unchanged.")
            return audio

        # Map VAD sample indices back to original sample rate
        ratio = sr / _VAD_SR
        start = max(0, int(timestamps[0]["start"] * ratio))
        end = min(len(arr), int(timestamps[-1]["end"] * ratio))

        if end <= start:
            logger.warning(
                "trim_silence: degenerate crop [%d:%d] — audio returned unchanged.", start, end
            )
            return audio

        logger.debug("trim_silence: cropped %d -> %d samples (%.2f s removed)",
                     len(arr), end - start, (len(arr) - (end - start)) / sr)
        return arr[start:end], sr
