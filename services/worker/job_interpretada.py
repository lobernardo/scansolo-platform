"""
Interpretada job handler.

Disparado após finalizeReview (status revisao_concluida).

Flow:
  1. Busca perfis do projeto com alvos aprovados em technical_reviews
  2. Para cada perfil: baixa _processada.png do Supabase Storage
  3. Desenha marcadores apenas dos alvos aprovados (vai_para_relatorio=True)
     com: tipo em português, profundidade, diâmetro, score
  4. Salva _interpretada.png e faz upload para Storage
  5. Atualiza gpr_profiles.imagem_interpretada_url + status = 'pendente' (aguarda Amilson aprovar)
  6. Salva ia_training_examples com os alvos aprovados (loop de aprendizado)
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import TYPE_CHECKING

import structlog
from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

# Cor por tipo de alvo
_TIPO_COR = {
    "tubulacao_agua":    (30,  144, 255),   # azul
    "tubulacao_gas":     (255, 165,  0),    # laranja
    "tubulacao_esgoto":  (139,  69, 19),    # marrom
    "cabo_eletrico":     (255,  50,  50),   # vermelho
    "cabo_telecom":      (160,  32, 240),   # roxo
    "galeria_concreto":  (100, 100, 100),   # cinza escuro
    "vazio":             (0,   200, 200),   # ciano
    "vazio_ar":          (0,   200, 200),
    "rocha":             (150, 150, 150),
    "raiz":              (34,  139, 34),    # verde
    "desconhecido":      (180, 180, 180),
    "inconclusivo":      (180, 180, 180),
}
_COR_DEFAULT = (255, 220, 0)  # amarelo para tipos não mapeados

_TIPO_LABEL = {
    "tubulacao_agua":    "Tubulação água",
    "tubulacao_gas":     "Tubulação gás",
    "tubulacao_esgoto":  "Tubulação esgoto",
    "cabo_eletrico":     "Cabo elétrico",
    "cabo_telecom":      "Cabo telecom",
    "galeria_concreto":  "Galeria concreto",
    "vazio":             "Vazio",
    "vazio_ar":          "Vazio/cavidade",
    "rocha":             "Rocha",
    "raiz":              "Raiz",
    "desconhecido":      "Desconhecido",
    "inconclusivo":      "Inconclusivo",
}


def handle_interpretada_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    log.info("interpretada_job_start", job_id=job_id, project_id=project_id)
    supa.update_job_status(job_id, "processando_interpretada")
    supa.update_project_status(project_id, "processando_interpretada")

    profiles = supa.get_profiles_for_project(project_id)
    if not profiles:
        raise RuntimeError(f"Nenhum perfil para projeto {project_id}")

    # Pega somente o run mais recente
    run_id = supa.get_latest_run_id(project_id)
    profiles = [p for p in profiles if p.get("run_id") == run_id]

    training_examples = []

    for profile in profiles:
        profile_id = profile["id"]
        arquivo_dzt = profile.get("arquivo_dzt", "")
        processada_url = profile.get("imagem_processada_url", "")

        if not processada_url:
            log.warning("sem_imagem_processada", profile_id=profile_id)
            continue

        # Alvos aprovados para este perfil
        targets = _get_approved_targets(supa, profile_id)
        if not targets:
            log.info("sem_alvos_aprovados", profile_id=profile_id)
            continue

        log.info("gerando_interpretada", profile_id=profile_id, n_alvos=len(targets))

        try:
            img_bytes = _download_from_storage_url(supa, processada_url)
            if not img_bytes:
                log.warning("download_processada_vazio", profile_id=profile_id)
                continue
            interpretada_bytes = _gerar_interpretada(img_bytes, targets, profile)
        except Exception as e:
            log.error("falha_gerar_interpretada", profile_id=profile_id, error=str(e))
            continue

        # Upload para Storage (gpr-images é público — PNGs de saída)
        stem = Path(arquivo_dzt).stem
        storage_path = f"{project_id}/{run_id}/{stem}_interpretada.png"
        try:
            supa.upload_file(
                bucket="gpr-images",
                path=storage_path,
                data=interpretada_bytes,
                content_type="image/png",
            )
            url = supa.get_public_url("gpr-images", storage_path)
        except Exception as e:
            log.error("falha_upload_interpretada", error=str(e))
            continue

        # Atualiza perfil: URL + status pendente (aguarda aprovação do Amilson)
        supa._client.table("gpr_profiles").update({
            "imagem_interpretada_url": url,
            "imagem_interpretada_status": "pendente",
        }).eq("id", profile_id).execute()

        log.info("interpretada_salva", profile_id=profile_id, url=url)

        # Prepara exemplo de treino
        training_examples.append({
            "project_id": project_id,
            "profile_id": profile_id,
            "source": "revisao",
            "annotation_data": _alvos_para_annotation(targets),
            "imagem_url": processada_url,
        })

    # Salva exemplos de treino no banco
    if training_examples:
        try:
            supa._client.table("ia_training_examples").insert(training_examples).execute()
            log.info("training_examples_salvos", n=len(training_examples))
        except Exception as e:
            log.warning("falha_salvar_training_examples", error=str(e))

    # Alimenta tabela de ground truth com resultados da revisão técnica
    try:
        n_vp = 0
        n_fp = 0
        _conf_map = {"alta": "certa", "media": "provavel", "média": "provavel", "baixa": "duvidosa"}
        _conf_allowed = {"certa", "provavel", "duvidosa"}
        for profile in profiles:
            profile_id = profile["id"]
            result = (
                supa._client.table("detected_targets")
                .select(
                    "id, rank, x_m, depth_m, diam_est_m, confidence_score, "
                    "technical_reviews(vai_para_relatorio, tipo_final, revisado_por, "
                    "observacoes, confianca_revisao)"
                )
                .eq("profile_id", profile_id)
                .execute()
            )
            filtros = profile.get("filtros_customizados") or {}
            for t in result.data or []:
                reviews = t.get("technical_reviews") or []
                if isinstance(reviews, dict):
                    reviews = [reviews]
                if not reviews:
                    continue
                rev = reviews[0]
                e_vp = bool(rev.get("vai_para_relatorio", False))
                conf_raw = rev.get("confianca_revisao") or "provavel"
                conf = conf_raw if conf_raw in _conf_allowed else _conf_map.get(conf_raw, "provavel")
                ground_truth_row = {
                    "project_id": project_id,
                    "profile_id": profile_id,
                    "target_rank": t.get("rank"),
                    "x_m": t.get("x_m"),
                    "depth_m": t.get("depth_m"),
                    "diam_est_m": t.get("diam_est_m"),
                    "tipo_confirmado": rev.get("tipo_final"),
                    "e_falso_positivo": not e_vp,
                    "score_detector": t.get("confidence_score"),
                    "preset_usado": filtros.get("preset", "270mhz"),
                    "confianca_revisao": conf,
                    "observacoes": rev.get("observacoes"),
                    "validado_por": rev.get("revisado_por"),
                }
                supa._client.table("gpr_ground_truth").upsert(
                    ground_truth_row, on_conflict="profile_id,target_rank"
                ).execute()
                if e_vp:
                    n_vp += 1
                else:
                    n_fp += 1
        log.info("ground_truth_saved", n_vp=n_vp, n_fp=n_fp, project_id=project_id)
    except Exception as e:
        log.warning("ground_truth_skipped", error=str(e))

    supa.update_job_status(job_id, "concluido")
    supa.update_project_status(project_id, "interpretada_gerada")
    log.info("interpretada_job_done", project_id=project_id)


def _get_approved_targets(supa: "SupabaseClient", profile_id: str) -> list[dict]:
    """Retorna alvos aprovados (vai_para_relatorio=True) para o perfil."""
    result = (
        supa._client.table("detected_targets")
        .select(
            "id, x_m, depth_m, diam_est_m, confidence_score, "
            "technical_reviews(status_review, tipo_final, profundidade_ajustada, "
            "diametro_ajustado, vai_para_relatorio, observacao)"
        )
        .eq("profile_id", profile_id)
        .execute()
    )
    targets = []
    for t in (result.data or []):
        review = t.get("technical_reviews")
        if isinstance(review, list):
            review = review[0] if review else None
        if not review:
            continue
        if review.get("status_review") not in ("aprovado", "ajustado"):
            continue
        if not review.get("vai_para_relatorio", False):
            continue
        targets.append({
            "x_m":         t.get("x_m") or 0,
            "depth_m":     review.get("profundidade_ajustada") or t.get("depth_m") or 0,
            "diameter_m":  review.get("diametro_ajustado") or t.get("diam_est_m") or 0,
            "tipo":        review.get("tipo_final") or "desconhecido",
            "score":       t.get("confidence_score") or 0,
            "observacao":  review.get("observacao") or "",
        })
    return targets


def _gerar_interpretada(img_bytes: bytes, targets: list[dict], profile: dict) -> bytes:
    """
    Desenha marcadores sobre a imagem processada e retorna PNG em bytes.
    Cada marcador: círculo colorido por tipo + label com tipo/profundidade/diâmetro.
    """
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    W, H = img.size

    dist_max = profile.get("distancia_max_m") or 20.0
    depth_max = profile.get("profundidade_max_m") or 3.5

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Área de dados dentro da figura matplotlib (igual a job_ia.py — compensa margens de eixo)
    DL, DR, DT, DB = int(0.09 * W), int(0.96 * W), int(0.10 * H), int(0.87 * H)
    dW = DR - DL
    dH = DB - DT

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        font = ImageFont.load_default()
        font_sm = font

    for t in targets:
        # Posição em pixels com offsets da área de dados matplotlib
        x_pct = t["x_m"] / max(dist_max, 0.01)
        y_pct = t["depth_m"] / max(depth_max, 0.01)
        px = DL + int(x_pct * dW)
        py = DT + int(y_pct * dH)
        px = max(10, min(W - 10, px))
        py = max(10, min(H - 10, py))

        cor = _TIPO_COR.get(t["tipo"], _COR_DEFAULT)
        cor_alpha = cor + (220,)
        r = 14  # raio do círculo

        # Círculo preenchido semi-transparente + borda sólida
        draw.ellipse([px - r, py - r, px + r, py + r], fill=cor_alpha, outline=cor + (255,), width=2)
        # Cruz central
        draw.line([px - 5, py, px + 5, py], fill=(255, 255, 255, 255), width=2)
        draw.line([px, py - 5, px, py + 5], fill=(255, 255, 255, 255), width=2)

        # Label: tipo + profundidade
        tipo_label = _TIPO_LABEL.get(t["tipo"], t["tipo"])
        linha1 = tipo_label
        linha2 = f"{t['depth_m']:.2f}m" + (f" ⌀{t['diameter_m']:.2f}m" if t["diameter_m"] else "")

        # Caixa de texto com fundo semi-transparente
        lx, ly = px + r + 4, py - r
        tw1 = draw.textlength(linha1, font=font)
        tw2 = draw.textlength(linha2, font=font_sm)
        box_w = max(tw1, tw2) + 6
        draw.rectangle([lx - 2, ly - 1, lx + box_w, ly + 26], fill=(0, 0, 0, 160))
        draw.text((lx, ly), linha1, font=font, fill=(255, 255, 255, 255))
        draw.text((lx, ly + 14), linha2, font=font_sm, fill=(220, 220, 220, 255))

    # Merge overlay sobre imagem base
    img_final = Image.alpha_composite(img, overlay).convert("RGB")

    buf = io.BytesIO()
    img_final.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _alvos_para_annotation(targets: list[dict]) -> list[dict]:
    return [
        {
            "tipo": t["tipo"],
            "depth_m": t["depth_m"],
            "diameter_m": t["diameter_m"],
            "x_m": t["x_m"],
            "observacao": t.get("observacao", ""),
        }
        for t in targets
    ]


def _download_from_storage_url(supa: "SupabaseClient", url: str | None) -> bytes | None:
    """Baixa imagem a partir da URL pública do Supabase Storage (gpr-images)."""
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
                log.warning("download_failed", path=storage_path, error=str(exc))
                return None
    log.warning("unrecognized_url", url=url[:120])
    return None
