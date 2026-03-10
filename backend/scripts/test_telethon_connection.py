"""
Test script to verify Telethon connection and analytics access.

Run this after setting up environment variables:
    cd backend
    python scripts/test_telethon_connection.py

Requires: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING, TELEGRAM_CHANNEL_ID
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
    session_string = os.getenv("TELEGRAM_SESSION_STRING")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID", "@idigovnews")

    if not all([api_id, api_hash, session_string]):
        print("Missing env vars: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION_STRING")
        return

    client = TelegramClient(StringSession(session_string), int(api_id), api_hash)
    await client.connect()

    if not await client.is_user_authorized():
        print("Session is not authorized. Run generate_telethon_session.py again.")
        await client.disconnect()
        return

    print(f"Connected. Fetching channel: {channel_id}\n")

    entity = await client.get_entity(channel_id)
    print(f"Channel: {entity.title}")
    print(f"Username: @{entity.username}")
    print(f"ID: {entity.id}\n")

    messages = await client.get_messages(entity, limit=5)
    print(f"Last {len(messages)} messages:\n")

    for msg in messages:
        views = msg.views or 0
        forwards = msg.forwards or 0
        replies = msg.replies.replies if msg.replies else 0
        reactions_list = []
        if msg.reactions and msg.reactions.results:
            for r in msg.reactions.results:
                emoji = r.reaction.emoticon if hasattr(r.reaction, 'emoticon') else str(r.reaction)
                reactions_list.append(f"{emoji}: {r.count}")

        title = (msg.text or "")[:60]
        print(f"  ID: {msg.id}")
        print(f"  Text: {title}...")
        print(f"  Views: {views:,} | Forwards: {forwards} | Replies: {replies}")
        print(f"  Reactions: {', '.join(reactions_list) if reactions_list else 'none'}")
        print(f"  Link: https://t.me/{entity.username}/{msg.id}")
        print()

    await client.disconnect()
    print("Test complete.")


if __name__ == "__main__":
    asyncio.run(main())
