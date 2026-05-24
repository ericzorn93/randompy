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

REQUEST_URL = "https://randompy.fly.dev/todos"
REQUEST_COUNT = 1_000
MAX_CONCURRENCY = 100
TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=30.0, pool=30.0)
VERBOSE = False


async def make_call(index: int, client: httpx.AsyncClient, statuses: list[int], semaphore: asyncio.Semaphore) -> None:
  async with semaphore:
    if VERBOSE:
      logger.info(f"Processing call {index}")

    start = time.perf_counter()
    try:
      response = await client.get(REQUEST_URL)
      statuses[index - 1] = response.status_code
    except httpx.HTTPError as exc:
      elapsed = time.perf_counter() - start
      logger.error("Call %d failed after %.2f seconds: %s", index, elapsed, exc)
      statuses[index - 1] = 0
    finally:
      if VERBOSE:
        elapsed = time.perf_counter() - start
        logger.info(f"Call {index} finished in {elapsed:.2f} seconds")


async def main() -> None:
  limits = httpx.Limits(
      max_connections=MAX_CONCURRENCY,
      max_keepalive_connections=MAX_CONCURRENCY,
  )
  async with httpx.AsyncClient(timeout=TIMEOUT, limits=limits, follow_redirects=False) as client:
    statuses = [0] * REQUEST_COUNT
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    start = time.perf_counter()
    async with asyncio.TaskGroup() as tg:
      for i in range(1, REQUEST_COUNT + 1):
        tg.create_task(make_call(i, client, statuses, semaphore))

    end = time.perf_counter()
    success_codes = [status for status in statuses if status == http.HTTPStatus.OK]

    total_time = end - start
    logger.info(
        f"All calls completed with success codes: {len(success_codes)} in {total_time:.2f} seconds"
    )



if __name__ == "__main__":
    asyncio.run(main())
