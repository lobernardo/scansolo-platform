"""
ScanSOLO Worker — polling loop for processing_jobs.

Phase 0: stubs only. Pipeline and AI not yet connected.
Phase 1: connect pipeline_v1.py and detector_hiperboles.py.
"""

import os
import time
import structlog
from dotenv import load_dotenv

from clients.supabase_client import SupabaseClient
from job_gpr import handle_gpr_job

load_dotenv()

log = structlog.get_logger()

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "10"))


def poll_once(supa: SupabaseClient) -> None:
    jobs = supa.fetch_pending_jobs(limit=1)
    if not jobs:
        return

    job = jobs[0]
    job_id = job["id"]
    job_type = job["job_type"]

    log.info("job_picked", job_id=job_id, job_type=job_type)

    if job_type == "gpr":
        handle_gpr_job(supa, job)
    else:
        log.warning("unknown_job_type", job_id=job_id, job_type=job_type)


def main() -> None:
    log.info("worker_starting", poll_interval=POLL_INTERVAL)
    supa = SupabaseClient()

    while True:
        try:
            poll_once(supa)
        except Exception:
            log.exception("poll_error")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
