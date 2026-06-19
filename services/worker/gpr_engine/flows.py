"""
Modulo flows para o ScanSOLO GPR Engine -- tres fluxos independentes.

Implementa os tres fluxos do processamento GPR v2.0.0:

  raw -> dewow -> [bandpass] -> arr_dewow_bp -> [bifurcacao]
                                     |
              [tpow]      [bgremoval -> tpow -> AGC]    [AGC(preview)]
                 |                   |                        |
        arr_cientifico        arr_sem_agc           arr_preview_radan
        (Amilson/detector)    arr_relatorio          (comparacao RADAN)

Todas as funcoes:
  - Recebem np.ndarray e retornam np.ndarray float32 ou FlowArrays
  - Nunca modificam o array de entrada in-place
  - Preservam shape (n_samples x n_traces) em todos os outputs
  - Nao importam GPRPy nem dependem de pipeline_v1.py

Bandpass OFF: bandpass_low_mhz=0 (convencao pipeline) ou bandpass_enabled=False.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from gpr_engine.filters import agc, bandpass, bgremoval, dewow, tpow


# ---------------------------------------------------------------------------
# FlowArrays -- container dos resultados dos tres fluxos
# ---------------------------------------------------------------------------

@dataclass
class FlowArrays:
    """Todos os arrays de saida dos tres fluxos de processamento GPR."""

    arr_dewow_bp: np.ndarray
    """Base: dewow + bandpass (ou so dewow se bandpass OFF).
    Ponto de bifurcacao: alimenta os tres fluxos seguintes."""

    arr_cientifico: np.ndarray
    """Fluxo cientifico: arr_dewow_bp -> tpow.
    Sem AGC -- preserva decaimento fisico. Usado por Amilson e detector."""

    arr_sem_agc: np.ndarray
    """Fluxo relatorio pre-AGC: arr_dewow_bp -> bgremoval -> tpow.
    Sem distorcao de AGC -- adequado para analise de amplitude/fase."""

    arr_relatorio: np.ndarray
    """Fluxo relatorio completo: arr_sem_agc -> AGC.
    Visual para cliente e PDF."""

    arr_preview_radan: np.ndarray
    """Fluxo preview: arr_dewow_bp -> AGC(agc_window_preview).
    Imita output visual do RADAN com janela AGC menor."""


# ---------------------------------------------------------------------------
# Defaults de configuracao e helpers
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "dewow_window":       5,
    "bandpass_low_mhz":   80.0,
    "bandpass_high_mhz":  500.0,
    "bandpass_order":     5,
    "bandpass_tipo":      "butterworth",
    "bandpass_enabled":   True,
    "bgremoval_traces":   30,
    "tpow_power":         0.5,
    "agc_window":         150,
    "agc_window_preview": 80,
}


def _cfg(config: dict, key: str):
    """Retorna config[key] ou default seguro de _DEFAULTS."""
    return config.get(key, _DEFAULTS[key])


def _is_bandpass_enabled(config: dict) -> bool:
    """
    Bandpass esta ativo quando:
      - bandpass_enabled nao e False (ou ausente), E
      - bandpass_low_mhz != 0 (convencao pipeline: 0 significa OFF)
    """
    if not config.get("bandpass_enabled", True):
        return False
    if float(config.get("bandpass_low_mhz", _DEFAULTS["bandpass_low_mhz"])) == 0:
        return False
    return True


# ---------------------------------------------------------------------------
# Fluxo base: raw -> dewow -> [bandpass]
# ---------------------------------------------------------------------------

def build_base_filtered_flow(arr_raw: np.ndarray, config: dict) -> np.ndarray:
    """
    Fluxo base: raw -> dewow -> [bandpass opcional].

    Ponto de bifurcacao que alimenta os tres fluxos seguintes.
    Bandpass ativo quando bandpass_low_mhz != 0 e bandpass_enabled != False.

    :param arr_raw: Array 2-D bruto (n_samples x n_traces)
    :param config:  Dict de parametros. Campos relevantes:
                    dewow_window, bandpass_*, samp_freq_hz (obrigatorio se bandpass ON)
    :returns:       arr_dewow_bp float32, mesmo shape que arr_raw
    :raises ValueError: Se bandpass ativo e 'samp_freq_hz' ausente na config
    """
    arr = dewow(arr_raw, window=int(_cfg(config, "dewow_window")))

    if _is_bandpass_enabled(config):
        samp_freq_hz = config.get("samp_freq_hz")
        if samp_freq_hz is None:
            raise ValueError(
                "build_base_filtered_flow: 'samp_freq_hz' ausente na config. "
                "Bandpass requer frequencia de amostragem (DZTData.samp_freq_hz)."
            )
        arr = bandpass(
            arr,
            samp_freq_hz=float(samp_freq_hz),
            low_mhz=float(_cfg(config, "bandpass_low_mhz")),
            high_mhz=float(_cfg(config, "bandpass_high_mhz")),
            order=int(_cfg(config, "bandpass_order")),
            tipo=str(_cfg(config, "bandpass_tipo")),
        )

    return arr


# ---------------------------------------------------------------------------
# Fluxo cientifico: arr_dewow_bp -> tpow
# ---------------------------------------------------------------------------

def build_scientific_flow(arr_dewow_bp: np.ndarray, config: dict) -> np.ndarray:
    """
    Fluxo cientifico: arr_dewow_bp -> tpow.

    Sem AGC nem bgremoval: preserva o decaimento fisico de amplitude.
    Usado por Amilson para revisao tecnica e pelo detector de hiperboles.

    :param arr_dewow_bp: Saida de build_base_filtered_flow
    :param config:       Dict com tpow_power (default 0.5)
    :returns:            arr_cientifico float32, mesmo shape
    """
    return tpow(arr_dewow_bp, power=float(_cfg(config, "tpow_power")))


# ---------------------------------------------------------------------------
# Fluxo relatorio: arr_dewow_bp -> bgremoval -> tpow -> AGC
# ---------------------------------------------------------------------------

def build_report_flow(
    arr_dewow_bp: np.ndarray,
    config: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Fluxo relatorio: arr_dewow_bp -> bgremoval -> tpow -> AGC.

    Retorna dois arrays com o mesmo shape:
      arr_sem_agc   -- apos bgremoval+tpow, antes do AGC (analise de amplitude)
      arr_relatorio -- com AGC completo (visual cliente / PDF)

    :param arr_dewow_bp: Saida de build_base_filtered_flow
    :param config:       Dict com bgremoval_traces, tpow_power, agc_window
    :returns:            (arr_sem_agc, arr_relatorio), ambos float32
    """
    arr_bg = bgremoval(arr_dewow_bp, window=int(_cfg(config, "bgremoval_traces")))
    arr_sem_agc = tpow(arr_bg, power=float(_cfg(config, "tpow_power")))
    arr_relatorio = agc(arr_sem_agc, window=int(_cfg(config, "agc_window")))
    return arr_sem_agc, arr_relatorio


# ---------------------------------------------------------------------------
# Fluxo preview RADAN-like: arr_dewow_bp -> AGC(preview_window)
# ---------------------------------------------------------------------------

def build_radan_like_flow(arr_dewow_bp: np.ndarray, config: dict) -> np.ndarray:
    """
    Fluxo preview RADAN: arr_dewow_bp -> AGC(agc_window_preview).

    Usa janela AGC menor que o relatorio e sem bgremoval/tpow, para imitar
    o output visual do RADAN com escala fixa de 5 m.

    :param arr_dewow_bp: Saida de build_base_filtered_flow
    :param config:       Dict com agc_window_preview (default 80)
    :returns:            arr_preview_radan float32, mesmo shape
    """
    return agc(arr_dewow_bp, window=int(_cfg(config, "agc_window_preview")))


# ---------------------------------------------------------------------------
# Funcao principal: process_flows
# ---------------------------------------------------------------------------

def process_flows(arr_raw: np.ndarray, config: dict) -> FlowArrays:
    """
    Executa os tres fluxos completos a partir do arr_raw.

    Sequencia:
      1. Base:      arr_raw -> dewow -> [bandpass] -> arr_dewow_bp
      2. Cientifico: arr_dewow_bp -> tpow -> arr_cientifico
      3. Relatorio:  arr_dewow_bp -> bgremoval -> tpow -> arr_sem_agc -> AGC -> arr_relatorio
      4. Preview:    arr_dewow_bp -> AGC(agc_window_preview) -> arr_preview_radan

    :param arr_raw: Array 2-D bruto do DZT (n_samples x n_traces)
    :param config:  Dict de parametros de processamento
    :returns:       FlowArrays com todos os cinco arrays de saida
    :raises ValueError: Se bandpass ativo e samp_freq_hz ausente da config
    """
    arr_dewow_bp = build_base_filtered_flow(arr_raw, config)
    arr_cientifico = build_scientific_flow(arr_dewow_bp, config)
    arr_sem_agc, arr_relatorio = build_report_flow(arr_dewow_bp, config)
    arr_preview_radan = build_radan_like_flow(arr_dewow_bp, config)

    return FlowArrays(
        arr_dewow_bp=arr_dewow_bp,
        arr_cientifico=arr_cientifico,
        arr_sem_agc=arr_sem_agc,
        arr_relatorio=arr_relatorio,
        arr_preview_radan=arr_preview_radan,
    )
