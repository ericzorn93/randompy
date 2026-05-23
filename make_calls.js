const https = require("https");
const { URL } = require("url");

const MAX_CONCURRENCY = 100;
const REQUEST_COUNT = 1000;
const REQUEST_URL = "https://randompy.fly.dev/todos";
const TIMEOUT_MS = 30_000;

const url = new URL(REQUEST_URL);
const agent = new https.Agent({ keepAlive: true, maxSockets: MAX_CONCURRENCY });

function log(message, ...args) {
  const timestamp = new Date().toISOString();
  console.log(`${timestamp} ${message}`, ...args);
}

function makeCall(index) {
  return new Promise((resolve) => {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);

    const options = {
      hostname: url.hostname,
      port: url.port || 443,
      path: url.pathname + url.search,
      method: "GET",
      agent,
      signal: controller.signal,
      headers: {
        "User-Agent": "nodejs/vanilla",
        Accept: "application/json",
      },
    };

    log("Making call %d", index);
    const start = Date.now();

    const req = https.request(options, (res) => {
      res.on("data", () => {});
      res.on("end", () => {
        clearTimeout(timeout);
        const elapsed = (Date.now() - start) / 1000;
        log(
          "Call %d completed in %.2f seconds (status %d)",
          index,
          elapsed,
          res.statusCode,
        );
        resolve(res.statusCode);
      });
    });

    req.on("error", (err) => {
      clearTimeout(timeout);
      const elapsed = (Date.now() - start) / 1000;
      log("Call %d failed after %.2f seconds: %s", index, elapsed, err.message);
      resolve(0);
    });

    req.end();
  });
}

async function run() {
  const statuses = new Array(REQUEST_COUNT).fill(0);
  let inFlight = 0;
  let nextIndex = 1;

  const start = Date.now();

  return new Promise((resolve) => {
    function schedule() {
      while (inFlight < MAX_CONCURRENCY && nextIndex <= REQUEST_COUNT) {
        const current = nextIndex;
        nextIndex += 1;
        inFlight += 1;

        makeCall(current)
          .then((status) => {
            statuses[current - 1] = status;
          })
          .finally(() => {
            inFlight -= 1;
            if (nextIndex > REQUEST_COUNT && inFlight === 0) {
              resolve(statuses);
            } else {
              schedule();
            }
          });
      }
    }

    schedule();
  }).then((statuses) => {
    const elapsed = (Date.now() - start) / 1000;
    const successCount = statuses.filter((status) => status === 200).length;
    log(
      "All calls completed with success codes: %d in %.2f seconds",
      successCount,
      elapsed,
    );
  });
}

run().catch((err) => {
  console.error("Error running requests:", err);
  process.exit(1);
});
