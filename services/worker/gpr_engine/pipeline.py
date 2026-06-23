"""
Orchestrador end-to-end do ScanSOLO GPR Engine.

process_dzt() recebe um arquivo .DZT e um diretorio de saida e executa
o pipeline completo, retornando ProcessResult com todos os outputs.

Modulos usados:
  reader   -- DZTReader: le o arquivo .DZT
  snr      -- calcular_snr_*, detectar_modo_processamento, detectar_time_zero
  flows    -- process_flows: tres fluxos de sinal (cientifico, relatorio, preview)
  images   -- render_*: gera PNGs
  arrays   -- save_engine_arrays: salva .npy
  metrics  -- build_pipeline_metrics, save_metrics_atomic: salva JSON
  detector -- run_scansolo_detector: detector de hiperboles (legado integrado)

Sem GPRPy. Sem Supabase.
"""
from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from gpr_engine._types import DZTData
from gpr_engine.flows import FlowArrays, process_flows
from gpr_engine.preflight import build_preflight_from_dzt_data, recommend_processing_config
from gpr_engine.reader import DZTReader
from gpr_engine.snr import (
    calcular_snr_imagem_db,
    calcular_snr_ratio,
    detectar_modo_processamento,
    detectar_time_zero,
)
from gpr_engine.images import (
    render_raw_image,
    render_scientific_image,
    render_report_image,
    render_radan_like_preview,
    render_radargram_readgssi_reference,
)
from gpr_engine.arrays import save_engine_arrays
from gpr_engine.metrics import build_pipeline_metrics, save_metrics_atomic
from gpr_engine.detector import DetectorResult, build_detector_params, run_scansolo_detector

_log = logging.getLogger("gpr_engine.pipeline")

_ENGINE_VERSION = "0.1.0"
_PIPELINE_VERSION = "2.0.0"
_ENGINE_NAME = "readgssi_engine"

_DEFAULTS: dict = {
    "dewow_window":        5,
    "bandpass_low_mhz":    80.0,
    "bandpass_high_mhz":   500.0,
    "bandpass_order":      5,
    "bandpass_tipo":       "butterworth",
    "bandpass_enabled":    True,
    "bgremoval_traces":    30,
    "tpow_power":          0.5,
    "agc_window":          150,
    "agc_window_preview":  80,
    "velocity_mns":        0.10,
    "contrast":            2.5,
    "colormap":            "gray",
    "dpi":                 150,
    "depth_preview_m":     5.0,
    "detector_input_mode": "raw",
    "det_depth_min_m":     0.30,
    # Fase 8.6 — visual profile
    # "readgssi_reference" e o default: processada.png = fiel ao readgssi (sem filtros ScanSOLO)
    # Altere explicitamente para "scientific" ou outro valor apenas quando necessario
    "visual_profile":      "readgssi_reference",
    "gain":                1.0,           # readgssi SymLogNorm gain (linthresh=std/gain)
    # G3 — render config (display-only; nao mutam dados)
    "normalization":       "linear_percentile",  # "linear_percentile" | "symlog" | "linear_minmax"
    "polarity":            "normal",              # "normal" | "inverted"
    "display_depth_m":     None,                  # Y-axis scale; None = profundidade fisica
    # G3 — preview visual depth mode (apenas para imagem de preview RADAN)
    # "stretch_to_preview_depth" (default): extent = depth_preview_m; data esticado visualmente
    # "axis_limit_no_stretch": extent = depth_max_m fisico; ylim = depth_preview_m (espaco vazio abaixo)
    "preview_visual_depth_mode": "stretch_to_preview_depth",
}


@dataclass
class ProcessResult:
    """Resultado completo do processamento de um DZT pelo motor GPR."""

    dzt_data: DZTData
    """Metadados e array bruto lidos pelo DZTReader."""

    flow_arrays: FlowArrays
    """Arrays dos tres fluxos de sinal (cientifico, relatorio, preview)."""

    image_paths: dict[str, Path]
    """Caminhos das imagens PNG geradas.
    Chaves: bruta, cientifica, relatorio, processada, preview_radan_5m, readgssi_reference,
    anotada (quando detector executado e imagem gerada com sucesso)."""

    array_paths: dict[str, Path]
    """Caminhos dos arrays .npy salvos.
    Chaves: raw, radargrama_cientifico, processado_sem_agc, processado_visual, processado."""

    metrics_path: Path
    """Caminho do arquivo pipeline_metrics.json."""

    metrics: dict
    """Dict retornado por build_pipeline_metrics (compativel com PipelineLog.tsx)."""

    output_dir: Path
    """Diretorio onde todos os outputs foram salvos."""

    index_row: dict
    """Linha compativel com index_projeto.csv (campos minimos garantidos)."""

    detected_targets: list[dict]
    """Alvos detectados prontos para CSV; lista vazia quando detector nao executou."""

    detector_status: str
    """
    "executed"         -- rodou e encontrou alvos
    "no_targets"       -- rodou mas 0 alvos apos filtros
    "skipped_no_dist"  -- dist_total_m == 0
    "failed"           -- excecao durante execucao
    """

    detector_error: str | None
    """Mensagem de erro quando detector_status == 'failed', senao None."""


def process_dzt(
    dzt_path: str | Path,
    output_dir: str | Path,
    config: dict | None = None,
    tipo_solo: str = "standard",
    stem: str | None = None,
    run_detector: bool = True,
) -> ProcessResult:
    """
    Processa um arquivo .DZT completo com o motor GPR.

    Fluxo interno:
      1. Leitura do DZT (DZTReader)
      2. SNR bruto + modo de processamento (minimo/padrao/agressivo)
      3. Time-zero detectado e logado (crop adiado para fase futura)
      4. Tres fluxos de sinal via process_flows()
      5. SNR medido em 6 estagios (raw, dewow_bp, cientifico, sem_agc, relatorio, preview_radan)
      6. Imagens PNG: bruta, cientifico, relatorio, processada (alias), preview RADAN
      7. Arrays .npy (raw, cientifico, sem_agc, visual, processado alias)
      8. Detector de hiperboles (run_scansolo_detector): Hough+CurveFit+DeltaT+fisica
         - entrada: arr_raw (v2.0.0 default; detector_input_mode configuravel)
         - saida: _anotada_completa.png sobre arr_cientifico + lista de alvos
         - falha graciosamente (status="failed" nao aborta o pipeline)
      9. pipeline_metrics.json (atomico) com detector_status
     10. index_row com campos minimos para index_projeto.csv

    :param dzt_path:     Caminho para o arquivo .DZT
    :param output_dir:   Diretorio de saida (criado automaticamente)
    :param config:       Overrides sobre _DEFAULTS (usuario/preset)
    :param tipo_solo:    "standard" | "arenoso" | "argiloso" | "umido" | "pedregoso"
    :param stem:         Nome base dos arquivos de saida (default: dzt_path.stem)
    :param run_detector: Executa detector de hiperboles (default: True)
    :returns:            ProcessResult com todos os outputs
    """
    dzt_path = Path(dzt_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _stem = stem or dzt_path.stem

    # 1. Leitura do DZT
    reader = DZTReader()
    dzt_data = reader.read(dzt_path)

    # 2. Config final: defaults + overrides do usuario; samp_freq_hz sempre do header
    final_config: dict = {**_DEFAULTS, **(config or {})}
    final_config["samp_freq_hz"] = dzt_data.samp_freq_hz
    final_config["tipo_solo"] = tipo_solo

    # 2b. Preflight: extrai metadados do DZT e gera recomendacoes (sem alterar config)
    preflight_metadata = build_preflight_from_dzt_data(dzt_data)
    _selected_preset_pf: dict = {}
    if final_config.get("antenna_freq_mhz"):
        _selected_preset_pf["antenna_freq_mhz"] = int(final_config["antenna_freq_mhz"])
    if final_config.get("preset_name"):
        _selected_preset_pf["name"] = str(final_config["preset_name"])
    preflight_recommendation = recommend_processing_config(
        preflight_metadata, selected_preset=_selected_preset_pf,
    )

    _log.info(
        "readgssi_preflight_done filename=%s confidence=%s "
        "freq_detected=%s velocity_header=%.4f",
        dzt_data.dzt_filename,
        preflight_metadata["header_confidence"],
        preflight_metadata["antenna_freq_mhz_detected"],
        preflight_metadata["velocity_header_mns"],
    )
    for _w in preflight_metadata.get("warnings", []):
        _log.warning("readgssi_preflight_warning filename=%s msg=%r",
                     dzt_data.dzt_filename, _w)
    if preflight_recommendation.get("frequency_mismatch"):
        _log.warning(
            "readgssi_frequency_mismatch filename=%s "
            "detected_freq=%s selected_freq=%s recommended_family=%s "
            "recommended_velocity=%.4f",
            dzt_data.dzt_filename,
            preflight_recommendation.get("detected_freq_mhz"),
            preflight_recommendation.get("selected_preset_freq_mhz"),
            preflight_recommendation.get("recommended_preset_family"),
            preflight_recommendation.get("recommended_velocity_mns", 0.0),
        )

    # 3. SNR do dado bruto e modo de processamento
    snr_raw_ratio = calcular_snr_ratio(dzt_data.arr_raw)
    snr_raw_db = calcular_snr_imagem_db(dzt_data.arr_raw)
    modo_processamento = detectar_modo_processamento(snr_raw_db, tipo_solo)

    # 4. Time-zero detectado (logado no index_row; crop nao aplicado nesta fase)
    timezero_detected = detectar_time_zero(dzt_data.arr_raw)

    # 5. Profundidade maxima: twtt_max_ns x velocity / 2
    velocity_mns = float(final_config["velocity_mns"])
    depth_max_m = round(dzt_data.twtt_max_ns * velocity_mns / 2.0, 4)
    depth_preview_m = float(final_config.get("depth_preview_m", 5.0))

    # 6. Tres fluxos de sinal
    flow_arrays = process_flows(dzt_data.arr_raw, final_config)

    # 7. SNR em 6 estagios do pipeline
    snr_stages_db = {
        "raw":           snr_raw_db,
        "dewow_bp":      calcular_snr_imagem_db(flow_arrays.arr_dewow_bp),
        "cientifico":    calcular_snr_imagem_db(flow_arrays.arr_cientifico),
        "sem_agc":       calcular_snr_imagem_db(flow_arrays.arr_sem_agc),
        "relatorio":     calcular_snr_imagem_db(flow_arrays.arr_relatorio),
        "preview_radan": calcular_snr_imagem_db(flow_arrays.arr_preview_radan),
    }

    # 8. Imagens PNG
    dist_m = float(dzt_data.dist_total_m)

    # G3: display_depth_m — limite VISUAL do eixo Y (nao altera dados nem extent).
    # depth_max_m (fisico) sempre vai para o extent.
    # display_depth_m (do config) vai apenas para set_ylim.
    # None = usa depth_max_m como limite visual (comportamento identico ao original).
    _cfg_display_depth = final_config.get("display_depth_m")
    _display_depth_m: float | None = (
        float(_cfg_display_depth)
        if _cfg_display_depth is not None and float(_cfg_display_depth) > 0
        else None
    )
    if _display_depth_m is not None and abs(_display_depth_m - depth_max_m) > 1e-3:
        _log.warning(
            "display_depth_differs_from_physical dzt=%s "
            "display_depth_m=%.3f depth_max_m=%.3f (physical) "
            "mode=%s",
            dzt_data.dzt_filename,
            _display_depth_m,
            depth_max_m,
            "crop" if _display_depth_m < depth_max_m else "extend",
        )

    render_kw = {
        "contrast":        float(final_config.get("contrast", 2.5)),
        "colormap":        str(final_config.get("colormap", "gray")),
        "dpi":             int(final_config.get("dpi", 150)),
        "normalization":   str(final_config.get("normalization", "linear_percentile")),
        "polarity":        str(final_config.get("polarity", "normal")),
        "display_depth_m": _display_depth_m,  # None → renderer usa depth_max_m
    }

    # depth_max_m (fisico) e passado como 4o arg (depth_max_m) → extent
    # _display_depth_m e passado via render_kw → set_ylim apenas
    p_bruta = render_raw_image(
        dzt_data.arr_raw,
        out_dir / f"{_stem}_bruta.png",
        dist_m, depth_max_m,
        **render_kw,
    )
    p_cientifica = render_scientific_image(
        flow_arrays.arr_cientifico,
        out_dir / f"{_stem}_radargrama_cientifico.png",
        dist_m, depth_max_m,
        **render_kw,
    )
    p_relatorio = render_report_image(
        flow_arrays.arr_relatorio,
        out_dir / f"{_stem}_radargrama_relatorio.png",
        dist_m, depth_max_m,
        **render_kw,
    )
    # _processada.png e alias de _radargrama_relatorio.png (backward compat)
    p_processada = out_dir / f"{_stem}_processada.png"
    shutil.copy2(p_relatorio, p_processada)

    # G3 — preview visual depth mode:
    # "stretch_to_preview_depth" (default): extent = depth_preview_m → data esticado visualmente
    # "axis_limit_no_stretch": extent = depth_max_m fisico → ylim = depth_preview_m (espaco vazio)
    preview_visual_depth_mode = str(final_config.get("preview_visual_depth_mode", "stretch_to_preview_depth"))
    _visual_stretch_occurred = (
        preview_visual_depth_mode == "stretch_to_preview_depth" and
        abs(depth_preview_m - depth_max_m) > 1e-3
    )

    if preview_visual_depth_mode == "axis_limit_no_stretch":
        # Modo fisicamente correto: dados mapeados na profundidade real, eixo Y estende-se ate depth_preview_m
        p_preview = render_radan_like_preview(
            flow_arrays.arr_preview_radan,
            out_dir / f"{_stem}_radargrama_preview_radan_5m.png",
            dist_m, depth_max_m,                                 # extent = profundidade FISICA
            footer_text="AVISO: preview RADAN 5m -- nao usar como radargrama cientifico",
            **{**render_kw, "display_depth_m": depth_preview_m}, # ylim = depth_preview_m (sem esticamento)
        )
    else:  # stretch_to_preview_depth (default, backward compat)
        # Modo visual: dados esticados para preencher depth_preview_m (comportamento original)
        p_preview = render_radan_like_preview(
            flow_arrays.arr_preview_radan,
            out_dir / f"{_stem}_radargrama_preview_radan_5m.png",
            dist_m, depth_preview_m,                             # extent = depth_preview_m (estica)
            footer_text="AVISO: preview RADAN 5m -- nao usar como radargrama cientifico",
            **render_kw,
        )

    # readgssi_reference: arr_raw -> bgremoval_readgssi(window=0) -> SymLogNorm
    # Sempre usa normalizacao SymLogNorm (identica ao readgssi) — nao alterada por render_kw.
    from gpr_engine.filters import bgremoval_readgssi as _bgr_readgssi
    _arr_readgssi_ref = _bgr_readgssi(dzt_data.arr_raw, window=0)
    p_readgssi_ref = render_radargram_readgssi_reference(
        _arr_readgssi_ref,
        out_dir / f"{_stem}_radargrama_readgssi_reference.png",
        dist_m, depth_max_m,                   # extent usa profundidade FISICA
        gain=float(final_config.get("gain", 1.0)),
        colormap=str(final_config.get("colormap", "gray")),
        dpi=int(final_config.get("dpi", 150)),
        display_depth_m=_display_depth_m,       # limite VISUAL apenas
    )

    image_paths: dict[str, Path] = {
        "bruta":                p_bruta,
        "cientifica":           p_cientifica,
        "relatorio":            p_relatorio,
        "processada":           p_processada,
        "preview_radan_5m":     p_preview,
        "readgssi_reference":   p_readgssi_ref,
    }

    # 9. Arrays .npy
    array_paths = save_engine_arrays(
        flow_arrays, out_dir, stem=_stem, arr_raw=dzt_data.arr_raw,
    )

    # 10. Detector de hiperboles (Hough + CurveFit + DeltaT + fisica)
    det_result: DetectorResult
    if run_detector:
        det_params = build_detector_params(
            config=final_config,
            velocity_mns=velocity_mns,
            samp_freq_hz=float(dzt_data.samp_freq_hz),
            dist_total_m=float(dzt_data.dist_total_m),
            n_traces=int(dzt_data.n_traces),
        )
        p_anotada = out_dir / f"{_stem}_anotada_completa.png"
        det_result = run_scansolo_detector(
            arr_detection=dzt_data.arr_raw,
            arr_sem_agc=flow_arrays.arr_sem_agc,
            arr_raw=dzt_data.arr_raw,
            arr_annotation=flow_arrays.arr_cientifico,
            detector_params=det_params,
            output_path=p_anotada,
            dzt_filename=dzt_data.dzt_filename,
            config=final_config,
            dist_total_m=float(dzt_data.dist_total_m),
        )
        if det_result.anotada_ok and det_result.anotada_path is not None:
            image_paths["anotada"] = det_result.anotada_path
        _log.info(
            "detector_done dzt=%s status=%s n_alvos=%d anotada_ok=%s",
            dzt_data.dzt_filename, det_result.status, det_result.n_total, det_result.anotada_ok,
        )
    else:
        det_result = DetectorResult(status="skipped_not_integrated")

    # 11. Pipeline metrics JSON
    metrics = build_pipeline_metrics(
        dzt_data=dzt_data,
        flow_arrays=flow_arrays,
        config=final_config,
        modo_processamento=modo_processamento,
        snr_raw_db=snr_raw_db,
        snr_raw_ratio=snr_raw_ratio,
        snr_stages_db=snr_stages_db,
        image_paths=image_paths,
        array_paths=array_paths,
        engine_version=_ENGINE_VERSION,
        pipeline_version=_PIPELINE_VERSION,
        engine_name=_ENGINE_NAME,
        preflight_metadata=preflight_metadata,
        preflight_recommendation=preflight_recommendation,
        detector_status=det_result.status,
        detector_n_total=det_result.n_total,
        detector_error=det_result.detector_error,
        imagem_anotada_ok=det_result.anotada_ok,
    )
    metrics_path = save_metrics_atomic(
        metrics, out_dir / f"{_stem}_pipeline_metrics.json",
    )

    # 11. index_row compativel com index_projeto.csv
    index_row: dict = {
        "arquivo":                        str(dzt_data.dzt_filename),
        "n_tracos":                       int(dzt_data.n_traces),
        "distancia_max_m":                float(dzt_data.dist_total_m),
        "profundidade_max_m":             depth_max_m,               # profundidade FISICA
        "display_depth_m":                _display_depth_m,          # limite visual tecnico (None = auto)
        "snr_raw_db":                     snr_raw_db,
        "snr_raw_ratio":                  snr_raw_ratio,
        "modo_processamento":             modo_processamento,
        "tipo_solo":                      tipo_solo,
        "velocity_mns":                   velocity_mns,
        "timezero_detected":              timezero_detected,
        "engine_name":                    _ENGINE_NAME,
        "pipeline_version":               _PIPELINE_VERSION,
        "imagem_bruta":                   str(p_bruta),
        "imagem_cientifica":              str(p_cientifica),
        "imagem_relatorio":               str(p_relatorio),
        "imagem_preview_radan_5m":        str(p_preview),
        "imagem_readgssi_reference":      str(p_readgssi_ref),
        "metrics_path":                   str(metrics_path),
        # G3 — preview depth mode audit fields
        "depth_preview_m":                depth_preview_m,
        "preview_visual_depth_mode":      preview_visual_depth_mode,
        "visual_stretch_occurred":        _visual_stretch_occurred,
    }

    return ProcessResult(
        dzt_data=dzt_data,
        flow_arrays=flow_arrays,
        image_paths=image_paths,
        array_paths=array_paths,
        metrics_path=metrics_path,
        metrics=metrics,
        output_dir=out_dir,
        index_row=index_row,
        detected_targets=det_result.targets,
        detector_status=det_result.status,
        detector_error=det_result.detector_error,
    )
