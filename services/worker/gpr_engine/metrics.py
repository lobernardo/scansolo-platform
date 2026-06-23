"""
Modulo de metricas de pipeline para o ScanSOLO GPR Engine.

Monta e persiste o pipeline_metrics.json compativel com o que a UI
(PipelineLog.tsx / getPipelineMetrics server action) espera nos campos
salvos em gpr_profiles.metricas_pipeline_url.

Funcoes principais:
  build_pipeline_metrics  -- constroi dict com todos os campos obrigatorios
  save_metrics_atomic     -- persiste JSON via escrita atomica (UTF-8, indentado)
  load_metrics            -- le e retorna o dict do JSON

Campos obrigatorios do JSON:
  dzt_filename, pipeline_version, engine_name, modo_processamento, tipo_solo,
  n_tracos, dist_total_m, profundidade_max_m, snr_raw_db, snr_raw_ratio,
  snr_stages_db, filtros_customizados, imagem_bruta_ok, imagem_cientifica_ok,
  imagem_relatorio_ok, imagem_preview_radan_5m_ok, imagem_anotada_ok,
  detector_input_mode, det_depth_min_m_usado, dzt_sha256, outputs

Regras:
  - Escrita atomica via arquivo temporario + os.replace()
  - JSON UTF-8, indentado (indent=2), sem escape de ASCII
  - Converte Path -> str e numpy scalars -> tipos Python nativos
  - Nao importa GPRPy
  - Nao depende de pipeline_v1.py
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

from gpr_engine._types import DZTData
from gpr_engine.flows import FlowArrays


# ---------------------------------------------------------------------------
# Serializacao JSON -- handler para tipos nao nativos
# ---------------------------------------------------------------------------

def _to_serializable(obj: Any) -> Any:
    """
    Converte tipos nao-JSON-nativos para representacoes serializaveis.

    Cobertura: Path, numpy integers, numpy floats, numpy bool, numpy ndarray.
    Levanta TypeError para tipos desconhecidos.
    """
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _path_ok(paths: dict[str, Any] | None, key: str) -> bool:
    """Retorna True se paths[key] nao for None."""
    if not paths:
        return False
    return paths.get(key) is not None


def _paths_to_str(paths: dict[str, Any] | None) -> dict[str, str | None]:
    """Converte todos os valores Path para str; preserva None."""
    if not paths:
        return {}
    return {k: str(v) if v is not None else None for k, v in paths.items()}


def _calc_profundidade_max_m(dzt_data: DZTData, config: dict) -> float:
    """
    Calcula profundidade maxima em metros.

    Usa velocity_mns do config (se presente) ou wave_speed_mns do DZTData.
    Formula: profundidade = twtt_max_ns * velocity / 2
    """
    velocity = float(config.get("velocity_mns", dzt_data.wave_speed_mns))
    return round(float(dzt_data.twtt_max_ns) * velocity / 2.0, 4)


# ---------------------------------------------------------------------------
# Construcao do dict de metricas
# ---------------------------------------------------------------------------

def _bandpass_descricao(config: dict) -> tuple[str, float, float]:
    """
    Retorna (descricao, low_mhz, high_mhz) do bandpass configurado.

    descricao: "desativado" | "80-500 MHz" (ou faixa real do config)
    low_mhz/high_mhz: 0.0/0.0 quando desativado
    """
    low_mhz = float(config.get("bandpass_low_mhz", 80.0))
    high_mhz = float(config.get("bandpass_high_mhz", 500.0))
    enabled = bool(config.get("bandpass_enabled", True)) and low_mhz > 0
    if not enabled:
        return "desativado", 0.0, 0.0
    return f"{low_mhz:.0f}-{high_mhz:.0f} MHz", low_mhz, high_mhz


def _render_profile_fields(config: dict) -> dict:
    """
    Campos de rastreabilidade do perfil de renderizacao (visual_profile).

    Quando visual_profile="readgssi_reference":
      renderer=readgssi_reference, normalization=SymLogNorm, background_removal=readgssi_bgr
    Caso contrario (scientific/relatorio):
      renderer=relatorio, normalization=linear_percentile99, background_removal=bgremoval_windowed
    """
    visual_profile = str(config.get("visual_profile", "readgssi_reference"))
    is_readgssi = visual_profile == "readgssi_reference"
    bgr_window_used = 0 if is_readgssi else int(config.get("bgremoval_traces", 30))
    # G3: render config — user-explicit, never hidden
    normalization = str(config.get("normalization", "linear_percentile"))
    polarity = str(config.get("polarity", "normal"))
    _cfg_display_depth = config.get("display_depth_m")
    display_depth_m = float(_cfg_display_depth) if _cfg_display_depth is not None else None
    return {
        "visual_profile":        visual_profile,
        "renderer":              visual_profile if is_readgssi else "relatorio",
        "normalization":         "SymLogNorm" if is_readgssi else normalization,
        "background_removal":    "readgssi_bgr" if is_readgssi else "bgremoval_windowed",
        "bgr_window":            bgr_window_used,
        "gain":                  float(config.get("gain", 1.0)),
        "polarity":              polarity,
        # G3 — depth fields
        "display_depth_m":       display_depth_m,
        "depth_display_mode":    "axis_limit_no_stretch",
        "depth_source":          "velocity_config" if config.get("velocity_mns") else "velocity_default",
    }


def build_pipeline_metrics(
    dzt_data: DZTData,
    flow_arrays: FlowArrays | None,
    config: dict,
    modo_processamento: str,
    snr_raw_db: float,
    snr_raw_ratio: float,
    snr_stages_db: dict[str, float] | None = None,
    image_paths: dict[str, Any] | None = None,
    array_paths: dict[str, Any] | None = None,
    engine_version: str = "0.1.0",
    pipeline_version: str = "2.0.0",
    engine_name: str = "readgssi_engine",
    dzt_sha256: str | None = None,
    preflight_metadata: dict | None = None,
    preflight_recommendation: dict | None = None,
    detector_status: str = "skipped_not_integrated",
    detector_n_total: int = 0,
    detector_error: str | None = None,
    imagem_anotada_ok: bool = False,
) -> dict:
    """
    Constroi o dict de metricas do pipeline para um DZT processado.

    O dict resultante e diretamente serializavel para JSON via
    save_metrics_atomic() e compativel com os campos que PipelineLog.tsx
    consome via getPipelineMetrics() server action.

    Fase 8.10: campos de rastreabilidade do readgssi_engine adicionados ao
    nivel raiz (visual_profile, renderer, normalization, background_removal,
    bgr_window, gain, skip_ia, detector_status) e campos de filtros efetivos
    promovidos ao nivel raiz (dewow_window, bandpass_*, bgremoval_traces,
    tpow_power, agc_window, velocity_mns, depth_tecnica_m, preview_*).

    :param dzt_data:          Metadados e array bruto do DZT (de DZTReader.read)
    :param flow_arrays:       Resultados dos tres fluxos (de process_flows); pode ser None
    :param config:            Dict de parametros usados no processamento
    :param modo_processamento: "minimo" | "padrao" | "agressivo"
    :param snr_raw_db:        SNR do dado bruto em dB (de calcular_snr_imagem_db)
    :param snr_raw_ratio:     SNR ratio S/sigma (de calcular_snr_ratio)
    :param snr_stages_db:     Dict estagio -> SNR em dB (ex: raw, dewow_bp, cientifico)
    :param image_paths:       Dict nome -> Path | None para cada imagem gerada
    :param array_paths:       Dict nome -> Path | None para cada .npy gerado
    :param engine_version:    Versao do gpr_engine (default: "0.1.0")
    :param pipeline_version:  Versao do pipeline (default: "2.0.0")
    :param engine_name:       Nome do motor (default: "readgssi_engine")
    :param dzt_sha256:        SHA-256 do DZT; se None, usa dzt_data.dzt_sha256
    :returns:                 Dict pronto para save_metrics_atomic()
    """
    sha = dzt_sha256 if dzt_sha256 is not None else dzt_data.dzt_sha256
    prof_max = _calc_profundidade_max_m(dzt_data, config)
    velocity = float(config.get("velocity_mns", 0.10))
    depth_preview = float(config.get("depth_preview_m", 5.0))
    bandpass_descr, bp_low, bp_high = _bandpass_descricao(config)

    return {
        # -- Identidade do arquivo e engine --------------------------------
        "dzt_filename":      dzt_data.dzt_filename,
        "dzt_sha256":        sha,
        "engine_name":       engine_name,
        "engine_version":    engine_version,
        "pipeline_version":  pipeline_version,

        # -- Configuracao de processamento ---------------------------------
        "modo_processamento":    modo_processamento,
        "tipo_solo":             config.get("tipo_solo", "standard"),
        "preset_name":           config.get("preset_name", None),
        "preset_id":             config.get("preset_id", None),
        "detector_input_mode":   config.get("detector_input_mode", "raw"),
        "det_depth_min_m_usado": float(config.get("det_depth_min_m", 0.30)),
        "filtros_customizados":  config,

        # -- Rastreabilidade do perfil de renderizacao (Fase 8.10) --------
        **_render_profile_fields(config),
        "skip_ia":            bool(config.get("skip_ia", False)),
        "detector_status":    detector_status,
        "detector_n_total":   detector_n_total,
        "detector_error":     detector_error,

        # -- Filtros efetivos no nivel raiz (lidos por PipelineLog via UI) -
        # Dewow
        "dewow_window":         int(config.get("dewow_window", 5)),
        # Bandpass
        "bandpass_aplicado":    bandpass_descr,
        "bandpass_low_mhz_usado":  bp_low,
        "bandpass_high_mhz_usado": bp_high,
        "bandpass_order_usado":    int(config.get("bandpass_order", 5)),
        "bandpass_tipo_usado":     str(config.get("bandpass_tipo", "butterworth")),
        # BGRemoval / TPow / AGC (fluxo relatorio/cientifico)
        "bgremoval_traces":     int(config.get("bgremoval_traces", 30)),
        "tpow_power":           float(config.get("tpow_power", 0.5)),
        "agc_window":           int(config.get("agc_window", 150)),
        "agc_window_preview":   int(config.get("agc_window_preview", 80)),
        # Velocity e profundidade
        "velocity_mns":         velocity,
        "velocity_fonte":       "config",
        "depth_tecnica_m":      prof_max,
        # G3 — separacao fisica / visual
        "physical_depth_m":     prof_max,
        "display_depth_m":      float(config["display_depth_m"]) if config.get("display_depth_m") else None,
        "depth_display_mode":   "axis_limit_no_stretch",
        "visual_crop_occurred": (
            bool(config.get("display_depth_m") and float(config["display_depth_m"]) < prof_max)
        ),
        # Preview RADAN
        "depth_preview_m":                  depth_preview,
        "preview_depth_real_m":             prof_max,
        "preview_visual_depth_configurado": depth_preview != 5.0,
        "preview_velocity_mns":             velocity,

        # -- Dimensoes do levantamento ------------------------------------
        "n_tracos":           int(dzt_data.n_traces),
        "dist_total_m":       float(dzt_data.dist_total_m),
        "profundidade_max_m": prof_max,

        # -- SNR em tres estagios -----------------------------------------
        "snr_raw_db":    float(snr_raw_db),
        "snr_raw_ratio": float(snr_raw_ratio),
        "snr_stages_db": {k: float(v) for k, v in (snr_stages_db or {}).items()},

        # -- Flags de imagens geradas -------------------------------------
        "imagem_bruta_ok":            _path_ok(image_paths, "bruta"),
        "imagem_cientifica_ok":       _path_ok(image_paths, "cientifica"),
        "imagem_relatorio_ok":        _path_ok(image_paths, "relatorio"),
        "imagem_preview_radan_5m_ok": _path_ok(image_paths, "preview_radan_5m"),
        "imagem_anotada_ok":          imagem_anotada_ok,

        # -- Paths completos dos outputs -----------------------------------
        "outputs": {
            "images": _paths_to_str(image_paths),
            "arrays": _paths_to_str(array_paths),
        },

        # -- Preflight: metadados do DZT e recomendacoes (Fase 8.13) ------
        # Campos resumidos no nivel raiz para acesso rapido pela UI
        "antenna_freq_mhz_detected":           (preflight_metadata or {}).get("antenna_freq_mhz_detected", 0),
        "velocity_header_mns":                 (preflight_metadata or {}).get("velocity_header_mns", None),
        "epsr_header":                         (preflight_metadata or {}).get("epsr_header", None),
        "frequency_mismatch":                  (preflight_recommendation or {}).get("frequency_mismatch", False),
        "recommended_preset_family":           (preflight_recommendation or {}).get("recommended_preset_family", None),
        "recommended_velocity_mns":            (preflight_recommendation or {}).get("recommended_velocity_mns", None),
        "recommended_visual_profile":          (preflight_recommendation or {}).get("recommended_visual_profile", None),
        "preflight_header_confidence":         (preflight_metadata or {}).get("header_confidence", None),
        "preflight_warnings":                  (preflight_recommendation or {}).get("warnings", []),
        # Bloco completo para auditoria
        "preflight": {
            "dzt_metadata":   preflight_metadata or {},
            "recommendation": preflight_recommendation or {},
        },
    }


# ---------------------------------------------------------------------------
# Persistencia JSON atomica
# ---------------------------------------------------------------------------

def save_metrics_atomic(metrics: dict, path: str | Path) -> Path:
    """
    Persiste o dict de metricas em JSON via escrita atomica.

    Formato: UTF-8, indent=2, sem escape de caracteres ASCII-safe.
    Converte automaticamente Path e numpy scalars via _to_serializable.

    Estrategia: grava em arquivo temporario no mesmo diretorio e substitui
    via os.replace() (atomico em POSIX; best-effort no Windows).

    :param metrics: Dict retornado por build_pipeline_metrics()
    :param path:    Caminho de saida (.json); diretorio pai criado automaticamente
    :returns:       Path do arquivo salvo
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    json_bytes = json.dumps(
        metrics,
        ensure_ascii=False,
        indent=2,
        default=_to_serializable,
    ).encode("utf-8")

    fd, tmp_path = tempfile.mkstemp(dir=out_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(json_bytes)
        os.replace(tmp_path, out_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return out_path


def load_metrics(path: str | Path) -> dict:
    """
    Le e retorna o dict de metricas de um arquivo JSON.

    :param path: Caminho do arquivo .json
    :returns:    Dict com os campos do pipeline_metrics.json
    :raises FileNotFoundError: Se o arquivo nao existir
    :raises json.JSONDecodeError: Se o conteudo nao for JSON valido
    """
    return json.loads(Path(path).read_text(encoding="utf-8"))
