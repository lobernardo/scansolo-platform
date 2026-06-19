"""
Filtros de sinal para o ScanSOLO GPR Engine — funções puras.

Todas as funções:
  - Recebem np.ndarray 2-D (n_samples × n_traces), dtype qualquer
  - Retornam np.ndarray float32
  - Nunca modificam o array de entrada (sempre copiam antes de processar)
  - Preservam o shape exatamente

readgssi.filtering NÃO é importado aqui. Todos os algoritmos usam
scipy.signal e scipy.ndimage diretamente por três razões:
  1. readgssi.filtering.triangular usa numtaps=25 fixo — insuficiente para
     a resolução em baixas frequências (pipeline_v1 usa adaptativo ≥101)
  2. readgssi.filtering.dewow é marcado experimental e não tem parâmetro window
  3. readgssi.filtering.bgr usa scipy.ndimage.filters (removido em scipy 1.15)

A nota de scipy compatibilidade está em requirements.txt.
"""
from __future__ import annotations

import numpy as np
from scipy import signal as sp_signal
from scipy.ndimage import uniform_filter1d


# ── dewow ─────────────────────────────────────────────────────────────────────

def dewow(arr: np.ndarray, window: int = 5) -> np.ndarray:
    """
    Remove o artefato de "wow" subtraindo uma média móvel por traço.

    Equivalente a GPRPy.dewow(window). Opera coluna a coluna (por traço)
    ao longo do eixo de tempo (axis=0).

    No GPR, "wow" é a variação lenta de baseline em cada traço individual
    causada por acoplamento de antena, trilho DC de instrumento e saturação.

    :param arr:    Array 2-D (n_samples × n_traces)
    :param window: Número de amostras da média móvel (preset padrão: 5)
    :returns:      float32, mesmo shape
    """
    if window <= 0:
        return arr.astype(np.float32).copy()
    w = max(3, int(window))
    f = arr.astype(np.float64)
    running_mean = uniform_filter1d(f, size=w, axis=0, mode="nearest")
    return (f - running_mean).astype(np.float32)


# ── bandpass ──────────────────────────────────────────────────────────────────

def bandpass_butterworth(
    arr: np.ndarray,
    samp_freq_hz: float,
    low_mhz: float,
    high_mhz: float,
    order: int = 5,
) -> np.ndarray:
    """
    Bandpass Butterworth SOS aplicado por traço (coluna), zero-fase.

    Equivalente a pipeline_v1.aplicar_bandpass(..., tipo="butterworth").
    Usa scipy.signal.sosfiltfilt (zero-fase, sem deslocamento de fase).

    :param arr:          Array 2-D (n_samples × n_traces)
    :param samp_freq_hz: Frequência de amostragem (Hz), de DZTData.samp_freq_hz
    :param low_mhz:      Frequência de corte inferior (MHz)
    :param high_mhz:     Frequência de corte superior (MHz)
    :param order:        Ordem do filtro Butterworth (padrão: 5)
    :returns:            float32, mesmo shape
    """
    nyq_hz = samp_freq_hz / 2.0
    low_hz = low_mhz * 1e6
    high_hz = high_mhz * 1e6
    low_n = float(np.clip(low_hz / nyq_hz, 1e-6, 0.9999))
    high_n = float(np.clip(high_hz / nyq_hz, 1e-6, 0.9999))
    if low_n >= high_n:
        raise ValueError(
            f"bandpass_butterworth: low_n ({low_n:.4f}) >= high_n ({high_n:.4f}). "
            f"Verifique low_mhz={low_mhz}, high_mhz={high_mhz}, "
            f"samp_freq_hz={samp_freq_hz:.3e}"
        )
    sos = sp_signal.butter(order, [low_n, high_n], btype="band", output="sos")
    out = np.empty_like(arr, dtype=np.float32)
    for col in range(arr.shape[1]):
        filtered = sp_signal.sosfiltfilt(sos, arr[:, col].astype(np.float64))
        out[:, col] = filtered.astype(np.float32)
    return out


def bandpass_triangular(
    arr: np.ndarray,
    samp_freq_hz: float,
    low_mhz: float,
    high_mhz: float,
) -> np.ndarray:
    """
    Bandpass FIR triangular por traço, zero-fase, com numtaps adaptativo.

    Equivalente a pipeline_v1.aplicar_bandpass(..., tipo="triangular").
    Usa scipy.signal.firwin2 com resposta triangular fl→fc→fh.
    Menos ringing que Butterworth para reflexões largas/múltiplas
    (vazios, galerias, concreto armado).

    numtaps = max(101, ceil(fs / fl) * 3) | 1   (sempre ímpar, ≥ 101)

    :param arr:          Array 2-D (n_samples × n_traces)
    :param samp_freq_hz: Frequência de amostragem (Hz)
    :param low_mhz:      Frequência de corte inferior (MHz)
    :param high_mhz:     Frequência de corte superior (MHz)
    :returns:            float32, mesmo shape
    """
    nyq_hz = samp_freq_hz / 2.0
    fl = low_mhz * 1e6
    fh = high_mhz * 1e6
    fc = (fl + fh) / 2.0
    # numtaps adaptativo: garante resolução em baixas frequências
    numtaps_ideal = max(101, int(np.ceil(samp_freq_hz / fl) * 3)) | 1
    # filtfilt requer n_samples > 3 * numtaps (padlen = 3 * numtaps).
    # Cap: numtaps < n_samples / 3  →  max_taps = (n_samples // 3) - 1, par → -1
    n_samples = arr.shape[0]
    max_taps = max(11, (n_samples // 3) - 1)
    if max_taps % 2 == 0:
        max_taps -= 1  # garante ímpar
    numtaps = min(numtaps_ideal, max_taps)
    freqs = [0.0, fl, fc, fh, nyq_hz]
    gains = [0.0, 0.0, 1.0, 0.0, 0.0]
    b = sp_signal.firwin2(numtaps, freqs, gains, fs=samp_freq_hz)
    out = np.empty_like(arr, dtype=np.float32)
    for col in range(arr.shape[1]):
        filtered = sp_signal.filtfilt(b, [1.0], arr[:, col].astype(np.float64))
        out[:, col] = filtered.astype(np.float32)
    return out


def bandpass(
    arr: np.ndarray,
    samp_freq_hz: float,
    low_mhz: float,
    high_mhz: float,
    order: int = 5,
    tipo: str = "butterworth",
) -> np.ndarray:
    """
    Dispatcher de bandpass — seleciona butterworth ou triangular.

    Interface unificada que corresponde ao parâmetro bandpass_tipo do preset.

    :param tipo: "butterworth" (padrão) ou "triangular"
    """
    if tipo == "triangular":
        return bandpass_triangular(arr, samp_freq_hz, low_mhz, high_mhz)
    return bandpass_butterworth(arr, samp_freq_hz, low_mhz, high_mhz, order)


# ── bgremoval ─────────────────────────────────────────────────────────────────

def bgremoval(arr: np.ndarray, window: int = 0) -> np.ndarray:
    """
    Background removal horizontal — subtrai a média ao longo dos traços.

    Equivalente a GPRPy.remMeanTrace(window). Remove reflexões horizontais
    (onda direta, reverberações, ruído de cabo) subtraindo a média
    por janela ao longo do eixo horizontal (axis=1).

    window=0 ou window >= n_traces: BGR global (subtrai média de cada linha).
    window > 1: BGR janelado (running mean com `window` traços).

    Corresponde a readgssi.filtering.bgr() sem a dependência de
    scipy.ndimage.filters (usa scipy.ndimage.uniform_filter1d diretamente).

    :param arr:    Array 2-D (n_samples × n_traces)
    :param window: Número de traços na janela (preset padrão: 30; 0 = global)
    :returns:      float32, mesmo shape
    """
    f = arr.astype(np.float64)
    n_traces = f.shape[1]
    if window <= 1 or window >= n_traces:
        # BGR global: subtrai média de cada linha entre todos os traços
        return (f - f.mean(axis=1, keepdims=True)).astype(np.float32)
    # BGR janelado: running mean horizontal
    win = int(window)
    if win % 2 == 0:
        win += 1  # garante janela ímpar para centramento simétrico
    running = uniform_filter1d(f, size=win, axis=1, mode="reflect")
    return (f - running).astype(np.float32)


# ── tpow ─────────────────────────────────────────────────────────────────────

def tpow(arr: np.ndarray, power: float = 0.5) -> np.ndarray:
    """
    Ganho de tempo — multiplica cada amostra por (t / t_max)^power.

    Equivalente a pipeline_v1._aplicar_tpow_manual() e GPRPy.tpowGain().
    Compensa o espalhamento geométrico e a atenuação com a profundidade.

    A rampa é normalizada: amostra 0 → ganho=0, amostra n-1 → ganho=1.
    Modos SNR do pipeline: minimo→power=0.3, padrao→0.5, agressivo→0.75.

    :param arr:   Array 2-D (n_samples × n_traces)
    :param power: Expoente da rampa (preset padrão: 0.5)
    :returns:     float32, mesmo shape
    """
    if power <= 0:
        return arr.astype(np.float32).copy()
    n = arr.shape[0]
    if n <= 1:
        return arr.astype(np.float32).copy()
    gains = (np.arange(n, dtype=np.float64) / max(n - 1, 1)) ** float(power)
    return (arr.astype(np.float64) * gains[:, np.newaxis]).astype(np.float32)


# ── agc ──────────────────────────────────────────────────────────────────────

def agc(arr: np.ndarray, window: int = 150) -> np.ndarray:
    """
    AGC — normalização de amplitude por RMS janelado, por traço.

    Equivalente a GPRPy.agcGain(window). Para cada posição de amostra,
    divide pelo RMS local calculado sobre uma janela ao longo do eixo de
    tempo. Produz amplitude visualmente uniforme em toda a profundidade.

    O denominador tem piso de 1e-10 para evitar divisão por zero em
    regiões sem sinal.

    :param arr:    Array 2-D (n_samples × n_traces)
    :param window: Tamanho da janela RMS em amostras (preset padrão: 150)
    :returns:      float32, mesmo shape
    """
    win = max(3, int(window))
    f = arr.astype(np.float64)
    rms = np.sqrt(uniform_filter1d(f ** 2, size=win, axis=0, mode="reflect") + 1e-10)
    return (f / rms).astype(np.float32)
