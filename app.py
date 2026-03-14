import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from telethon import TelegramClient
from telethon.sessions import StringSession

app = FastAPI()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_STRING = os.getenv("TELEGRAM_SESSION", "")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

MEDIA_DIR = Path("/tmp/media")
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/media", StaticFiles(directory=str(MEDIA_DIR)), name="media")


def fix_text(text: str | None) -> str:
    if not text:
        return ""
    try:
        return text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


@app.get("/")
def home():
    return {"message": "Iran OSINT backend is running"}


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
            },
            media_type="application/json; charset=utf-8",
        )
    except Exception as e:
        return JSONResponse(
            content={"ok": False, "error": str(e)},
            media_type="application/json; charset=utf-8",
        )


@app.get("/channel-test")
async def channel_test():
    channel_username = "wfwitness"

    try:
        await client.connect()

        messages = []
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

            messages.append(
                {
                    "id": message.id,
                    "date": str(message.date),
                    "text": fix_text(message.text),
                    "media_type": media_type,
                    "media_url": media_url,
                }
            )

        await client.disconnect()

        return JSONResponse(
            content={
                "ok": True,
                "channel": channel_username,
                "messages": messages,
            },
            media_type="application/json; charset=utf-8",
        )

    except Exception as e:
        return JSONResponse(
            content={"ok": False, "error": str(e)},
            media_type="application/json; charset=utf-8",
        )
