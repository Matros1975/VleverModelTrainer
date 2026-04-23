from __future__ import annotations

import logging

import numpy as np
import torch

from ..base import AudioData, AudioPlugin

logger = logging.getLogger(__name__)


class VoiceEnhancePlugin(AudioPlugin):
    """AI-powered bandwidth restoration via Resemble Enhance.

    Disabled by default in processing_config.yaml.
    Enable only when a GPU is available — CPU inference takes 10–30 s per clip.
    """

    name = "voice_enhance"

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.nfe = int(params.get("nfe", 64))
        self.solver = str(params.get("solver", "midpoint"))
        self.lambd = float(params.get("lambd", 0.9))
        self.tau = float(params.get("tau", 0.5))
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def process(self, audio: AudioData) -> AudioData:
        try:
            from resemble_enhance.enhancer.inference import enhance
        except ImportError as exc:
            raise ImportError(
                "resemble-enhance is not installed. "
                "Install it with: pip install -r requirements-enhance.txt "
                "(note: requires torch==2.1.1 and a GPU)."
            ) from exc

        arr, sr = audio

        if self._device.type == "cpu":
            logger.warning(
                "voice_enhance: running on CPU — this may take 10–30 s per clip. "
                "Consider disabling this plugin or using a GPU."
            )

        wav_tensor = torch.from_numpy(arr).to(self._device)
        enhanced, out_sr = enhance(
            wav_tensor,
            sr,
            self._device,
            nfe=self.nfe,
            solver=self.solver,
            lambd=self.lambd,
            tau=self.tau,
        )

        result = enhanced.cpu().numpy().astype(np.float32)
        logger.debug("voice_enhance: done on %s, out_sr=%d.", self._device, int(out_sr))
        return result, int(out_sr)
