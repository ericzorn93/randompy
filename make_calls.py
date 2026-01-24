import asyncio
import http
import time

import httpx

_sem = asyncio.Semaphore(100)


async def make_call(i) -> int:
    async with _sem:
        async with httpx.AsyncClient() as client:
            print(f"Making call {i}")
            start = time.perf_counter()
            response = await client.get("https://randompy.fly.dev/todos")
            end = time.perf_counter()
            print(f"Call {i} completed in {end - start:.2f} seconds")

        await asyncio.sleep(0.1)

    return response.status_code


async def main() -> None:
    start = time.perf_counter()
    tasks = [asyncio.create_task(make_call(i)) for i in range(1_000)]
    statuses = await asyncio.gather(*tasks)
    end = time.perf_counter()
    success_codes = [status for status in statuses if status == http.HTTPStatus.OK]

    total_time = end - start
    print(
        f"All calls completed with success codes: {len(success_codes)} in {total_time:.2f} seconds"
    )


if __name__ == "__main__":
    asyncio.run(main())
