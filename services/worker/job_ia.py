"""
IA job handler — Fase 2.

Flow:
  1. Fetch detected_targets for the latest run of this project
  2. For each profile: download radargram image from Storage
  3. For each target: crop the radargram around the hyperbola
  4. Call GPT-4o via OpenAIClient for each target
  5. Insert ai_interpretation records
  6. Update project status to ia_concluida
"""

from __future__ import annotations

import base64
import io
import os
from typing import TYPE_CHECKING

import structlog
from PIL import Image

from clients.openai_client import OpenAIClient

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

# Pixels to include around the target center when cropping
CROP_HALF = 120


def handle_ia_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    log.info("ia_job_start", job_id=job_id, project_id=project_id)
    supa.update_job_status(job_id, "processando_ia")
    supa.update_project_status(project_id, "processando_ia")

    project = supa.get_project(project_id)
    if not project:
        raise RuntimeError(f"Project {project_id} not found")

    run_id = supa.get_latest_run_id(project_id)
    if not run_id:
        raise RuntimeError(f"No GPR run found for project {project_id}")

    profiles = [p for p in supa.get_profiles_for_project(project_id) if p["run_id"] == run_id]
    if not profiles:
        raise RuntimeError(f"No profiles for run {run_id}")

    openai = OpenAIClient()
    total_targets = 0
    total_cost = 0.0

    for profile in profiles:
        targets = supa.get_targets_for_profile(profile["id"])
        if not targets:
            log.info("ia_profile_no_targets", profile_id=profile["id"])
            continue

        radargram_b64 = _load_image_b64(supa, profile.get("imagem_anotada_url") or profile.get("imagem_processada_url"))
        radargram_pil = _load_image_pil(supa, profile.get("imagem_processada_url"))

        log.info(
            "ia_profile_start",
            profile_id=profile["id"],
            arquivo=profile.get("arquivo_dzt"),
            n_targets=len(targets),
        )

        for target in targets:
            crop_b64 = _make_crop_b64(radargram_pil, target, profile) if radargram_pil else None

            result = openai.interpret_target(
                project_context=project,
                target_data=target,
                radargram_image_b64=radargram_b64,
                crop_image_b64=crop_b64,
            )

            supa.insert_ai_interpretation({
                "target_id": target["id"],
                **{k: result[k] for k in (
                    "ia_tipo_sugerido", "ia_descricao",
                    "ia_justificativa_visual", "ia_justificativa_tecnica",
                    "ia_confianca", "ia_recomendacao",
                    "vai_para_planta_sugerido", "vai_para_relatorio_sugerido",
                    "observacoes", "raw_response_json",
                    "model_usado", "tokens_usados", "custo_usd",
                )},
            })

            total_cost += result.get("custo_usd", 0.0)
            total_targets += 1

    log.info(
        "ia_job_done",
        job_id=job_id,
        targets_interpreted=total_targets,
        total_cost_usd=round(total_cost, 4),
    )
    supa.update_job_status(job_id, "concluido")
    supa.update_project_status(project_id, "ia_concluida")


def _load_image_pil(supa: "SupabaseClient", url: str | None) -> Image.Image | None:
    if not url:
        return None
    data = _download_from_storage_url(supa, url)
    if not data:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        log.warning("ia_image_open_failed", url=url, error=str(exc))
        return None


def _load_image_b64(supa: "SupabaseClient", url: str | None) -> str | None:
    if not url:
        return None
    data = _download_from_storage_url(supa, url)
    if not data:
        return None
    # Resize to reduce token cost (keep it under ~1MB base64)
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((800, 400))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        log.warning("ia_image_resize_failed", url=url, error=str(exc))
        return None


def _download_from_storage_url(supa: "SupabaseClient", url: str) -> bytes | None:
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    for bucket in ("gpr-images", "gpr-tabelas"):
        prefix = f"{supabase_url}/storage/v1/object/public/{bucket}/"
        if url.startswith(prefix):
            storage_path = url[len(prefix):]
            try:
                return supa.download_file(bucket, storage_path)
            except Exception as exc:
                log.warning("ia_download_failed", path=storage_path, error=str(exc))
                return None
    log.warning("ia_unrecognized_url", url=url[:120])
    return None


def _make_crop_b64(
    img: Image.Image | None,
    target: dict,
    profile: dict,
) -> str | None:
    if img is None:
        return None
    x_m = target.get("x_m")
    depth_m = target.get("depth_m")
    dist_max = profile.get("distancia_max_m")
    depth_max = profile.get("profundidade_max_m")
    if None in (x_m, depth_m, dist_max, depth_max) or dist_max == 0 or depth_max == 0:
        return None

    w, h = img.size
    cx = int(x_m / dist_max * w)
    cy = int(depth_m / depth_max * h)

    left = max(0, cx - CROP_HALF)
    top = max(0, cy - CROP_HALF)
    right = min(w, cx + CROP_HALF)
    bottom = min(h, cy + CROP_HALF)

    crop = img.crop((left, top, right, bottom))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
