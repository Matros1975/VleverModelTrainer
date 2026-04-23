# ModelTrainer

A Telegram bot that collects labeled voice recordings for TTS model training. It guides a single authorized user through a list of phrases, prompting them to record each one via Telegram voice messages. Each recording is automatically cleaned and enhanced by an audio processing pipeline before being saved as a training-ready WAV file.

---

## How it works

1. You send a trigger word (`start`, `next`, `go`, etc.) to the bot
2. The bot sends the next uncollected phrase from `Data/train_phrases.txt`
3. You record and send a voice message
4. The bot saves the raw OGG, replies "Thank you!", and immediately prompts the next phrase
5. In the background, the recording is processed through the audio pipeline and saved as a clean WAV

All phrase–filename mappings are tracked in JSON status files so collection can be paused and resumed at any time.

---

## Project structure

```
ModelTrainer/
├── bot.py                        Telegram bot — all handlers and conversation logic
├── config.py                     Paths and credentials (loaded from .env)
├── start_bot.sh                  Start script — activates venv and runs the bot
├── .env                          Secrets (not committed)
├── requirements.txt              Python dependencies
├── requirements-enhance.txt      Optional: resemble-enhance (requires GPU + torch 2.1.1)
├── Data/
│   ├── train_phrases.txt         One phrase per line; # lines are comments
│   ├── Collected/
│   │   ├── Audio/                Raw .ogg files from Telegram (UUID filenames)
│   │   └── status.json           Tracks raw collected files
│   └── Processed/
│       ├── Audio/                Processed .wav files (p_ prefix)
│       └── status.json           Tracks processed files
└── processing/
    ├── pipeline.py               Async entry point: process_audio()
    ├── processing_config.yaml    Pipeline configuration (hot-reloaded on every run)
    └── plugins/                  One file per plugin
```

---

## Setup

### 1. Create a Telegram bot

1. Open Telegram and start a chat with [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts to choose a name and username
3. BotFather will give you a **bot token** — copy it
4. Find your **chat ID**: start a chat with [@userinfobot](https://t.me/userinfobot) — it will reply with your numeric user ID

### 2. Clone and configure

```bash
git clone <repo-url>
cd ModelTrainer
```

Create a `.env` file with your credentials:

```bash
cp .env.example .env   # or create manually
```

```ini
BOT_TOKEN=<your bot token from BotFather>
ALLOWED_CHAT_ID=<your numeric Telegram user ID>
```

Only the user ID in `ALLOWED_CHAT_ID` can interact with the bot — all other messages are silently ignored.

### 3. Install dependencies

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> **Note:** `ffmpeg` must be installed on the system to decode OGG/Opus files from Telegram.
> - Ubuntu/Debian: `sudo apt install ffmpeg`
> - macOS: `brew install ffmpeg`

### 4. Add your phrases

Edit `Data/train_phrases.txt` — one phrase per line. Lines starting with `#` are treated as comments:

```
# Greetings
Hello, how are you today?
Good morning, I hope you have a great day.
# Weather
The weather is nice today.
```

### 5. Run the bot

```bash
./start_bot.sh
```

Or manually:

```bash
source .venv/bin/activate
python bot.py
```

---

## Connecting to the bot

Once running, open Telegram and send any of these trigger words to your bot:

```
start   begin   go   collect   next   continue   record
```

The bot will send the first uncollected phrase. Record it as a voice message and send it. The bot will confirm receipt and immediately send the next phrase. Repeat until all phrases are collected.

---

## Audio processing pipeline

Each voice recording is automatically processed after download. The pipeline is configured in `processing/processing_config.yaml` and re-reads itself on every run — you can change settings without restarting the bot.

| Step | Plugin | Library | Purpose |
|------|--------|---------|---------|
| 1 | `to_mono` | numpy | Convert stereo to mono |
| 2 | `trim_silence` | [silero-vad](https://github.com/snakers4/silero-vad) | ML-based silence trimming |
| 3 | `noise_reduction` | [DeepFilterNet](https://github.com/Rikorose/DeepFilterNet) | Neural noise suppression |
| 4 | `highpass_filter` | [pedalboard](https://github.com/spotify/pedalboard) | Remove low-frequency rumble |
| 5 | `normalize` | pyloudnorm | LUFS loudness normalization (−23 LUFS) |
| 6 | `resample` | librosa | Resample to target sample rate (22050 Hz) |
| 7 | `voice_enhance` | [resemble-enhance](https://github.com/resemble-ai/resemble-enhance) | AI bandwidth restoration *(disabled by default — GPU required)* |

Models are downloaded and cached automatically on first use (~50 MB for DeepFilterNet, ~2 MB for Silero VAD).

Raw `.ogg` files are always preserved. Processed `.wav` files are written to `Data/Processed/Audio/` with a `p_` filename prefix. If processing fails, only the raw status entry is kept.

### Enabling voice enhancement (GPU only)

```bash
.venv/bin/pip install torch==2.1.1 --index-url https://download.pytorch.org/whl/cu118
.venv/bin/pip install -r requirements-enhance.txt
```

Then set `enabled: true` for the `voice_enhance` plugin in `processing/processing_config.yaml`.

---

## Logs

The bot logs to both stdout and `bot.log` (rotating, max 10 MB, 3 backups). Each log line shows the sender's Telegram username, what was received, what was sent, and processing status:

```
2026-04-23 10:09:01 INFO     [IN ] @andrei: "start"
2026-04-23 10:09:01 INFO     [BOT→] Sent phrase [5/50]: "The weather is nice today."
2026-04-23 10:09:14 INFO     [IN ] @andrei: voice message (3s)
2026-04-23 10:09:14 INFO     File saved: a3f7c2d1...b8e4.ogg  (raw total: 5)
2026-04-23 10:09:14 INFO     Processing started: a3f7c2d1...b8e4.ogg
2026-04-23 10:09:22 INFO     Processing done:    a3f7c2d1...b8e4.ogg → p_a3f7c2d1...b8e4.wav
```

---

## Status files

### `Data/Collected/status.json`
```json
[
  {
    "phrase": "The weather is nice today.",
    "media_file": "a3f7c2d1b8e4....ogg",
    "collected_at": "2026-04-23T10:09:14+00:00"
  }
]
```

### `Data/Processed/status.json`
```json
[
  {
    "phrase": "The weather is nice today.",
    "raw_file": "a3f7c2d1b8e4....ogg",
    "processed_file": "p_a3f7c2d1b8e4....wav",
    "processed_at": "2026-04-23T10:09:22+00:00"
  }
]
```
