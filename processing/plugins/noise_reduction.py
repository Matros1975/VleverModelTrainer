from __future__ import annotations

import logging
import threading

import numpy as np

from ..base import AudioData, AudioPlugin

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_model = None
_df_state = None


def _get_df():
    global _model, _df_state
    if _model is None:
        with _lock:
            if _model is None:
                from df.enhance import init_df

                _model, _df_state, _ = init_df()
                logger.info("DeepFilterNet model loaded (sr=%d Hz).", _df_state.sr())
    return _model, _df_state


class NoiseReductionPlugin(AudioPlugin):
    name = "noise_reduction"

    def __init__(self, params: dict) -> None:
        super().__init__(params)
        self.atten_lim_db = float(params.get("atten_lim_db", 15.0))

    def process(self, audio: AudioData) -> AudioData:
        import torch
        import librosa
        from df.enhance import enhance

        arr, sr = audio
        model, df_state = _get_df()
        df_sr = df_state.sr()  # 48 000 Hz

        # Resample to model's required sample rate if needed
        if sr != df_sr:
            arr_in = librosa.resample(arr, orig_sr=sr, target_sr=df_sr).astype(np.float32)
        else:
            arr_in = arr.astype(np.float32)

        # enhance() expects a (channels, samples) tensor
        audio_tensor = torch.from_numpy(arr_in).unsqueeze(0)  # (1, N)

        with torch.no_grad():
            enhanced = enhance(model, df_state, audio_tensor, atten_lim_db=self.atten_lim_db)

        result = enhanced.squeeze(0).numpy().astype(np.float32)
        logger.debug("noise_reduction: processed %d samples at %d Hz.", len(result), df_sr)
        return result, df_sr  # downstream resample plugin brings to final target SR
