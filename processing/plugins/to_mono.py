from __future__ import annotations

import numpy as np

from ..base import AudioData, AudioPlugin


class ToMonoPlugin(AudioPlugin):
    name = "to_mono"

    def __init__(self, params: dict) -> None:
        super().__init__(params)

    def process(self, audio: AudioData) -> AudioData:
        arr, sr = audio
        if arr.ndim == 1:
            return audio
        return arr.mean(axis=1).astype(np.float32), sr
