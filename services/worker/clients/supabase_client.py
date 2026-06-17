"""
Supabase client wrapper for the worker.

Uses the service role key — server-side only.
Never exposed to frontend or committed to source control.
"""

from __future__ import annotations

import os
import time
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
        if not targets:
            return
        try:
            self._client.table("detected_targets").insert(targets).execute()
        except Exception as batch_err:
            # Batch failed — likely DB constraint violation on confidence_label_relatorio
            # (old schema accepts only 'alta'/'baixa'; 'media' triggers check violation).
            # Retry row-by-row so alta/baixa rows are not lost.
            # Fix: apply migration 20260606000001_fix_confidence_label_relatorio_constraint.sql
            log = structlog.get_logger()
            log.warning(
                "detected_targets_batch_insert_failed",
                error=str(batch_err),
                n=len(targets),
                hint="apply migration 20260606000001 to allow confidence_label_relatorio='media'",
            )
            inserted = 0
            for t in targets:
                try:
                    self._client.table("detected_targets").insert(t).execute()
                    inserted += 1
                except Exception as row_err:
                    log.warning(
                        "detected_targets_row_insert_failed",
                        rank=t.get("rank"),
                        confidence_label_relatorio=t.get("confidence_label_relatorio"),
                        error=str(row_err),
                    )
            log.info("detected_targets_inserted_fallback", count=inserted, total=len(targets))

    # ── Storage ───────────────────────────────────────────────────────────────

    def download_file(self, bucket: str, path: str) -> bytes:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return self._client.storage.from_(bucket).download(path)
            except Exception as e:
                last_exc = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                log.warning(
                    "download_file_retry",
                    bucket=bucket,
                    path=path,
                    attempt=attempt + 1,
                    wait_s=wait,
                    error=str(e),
                )
                time.sleep(wait)
        raise last_exc

    def upload_file(self, bucket: str, path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                self._client.storage.from_(bucket).upload(
                    path=path,
                    file=data,
                    file_options={"content-type": content_type, "upsert": "true"},
                )
                return
            except Exception as e:
                last_exc = e
                wait = 2 ** attempt  # 1s, 2s, 4s
                log.warning(
                    "upload_file_retry",
                    bucket=bucket,
                    path=path,
                    attempt=attempt + 1,
                    wait_s=wait,
                    error=str(e),
                )
                time.sleep(wait)
        raise last_exc

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

    # ── Cartography ───────────────────────────────────────────────────────────

    def get_all_project_files(self, project_id: str) -> list[dict[str, Any]]:
        """All confirmed project files (any extension)."""
        result = (
            self._client.table("project_files")
            .select("id, file_name, supabase_storage_path, extension, status")
            .eq("project_id", project_id)
            .eq("status", "confirmado")
            .execute()
        )
        return result.data or []

    def get_reviewed_targets(self, project_id: str) -> list[dict[str, Any]]:
        """
        Returns detected_targets merged with technical_reviews + ai_interpretations
        for the latest run, filtered to vai_para_planta OR vai_para_relatorio = true.
        """
        run_id = self.get_latest_run_id(project_id)
        if not run_id:
            return []

        profiles = [p for p in self.get_profiles_for_project(project_id) if p.get("run_id") == run_id]
        profile_ids = [p["id"] for p in profiles]
        if not profile_ids:
            return []

        t_result = (
            self._client.table("detected_targets")
            .select("*")
            .in_("profile_id", profile_ids)
            .order("rank")
            .execute()
        )
        targets = t_result.data or []
        target_ids = [t["id"] for t in targets]
        if not target_ids:
            return []

        r_result = (
            self._client.table("technical_reviews")
            .select("*")
            .in_("target_id", target_ids)
            .execute()
        )
        reviews = {r["target_id"]: r for r in (r_result.data or [])}

        ai_result = (
            self._client.table("ai_interpretations")
            .select("target_id, ia_tipo_sugerido, ia_confianca, vai_para_planta_sugerido, vai_para_relatorio_sugerido")
            .in_("target_id", target_ids)
            .execute()
        )
        ai_map = {a["target_id"]: a for a in (ai_result.data or [])}

        merged = []
        for t in targets:
            rv = reviews.get(t["id"], {})
            ai = ai_map.get(t["id"], {})
            vai_planta = rv.get("vai_para_planta") or False
            vai_rel = rv.get("vai_para_relatorio") or False
            if not vai_planta and not vai_rel:
                continue
            merged.append({
                **t,
                "tipo_final": rv.get("tipo_final") or ai.get("ia_tipo_sugerido"),
                "vai_para_planta": vai_planta,
                "vai_para_relatorio": vai_rel,
                "observacao_revisao": rv.get("observacao"),
                "review_status": rv.get("status_review", "pendente"),
                "ia_tipo_sugerido": ai.get("ia_tipo_sugerido"),
                "ia_confianca": ai.get("ia_confianca"),
            })
        return merged

    def insert_cartography_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table("cartography_outputs").insert(payload).execute()
        return result.data[0]

    def get_cartography_output(self, project_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("cartography_outputs")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    # ── Report outputs ────────────────────────────────────────────────────────

    def get_report_outputs(self, project_id: str) -> list[dict[str, Any]]:
        result = (
            self._client.table("report_outputs")
            .select("id, version, status, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []

    def insert_report_output(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self._client.table("report_outputs").insert(payload).execute()
        return result.data[0]

    def get_latest_report_output(self, project_id: str) -> dict[str, Any] | None:
        result = (
            self._client.table("report_outputs")
            .select("*")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

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
