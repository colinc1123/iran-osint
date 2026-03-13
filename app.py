import os
from fastapi import FastAPI
from telethon import TelegramClient
from telethon.sessions import StringSession

app = FastAPI()

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_STRING = os.getenv("TELEGRAM_SESSION", "")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@app.get("/")
def home():
    return {"message": "Iran OSINT backend is running"}

@app.get("/telegram-check")
async def telegram_check():
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

@app.get("/channel-test")
async def channel_test():
    channel_username = "wfwitness"

    try:
        await client.connect()

        messages = []
        async for message in client.iter_messages(channel_username, limit=5):
            messages.append({
                "id": message.id,
                "date": str(message.date),
                "text": message.text
            })

        await client.disconnect()

        return {
            "ok": True,
            "channel": channel_username,
            "messages": messages
        }

    except Exception as e:
        return {"ok": False, "error": str(e)}
