import aiohttp
import asyncio
import time
from pathlib import Path

URL = "http://localhost:5003/api/upload"
IMAGE_PATH = Path("static/inputs/kingsday_in_e3d7f416-7e95-4d6e-85b2-42443f11f9f9_20250427_151407.jpg")
N_REQUESTS = 10

async def send_request(session, idx):
    start = time.perf_counter()
    with IMAGE_PATH.open("rb") as f:
        data = aiohttp.FormData()
        data.add_field("image", f, filename=IMAGE_PATH.name, content_type="image/jpeg")
        data.add_field("choice", "queen")

        async with session.post(URL, data=data) as resp:
            duration = time.perf_counter() - start
            result = await resp.text()
            print(f"[{idx}] {resp.status} | {duration:.2f}s")
            return resp.status, duration, result

async def main():
    async with aiohttp.ClientSession() as session:
        tasks = [send_request(session, i) for i in range(1, N_REQUESTS + 1)]
        results = await asyncio.gather(*tasks)

    durations = [d for _, d, _ in results]
    print(f"\nMédia: {sum(durations)/len(durations):.2f}s | Máximo: {max(durations):.2f}s | Mínimo: {min(durations):.2f}s")

if __name__ == "__main__":
    asyncio.run(main())
