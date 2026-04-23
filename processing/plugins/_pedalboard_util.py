from __future__ import annotations

import numpy as np
from pedalboard import Pedalboard


def apply_pedalboard(
    arr: np.ndarray, sr: int, board: Pedalboard
) -> tuple[np.ndarray, int]:
    """Run a pedalboard effect chain on a mono (N,) or multi-channel (N, C) float32 array.

    pedalboard requires (channels, samples) layout and float32 dtype.
    This helper handles the transpose in/out so callers don't have to.
    """
    if arr.ndim == 1:
        pb_in = arr[np.newaxis, :]   # (1, N)
    else:
        pb_in = arr.T                # (C, N)

    pb_out = board(pb_in.astype(np.float32), sr)  # (C, N)

    if pb_out.shape[0] == 1:
        return pb_out[0], sr                        # back to (N,)
    return pb_out.T.astype(np.float32), sr          # back to (N, C)
