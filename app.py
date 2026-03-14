import os
import re
import sqlite3
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient
from telethon.sessions import StringSession
from difflib import SequenceMatcher


app = FastAPI()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_STRING = os.getenv("TELEGRAM_SESSION", "")

CHANNELS = [
    ch.strip()
    for ch in os.getenv("TELEGRAM_CHANNELS", "wfwitness").split(",")
    if ch.strip()
]

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

MEDIA_DIR = Path("/tmp/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "osint.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def fix_text(text: str | None) -> str:
    if not text:
        return ""
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def normalize_text(text: str | None) -> str:
    if not text:
        return ""

    text = fix_text(text).lower()

    text = re.sub(r"http\S+|www\.\S+", " ", text)
    text = re.sub(r"@\w+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text

def text_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def find_duplicate(normalized_text: str, hours=6, threshold=0.85):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, normalized_text
        FROM posts
        WHERE posted_at >= datetime('now', ?)
        """,
        (f"-{hours} hours",),
    )

    rows = cursor.fetchall()
    conn.close()

    for row in rows:
        existing_text = row["normalized_text"] or ""
        similarity = text_similarity(normalized_text, existing_text)

        if similarity >= threshold:
            return row["id"]

    return None

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT NOT NULL,
            telegram_message_id INTEGER NOT NULL,
            message_text TEXT,
            normalized_text TEXT,
            media_path TEXT,
            media_type TEXT,
            status TEXT NOT NULL DEFAULT 'unconfirmed',
            posted_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_name, telegram_message_id, media_path)
        )
    """)

    try:
        cursor.execute("ALTER TABLE posts ADD COLUMN normalized_text TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def save_post(
    channel_name,
    telegram_message_id,
    message_text=None,
    normalized_text=None,
    media_path=None,
    media_type=None,
    posted_at=None,
    status="unconfirmed",
):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            INSERT OR IGNORE INTO posts (
                channel_name,
                telegram_message_id,
                message_text,
                normalized_text,
                media_path,
                media_type,
                status,
                posted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            channel_name,
            telegram_message_id,
            message_text,
            normalized_text,
            media_path,
            media_type,
            status,
            posted_at,
        ))
        conn.commit()
    finally:
        conn.close()


@app.on_event("startup")
async def startup_event():
    init_db()


@app.get("/")
def home():
    return {
        "message": "Iran OSINT backend is running",
        "channels": CHANNELS,
    }


@app.get("/telegram-check")
async def telegram_check():
    try:
        await client.connect()
        me = await client.get_me()
        await client.disconnect()

        return JSONResponse(
            content={
                "ok": True,
                "authorized": True,
                "me": {
                    "id": me.id,
                    "username": me.username,
                    "first_name": me.first_name,
                },
                "channels": CHANNELS,
            },
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        return JSONResponse(
            content={"ok": False, "error": str(e)},
            media_type="application/json; charset=utf-8",
        )


@app.get("/db-test")
def db_test():
    try:
        test_text = "Test OSINT post"
        test_normalized = normalize_text(test_text)

        save_post(
            channel_name="test_channel",
            telegram_message_id=1001,
            message_text=test_text,
            normalized_text=test_normalized,
            media_path="media/test_channel/1001_1.jpg",
            media_type="image",
            posted_at="2026-03-13T12:00:00",
        )

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM posts")
        row = cursor.fetchone()
        conn.close()

        return {
            "ok": True,
            "message": "Test post saved or ignored if duplicate",
            "post_count": row["count"],
            "normalized_text": test_normalized,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/channel-test")
async def channel_test():
    try:
        await client.connect()

        results = []

        for channel_username in CHANNELS:
            messages = []

            try:
                async for message in client.iter_messages(channel_username, limit=5):
                    media_url = None
                    media_type = None

                    if message.photo:
                        file_name = f"{channel_username}_{message.id}.jpg"
                        file_path = MEDIA_DIR / file_name
                        await client.download_media(message, file=str(file_path))
                        media_url = f"/media/{file_name}"
                        media_type = "photo"

                    elif message.video:
                        file_name = f"{channel_username}_{message.id}.mp4"
                        file_path = MEDIA_DIR / file_name
                        await client.download_media(message, file=str(file_path))
                        media_url = f"/media/{file_name}"
                        media_type = "video"

                    clean_text = fix_text(message.text)
                    duplicate_id = find_duplicate(normalized)
                    normalized = normalize_text(clean_text)

                    save_post(
                        channel_name=channel_username,
                        telegram_message_id=message.id,
                        message_text=clean_text,
                        normalized_text=normalized,
                        media_path=media_url,
                        media_type=media_type,
                        posted_at=str(message.date),
                        status="duplicate" if duplicate_id else "unconfirmed",
                    )

                    messages.append(
                        {
                            "id": message.id,
                            "date": str(message.date),
                            "text": clean_text,
                            "normalized_text": normalized,
                            "media_type": media_type,
                            "media_url": media_url,
                        }
                    )

                results.append(
                    {
                        "channel": channel_username,
                        "ok": True,
                        "message_count": len(messages),
                        "messages": messages,
                    }
                )

            except Exception as channel_error:
                results.append(
                    {
                        "channel": channel_username,
                        "ok": False,
                        "error": str(channel_error),
                        "messages": [],
                    }
                )

        await client.disconnect()

        return JSONResponse(
            content={
                "ok": True,
                "channels": CHANNELS,
                "results": results,
            },
            media_type="application/json; charset=utf-8",
        )

    except Exception as e:
        try:
            await client.disconnect()
        except Exception:
            pass

        return JSONResponse(
            content={"ok": False, "error": str(e)},
            media_type="application/json; charset=utf-8",
        )
