"""
gpr_engine/detector.py — Bridge entre detector legado e readgssi_engine.

Wraps detector_hiperboles.py (pipeline/detector_hiperboles.py) para uso no
novo motor GPR sem modificar o módulo legado.

Funcao publica:
  run_scansolo_detector(arr_detection, arr_sem_agc, arr_raw, arr_annotation,
                        detector_params, output_path, dzt_filename, config)
  -> DetectorResult

Funcoes auxiliares:
  build_detector_params(config, velocity_mns, samp_freq_hz, dist_total_m, n_traces)
  -> dict de params para detectar_hiperboles / enriquecer_deteccoes_fisica
"""
from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

_log = logging.getLogger("gpr_engine.detector")

# Defaults mapeados de pipeline config -> detector legado
_DET_DEFAULTS: dict = {
    "amp_threshold":         0.50,
    "h_min_m":               0.10,
    "h_max_m":               3.00,
    "h_step_m":              0.04,
    "col_search_half":       80,
    "nms_radius_m":          0.50,
    "top_n":                 25,
    "cf_wing_half_m":        2.0,
    "cf_amp_frac":           0.30,
    "dt_min_diam_m":         0.05,
    "dt_max_diam_m":         1.50,
    "dt_conf_frac":          0.20,
    "fis_ativo":             True,
    "fis_amp_metal_thr":     0.65,
    "fis_amp_nao_metal_thr": 0.22,
    "det_min_score_csv":     30,
    "det_min_score_plot":    40,
    "det_depth_min_m":       0.30,
}


@dataclass
class DetectorResult:
    """Resultado do detector de alvos."""

    status: str
    """
    "executed"         -- rodou e encontrou alvos (apos filtros)
    "no_targets"       -- rodou mas 0 alvos apos filtros de profundidade e score
    "skipped_no_dist"  -- dist_total_m == 0; dx_m nao calculavel
    "failed"           -- excecao durante execucao do detector
    """

    targets: list[dict] = field(default_factory=list)
    """Dicts prontos para escrever no CSV de alvos (_alvos.csv)."""

    anotada_path: Path | None = None
    """PNG anotado gerado por plotar_deteccoes, ou None se nao gerado."""

    anotada_ok: bool = False
    """True quando anotada_path existe em disco."""

    detector_error: str | None = None
    """Mensagem de erro quando status == 'failed'."""

    n_total: int = 0
    """Total de alvos apos filtros (len(targets))."""

    n_score_30: int = 0
    """Alvos com confidence_score_0_100 >= 30."""


def build_detector_params(
    config: dict,
    velocity_mns: float,
    samp_freq_hz: float,
    dist_total_m: float,
    n_traces: int,
) -> dict:
    """
    Constroi dict de params do detector legado a partir da config do pipeline.

    velocity_mns : m/ns (converte para m/s internamente)
    samp_freq_hz : frequencia de amostragem em Hz (dt_s = 1 / samp_freq_hz)
    dist_total_m : distancia total da linha (m); 0 quando coleta por tempo
    n_traces     : numero de tracos do DZT
    """
    dx_m = dist_total_m / max(1, n_traces) if dist_total_m > 0 else 0.03
    dt_s = 1.0 / max(samp_freq_hz, 1.0)

    return {
        "v_m_per_s":             velocity_mns * 1e9,
        "dt_s":                  dt_s,
        "dx_m":                  dx_m,
        "amp_threshold":         float(config.get("det_amp_threshold", _DET_DEFAULTS["amp_threshold"])),
        "h_min_m":               float(config.get("det_h_min_m", _DET_DEFAULTS["h_min_m"])),
        "h_max_m":               float(config.get("det_h_max_m", _DET_DEFAULTS["h_max_m"])),
        "h_step_m":              float(config.get("h_step_m", _DET_DEFAULTS["h_step_m"])),
        "col_search_half":       int(config.get("col_search_half", _DET_DEFAULTS["col_search_half"])),
        "nms_radius_m":          float(config.get("nms_radius_m", _DET_DEFAULTS["nms_radius_m"])),
        "top_n":                 int(config.get("det_top_n", _DET_DEFAULTS["top_n"])),
        "cf_wing_half_m":        float(config.get("cf_wing_half_m", _DET_DEFAULTS["cf_wing_half_m"])),
        "cf_amp_frac":           float(config.get("cf_amp_frac", _DET_DEFAULTS["cf_amp_frac"])),
        "dt_min_diam_m":         float(config.get("dt_min_diam_m", _DET_DEFAULTS["dt_min_diam_m"])),
        "dt_max_diam_m":         float(config.get("dt_max_diam_m", _DET_DEFAULTS["dt_max_diam_m"])),
        "dt_conf_frac":          float(config.get("dt_conf_frac", _DET_DEFAULTS["dt_conf_frac"])),
        "fis_ativo":             bool(config.get("fis_ativo", _DET_DEFAULTS["fis_ativo"])),
        "fis_amp_metal_thr":     float(config.get("fis_amp_metal_thr", _DET_DEFAULTS["fis_amp_metal_thr"])),
        "fis_amp_nao_metal_thr": float(config.get("fis_amp_nao_metal_thr", _DET_DEFAULTS["fis_amp_nao_metal_thr"])),
    }


def run_scansolo_detector(
    arr_detection: np.ndarray,
    arr_sem_agc: np.ndarray,
    arr_raw: np.ndarray,
    arr_annotation: np.ndarray,
    detector_params: dict,
    output_path: Path,
    dzt_filename: str,
    config: dict,
    dist_total_m: float = 0.0,
) -> DetectorResult:
    """
    Roda o detector legado sobre os arrays do readgssi_engine.

    Entradas:
      arr_detection  -- arr_raw (v2.0.0 default; melhor CurveFit com dado bruto)
      arr_sem_agc    -- fluxo bgremoval+tpow, sem AGC; para analise fisica de amplitude
      arr_raw        -- dado bruto pre-qualquer-filtro; evidencia independente
      arr_annotation -- arr_cientifico (dewow+bp+tpow, sem AGC); background do PNG anotado
      detector_params-- dict de params (output de build_detector_params)
      output_path    -- caminho destino do PNG {stem}_anotada_completa.png
      dzt_filename   -- basename do DZT (campo arquivo_dzt no CSV de alvos)
      config         -- config efetiva do pipeline (para det_min_score_csv/plot/depth_min)
      dist_total_m   -- distancia total da linha; se 0, pula detector

    Retorna DetectorResult com status, targets, anotada_path.
    Nunca levanta excecao — erros viram status="failed".
    """
    if dist_total_m <= 0:
        _log.info("detector_skipped_no_dist", dzt=dzt_filename)
        return DetectorResult(status="skipped_no_dist")

    try:
        _ensure_legacy_path()
        from detector_hiperboles import (   # noqa: PLC0415
            detectar_hiperboles,
            enriquecer_deteccoes_fisica,
            plotar_deteccoes,
        )
    except ImportError as exc:
        msg = f"detector_hiperboles nao importavel: {exc}"
        _log.warning("detector_import_failed", error=msg)
        return DetectorResult(status="failed", detector_error=msg)

    det_min_score_csv  = int(config.get("det_min_score_csv",  _DET_DEFAULTS["det_min_score_csv"]))
    det_min_score_plot = int(config.get("det_min_score_plot", _DET_DEFAULTS["det_min_score_plot"]))
    det_depth_min_m    = float(config.get("det_depth_min_m",  _DET_DEFAULTS["det_depth_min_m"]))
    top_n              = int(detector_params.get("top_n", 25))

    try:
        _log.info("detector_start", dzt=dzt_filename, shape=arr_detection.shape)

        # 1. Deteccao: Hough -> CurveFit -> DeltaT
        deteccoes_df, _accum, _depths = detectar_hiperboles(
            arr_detection, params=detector_params, top_n=top_n,
        )

        if deteccoes_df.empty:
            _log.info("detector_no_raw_detections", dzt=dzt_filename)
            return DetectorResult(status="no_targets")

        # 2. Enriquecimento fisico (arr_sem_agc para amplitude/fase sem distorcao AGC)
        deteccoes_enriq, _espectro = enriquecer_deteccoes_fisica(
            arr_detection, arr_sem_agc, arr_raw, deteccoes_df, detector_params,
        )

        # 3. Filtros pos-deteccao
        df = deteccoes_enriq.copy()

        if det_depth_min_m > 0:
            n_before = len(df)
            df = df[df["depth_m"] >= det_depth_min_m].reset_index(drop=True)
            _log.info("detector_depth_filter", removed=n_before - len(df), remaining=len(df))

        if det_min_score_csv > 0 and "confidence_score_0_100" in df.columns:
            n_before = len(df)
            df = df[df["confidence_score_0_100"] >= det_min_score_csv].reset_index(drop=True)
            _log.info("detector_score_filter_csv", removed=n_before - len(df), remaining=len(df))

        if df.empty:
            _log.info("detector_empty_after_filters", dzt=dzt_filename)
            return DetectorResult(status="no_targets")

        # 4. Construir lista de dicts para CSV
        targets: list[dict] = []
        for _, row in df.iterrows():
            amp_sem = float(row.get("amplitude_relativa_sem_agc", 0.0))
            amp_raw = float(row.get("amplitude_relativa_raw", 0.0))
            targets.append({
                "arquivo_dzt":                dzt_filename,
                "rank":                       int(row.get("rank", 0)),
                "x_m":                        float(row.get("x_m", 0.0)),
                "depth_m":                    float(row.get("depth_m", 0.0)),
                "diam_est_m":                 float(row.get("diam_est_m", 0.0)),
                "diam_confianca":             str(row.get("diam_confianca", "baixa")),
                "fit_ok":                     bool(row.get("fit_ok", False)),
                "score":                      float(row.get("score", 0.0)),
                "tipo_material":              str(row.get("tipo_material", "N/A")),
                "confianca_tipo":             str(row.get("confianca_tipo", "N/A")),
                "amplitude_relativa_max":     round(max(amp_sem, amp_raw), 4),
                "amplitude_relativa_raw":     round(amp_raw, 4),
                "fase_consistente":           bool(row.get("fase_consistente", False)),
                "evidencia_raw":              bool(row.get("evidencia_raw", False)),
                "evidencia_sem_agc":          bool(row.get("evidencia_sem_agc", False)),
                "snr_local":                  float(row.get("snr_local", 0.0)),
                "confidence_score_0_100":     int(row.get("confidence_score_0_100", 0)),
                "confidence_label_tecnico":   str(row.get("confidence_label_tecnico", "baixa")),
                "confidence_label_relatorio": str(row.get("confidence_label_relatorio", "baixa")),
                "motivo_confianca":           str(row.get("motivo_confianca", "")),
            })

        n_total   = len(targets)
        n_score30 = sum(1 for t in targets if int(t.get("confidence_score_0_100", 0)) >= 30)
        _log.info("detector_results", dzt=dzt_filename, n_total=n_total, n_score30=n_score30)

        # 5. Imagem anotada sobre arr_annotation (arr_cientifico — sem AGC, leitura tecnica)
        anotada_ok = False
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            plotar_deteccoes(
                arr_annotation, df, detector_params,
                output_path=str(output_path),
                min_score=det_min_score_plot,
            )
            anotada_ok = output_path.exists()
            _log.info("detector_anotada_saved", path=str(output_path), ok=anotada_ok)
        except Exception as plot_exc:
            _log.warning("detector_plot_failed", error=str(plot_exc))

        return DetectorResult(
            status="executed" if n_total > 0 else "no_targets",
            targets=targets,
            anotada_path=output_path if anotada_ok else None,
            anotada_ok=anotada_ok,
            n_total=n_total,
            n_score_30=n_score30,
        )

    except Exception as exc:
        msg = str(exc)
        _log.error("detector_failed", dzt=dzt_filename, error=msg, exc_info=True)
        return DetectorResult(status="failed", detector_error=msg)


def _ensure_legacy_path() -> None:
    """Garante que services/worker/pipeline/ esta no sys.path para importar o detector legado."""
    pipeline_dir = Path(__file__).resolve().parent.parent / "pipeline"
    path_str = str(pipeline_dir)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)
