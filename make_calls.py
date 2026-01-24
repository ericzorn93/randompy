import asyncio
import http

import httpx

_sem = asyncio.Semaphore(100)


async def make_call(i) -> int:
    async with _sem:
        async with httpx.AsyncClient() as client:
            print(f"Making call {i}")
            response = await client.get("https://randompy.fly.dev/healthz")
            print(response.status_code)

        await asyncio.sleep(0.1)

    return response.status_code


async def main() -> None:
    tasks = [asyncio.create_task(make_call(i)) for i in range(1_000)]
    statuses = await asyncio.gather(*tasks)
    success_codes = [status for status in statuses if status == http.HTTPStatus.OK]

    print(f"All calls completed with success codes: {len(success_codes)}")


if __name__ == "__main__":
    asyncio.run(main())
