# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Does

ModelTrainer is a Telegram bot that collects labeled voice samples for ML model training. It guides a single authorized user through a list of phrases, prompting them to record each one, then stores the audio files locally with metadata.

## Running the Bot

```bash
# First-time setup
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run
.venv/bin/python bot.py
```

There are no tests or lint configuration. The bot runs until killed (Ctrl+C).

## Configuration

All configuration lives in `config.py`:
- `BOT_TOKEN` — Telegram bot token (currently hardcoded; should be moved to an env var)
- `ALLOWED_CHAT_ID` — only this Telegram user ID can interact with the bot (191406357)
- Directory paths under `Data/`

## Architecture

**Data flow:** User sends trigger word → bot sends phrase → user sends voice message → bot downloads audio → updates `status.json` → sends next phrase.

**Key files:**
- `bot.py` — all bot logic: handlers, file I/O helpers, audio download
- `config.py` — paths, credentials, `ensure_dirs()` called at startup
- `Data/train_phrases.txt` — one phrase per line; lines starting with `#` are comments
- `Data/Collected/status.json` — JSON array tracking collected samples: `{phrase, media_file, collected_at}`
- `Data/Collected/Audio/` — downloaded `.ogg` voice files
- `Data/Selected/Audio/` — post-processed/curated audio (populated externally)

**Handlers in `bot.py`:**
- `handle_start_command` — `/start` and `/collect` commands
- `handle_trigger` — text triggers (start, begin, go, collect, next, continue, record)
- `handle_audio` — processes incoming voice/audio messages, downloads, saves status
- `handle_fallback` — help text for unexpected messages
- `send_next_phrase` — shared helper that sends `[n/total] Please say this: <phrase>`

**Filename format:** `YYYYMMDD_HHMMSS_<sanitized_phrase>.ogg`
