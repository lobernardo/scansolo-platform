"""
Modulo SNR para o ScanSOLO GPR Engine -- funcoes puras.

Calcula SNR por Hilbert per-trace, detecta modo de processamento
(minimo/padrao/agressivo), localiza e aplica correcao de time-zero,
e computa a profundidade minima adaptativa do detector.

Todas as funcoes:
  - Recebem np.ndarray e retornam tipos simples ou np.ndarray float32
  - Nunca modificam o array de entrada in-place
  - Nao importam GPRPy nem dependem de pipeline_v1.py

Logica identica ao SNR gate de pipeline_v1.py (v2.0.0):
  - Janela sinal:  amostras 10%-75%
  - Janela ruido:  amostras 95%-100% (ruido termico genuino)
  - Hilbert per-trace: pico de envelope / desvio do ruido
  - Mediana sobre todos os tracos (robusta a outliers)
"""
from __future__ import annotations

import numpy as np
from scipy.signal import hilbert


# ---------------------------------------------------------------------------
# Limiares SNR por tipo de solo: (limiar_minimo, limiar_padrao)
# Valores sao S/sigma ratio (nao dB), calibrados por Hilbert per-trace.
# Referencia: PATIO_001=9.25, _002=5.44, _003=6.45, _004=4.56 -- modo PADRAO
# ---------------------------------------------------------------------------
SNR_LIMIARES: dict[str, tuple[float, float]] = {
    "standard":  (30.0, 4.0),
    "arenoso":   (30.0, 4.0),
    "argiloso":  (20.0, 3.5),
    "umido":     (15.0, 3.0),
    "pedregoso": (35.0, 6.0),
}

# Profundidade base usada no calculo adaptativo (modo padrao/agressivo)
_DEPTH_MIN_BASE = 0.30


# ---------------------------------------------------------------------------
# SNR
# ---------------------------------------------------------------------------

def calcular_snr_ratio(arr: np.ndarray) -> float:
    """
    SNR ratio via envelope analitico de Hilbert, mediana por traco.

    Formula: ratio = max|H[sinal]| / std[ruido]
      - Sinal:  amostras 10%-75% de cada traco
      - Ruido:  amostras 95%-100% de cada traco
      - Resultado: mediana dos ratios por traco (robusto a outliers)

    :param arr: Array 2-D (n_samples x n_traces), qualquer dtype
    :returns:   float -- ratio mediano (sempre > 0)
    """
    n_samples = arr.shape[0]
    s0 = max(1, int(0.10 * n_samples))
    s1 = int(0.75 * n_samples)
    r0 = int(0.95 * n_samples)

    ratios: list[float] = []
    for col in range(arr.shape[1]):
        trace = arr[:, col].astype(np.float64)
        envelope = np.abs(hilbert(trace[s0:s1]))
        pico = float(np.max(envelope))
        ruido = float(np.std(trace[r0:])) + 1e-10
        ratios.append(pico / ruido)

    return float(np.median(ratios))


def calcular_snr_imagem_db(arr: np.ndarray) -> float:
    """
    SNR em dB = 20 * log10(calcular_snr_ratio(arr)).

    :param arr: Array 2-D (n_samples x n_traces)
    :returns:   SNR em dB, arredondado a 1 casa decimal
    """
    ratio = calcular_snr_ratio(arr)
    if ratio <= 0:
        return 0.0
    return round(20.0 * float(np.log10(ratio)), 1)


# ---------------------------------------------------------------------------
# Modo de processamento
# ---------------------------------------------------------------------------

def detectar_modo_processamento(snr_raw_db: float, tipo_solo: str = "standard") -> str:
    """
    Determina o modo de processamento com base no SNR do dado bruto.

    Converte snr_raw_db para ratio (10^(db/20)) e compara com
    SNR_LIMIARES[tipo_solo]:

      ratio >= limiar_minimo  -> "minimo"    (SNR alto, onda direta forte)
      ratio >= limiar_padrao  -> "padrao"    (comportamento normal)
      ratio <  limiar_padrao  -> "agressivo" (sinal fraco / ruidoso)

    :param snr_raw_db: SNR do dado bruto em dB (de calcular_snr_imagem_db)
    :param tipo_solo:  Tipo de solo (standard, arenoso, argiloso, umido, pedregoso)
    :returns:          "minimo" | "padrao" | "agressivo"
    """
    ratio = 10.0 ** (snr_raw_db / 20.0)
    thr_min, thr_pad = SNR_LIMIARES.get(tipo_solo, SNR_LIMIARES["standard"])
    if ratio >= thr_min:
        return "minimo"
    if ratio >= thr_pad:
        return "padrao"
    return "agressivo"


# ---------------------------------------------------------------------------
# Time-zero
# ---------------------------------------------------------------------------

def detectar_time_zero(arr: np.ndarray) -> int:
    """
    Detecta a amostra de time-zero pelo pico do envelope de Hilbert
    na media de todos os tracos.

    Busca apenas nas primeiras 25% das amostras -- o pulso direto
    antena-solo aparece no inicio da janela de tempo.

    Retorna 0 quando o pico esta em 0 ou 1 (dado ja pode estar corrigido).

    :param arr: Array 2-D (n_samples x n_traces)
    :returns:   Indice inteiro da amostra de time-zero (>= 0)
    """
    trace_media = np.mean(arr.astype(np.float64), axis=1)
    envelope = np.abs(hilbert(trace_media))
    search_end = max(2, int(0.25 * len(trace_media)))
    tz = int(np.argmax(envelope[:search_end]))
    if tz <= 1:
        return 0
    return tz


def aplicar_time_zero(arr: np.ndarray, timezero_sample: int) -> np.ndarray:
    """
    Remove as amostras antes do pulso direto (time-zero).

    Retorna sempre um novo array float32 -- nunca modifica o input.
    Quando timezero_sample <= 1, retorna copia completa com shape original.

    :param arr:             Array 2-D (n_samples x n_traces)
    :param timezero_sample: Indice da amostra de time-zero (de detectar_time_zero)
    :returns:               float32, shape (n_samples - timezero_sample, n_traces)
                            ou (n_samples, n_traces) quando timezero_sample <= 1
    """
    if timezero_sample <= 1:
        return arr.astype(np.float32).copy()
    return arr[timezero_sample:, :].astype(np.float32).copy()


# ---------------------------------------------------------------------------
# Profundidade minima adaptativa
# ---------------------------------------------------------------------------

def calcular_depth_min_adaptativo(
    snr_raw_db: float,
    tipo_solo: str = "standard",
    valor_explicito: float | None = None,
) -> float:
    """
    Calcula det_depth_min_m adaptativo com base no modo SNR.

    Se valor_explicito nao for None, retorna esse valor diretamente
    (override explicito sempre prevalece -- sem logica adaptativa).

    Caso contrario, determina o modo e aplica:
      minimo    -> 0.50 m  (onda direta forte; margem maior por seguranca)
      padrao    -> 0.30 m  (comportamento padrao do preset)
      agressivo -> max(0.20, 0.30 x 0.67)  (aceitar candidatos rasos)

    :param snr_raw_db:      SNR bruto em dB (de calcular_snr_imagem_db)
    :param tipo_solo:       Tipo de solo
    :param valor_explicito: Quando fornecido, prevalece sobre calculo adaptativo
    :returns:               det_depth_min_m em metros
    """
    if valor_explicito is not None:
        return float(valor_explicito)
    modo = detectar_modo_processamento(snr_raw_db, tipo_solo)
    if modo == "minimo":
        return 0.50
    if modo == "agressivo":
        return max(0.20, _DEPTH_MIN_BASE * 0.67)
    return _DEPTH_MIN_BASE
