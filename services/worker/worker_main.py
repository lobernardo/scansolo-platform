"""
ScanSOLO Worker — polling loop for processing_jobs.
"""

import os
import time
import structlog
from dotenv import load_dotenv

load_dotenv()

# Injetar certificados do Windows Certificate Store no Python (redes corporativas com inspeção TLS)
# Necessário porque httpx/httpcore não lê o cert store do Windows por padrão
# Requer: pip install truststore
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass  # se não instalado, continuará com certifi padrão

from clients.supabase_client import SupabaseClient
from job_gpr import handle_gpr_job
from job_ia import handle_ia_job
from job_cartografia import handle_cartografia_job

log = structlog.get_logger()

POLL_INTERVAL = int(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "10"))


def _check_env() -> bool:
    required = ["NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        log.error("env_missing", keys=missing)
        return False
    log.info("env_ok", keys_present=required)
    return True


def poll_once(supa: SupabaseClient) -> None:
    jobs = supa.fetch_pending_jobs(limit=1)
    log.info("poll", jobs_found=len(jobs))

    if not jobs:
        return

    job = jobs[0]
    job_id = job["id"]
    job_type = job["job_type"]
    project_id = job["project_id"]

    log.info("job_picked", job_id=job_id, job_type=job_type, project_id=project_id, status_anterior="aguardando")

    if job_type == "gpr":
        handle_gpr_job(supa, job)
    elif job_type == "ia":
        handle_ia_job(supa, job)
    elif job_type == "cartografia":
        handle_cartografia_job(supa, job)
    else:
        log.warning("unknown_job_type_skipped", job_id=job_id, job_type=job_type)
        supa.update_job_status(job_id, "erro", error_message=f"job_type '{job_type}' not implemented in this worker version")


def main() -> None:
    log.info("worker_starting", poll_interval_s=POLL_INTERVAL)

    if not _check_env():
        raise SystemExit(1)

    supa = SupabaseClient()
    log.info("supabase_connected")
    log.info("polling_started", interval_s=POLL_INTERVAL)

    while True:
        try:
            poll_once(supa)
        except Exception:
            log.exception("poll_error")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
