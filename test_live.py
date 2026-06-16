import httpx
import asyncio

async def main():
    print("Sending standard message...")
    async with httpx.AsyncClient(timeout=120.0) as client:
        res = await client.post("http://localhost:5000/api/send_message", json={"message": "Hello, system check.", "interface": "web"})
        print("Non-streaming response:", res.text)
        
        print("Sending streaming tool message...")
        res = await client.post("http://localhost:5000/api/send_message_stream", json={"message": "/bash date", "interface": "web"})
        print("Streaming response:", res.text)

asyncio.run(main())
