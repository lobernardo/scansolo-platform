"""
GPR job handler — Phase 0 stub.

Phase 1: connect pipeline/pipeline_v1.py and pipeline/detector_hiperboles.py.
"""

from __future__ import annotations

import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()


def handle_gpr_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    log.info("gpr_job_start", job_id=job_id, project_id=project_id)
    supa.update_job_status(job_id, "processando_gpr")
    supa.update_project_status(project_id, "processando_gpr")

    try:
        _run_pipeline_stub(project_id)
        supa.update_job_status(job_id, "concluido")
        supa.update_project_status(project_id, "gpr_concluido")
        log.info("gpr_job_done", job_id=job_id)

        # Phase 1: create IA job after GPR succeeds
        supa.create_job(project_id, "ia")

    except Exception as exc:
        log.error("gpr_job_failed", job_id=job_id, error=str(exc))
        supa.update_job_status(job_id, "erro", error_message=str(exc))
        supa.update_project_status(project_id, "erro")
        raise


def _run_pipeline_stub(project_id: str) -> None:
    """Placeholder — Phase 1 replaces this with pipeline_v1.py execution."""
    log.info("pipeline_stub", project_id=project_id, note="Phase 0 — no-op")
