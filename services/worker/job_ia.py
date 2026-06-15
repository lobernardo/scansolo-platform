"""
IA job handler — Fase 2.

Flow:
  1. Fetch detected_targets for the latest run of this project
  2. For each profile: download radargram image from Storage
  3. For each target: crop the radargram around the hyperbola
  4. Call GPT-4o via OpenAIClient for each target
  5. Insert ai_interpretation records
  6. Generate _interpretada_ia.png with IA labels overlaid
  7. Auto-approve if project.auto_accept_ia = true
  8. Update project status
"""

from __future__ import annotations

import base64
import io
import os
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog
from PIL import Image, ImageDraw, ImageFont

from clients.openai_client import OpenAIClient

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

CROP_HALF = 120

# Tipo label → texto em português
_TIPO_LABEL = {
    "tubulacao_agua":    "Tubulação água",
    "tubulacao_gas":     "Tubulação gás",
    "tubulacao_esgoto":  "Tubulação esgoto",
    "cabo_eletrico":     "Cabo elétrico",
    "cabo_telecom":      "Cabo telecom",
    "galeria_concreto":  "Galeria concreto",
    "vazio_ar":          "Vazio/cavidade",
    "vazio":             "Vazio/cavidade",
    "rocha":             "Rocha",
    "inconclusivo":      "Inconclusivo",
    "desconhecido":      "Desconhecido",
}

# Cor RGB por confiança
_CONF_COLOR = {
    "alta":  (50, 200, 80),    # verde
    "media": (255, 190, 0),    # amarelo
    "baixa": (160, 160, 160),  # cinza
}


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
    all_interpretations: dict[str, dict] = {}  # target_id → ai_result

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

        targets_ia: list[dict] = []

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
            all_interpretations[target["id"]] = result
            targets_ia.append({"target": target, "ai": result})

        # Gerar imagem interpretada para este perfil
        interp_url = _gerar_imagem_interpretada(supa, profile, targets_ia)
        if interp_url:
            try:
                supa._client.table("gpr_profiles").update(
                    {"imagem_interpretada_url": interp_url}
                ).eq("id", profile["id"]).execute()
                log.info("ia_interpretada_url_saved", profile_id=profile["id"])
            except Exception as exc:
                log.warning("ia_interpretada_url_save_failed", error=str(exc))

    log.info(
        "ia_job_done",
        job_id=job_id,
        targets_interpreted=total_targets,
        total_cost_usd=round(total_cost, 4),
    )

    supa.update_job_status(job_id, "concluido")

    # Auto-aprovação ou revisão manual
    auto_accept = bool((project or {}).get("auto_accept_ia", False))
    if auto_accept and all_interpretations:
        _auto_aprovar_targets(supa, project_id, all_interpretations)
    else:
        supa.update_project_status(project_id, "ia_concluida")


# ── Auto-aprovação ────────────────────────────────────────────────────────────

def handle_ia_p2_job(supa: "SupabaseClient", job: dict) -> None:
    """
    Gera _interpretada_ia_p2.png: anotação dos resultados de IA já existentes
    sobre a imagem Processada 2 (_radargrama_preview_radan_5m.png).
    Não chama GPT-4o — apenas redesenha os labels com a escala de profundidade da P2.
    """
    job_id: str = job["id"]
    project_id: str = job["project_id"]
    profile_id: str = (job.get("payload") or {}).get("profile_id", "")

    log.info("ia_p2_job_start", job_id=job_id, profile_id=profile_id)
    supa.update_job_status(job_id, "processando")

    if not profile_id:
        supa.update_job_status(job_id, "erro", error_message="payload.profile_id ausente")
        return

    # Busca perfil
    res = supa._client.table("gpr_profiles").select("*").eq("id", profile_id).maybeSingle().execute()
    profile = res.data
    if not profile:
        supa.update_job_status(job_id, "erro", error_message=f"perfil {profile_id} não encontrado")
        return

    if not profile.get("imagem_preview_radan_5m_url"):
        supa.update_job_status(job_id, "erro", error_message="imagem_preview_radan_5m_url ausente no perfil")
        return

    # Busca alvos do perfil
    targets = supa.get_targets_for_profile(profile_id)
    if not targets:
        supa.update_job_status(job_id, "erro", error_message="sem alvos detectados neste perfil")
        return

    # Busca interpretações IA existentes
    target_ids = [t["id"] for t in targets]
    ai_res = supa._client.table("ai_interpretations").select("*").in_("target_id", target_ids).execute()
    ai_by_target_id = {row["target_id"]: row for row in (ai_res.data or [])}

    if not ai_by_target_id:
        supa.update_job_status(job_id, "erro", error_message="sem interpretações IA para este perfil — rode o job 'ia' primeiro")
        return

    # Monta lista com pares (target, ai)
    targets_ia = [
        {"target": t, "ai": ai_by_target_id[t["id"]]}
        for t in targets
        if t["id"] in ai_by_target_id
    ]

    url = _gerar_imagem_interpretada_p2(supa, profile, targets_ia)
    if url:
        supa._client.table("gpr_profiles").update(
            {"imagem_interpretada_ia_p2_url": url}
        ).eq("id", profile_id).execute()
        log.info("ia_p2_done", profile_id=profile_id, url=url[:80])
    else:
        supa.update_job_status(job_id, "erro", error_message="falha ao gerar imagem P2")
        return

    supa.update_job_status(job_id, "concluido")


def _gerar_imagem_interpretada_p2(
    supa: "SupabaseClient",
    profile: dict,
    targets_ia: list[dict],
) -> str | None:
    """
    Mesma lógica de _gerar_imagem_interpretada mas usa imagem_preview_radan_5m_url
    como base e depth_preview_m (default 5.0) como escala de profundidade.
    """
    if not targets_ia:
        return None

    base_url = profile.get("imagem_preview_radan_5m_url")
    img_data = _download_from_storage_url(supa, base_url)
    if not img_data:
        return None

    try:
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception as exc:
        log.warning("ia_p2_image_open_failed", error=str(exc))
        return None

    draw = ImageDraw.Draw(img)
    W, H = img.size
    dist_max = float(profile.get("distancia_max_m") or 1.0)

    # depth_max da Processada 2 — lê de filtros_customizados ou usa 5.0 padrão
    filtros = profile.get("filtros_customizados") or {}
    depth_max = float(filtros.get("depth_preview_m", 5.0))

    font = _get_font(13)

    DL, DR, DT, DB = int(0.09 * W), int(0.96 * W), int(0.10 * H), int(0.87 * H)
    dW = DR - DL
    dH = DB - DT

    for item in targets_ia:
        target = item["target"]
        ai = item["ai"]

        x_m = target.get("x_m")
        depth_m = target.get("depth_m")
        if x_m is None or depth_m is None:
            continue
        if float(depth_m) > depth_max:
            continue  # alvo além da janela visível desta imagem

        cx = DL + int(float(x_m) / dist_max * dW)
        cy = DT + int(float(depth_m) / depth_max * dH)
        cx = max(0, min(W - 1, cx))
        cy = max(0, min(H - 1, cy))

        tipo = ai.get("ia_tipo_sugerido", "desconhecido")
        confianca = ai.get("ia_confianca", "baixa")
        conf_pct = ai.get("ia_confianca_pct", 0)
        color = _CONF_COLOR.get(confianca, (160, 160, 160))

        r = 7
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)

        label = f"{_TIPO_LABEL.get(tipo, tipo)} {conf_pct}%"
        tx = min(cx + 10, W - 160)
        ty = max(cy - 18, 2)
        try:
            bbox = draw.textbbox((tx, ty), label, font=font)
            draw.rectangle([bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1], fill=(0, 0, 0))
        except AttributeError:
            pass
        draw.text((tx, ty), label, fill=color, font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    storage_path = _extract_storage_path(base_url, "gpr-images")
    if storage_path:
        interp_path = storage_path.replace(
            "_radargrama_preview_radan_5m.png", "_interpretada_ia_p2.png"
        )
        if interp_path == storage_path:
            interp_path = storage_path.rsplit(".", 1)[0] + "_interpretada_ia_p2.png"
    else:
        interp_path = f"interp/{profile['id'][:8]}_interpretada_ia_p2.png"

    try:
        supa.upload_file("gpr-images", interp_path, img_bytes, "image/png")
        return supa.get_public_url("gpr-images", interp_path)
    except Exception as exc:
        log.warning("ia_p2_upload_failed", error=str(exc))
        return None


def _auto_aprovar_targets(
    supa: "SupabaseClient",
    project_id: str,
    interpretations: dict[str, dict],
) -> None:
    """
    Insere technical_reviews automaticamente com base na confiança da IA.
      alta  → vai_para_planta=True,  vai_para_relatorio=True
      media → vai_para_planta=True,  vai_para_relatorio=False
      baixa → vai_para_planta=False, vai_para_relatorio=False
    """
    now = datetime.now(timezone.utc).isoformat()
    n_alta = n_media = n_baixa = 0
    rows = []

    for target_id, ai in interpretations.items():
        confianca = ai.get("ia_confianca", "baixa")
        if confianca == "alta":
            vai_planta, vai_rel = True, True
            n_alta += 1
        elif confianca == "media":
            vai_planta, vai_rel = True, False
            n_media += 1
        else:
            vai_planta, vai_rel = False, False
            n_baixa += 1

        rows.append({
            "target_id": target_id,
            "status_review": "aprovado",
            "tipo_final": ai.get("ia_tipo_sugerido"),
            "vai_para_planta": vai_planta,
            "vai_para_relatorio": vai_rel,
            "reviewed_at": now,
        })

    if rows:
        supa._client.table("technical_reviews").insert(rows).execute()

    log.info(
        "ia_auto_aprovacao",
        project_id=project_id,
        alta=n_alta,
        media=n_media,
        baixa=n_baixa,
    )
    supa.update_project_status(project_id, "revisao_concluida")
    supa.create_job(project_id, "interpretada")
    log.info("interpretada_job_enqueued", project_id=project_id)


# ── Geração de imagem interpretada ───────────────────────────────────────────

def _gerar_imagem_interpretada(
    supa: "SupabaseClient",
    profile: dict,
    targets_ia: list[dict],
) -> str | None:
    """
    Gera _interpretada_ia.png: imagem processada com labels da IA sobrepostos.
    Retorna URL pública ou None se falhar.
    """
    if not targets_ia:
        return None

    base_url = profile.get("imagem_processada_url") or profile.get("imagem_anotada_url")
    img_data = _download_from_storage_url(supa, base_url)
    if not img_data:
        return None

    try:
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
    except Exception as exc:
        log.warning("ia_interp_image_open_failed", error=str(exc))
        return None

    draw = ImageDraw.Draw(img)
    W, H = img.size
    dist_max = float(profile.get("distancia_max_m") or 1.0)
    depth_max = float(profile.get("profundidade_max_m") or 1.0)
    font = _get_font(13)

    # Área de dados dentro da figura matplotlib (estimativa conservadora)
    DL, DR, DT, DB = int(0.09 * W), int(0.96 * W), int(0.10 * H), int(0.87 * H)
    dW = DR - DL
    dH = DB - DT

    for item in targets_ia:
        target = item["target"]
        ai = item["ai"]

        x_m = target.get("x_m")
        depth_m = target.get("depth_m")
        if x_m is None or depth_m is None:
            continue

        cx = DL + int(float(x_m) / dist_max * dW)
        cy = DT + int(float(depth_m) / depth_max * dH)
        cx = max(0, min(W - 1, cx))
        cy = max(0, min(H - 1, cy))

        tipo = ai.get("ia_tipo_sugerido", "desconhecido")
        confianca = ai.get("ia_confianca", "baixa")
        conf_pct = ai.get("ia_confianca_pct", 0)
        color = _CONF_COLOR.get(confianca, (160, 160, 160))

        # Círculo no apex
        r = 7
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=color, width=2)

        # Label: "Tipo XX%"
        label = f"{_TIPO_LABEL.get(tipo, tipo)} {conf_pct}%"
        tx = min(cx + 10, W - 160)
        ty = max(cy - 18, 2)

        try:
            bbox = draw.textbbox((tx, ty), label, font=font)
            draw.rectangle([bbox[0] - 2, bbox[1] - 1, bbox[2] + 2, bbox[3] + 1],
                           fill=(0, 0, 0))
        except AttributeError:
            pass  # textbbox not available in older Pillow
        draw.text((tx, ty), label, fill=color, font=font)

    # Serializar
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()

    # Storage path baseado na imagem processada
    storage_path = _extract_storage_path(base_url, "gpr-images")
    if storage_path:
        interp_path = storage_path.replace("_processada.png", "_interpretada_ia.png")
        if interp_path == storage_path:
            interp_path = storage_path.rsplit(".", 1)[0] + "_interpretada_ia.png"
    else:
        interp_path = f"interp/{profile['id'][:8]}_interpretada_ia.png"

    try:
        supa.upload_file("gpr-images", interp_path, img_bytes, "image/png")
        return supa.get_public_url("gpr-images", interp_path)
    except Exception as exc:
        log.warning("ia_interp_upload_failed", error=str(exc))
        return None


def _get_font(size: int) -> ImageFont.ImageFont:
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    for path in font_paths:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _extract_storage_path(url: str | None, bucket: str) -> str | None:
    if not url:
        return None
    supabase_url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
    prefix = f"{supabase_url}/storage/v1/object/public/{bucket}/"
    if url.startswith(prefix):
        return url[len(prefix):]
    return None


# ── Helpers de imagem ─────────────────────────────────────────────────────────

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
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img.thumbnail((800, 400))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()
    except Exception as exc:
        log.warning("ia_image_resize_failed", url=url, error=str(exc))
        return None


def _download_from_storage_url(supa: "SupabaseClient", url: str | None) -> bytes | None:
    if not url:
        return None
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
