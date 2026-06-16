import asyncio
from app.orchestrator import handle_user_message
from app.db import Database


async def main():
    await Database.init_async()
    try:
        reply = await handle_user_message("Hello, system check.", interface="web")
        print("Reply:", reply)
    except Exception:
        import traceback

        traceback.print_exc()


asyncio.run(main())
