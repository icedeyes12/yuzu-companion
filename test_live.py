import httpx
import asyncio


async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        print("Sending streaming tool message...")
        async with client.stream(
            "POST",
            "http://localhost:5000/api/send_message_stream",
            json={
                "message": "Tolong cek tanggal hari ini pakai bash command (native function call) ya, lalu analisis hasilnya sedikit.",
                "interface": "web",
            },
        ) as response:
            async for chunk in response.aiter_text():
                print(chunk, end="", flush=True)


asyncio.run(main())
