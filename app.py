import os
from fastapi import FastAPI
from telethon import TelegramClient
from telethon.sessions import StringSession

app = FastAPI()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_STRING = os.getenv("TELEGRAM_SESSION", "")

@app.get("/")
def home():
    return {"message": "Iran OSINT backend is running"}

@app.get("/telegram-check")
async def telegram_check():
    if not API_ID or not API_HASH or not SESSION_STRING:
        return {"ok": False, "error": "Missing Telegram environment variables"}

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    try:
        await client.connect()
        me = await client.get_me()
        await client.disconnect()

        return {
            "ok": True,
            "authorized": True,
            "me": {
                "id": me.id,
                "username": me.username,
                "first_name": me.first_name
            }
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
