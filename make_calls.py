import asyncio
import http
import logging
import sys
import time

import httpx

# 1. Create a logger
logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)

# 2. Define the text format
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

# 3. Add the formatter to the handler and the handler to the logger
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

_sem = asyncio.Semaphore(100)


async def make_call(i: int, client: httpx.AsyncClient) -> int:
  async with _sem:
    logger.info(f"Making call {i}")
    start = time.perf_counter()

    try:
      response = await client.get("https://randompy.fly.dev/todos")
      status_code = response.status_code
    except httpx.HTTPError as exc:
      elapsed = time.perf_counter() - start
      logger.error(
          "Call %d failed after %.2f seconds: %s",
          i,
          elapsed,
          exc,
      )
      return 0

    end = time.perf_counter()
    logger.info(f"Call {i} completed in {end - start:.2f} seconds")
    return status_code


async def main() -> None:
  timeout = httpx.Timeout(30.0, connect=10.0)
  async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
    start = time.perf_counter()
    tasks = [asyncio.create_task(make_call(i, client)) for i in range(1_000)]
    statuses = await asyncio.gather(*tasks)
    end = time.perf_counter()
    success_codes = [status for status in statuses if status == http.HTTPStatus.OK]

    total_time = end - start
    logger.info(
        f"All calls completed with success codes: {len(success_codes)} in {total_time:.2f} seconds"
    )



if __name__ == "__main__":
    asyncio.run(main())
