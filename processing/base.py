from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

# Canonical in-memory audio representation passed between plugins.
# Shape: (N,) for mono float32 array; sr: sample rate in Hz.
AudioData = tuple[np.ndarray, int]


class AudioPlugin(ABC):
    name: str

    def __init__(self, params: dict) -> None:
        self.params = params

    @abstractmethod
    def process(self, audio: AudioData) -> AudioData: ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(params={self.params!r})"
