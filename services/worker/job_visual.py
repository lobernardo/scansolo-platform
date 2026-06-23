"""
Visual output job handler — job_type = 'visual'.

Gera uma imagem visual customizada (imagem_visual_url) por perfil GPR
sem afetar nenhuma saída técnica (bruta, científica, relatório, alvos,
detector, IA, cartografia).

Cadeia visual configurável:
  arr_raw
    → dewow  (visual_dewow_enabled ou base=dewow_bp)
    → bandpass (visual_bandpass_enabled ou base=dewow_bp)
    → bgremoval (visual_bgremoval_enabled=True — flag explícita, nunca bgr_traces=0)
    → tpow  (visual_tpow_enabled=True)
    → AGC   (visual_agc_enabled=True)
    → render_radargram
    → _radargrama_visual.png → gpr-images → imagem_visual_url

Atualiza APENAS: gpr_profiles.imagem_visual_url + gpr_profiles.visual_config
Nunca altera: imagem_bruta_url, imagem_cientifica_url, imagem_processada_url,
              imagem_anotada_url, imagem_preview_radan_5m_url, detector,
              relatório, IA, cartografia, processing_config do projeto.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

_VISUAL_BUCKET = "gpr-images"

# ── Defaults ──────────────────────────────────────────────────────────────────

DEFAULT_VISUAL_CONFIG: dict = {
    "visual_base":              "raw",
    "visual_depth_mode":        "real",
    "visual_depth_m":           None,
    "visual_aspect_ratio":      "default",
    "visual_normalization":     "linear_percentile",
    "visual_contrast":          2.5,
    "visual_colormap":          "gray",
    "visual_polarity":          "normal",
    "visual_dewow_enabled":     True,
    "visual_dewow_window":      5,
    "visual_bandpass_enabled":  True,
    "visual_bandpass_low_mhz":  80,
    "visual_bandpass_high_mhz": 500,
    "visual_bandpass_order":    5,
    "visual_bgremoval_enabled": False,
    "visual_bgremoval_traces":  30,
    "visual_tpow_enabled":      False,
    "visual_tpow_power":        0.5,
    "visual_agc_enabled":       True,
    "visual_agc_window":        150,
}


# ── Entry point ───────────────────────────────────────────────────────────────

def handle_visual_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]
    payload: dict = job.get("payload") or {}
    profile_id: str | None = payload.get("profile_id")

    if not profile_id:
        supa.update_job_status(job_id, "erro", error_message="payload.profile_id ausente")
        return

    # Merge defaults ← payload (payload wins)
    visual_config: dict = {**DEFAULT_VISUAL_CONFIG, **(payload.get("visual_config") or {})}

    log.info("visual_job_start", job_id=job_id, profile_id=profile_id,
             base=visual_config.get("visual_base"),
             aspect=visual_config.get("visual_aspect_ratio"))
    supa.update_job_status(job_id, "processando")

    tmp_dir = tempfile.mkdtemp(prefix="scansolo_visual_")
    try:
        _run_visual_job(supa, job_id, project_id, profile_id, visual_config, tmp_dir)
    except Exception as exc:
        log.error("visual_job_failed", job_id=job_id, error=str(exc))
        try:
            supa.update_job_status(job_id, "erro", error_message=str(exc)[:500])
        except Exception:
            pass
        raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Core logic ────────────────────────────────────────────────────────────────

def _run_visual_job(
    supa: "SupabaseClient",
    job_id: str,
    project_id: str,
    profile_id: str,
    vc: dict,
    tmp_dir: str,
) -> None:
    from gpr_engine.images import render_radargram
    from gpr_engine.reader import DZTReader

    # 1. Fetch profile — apenas os campos necessários
    r = (
        supa._client.table("gpr_profiles")
        .select("id, arquivo_dzt, velocity_mns, project_id")
        .eq("id", profile_id)
        .single()
        .execute()
    )
    profile_row = r.data
    if not profile_row:
        raise RuntimeError(f"Perfil {profile_id} não encontrado")

    arquivo_dzt: str = profile_row["arquivo_dzt"]
    velocity_mns = float(profile_row.get("velocity_mns") or 0.1)

    # 2. Localizar DZT no Storage
    r2 = (
        supa._client.table("project_files")
        .select("file_name, supabase_storage_path")
        .eq("project_id", project_id)
        .eq("file_name", arquivo_dzt)
        .eq("status", "confirmado")
        .limit(1)
        .execute()
    )
    dzt_records = r2.data or []
    if not dzt_records:
        raise RuntimeError(
            f"DZT '{arquivo_dzt}' não encontrado no Storage "
            f"(project_id={project_id}). Verifique se o upload foi confirmado."
        )
    dzt_record = dzt_records[0]

    # 3. Download DZT para tmp
    tmp_path = Path(tmp_dir)
    dzt_local = tmp_path / dzt_record["file_name"]
    dzt_bytes = supa.download_file("gpr-uploads", dzt_record["supabase_storage_path"])
    dzt_local.write_bytes(dzt_bytes)
    log.info("visual_dzt_downloaded", filename=arquivo_dzt, bytes=len(dzt_bytes))

    # 4. Ler DZT via reader canônico
    reader = DZTReader()
    dzt_data = reader.read(dzt_local)
    log.info("visual_dzt_read",
             n_traces=dzt_data.n_traces,
             n_samples=dzt_data.n_samples,
             twtt_max_ns=round(dzt_data.twtt_max_ns, 3))

    # 5. Aplicar cadeia visual
    arr = _apply_visual_chain(dzt_data, vc)

    # 6. Profundidade física e display
    depth_max_m = max(float(dzt_data.twtt_max_ns * velocity_mns / 2.0), 0.1)

    if vc.get("visual_depth_mode") == "manual":
        vdm = vc.get("visual_depth_m")
        display_depth_m: float | None = float(vdm) if vdm is not None else None
    else:
        display_depth_m = None  # render usa depth_max_m (profundidade física)

    # 7. Figsize por aspect_ratio
    figsize: tuple[float, float] = (20.0, 4.0) \
        if vc.get("visual_aspect_ratio") == "panoramic" else (10.0, 4.0)

    # 8. Renderizar
    stem = Path(arquivo_dzt).stem
    out_png = tmp_path / f"{stem}_radargrama_visual.png"
    render_radargram(
        arr=arr,
        output_path=out_png,
        dist_total_m=float(dzt_data.dist_total_m),
        depth_max_m=depth_max_m,
        title="Visual",
        colormap=str(vc.get("visual_colormap", "gray")),
        contrast=float(vc.get("visual_contrast", 2.5)),
        dpi=int(vc.get("visual_dpi", 150)),
        normalization=str(vc.get("visual_normalization", "linear_percentile")),
        polarity=str(vc.get("visual_polarity", "normal")),
        display_depth_m=display_depth_m,
        figsize=figsize,
    )
    log.info("visual_rendered", file=out_png.name,
             depth_max_m=round(depth_max_m, 3),
             display_depth_m=display_depth_m)

    # 9. Upload para gpr-images (bucket público)
    img_bytes = out_png.read_bytes()
    img_storage_path = f"{project_id}/visual/{profile_id[:8]}/{out_png.name}"
    supa.upload_file(_VISUAL_BUCKET, img_storage_path, img_bytes, "image/png")
    public_url = supa.get_public_url(_VISUAL_BUCKET, img_storage_path)
    log.info("visual_uploaded", path=img_storage_path)

    # 10. Salvar audit no visual_config
    vc_final = {
        **vc,
        "generated_at":          datetime.now(timezone.utc).isoformat(),
        "depth_max_m_physical":  round(depth_max_m, 3),
        "display_depth_m_used":  display_depth_m,
        "dzt_filename":          arquivo_dzt,
        "velocity_mns_used":     velocity_mns,
    }

    # 11. Atualizar APENAS imagem_visual_url + visual_config no perfil
    supa._client.table("gpr_profiles").update({
        "imagem_visual_url": public_url,
        "visual_config":     vc_final,
    }).eq("id", profile_id).execute()

    supa.update_job_status(job_id, "concluido")
    log.info("visual_job_done", job_id=job_id, profile_id=profile_id)


# ── Cadeia de filtros visuais ─────────────────────────────────────────────────

def _apply_visual_chain(dzt_data, vc: dict):
    """
    Aplica filtros visuais sobre arr_raw conforme visual_config.

    visual_base = "raw":
      Cada filtro controlado individualmente pelo flag correspondente.

    visual_base = "dewow_bp":
      Dewow e bandpass sempre aplicados (independente de visual_dewow_enabled
      e visual_bandpass_enabled). Demais filtros controlados por flag.
    """
    import numpy as np
    from gpr_engine.filters import agc, bandpass, bgremoval, dewow, tpow

    arr = dzt_data.arr_raw.copy().astype(np.float32)
    base = str(vc.get("visual_base", "raw"))

    # ── Dewow ──────────────────────────────────────────────────────────────────
    dewow_forced = (base == "dewow_bp")
    if dewow_forced or vc.get("visual_dewow_enabled", True):
        win = int(vc.get("visual_dewow_window", 5))
        arr = dewow(arr, window=max(1, win))
        log.debug("visual_filter_dewow", window=win)

    # ── Bandpass ───────────────────────────────────────────────────────────────
    bp_forced = (base == "dewow_bp")
    if bp_forced or vc.get("visual_bandpass_enabled", True):
        low  = float(vc.get("visual_bandpass_low_mhz",  80))
        high = float(vc.get("visual_bandpass_high_mhz", 500))
        order = int(vc.get("visual_bandpass_order", 5))
        if low > 0 and dzt_data.samp_freq_hz > 0 and low < high:
            try:
                arr = bandpass(
                    arr,
                    samp_freq_hz=float(dzt_data.samp_freq_hz),
                    low_mhz=low,
                    high_mhz=high,
                    order=order,
                )
                log.debug("visual_filter_bandpass", low=low, high=high)
            except Exception as exc:
                log.warning("visual_bandpass_skipped", reason=str(exc))

    # ── BGRemoval — flag explícita; nunca ativado por window=0 ─────────────────
    if vc.get("visual_bgremoval_enabled", False):
        traces = int(vc.get("visual_bgremoval_traces", 30))
        if traces > 0:
            arr = bgremoval(arr, window=traces)
            log.debug("visual_filter_bgremoval", traces=traces)

    # ── TPow ───────────────────────────────────────────────────────────────────
    if vc.get("visual_tpow_enabled", False):
        power = float(vc.get("visual_tpow_power", 0.5))
        arr = tpow(arr, power=power)
        log.debug("visual_filter_tpow", power=power)

    # ── AGC ────────────────────────────────────────────────────────────────────
    if vc.get("visual_agc_enabled", True):
        win = int(vc.get("visual_agc_window", 150))
        if win > 0:
            arr = agc(arr, window=win)
            log.debug("visual_filter_agc", window=win)

    return arr
