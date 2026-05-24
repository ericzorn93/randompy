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
TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=30.0, pool=30.0)
MAX_CONCURRENCY = 100
VERBOSE = False
SENTINEL_MESSAGE = object()
type QueueItem = int | object


async def worker(name: int, queue: asyncio.Queue[QueueItem], lock: asyncio.Lock, client: httpx.AsyncClient, statuses: list[int]) -> None:
  while True:
    i = await queue.get()

    # Check for sentinel value to stop the worker or if index is not an integer (shouldn't happen, but just in case)
    if i is SENTINEL_MESSAGE:
      logger.info(f"Stopping worker {name} sentinel received.")
      queue.task_done()
      break

    if not isinstance(i, int):
      logger.error(f"Worker {name} received invalid queue item: {i}. Stopping worker.")
      queue.task_done()
      break

    if VERBOSE:
      logger.info(f"Worker {name} processing call {i}")
    start = time.perf_counter()

    try:
      response = await client.get(REQUEST_URL)
      async with lock:
        statuses[i - 1] = response.status_code
    except httpx.HTTPError as exc:
      elapsed = time.perf_counter() - start
      logger.error("Call %d failed after %.2f seconds: %s", i, elapsed, exc)

      async with lock:
        statuses[i - 1] = 0
    finally:
      if VERBOSE:
        elapsed = time.perf_counter() - start
        logger.info(f"Call {i} finished in {elapsed:.2f} seconds")
      queue.task_done()


async def main() -> None:
  limits = httpx.Limits(
      max_connections=MAX_CONCURRENCY,
      max_keepalive_connections=MAX_CONCURRENCY,
  )
  async with httpx.AsyncClient(timeout=TIMEOUT, limits=limits, follow_redirects=False) as client:
    queue: asyncio.Queue[QueueItem] = asyncio.Queue()
    lock = asyncio.Lock()
    statuses = [0] * REQUEST_COUNT

    start = time.perf_counter()

    async with asyncio.TaskGroup() as tg:
      # Start worker tasks
      for i in range(MAX_CONCURRENCY):
        tg.create_task(worker(i + 1, queue, lock, client, statuses))

      # Enqueue calls
      for i in range(1, REQUEST_COUNT + 1):
        await queue.put(i)

      # Add sentinel values to stop workers
      for _ in range(MAX_CONCURRENCY):
        await queue.put(SENTINEL_MESSAGE)

      # Wait for all tasks to complete
      await queue.join()

    end = time.perf_counter()
    success_codes = [status for status in statuses if status == http.HTTPStatus.OK]

    total_time = end - start
    logger.info(
        f"All calls completed with success codes: {len(success_codes)} in {total_time:.2f} seconds"
    )



if __name__ == "__main__":
    asyncio.run(main())
