// Measure webhook latency under concurrent bursts.
// Usage: node scripts/load_test.mjs https://your-service.example.com
import http from "node:http";
import https from "node:https";
import { randomUUID } from "node:crypto";

const LATENCY_LIMIT_MS = 500;
const BURSTS = [100, 100, 100, 200];

const target = new URL(process.argv[2] ?? "");
const client = target.protocol === "https:" ? https : http;
const agent = new client.Agent({ keepAlive: true, maxSockets: 200 });

function post() {
  const body = JSON.stringify({
    transaction_id: `txn_${randomUUID()}`,
    source_account: "acc_load_source",
    destination_account: "acc_load_destination",
    amount: 1,
    currency: "INR",
  });
  const started = performance.now();
  return new Promise((resolve, reject) => {
    const request = client.request(
      new URL("/v1/webhooks/transactions", target),
      {
        agent,
        method: "POST",
        headers: {
          "content-type": "application/json",
          "content-length": Buffer.byteLength(body),
        },
      },
      (response) => {
        response.resume();
        response.on("end", () =>
          resolve({ status: response.statusCode, ms: performance.now() - started }),
        );
      },
    );
    request.on("error", reject);
    request.end(body);
  });
}

let passed = true;
for (const size of BURSTS) {
  const results = await Promise.all(Array.from({ length: size }, post));
  const latencies = results.map((result) => result.ms).sort((a, b) => a - b);
  const statuses = [...new Set(results.map((result) => result.status))].join(", ");
  const slowest = latencies.at(-1);
  const ok = statuses === "202" && slowest < LATENCY_LIMIT_MS;
  passed &&= ok;
  console.log(
    `${ok ? "PASS" : "FAIL"} burst of ${size}: status ${statuses}, ` +
      `median ${latencies[size >> 1].toFixed(0)} ms, slowest ${slowest.toFixed(0)} ms`,
  );
  await new Promise((resolve) => setTimeout(resolve, 500));
}

agent.destroy();
process.exitCode = passed ? 0 : 1;
