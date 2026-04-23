#!/usr/bin/env python3
"""
ModelTrainer audio collection bot.

Conducts a Telegram conversation that collects voice samples for ML training:
  1. Andrei sends a trigger word ("start", "begin", etc.)
  2. Bot sends the next uncollected phrase from Data/train_phrases.txt
  3. Andrei records and sends a voice message
  4. Bot downloads the audio, updates Data/Collected/status.json, says "Thank you!"
  5. Immediately prompts the next phrase — loops until all phrases are collected.

Run: ./start_bot.sh   (or: .venv/bin/python bot.py)
Stop: Ctrl+C
"""

import asyncio
import json
import logging
import logging.handlers
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
from processing.pipeline import process_audio

# ── Logging setup: console + rotating file (max 10 MB, 3 backups) ─────────────

_LOG_FILE = Path(__file__).parent / "bot.log"
_fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(message)s")

_console = logging.StreamHandler()
_console.setFormatter(_fmt)

_file = logging.handlers.RotatingFileHandler(
    _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8"
)
_file.setFormatter(_fmt)

logging.basicConfig(level=logging.INFO, handlers=[_console, _file])
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Trigger keywords that start/continue a collection session
TRIGGER_WORDS = {"start", "begin", "go", "collect", "next", "continue", "record"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user_tag(update: Update) -> str:
    """Return a readable sender identifier: @username or 'First Last' or id:N."""
    user = update.effective_user
    if user is None:
        return "<unknown>"
    if user.username:
        return f"@{user.username}"
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p)
    return name if name else f"id:{user.id}"


# ── Data helpers ──────────────────────────────────────────────────────────────

def load_phrases() -> list[str]:
    if not config.PHRASES_FILE.exists():
        return []
    phrases = []
    for line in config.PHRASES_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            phrases.append(line)
    return phrases


def load_status() -> list[dict]:
    if not config.STATUS_FILE.exists():
        return []
    try:
        data = json.loads(config.STATUS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_status(records: list[dict]) -> None:
    config.STATUS_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def append_status(phrase: str, filename: str) -> int:
    records = load_status()
    records.append({
        "phrase": phrase,
        "media_file": filename,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    })
    save_status(records)
    return len(records)


def get_next_phrase() -> str | None:
    phrases = load_phrases()
    collected = {r["phrase"] for r in load_status()}
    for p in phrases:
        if p not in collected:
            return p
    return None


def generate_filename() -> str:
    return f"{uuid.uuid4().hex}.ogg"


def count_phrases() -> tuple[int, int]:
    """Return (collected, total)."""
    return len(load_status()), len(load_phrases())


def load_processed_status() -> list[dict]:
    if not config.PROCESSED_STATUS_FILE.exists():
        return []
    try:
        data = json.loads(config.PROCESSED_STATUS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_processed_status(records: list[dict]) -> None:
    config.PROCESSED_STATUS_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def append_processed_status(phrase: str, raw_filename: str, processed_filename: str) -> None:
    records = load_processed_status()
    records.append({
        "phrase": phrase,
        "raw_file": raw_filename,
        "processed_file": processed_filename,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    })
    save_processed_status(records)


async def _process_and_track(phrase: str, raw_path: Path, processed_path: Path) -> None:
    """Background task: process audio and write to processed status on success."""
    logger.info("Processing started: %s", raw_path.name)
    try:
        await process_audio(raw_path, processed_path)
        append_processed_status(phrase, raw_path.name, processed_path.name)
        logger.info("Processing done:    %s → %s", raw_path.name, processed_path.name)
    except Exception:
        logger.exception(
            "Processing FAILED for %s — raw OGG is preserved.", raw_path.name
        )


# ── Conversation helpers ──────────────────────────────────────────────────────

def is_allowed(update: Update) -> bool:
    return update.effective_chat.id == config.ALLOWED_CHAT_ID


async def send_next_phrase(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    next_p = get_next_phrase()
    if next_p is None:
        collected, total = count_phrases()
        context.user_data.pop("pending_phrase", None)
        text = f"All done! {collected}/{total} phrases recorded."
        await update.effective_message.reply_text(text)
        logger.info("[BOT→] %s", text)
        return
    context.user_data["pending_phrase"] = next_p
    collected, total = count_phrases()
    text = f"[{collected + 1}/{total}] Please say this:\n\n{next_p}"
    await update.effective_message.reply_text(text)
    logger.info("[BOT→] Sent phrase [%d/%d]: %r", collected + 1, total, next_p)


# ── Handlers ─────────────────────────────────────────────────────────────────

async def handle_trigger(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        logger.warning("Unauthorized message from %s (chat %d) — ignored.",
                       _user_tag(update), update.effective_chat.id)
        return
    text = (update.message.text or "").lower()
    words = set(re.findall(r"\w+", text))
    if not (words & TRIGGER_WORDS):
        return
    logger.info("[IN ] %s: %r", _user_tag(update), update.message.text)
    await send_next_phrase(update, context)


async def handle_start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        logger.warning("Unauthorized command from %s (chat %d) — ignored.",
                       _user_tag(update), update.effective_chat.id)
        return
    logger.info("[IN ] %s: /start", _user_tag(update))
    await send_next_phrase(update, context)


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        logger.warning("Unauthorized audio from %s (chat %d) — ignored.",
                       _user_tag(update), update.effective_chat.id)
        return

    pending = context.user_data.get("pending_phrase")
    if not pending:
        text = "No active session. Send 'start' to begin collecting."
        await update.message.reply_text(text)
        logger.info("[BOT→] %s", text)
        return

    voice = update.message.voice or update.message.audio
    if voice is None:
        await update.message.reply_text("Please send a voice message.")
        return

    duration = getattr(voice, "duration", None)
    dur_str = f"{duration}s" if duration is not None else "?s"
    logger.info("[IN ] %s: voice message (%s)", _user_tag(update), dur_str)

    filename = generate_filename()
    dest = config.AUDIO_DIR / filename

    tg_file = await context.bot.get_file(voice.file_id)
    await tg_file.download_to_drive(dest)

    total_collected = append_status(pending, filename)
    context.user_data["pending_phrase"] = None
    logger.info("File saved: %s  (raw total: %d)", filename, total_collected)

    processed_filename = "p_" + dest.stem + ".wav"
    processed_dest = config.PROCESSED_AUDIO_DIR / processed_filename
    asyncio.create_task(_process_and_track(pending, dest, processed_dest))

    await update.message.reply_text("Thank you!")
    logger.info("[BOT→] Thank you!")
    await send_next_phrase(update, context)


async def handle_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        logger.warning("Unauthorized message from %s (chat %d) — ignored.",
                       _user_tag(update), update.effective_chat.id)
        return
    pending = context.user_data.get("pending_phrase")
    if pending:
        text = f"Please send a voice message for:\n\n{pending}"
        await update.effective_message.reply_text(text)
        logger.info("[BOT→] Reminded %s to record: %r", _user_tag(update), pending)
    else:
        text = "Send 'start' to begin collecting audio samples."
        await update.effective_message.reply_text(text)
        logger.info("[BOT→] %s", text)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    config.ensure_dirs()
    token = config.get_bot_token()

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler(["start", "collect"], handle_start_command))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trigger))
    app.add_handler(MessageHandler(filters.ALL, handle_fallback))

    collected, total = count_phrases()
    logger.info("Bot starting. %d/%d phrases collected. Log: %s", collected, total, _LOG_FILE)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
