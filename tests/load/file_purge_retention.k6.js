/**
 * Phase 260.1.A.9 — file purge retention (k6 scaffold).
 *
 * Intended as a nightly regression against staging: seed ~10k DELETING File
 * rows (past grace) via migration/fixture + run:
 *   k6 run tests/load/file_purge_retention.k6.js
 *
 * Thresholds (pass-3 T2-4): purge completes < 5m; lock acquisition p(95) < 100ms.
 * Wire `BASE_URL`, `AUTH_TOKEN`, and a controlled test tenant in your env.
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend, Rate } from "k6/metrics";

const purgeDuration = new Trend("file_purge_job_duration_ms");
const lockDeniedRate = new Rate("file_purge_lock_denied");

export const options = {
  scenarios: {
    smoke: {
      executor: "constant-vus",
      vus: 1,
      duration: "30s",
    },
  },
  thresholds: {
    file_purge_lock_denied: ["rate<0.01"],
  },
};

export default function () {
  // Placeholder HTTP probe: replace with operator-owned trigger (e.g. internal
  // job-runner webhook) or shell-out CronJob metric scrape in Grafana.
  const base = __ENV.BASE_URL || "http://localhost:8000";
  const res = http.get(`${base}/health`);
  const ok = check(res, { "health 200": (r) => r.status === 200 });
  if (!ok) {
    lockDeniedRate.add(1);
  }
  purgeDuration.add(res.timings.duration);
  sleep(1);
}
