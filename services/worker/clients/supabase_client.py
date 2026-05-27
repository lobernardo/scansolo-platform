"""
Supabase client wrapper for the worker.

Uses the service role key — server-side only.
Never exposed to frontend or committed to source control.
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from supabase import create_client, Client

log = structlog.get_logger()


class SupabaseClient:
    def __init__(self) -> None:
        url = os.environ["NEXT_PUBLIC_SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self._client: Client = create_client(url, key)

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def fetch_pending_jobs(self, limit: int = 1) -> list[dict[str, Any]]:
        result = (
            self._client.table("processing_jobs")
            .select("*")
            .eq("status", "aguardando")
            .order("created_at")
            .limit(limit)
            .execute()
        )
        return result.data or []

    def update_job_status(
        self,
        job_id: str,
        status: str,
        *,
        error_message: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {"status": status}
        if error_message is not None:
            payload["error_message"] = error_message
        if status in ("concluido", "erro"):
            from datetime import datetime, timezone
            payload["finished_at"] = datetime.now(timezone.utc).isoformat()
        elif status.startswith("processando"):
            from datetime import datetime, timezone
            payload["started_at"] = datetime.now(timezone.utc).isoformat()
        self._client.table("processing_jobs").update(payload).eq("id", job_id).execute()

    def create_job(self, project_id: str, job_type: str) -> dict[str, Any]:
        result = (
            self._client.table("processing_jobs")
            .insert({"project_id": project_id, "job_type": job_type, "status": "aguardando"})
            .execute()
        )
        return result.data[0]

    # ── Projects ──────────────────────────────────────────────────────────────

    def update_project_status(self, project_id: str, status: str) -> None:
        self._client.table("projects").update({"status": status}).eq("id", project_id).execute()

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("projects")
            .select("*")
            .eq("id", project_id)
            .single()
            .execute()
        )
        return result.data

    # ── Project files ─────────────────────────────────────────────────────────

    def get_dzt_files(self, project_id: str) -> list[dict[str, Any]]:
        result = (
            self._client.table("project_files")
            .select("*")
            .eq("project_id", project_id)
            .eq("extension", "dzt")
            .eq("status", "confirmado")
            .execute()
        )
        return result.data or []

    # ── GPR profiles ──────────────────────────────────────────────────────────

    def insert_gpr_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table("gpr_profiles").insert(payload).execute()
        return result.data[0]

    # ── Detected targets ──────────────────────────────────────────────────────

    def insert_detected_targets(self, targets: list[dict[str, Any]]) -> None:
        if targets:
            self._client.table("detected_targets").insert(targets).execute()

    # ── Audit log ─────────────────────────────────────────────────────────────

    def audit(
        self,
        *,
        project_id: str,
        user_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._client.table("audit_logs").insert(
            {
                "project_id": project_id,
                "user_id": user_id,
                "action": action,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "metadata_json": metadata or {},
            }
        ).execute()
