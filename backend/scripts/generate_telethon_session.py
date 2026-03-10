"""
One-time script to generate a Telethon StringSession.

Run this locally:
    cd backend
    python scripts/generate_telethon_session.py

Reads TELEGRAM_API_ID and TELEGRAM_API_HASH from .env file.
It will ask for your phone number and send an OTP to your Telegram app.
Set the output as TELEGRAM_SESSION_STRING in your environment.
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()


async def main():
    api_id = os.getenv("TELEGRAM_API_ID")
    api_hash = os.getenv("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("ERROR: TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
        return

    print("=== Telethon StringSession Generator ===\n")
    print(f"Using api_id: {api_id}")
    print("This will ask for your phone number and send a code to Telegram.\n")

    client = TelegramClient(StringSession(), int(api_id), api_hash)
    await client.start()

    session_string = client.session.save()

    print("\n=== Your StringSession ===")
    print(f"\n{session_string}\n")
    print("Copy this value and set it as TELEGRAM_SESSION_STRING in your .env and Railway env vars.")
    print("NEVER share this string or commit it to version control.\n")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
