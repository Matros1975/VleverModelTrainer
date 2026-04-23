from __future__ import annotations

import logging

import numpy as np
import pyloudnorm as pyln

from ..base import AudioData, AudioPlugin

logger = logging.getLogger(__name__)


class NormalizePlugin(AudioPlugin):
    name = "normalize"

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.target_lufs = float(params.get("target_lufs", -23.0))

    def process(self, audio: AudioData) -> AudioData:
        arr, sr = audio
        meter = pyln.Meter(sr)

        # pyloudnorm measures in float64 for precision
        arr64 = arr.astype(np.float64)
        loudness = meter.integrated_loudness(arr64)

        # integrated_loudness() returns -inf for clips shorter than ~400 ms
        if not np.isfinite(loudness):
            logger.warning(
                "normalize: loudness is %s (clip too short?), skipping normalization.", loudness
            )
            return audio

        normalized = pyln.normalize.loudness(arr64, loudness, self.target_lufs)
        # Clip to prevent inter-sample peaks from exceeding ±1.0
        return np.clip(normalized, -1.0, 1.0).astype(np.float32), sr
