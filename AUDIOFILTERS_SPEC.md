# Audio Processing Module — Specification

## Purpose

Post-process raw voice recordings collected by the Telegram bot before using them as TTS model training data. Each collected `.ogg` file is run through a configurable plugin pipeline and saved as a cleaned `.wav` file.

---

## Directory layout

```
Data/
├── Collected/
│   ├── Audio/          raw .ogg files from Telegram
│   └── status.json     tracks raw collected files
└── Processed/
    ├── Audio/          processed .wav files (p_ prefix)
    └── status.json     tracks processed files
```

---

## File naming

| Stage | Example |
|-------|---------|
| Raw (collected) | `20260422_143045_the_weather_is_nice_today.ogg` |
| Processed | `p_20260422_143045_the_weather_is_nice_today.wav` |

Processed filename = `"p_"` + raw stem + `".wav"`.

---

## Status files

### `Data/Collected/status.json`
Already maintained by the bot. Unchanged.
```json
[
  {
    "phrase": "The weather is nice today.",
    "media_file": "20260422_143045_the_weather_is_nice_today.ogg",
    "collected_at": "2026-04-22T14:30:45+00:00"
  }
]
```

### `Data/Processed/status.json`
New. Written by the bot after each successful processing run.
```json
[
  {
    "phrase": "The weather is nice today.",
    "raw_file": "20260422_143045_the_weather_is_nice_today.ogg",
    "processed_file": "p_20260422_143045_the_weather_is_nice_today.wav",
    "processed_at": "2026-04-22T14:30:52+00:00"
  }
]
```

---

## Processing pipeline

### Trigger
Auto-triggered by the bot immediately after each voice file is downloaded. Runs in a background thread (`asyncio.to_thread`) so it does not block the Telegram event loop. If processing fails, the raw `.ogg` and its collected-status entry are preserved unchanged; the processed-status entry is NOT written.

### Audio representation between plugins
Each plugin receives and returns `(numpy.ndarray[float32], sample_rate: int)`.  
Shape is `(N,)` mono throughout (enforced by `to_mono` as the first plugin).  
No plugin mutates its input array in-place.

### Plugin pipeline (in order)

| # | Name | Library | Enabled | Purpose |
|---|------|---------|---------|---------|
| 1 | `to_mono` | numpy | yes | Average stereo channels to single channel |
| 2 | `trim_silence` | silero-vad | yes | ML-based voice activity detection; trims leading/trailing non-speech |
| 3 | `noise_reduction` | DeepFilterNet | yes | Neural noise suppression |
| 4 | `highpass_filter` | pedalboard | yes | Remove low-frequency rumble (mic vibration, handling noise) |
| 5 | `normalize` | pyloudnorm | yes | LUFS loudness normalization for consistent training levels |
| 6 | `resample` | librosa | yes | Resample to target sample rate (default 22050 Hz) |
| 7 | `voice_enhance` | resemble-enhance | **no** | AI bandwidth restoration; enable only when GPU is available |

### Configuration
All plugins, their order, and their parameters are defined in `processing/processing_config.yaml`. The pipeline re-reads this file on every run — changes take effect immediately without restarting the bot.

---

## Plugin details

### `to_mono`
- Averages all channels along axis 1
- Passthrough if audio is already `(N,)` mono
- No configurable parameters

### `trim_silence` — [snakers4/silero-vad](https://github.com/snakers4/silero-vad)
- ML-based Voice Activity Detection; far more accurate than energy-threshold trimming
- Requires 16 kHz input — plugin temporarily downsamples, gets speech timestamps, maps indices back to original sample rate before cropping
- If no speech detected (all silence), returns audio unchanged
- **Parameters:** `threshold` (VAD confidence 0–1, default 0.5), `min_silence_duration_ms` (default 100)

### `noise_reduction` — [Rikorose/DeepFilterNet](https://github.com/Rikorose/DeepFilterNet)
- State-of-the-art deep neural network noise suppressor; works well on CPU
- Downloads ~50 MB model on first use (cached automatically)
- Operates at 48 kHz internally; handles resampling itself
- **Parameters:** `atten_lim_db` (max noise attenuation in dB, default 15)

### `highpass_filter` — [spotify/pedalboard](https://github.com/spotify/pedalboard)
- Professional-grade JUCE-based DSP
- Removes frequencies below the cutoff (default 80 Hz)
- **Parameters:** `cutoff_hz` (default 80)

### `normalize` — pyloudnorm
- ITU-R BS.1770-4 integrated loudness measurement + normalization
- Guards against `-inf` loudness on very short clips (< ~400 ms); returns audio unchanged in that case
- **Parameters:** `target_lufs` (default −23.0; use −16.0 for louder speech)

### `resample` — librosa
- High-quality resampling to target sample rate
- Passthrough if already at target SR
- **Parameters:** `target_sr` (default 22050), `res_type` (default `kaiser_best`)

### `voice_enhance` — [resemble-ai/resemble-enhance](https://github.com/resemble-ai/resemble-enhance)
- AI-powered denoiser + bandwidth restorer trained on 44.1 kHz speech
- Model size ~600 MB; slow on CPU (10–30 s per clip); **disabled by default**
- Enable in `processing_config.yaml` when GPU is available
- **Parameters:** `nfe` (quality/speed trade-off, default 64), `solver` (default `midpoint`)

---

## Module structure

```
processing/
├── __init__.py
├── base.py                   AudioPlugin ABC + AudioData type alias
├── pipeline.py               registry, _run_pipeline_sync, async process_audio()
├── processing_config.yaml    pipeline configuration
└── plugins/
    ├── __init__.py
    ├── _pedalboard_util.py   shared (N,)↔(C,N) transpose helper for pedalboard
    ├── to_mono.py
    ├── trim_silence.py
    ├── noise_reduction.py
    ├── highpass_filter.py
    ├── normalize.py
    ├── resample.py
    └── voice_enhance.py
```

---

## Dependencies added

```
torch>=2.0
librosa>=0.10
soundfile>=0.12
deepfilternet>=0.5
silero-vad>=5.0
resemble-enhance>=0.1
pedalboard>=0.9
pyloudnorm>=0.1
pyyaml>=6.0
```

---

## Quick-test (without bot)

```bash
python3 -c "
import asyncio
from pathlib import Path
from processing.pipeline import process_audio
asyncio.run(process_audio(
    Path('Data/Collected/Audio/<file>.ogg'),
    Path('Data/Processed/Audio/p_<file>.wav')
))"
```
