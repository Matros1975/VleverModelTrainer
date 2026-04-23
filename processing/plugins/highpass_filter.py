from __future__ import annotations

from pedalboard import HighpassFilter, Pedalboard

from ._pedalboard_util import apply_pedalboard
from ..base import AudioData, AudioPlugin


class HighpassFilterPlugin(AudioPlugin):
    name = "highpass_filter"

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.cutoff_hz = float(params.get("cutoff_hz", 80.0))

    def process(self, audio: AudioData) -> AudioData:
        arr, sr = audio
        board = Pedalboard([HighpassFilter(cutoff_frequency_hz=self.cutoff_hz)])
        result, _ = apply_pedalboard(arr, sr, board)
        return result, sr
