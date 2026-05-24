import asyncio
import http
import logging
import sys
import time

import httpx

logger = logging.getLogger()
logHandler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
logHandler.setFormatter(formatter)
logger.addHandler(logHandler)
logger.setLevel(logging.INFO)

REQUEST_URL = "https://randompy.fly.dev/todos"
REQUEST_COUNT = 1_000
MAX_CONCURRENCY = 100
TIMEOUT = httpx.Timeout(30.0, connect=10.0, read=30.0, pool=30.0)
VERBOSE = False
SENTINEL = object()


async def worker(
    worker_id: int,
    queue: asyncio.Queue,
    client: httpx.AsyncClient,
    statuses: list[int],
) -> None:
    """
    Each worker pulls indices off the queue and fires requests one at a time.
    A sentinel value is used to signal shutdown once all work is queued.
    """
    while True:
        index = await queue.get()
        if index is SENTINEL:
            queue.task_done()
            break

        start = time.perf_counter()
        try:
            response = await client.get(REQUEST_URL)
            statuses[index - 1] = response.status_code
            if VERBOSE:
                elapsed = time.perf_counter() - start
                logger.info("Worker %d: call %d finished in %.2f seconds (status %d)",
                            worker_id, index, elapsed, response.status_code)
        except httpx.HTTPError as exc:
            elapsed = time.perf_counter() - start
            logger.error("Call %d failed after %.2f seconds: %s", index, elapsed, exc)
            statuses[index] = 0
        finally:
            queue.task_done()


async def main() -> None:
    limits = httpx.Limits(
        max_connections=MAX_CONCURRENCY,
        max_keepalive_connections=MAX_CONCURRENCY,
        # Raise the keepalive expiry; default 5s is too aggressive under load
        keepalive_expiry=30.0,
    )
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        limits=limits,
        follow_redirects=False,
        http2=True,  # enables multiplexing if the server supports it
    ) as client:
        statuses = [0] * REQUEST_COUNT

        # Pre-fill a queue with every index — workers drain it
        queue: asyncio.Queue = asyncio.Queue()
        for i in range(0, REQUEST_COUNT):
            queue.put_nowait(i)

        # Add sentinel values so workers stop cleanly once the queue is empty
        for _ in range(MAX_CONCURRENCY):
            queue.put_nowait(SENTINEL)

        start = time.perf_counter()

        # Spawn exactly MAX_CONCURRENCY workers; they exit on sentinel
        workers = [
            asyncio.create_task(worker(i, queue, client, statuses))
            for i in range(MAX_CONCURRENCY)
        ]
        await queue.join()
        await asyncio.gather(*workers)

        total_time = time.perf_counter() - start
        success_count = sum(1 for s in statuses if s == http.HTTPStatus.OK)
        logger.info(
            "All calls completed with success codes: %d in %.2f seconds",
            success_count,
            total_time,
        )


if __name__ == "__main__":
    asyncio.run(main())
