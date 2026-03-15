import asyncio
import http
import logging
import sys
import time

import httpx
from cachetools.func import ttl_cache
from pythonjsonlogger import jsonlogger

# 1. Create a logger
logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)

# 2. Define the JSON format
# The fmt parameter defines which fields are included in the JSON object
formatter = jsonlogger.JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")

# 3. Add the formatter to the handler and the handler to the logger
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

_sem = asyncio.Semaphore(100)


@ttl_cache(maxsize=1000, ttl=60)
async def make_call(i) -> int:
    async with _sem:
        async with httpx.AsyncClient() as client:
            logger.info(f"Making call {i}")
            start = time.perf_counter()
            response = await client.get("https://randompy.fly.dev/todos")
            end = time.perf_counter()
            logger.info(f"Call {i} completed in {end - start:.2f} seconds")

        await asyncio.sleep(0.1)

    return response.status_code


async def main() -> None:
    start = time.perf_counter()
    tasks = [asyncio.create_task(make_call(i)) for i in range(1_000)]
    statuses = await asyncio.gather(*tasks)
    end = time.perf_counter()
    success_codes = [status for status in statuses if status == http.HTTPStatus.OK]

    total_time = end - start
    logger.info(
        f"All calls completed with success codes: {len(success_codes)} in {total_time:.2f} seconds"
    )


if __name__ == "__main__":
    asyncio.run(main())
