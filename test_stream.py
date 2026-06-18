import asyncio
import traceback
from app.orchestrator import handle_user_message_streaming


async def main():
    try:
        msg = "Coba kamu jalankan tool bash untuk menampilkan tanggal hari ini. Gunakan preamble sebelum panggil tool."
        async for chunk in handle_user_message_streaming(
            msg, "terminal", session_id=64
        ):
            print(f"CHUNK: {repr(chunk)}")
    except Exception:
        traceback.print_exc()


asyncio.run(main())
