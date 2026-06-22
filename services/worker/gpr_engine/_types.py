"""
Tipos de dados do ScanSOLO GPR Engine.

Apenas DZTData está definido na Fase 1. Fases futuras adicionarão
FlowArrays, ProcessResult e outros contratos.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class DZTData:
    """
    Dado bruto e metadados extraídos de um arquivo .DZT.
    Nenhum filtro de sinal foi aplicado sobre arr_raw.

    Produzido por DZTReader.read() e consumido pelos estágios do pipeline.
    """

    # ── Array bruto ──────────────────────────────────────────────────────────
    arr_raw: np.ndarray
    """shape (n_samples, n_traces), dtype float32.
    Saída direta do readgssi.dzt.readdzt(), sem nenhum filtro aplicado.
    Sempre np.ndarray — nunca np.matrix."""

    # ── Dimensões ────────────────────────────────────────────────────────────
    n_samples: int
    """número de amostras por traço (eixo vertical / profundidade)"""

    n_traces: int
    """número de traços (eixo horizontal / distância)"""

    # ── Eixo de tempo ────────────────────────────────────────────────────────
    twtt_max_ns: float
    """tempo de viagem duplo máximo (ns) — range temporal do DZT"""

    dt_ns: float
    """intervalo temporal entre amostras (ns/amostra)"""

    samp_freq_hz: float
    """frequência de amostragem (Hz), usada pelos filtros de bandpass"""

    # ── Eixo de espaço ───────────────────────────────────────────────────────
    dist_total_m: float
    """distância horizontal total da linha de levantamento (m)"""

    dist_per_trace_m: float
    """distância horizontal por traço (m/traço)"""

    modo_coleta: str
    """"distancia" se coletado por odômetro/encoder; "tempo" se por clock"""

    # ── Antena / física ──────────────────────────────────────────────────────
    antfreq_mhz: int
    """frequência central da antena (MHz), do header ou lookup readgssi.constants.ANT"""

    rhf_epsr: float
    """constante dielétrica relativa do header DZT (εr)"""

    wave_speed_mns: float
    """velocidade da onda EM no meio (m/ns). Para εr=9: ≈ 0.0999 m/ns.
    Derivado de header['cr'] (readgssi calcula via Mu_0, Eps_0, epsr)."""

    # ── Escalares do header ──────────────────────────────────────────────────
    rhf_spm: float
    """scans por metro do header DZT (0 se não configurado — coleta por tempo)"""

    rhf_sps: float
    """scans por segundo do header DZT"""

    rhf_range_ns: float
    """range temporal do header DZT (ns)"""

    # ── Time-zero ────────────────────────────────────────────────────────────
    timezero_sample: int
    """índice de amostra da onda direta, conforme header DZT.
    O módulo snr.py pode calcular um valor refinado a partir dos dados."""

    # ── Identidade do arquivo ────────────────────────────────────────────────
    dzt_filename: str
    """nome do arquivo fonte (ex: 'PATIO___001.DZT')"""

    dzt_sha256: str
    """digest SHA-256 dos bytes brutos do DZT para rastreabilidade de integridade"""

    # ── Arquivos auxiliares ──────────────────────────────────────────────────
    has_dzg: bool
    """True se um arquivo .DZG co-localizado foi encontrado e lido com sucesso"""

    has_dzx: bool
    """True se um arquivo .DZX co-localizado foi encontrado"""

    dzx_marks: list
    """lista de números de traço (int) dos user marks do DZX.
    Lista vazia se has_dzx for False ou se não houver marks."""

    dzx_data: dict = field(default_factory=dict, repr=False)
    """dict completo retornado por parse_dzx.py — inclui coordenadas GPS,
    dzx_survey_length_m, operador, data, etc. Vazio se DZX indisponível."""

    # ── Header bruto ─────────────────────────────────────────────────────────
    header_raw: dict = field(default_factory=dict, repr=False)
    """header completo de readgssi.dzt.readdzt() — armazenado para rastreabilidade"""
