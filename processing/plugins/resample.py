from __future__ import annotations

import librosa
import numpy as np

from ..base import AudioData, AudioPlugin


class ResamplePlugin(AudioPlugin):
    name = "resample"

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.target_sr = int(params.get("target_sr", 22050))
        self.res_type = str(params.get("res_type", "kaiser_best"))

    def process(self, audio: AudioData) -> AudioData:
        arr, sr = audio
        if sr == self.target_sr:
            return audio
        resampled = librosa.resample(
            arr, orig_sr=sr, target_sr=self.target_sr, res_type=self.res_type
        )
        return resampled.astype(np.float32), self.target_sr
