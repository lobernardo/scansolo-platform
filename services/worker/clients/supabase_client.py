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
            .select("id, file_name, supabase_storage_path, extension")
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

    # ── Storage ───────────────────────────────────────────────────────────────

    def download_file(self, bucket: str, path: str) -> bytes:
        response = self._client.storage.from_(bucket).download(path)
        return response

    def upload_file(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        self._client.storage.from_(bucket).upload(
            path=path,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )

    def get_public_url(self, bucket: str, path: str) -> str:
        return self._client.storage.from_(bucket).get_public_url(path)

    def get_signed_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        result = self._client.storage.from_(bucket).create_signed_url(path, expires_in)
        return result["signedURL"]

    # ── Detected targets ──────────────────────────────────────────────────────

    def get_targets_for_profile(self, profile_id: str) -> list[dict[str, Any]]:
        result = (
            self._client.table("detected_targets")
            .select("*")
            .eq("profile_id", profile_id)
            .order("rank")
            .execute()
        )
        return result.data or []

    def get_profiles_for_project(self, project_id: str) -> list[dict[str, Any]]:
        result = (
            self._client.table("gpr_profiles")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at")
            .execute()
        )
        return result.data or []

    def get_latest_run_id(self, project_id: str) -> str | None:
        result = (
            self._client.table("gpr_profiles")
            .select("run_id")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["run_id"]
        return None

    # ── AI interpretations ────────────────────────────────────────────────────

    def insert_ai_interpretation(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table("ai_interpretations").insert(payload).execute()
        return result.data[0]

    def get_ai_interpretations_for_targets(self, target_ids: list[str]) -> list[dict[str, Any]]:
        if not target_ids:
            return []
        result = (
            self._client.table("ai_interpretations")
            .select("*")
            .in_("target_id", target_ids)
            .execute()
        )
        return result.data or []

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
