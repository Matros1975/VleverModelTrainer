from pathlib import Path

from dotenv import load_dotenv
import os

load_dotenv(Path(__file__).parent / ".env")

PROJECT_DIR = Path(__file__).parent
DATA_DIR = PROJECT_DIR / "Data"
PHRASES_FILE = DATA_DIR / "train_phrases.txt"
COLLECTED_DIR = DATA_DIR / "Collected"
AUDIO_DIR = COLLECTED_DIR / "Audio"
STATUS_FILE = COLLECTED_DIR / "status.json"
SELECTED_AUDIO_DIR = DATA_DIR / "Selected" / "Audio"
PROCESSED_DIR = DATA_DIR / "Processed"
PROCESSED_AUDIO_DIR = PROCESSED_DIR / "Audio"
PROCESSED_STATUS_FILE = PROCESSED_DIR / "status.json"

BOT_TOKEN = os.environ["BOT_TOKEN"]
ALLOWED_CHAT_ID = int(os.environ["ALLOWED_CHAT_ID"])


def get_bot_token() -> str:
    return BOT_TOKEN


def ensure_dirs():
    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    SELECTED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
