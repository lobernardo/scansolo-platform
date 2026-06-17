"""
Recalibração automática de thresholds do detector a partir do gpr_ground_truth.

Calcula thresholds ótimos (confidence_score, det_amp_threshold, det_depth_min_m)
usando VP/FP validados pelo Amilson e salva um preset candidato em
gpr-tabelas/recalibracao/<timestamp>.json para revisão manual antes de aplicar.

-- Para disparar manualmente:
-- INSERT INTO processing_jobs (job_type, status, payload, project_id)
-- VALUES ('recalibrar', 'aguardando', '{}',
--         (SELECT id FROM projects LIMIT 1));
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

# Valores do preset de produção atual (270mhz) — referência para comparação
_PRESET_ATUAL = {
    "det_min_score_csv": 30,
    "det_amp_threshold": 0.50,
    "det_depth_min_m":   0.30,
}

_MIN_AMOSTRAS = 20


def _calcular_f1(rows: list[dict], threshold: float) -> tuple[float, int, int, int]:
    """Retorna (f1, tp, fp_count, fn) para um dado threshold de confidence_score."""
    tp = sum(
        1 for r in rows
        if r["e_verdadeiro_positivo"] and (r.get("score_detector") or 0) >= threshold
    )
    fp_count = sum(
        1 for r in rows
        if not r["e_verdadeiro_positivo"] and (r.get("score_detector") or 0) >= threshold
    )
    fn = sum(
        1 for r in rows
        if r["e_verdadeiro_positivo"] and (r.get("score_detector") or 0) < threshold
    )
    denom = 2 * tp + fp_count + fn
    f1 = (2 * tp / denom) if denom > 0 else 0.0
    return f1, tp, fp_count, fn


def _otimizar_threshold_score(rows: list[dict]) -> tuple[int, float]:
    """Varre thresholds de 10–90 (step=5) e retorna (melhor_threshold, melhor_f1)."""
    melhor_threshold = _PRESET_ATUAL["det_min_score_csv"]
    melhor_f1 = 0.0

    for thr in range(10, 95, 5):
        f1, tp, fp_count, fn = _calcular_f1(rows, thr)
        if f1 > melhor_f1:
            melhor_f1 = f1
            melhor_threshold = thr

    return melhor_threshold, melhor_f1


def _calcular_amp_threshold(vp: list[dict]) -> float | None:
    """
    Limiar conservador de amplitude: mediana(VP) - 0.1 * IQR(VP).
    Prefere VP a FP — limiar levemente abaixo da mediana dos acertos.
    """
    amps = [r["amplitude_relativa_max"] for r in vp if r.get("amplitude_relativa_max") is not None]
    if len(amps) < 5:
        return None
    amps_sorted = sorted(amps)
    n = len(amps_sorted)
    q1 = amps_sorted[n // 4]
    q3 = amps_sorted[(3 * n) // 4]
    iqr = q3 - q1
    med = statistics.median(amps)
    candidato = round(med - 0.1 * iqr, 3)
    return max(0.10, min(candidato, 0.90))


def _calcular_depth_min(fp: list[dict]) -> float:
    """
    Se há muitos FP rasos (< 0.5 m), sugere elevar det_depth_min_m.
    Usa mediana dos FP rasos + 0.05 m de margem.
    """
    fp_rasos = [r["depth_m"] for r in fp if r.get("depth_m") is not None and r["depth_m"] < 0.5]
    if len(fp_rasos) > 5:
        sugerido = round(statistics.median(fp_rasos) + 0.05, 2)
        return max(_PRESET_ATUAL["det_depth_min_m"], sugerido)
    return _PRESET_ATUAL["det_depth_min_m"]


def handle_recalibrar_job(job_id: str, payload: dict, supa: "SupabaseClient") -> None:
    log.info("recalibrar_start", job_id=job_id)

    # ── ETAPA 1: Buscar ground truth ──────────────────────────────────────────
    try:
        result = supa._client.table("gpr_ground_truth").select("*").execute()
        rows = result.data or []
    except Exception as exc:
        log.error("recalibrar_fetch_failed", error=str(exc))
        supa.update_job_status(job_id, "erro", error_message=f"fetch ground_truth: {exc}")
        return

    if len(rows) < _MIN_AMOSTRAS:
        log.warning(
            "recalibrar_insuficiente",
            n=len(rows),
            msg=f"Mínimo {_MIN_AMOSTRAS} amostras necessário",
        )
        supa.update_job_status(job_id, "concluido")
        return

    # ── ETAPA 2: Separar VP e FP ──────────────────────────────────────────────
    # Coluna no banco é e_falso_positivo; invertemos para e_verdadeiro_positivo
    for r in rows:
        r["e_verdadeiro_positivo"] = not r.get("e_falso_positivo", True)

    vp = [r for r in rows if r["e_verdadeiro_positivo"]]
    fp = [r for r in rows if not r["e_verdadeiro_positivo"]]

    log.info("recalibrar_dados", n_vp=len(vp), n_fp=len(fp), total=len(rows))

    # ── ETAPA 3a: Otimizar confidence_score (F1) ─────────────────────────────
    melhor_threshold, melhor_f1 = _otimizar_threshold_score(rows)

    # ── ETAPA 3b: det_amp_threshold ──────────────────────────────────────────
    amp_threshold_novo = _calcular_amp_threshold(vp)
    if amp_threshold_novo is None:
        amp_threshold_novo = _PRESET_ATUAL["det_amp_threshold"]

    # ── ETAPA 3c: det_depth_min_m ────────────────────────────────────────────
    depth_min_novo = _calcular_depth_min(fp)

    # ── ETAPA 4: Montar preset candidato ─────────────────────────────────────
    # Detalhes do F1 no threshold ótimo
    _, tp, fp_count, fn = _calcular_f1(rows, melhor_threshold)

    candidato = {
        "gerado_em": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "n_amostras": len(rows),
        "n_vp": len(vp),
        "n_fp": len(fp),
        "f1_score": round(melhor_f1, 3),
        "detalhes_f1": {
            "threshold_otimo": melhor_threshold,
            "tp": tp,
            "fp": fp_count,
            "fn": fn,
        },
        "thresholds_sugeridos": {
            "det_min_score_csv": melhor_threshold,
            "det_amp_threshold": amp_threshold_novo,
            "det_depth_min_m": depth_min_novo,
        },
        "thresholds_atuais": _PRESET_ATUAL.copy(),
        "aprovado": False,
        "notas": (
            f"F1={melhor_f1:.3f} em threshold={melhor_threshold}. "
            f"VP={len(vp)}, FP={len(fp)}. "
            "REVISAR antes de aplicar ao preset de produção."
        ),
    }

    # ── ETAPA 5: Salvar no Storage ────────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    storage_path = f"recalibracao/candidato_{ts}.json"
    candidato_bytes = json.dumps(candidato, indent=2, ensure_ascii=False).encode()

    try:
        supa._client.storage.from_("gpr-tabelas").upload(
            storage_path,
            candidato_bytes,
            file_options={"content-type": "application/json", "upsert": "true"},
        )
        log.info(
            "recalibrar_concluido",
            f1=round(melhor_f1, 3),
            threshold_sugerido=melhor_threshold,
            amp_sugerido=amp_threshold_novo,
            depth_min_sugerido=depth_min_novo,
            storage_path=storage_path,
        )
    except Exception as exc:
        log.error("recalibrar_upload_failed", error=str(exc))
        supa.update_job_status(job_id, "erro", error_message=f"upload candidato: {exc}")
        return

    supa.update_job_status(job_id, "concluido")
