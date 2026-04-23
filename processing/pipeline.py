from __future__ import annotations

import asyncio
import importlib
import logging
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf
import yaml

from .base import AudioData, AudioPlugin

logger = logging.getLogger(__name__)

# Maps the YAML 'plugin:' key to the dotted import path of its class.
# Add a new plugin here + create its module — nothing else needs to change.
_PLUGIN_REGISTRY: dict[str, str] = {
    "to_mono":         "processing.plugins.to_mono.ToMonoPlugin",
    "trim_silence":    "processing.plugins.trim_silence.TrimSilencePlugin",
    "noise_reduction": "processing.plugins.noise_reduction.NoiseReductionPlugin",
    "highpass_filter": "processing.plugins.highpass_filter.HighpassFilterPlugin",
    "normalize":       "processing.plugins.normalize.NormalizePlugin",
    "resample":        "processing.plugins.resample.ResamplePlugin",
    "voice_enhance":   "processing.plugins.voice_enhance.VoiceEnhancePlugin",
}

_CONFIG_PATH = Path(__file__).parent / "processing_config.yaml"


def _load_config(config_path: Path = _CONFIG_PATH) -> dict:
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _import_class(dotted_path: str) -> type[AudioPlugin]:
    module_path, class_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _build_pipeline(cfg: dict) -> list[AudioPlugin]:
    plugins: list[AudioPlugin] = []
    for entry in cfg.get("pipeline", []):
        plugin_name = entry["plugin"]
        if not entry.get("enabled", True):
            logger.debug("Plugin '%s' is disabled — skipping.", plugin_name)
            continue
        if plugin_name not in _PLUGIN_REGISTRY:
            raise ValueError(
                f"Unknown plugin '{plugin_name}'. "
                f"Available plugins: {sorted(_PLUGIN_REGISTRY)}"
            )
        cls = _import_class(_PLUGIN_REGISTRY[plugin_name])
        params: dict = entry.get("params") or {}
        plugins.append(cls(params))
        logger.debug("Loaded plugin: %s", plugin_name)
    return plugins


def _run_pipeline_sync(input_path: Path, output_path: Path) -> None:
    """Blocking pipeline execution — intended to run in a thread pool."""
    cfg = _load_config()
    pipeline = _build_pipeline(cfg)

    # librosa.load with sr=None preserves original sample rate.
    # mono=False keeps original channel layout; to_mono plugin handles collapsing.
    # OGG/Opus files require the audioread/ffmpeg backend — ensure ffmpeg is installed.
    arr, sr = librosa.load(str(input_path), sr=None, mono=False, dtype=np.float32)

    channels = arr.shape[0] if arr.ndim > 1 else 1
    duration = (arr.shape[-1] if arr.ndim > 1 else len(arr)) / sr
    logger.info(
        "Starting pipeline: %s | sr=%d Hz | ch=%d | %.2f s",
        input_path.name, sr, channels, duration,
    )

    audio: AudioData = (arr, sr)
    for plugin in pipeline:
        prev_sr = audio[1]
        try:
            audio = plugin.process(audio)
        except Exception:
            logger.exception(
                "Plugin '%s' raised an exception on %s — aborting pipeline.",
                plugin.name, input_path.name,
            )
            raise
        new_arr, new_sr = audio
        logger.debug(
            "  [%s] shape=%s sr=%d->%d",
            plugin.name, new_arr.shape, prev_sr, new_sr,
        )

    final_arr, final_sr = audio
    # Ensure float32 and clamp to valid PCM range before writing
    final_arr = np.clip(final_arr.astype(np.float32), -1.0, 1.0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(output_path), final_arr, final_sr, subtype="PCM_16")

    out_duration = len(final_arr) / final_sr
    logger.info(
        "Pipeline complete: %s -> %s | sr=%d Hz | %.2f s",
        input_path.name, output_path.name, final_sr, out_duration,
    )


async def process_audio(input_path: Path, output_path: Path) -> None:
    """Async entry point used by bot.py.

    Offloads the blocking pipeline to the default thread-pool executor via
    asyncio.to_thread so the Telegram event loop is never blocked.
    """
    await asyncio.to_thread(_run_pipeline_sync, input_path, output_path)
