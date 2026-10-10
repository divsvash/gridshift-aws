import json
import os
import time
from datetime import UTC, datetime


def current_time():
    return datetime.now(UTC).isoformat()


def run_workload():
    # A real, deterministic computational workload
    result = 0

    for number in range(2_000_000):
        result += number * number

    return result


def main():
    job_id = os.getenv("JOB_ID", "gridshift-test")

    print(json.dumps({
        "event": "job_started",
        "job_id": job_id,
        "timestamp": current_time()
    }), flush=True)

    start = time.perf_counter()

    result = run_workload()

    duration = time.perf_counter() - start

    print(json.dumps({
        "event": "job_completed",
        "job_id": job_id,
        "result": result,
        "duration_seconds": round(duration, 3),
        "timestamp": current_time()
    }), flush=True)


if __name__ == "__main__":
    main()
