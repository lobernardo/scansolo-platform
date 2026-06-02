"""
detector_hiperboles.py - V1.1 - ScanSOLO Pipeline GPR
Modulo de deteccao de hiperboles em radargramas GPR.

V1.1 — Correcao critica: classificacao fisica nao usa mais AGC.
  arr_detector (com AGC): Hough, CurveFit, DeltaT, visualizacao
  arr_sem_agc  (sem AGC): amplitude, fase, Hilbert, classificacao de material
  arr_raw      (bruta)  : evidencia independente — confirmacao no dado original

Metodos:
  Deteccao:   Transformada de Hough adaptada para hiperboles de GPR
  Depth:      Curve fitting por minimos quadrados (scipy.optimize.curve_fit)
  Diametro:   Separacao top-bottom (delta_t) - reflexao topo + fundo da tubulacao
  Material:   Classificacao fisica: amplitude relativa + inversao de fase (sem AGC)
  Solo:       Analise espectral por faixa de profundidade (FFT)
  Score:      Score composto 0-100 combinando evidencias geometricas e fisicas

Fisica:
  Hiperbole:  t(x) = (2/v) * sqrt(h^2 + (x - x0)^2)
  Depth:      h = v * t_apex / 2
  Diametro:   d = v * delta_t / 2
  Metal:      amplitude alta (sem AGC) + inversao de fase -> impedancia >> solo

AVISO: fis_amp_metal_thr e fis_amp_nao_metal_thr precisam ser calibrados com Amilson
       usando ~10 alvos de tipo conhecido antes de usar em producao.
"""

import numpy as np
from scipy.signal import hilbert
from scipy.optimize import curve_fit
from scipy.fft import rfft, rfftfreq
import matplotlib.pyplot as plt
import pandas as pd


# ---------------------------------------------------------------------------
# PARAMETROS PADRAO (calibrados para PATIO 270 MHz)
# ---------------------------------------------------------------------------
DEFAULT_PARAMS = {
    "v_m_per_s":             1.0e8,
    "dt_s":                  6.548e-11,
    "dx_m":                  1 / 33.26,
    "amp_threshold":         0.45,
    "h_min_m":               0.10,
    "h_max_m":               2.80,
    "h_step_m":              0.04,
    "col_search_half":       80,
    "nms_radius_m":          0.50,
    "top_n":                 30,
    "cf_wing_half_m":        2.0,
    "cf_amp_frac":           0.30,
    "dt_min_diam_m":         0.05,
    "dt_max_diam_m":         1.50,
    "dt_conf_frac":          0.20,
    # Analises fisicas
    "fis_ativo":             True,
    "fis_amp_metal_thr":     0.75,   # [CALIBRAR] com Amilson
    "fis_amp_nao_metal_thr": 0.40,   # [CALIBRAR] com Amilson
}


# ---------------------------------------------------------------------------
# HOUGH TRANSFORM — sem alteracoes
# ---------------------------------------------------------------------------
def hough_hiperbola(arr, params):
    v        = params["v_m_per_s"]
    dt       = params["dt_s"]
    dx       = params["dx_m"]
    h_min    = params["h_min_m"]
    h_max    = params["h_max_m"]
    h_step   = params["h_step_m"]
    col_half = params["col_search_half"]
    amp_thr  = params["amp_threshold"]

    n_samples, n_traces = arr.shape
    depths = np.arange(h_min, h_max, h_step)
    accum  = np.zeros((n_traces, len(depths)), dtype=float)

    env      = np.abs(hilbert(arr, axis=0))
    env_norm = env / (env.max() + 1e-10)
    strong   = np.argwhere(env_norm > amp_thr)

    for (row, col) in strong:
        amp       = env_norm[row, col]
        twtt      = row * dt
        half_dist = twtt * v / 2.0
        for h_idx, h in enumerate(depths):
            disc = half_dist**2 - h**2
            if disc < 0:
                continue
            offset_traces = int(round(np.sqrt(disc) / dx))
            if offset_traces > col_half:
                continue
            for sign in (+1, -1):
                col0 = col + sign * offset_traces
                if 0 <= col0 < n_traces:
                    accum[col0, h_idx] += amp

    return accum, depths


# ---------------------------------------------------------------------------
# NON-MAXIMUM SUPPRESSION — sem alteracoes
# ---------------------------------------------------------------------------
def nms_hough(accum, depths, dx, nms_radius_m):
    flat  = accum.copy()
    peaks = []
    while True:
        idx         = np.argmax(flat)
        col0, d_idx = np.unravel_index(idx, flat.shape)
        score       = flat[col0, d_idx]
        if score <= 0:
            break
        peaks.append((col0, d_idx, score))
        radius = int(round(nms_radius_m / dx))
        r0 = max(0, col0 - radius)
        r1 = min(flat.shape[0], col0 + radius + 1)
        flat[r0:r1, :] = 0
    return peaks


# ---------------------------------------------------------------------------
# CURVE FITTING - REFINAMENTO DE PROFUNDIDADE — sem alteracoes
# ---------------------------------------------------------------------------
_v_global = 1.0e8

def _modelo_hiperbola(x, x0, h):
    return (2.0 / _v_global) * np.sqrt(np.maximum(h**2 + (x - x0)**2, 0))


def refinar_profundidade_curvefitting(arr, col0_hough, h_hough, params):
    global _v_global
    _v_global = params["v_m_per_s"]

    dx        = params["dx_m"]
    dt        = params["dt_s"]
    wing_half = params["cf_wing_half_m"]
    amp_frac  = params["cf_amp_frac"]
    n_samples, n_traces = arr.shape

    env    = np.abs(hilbert(arr, axis=0))
    c_half = int(round(wing_half / dx))
    c_min  = max(0, col0_hough - c_half)
    c_max  = min(n_traces - 1, col0_hough + c_half)
    cols   = np.arange(c_min, c_max + 1)
    rows   = np.array([np.argmax(env[:, c]) for c in cols])
    amps   = env[rows, cols]

    amp_threshold = np.max(amps) * amp_frac
    mask = amps > amp_threshold
    if mask.sum() < 6:
        return h_hough, col0_hough, False

    x_data = cols[mask] * dx
    t_data = rows[mask] * dt

    try:
        x0_init    = col0_hough * dx
        popt, pcov = curve_fit(
            _modelo_hiperbola, x_data, t_data,
            p0=[x0_init, h_hough],
            bounds=([0.0, params["h_min_m"]], [n_traces * dx, params["h_max_m"]]),
            maxfev=2000
        )
        x0_ref, h_ref = popt
        perr = np.sqrt(np.diag(pcov))
        if perr[1] > 0.5 * h_ref:
            return h_hough, col0_hough, False
        col0_ref = int(round(x0_ref / dx))
        col0_ref = max(0, min(n_traces - 1, col0_ref))
        return round(float(h_ref), 3), col0_ref, True
    except Exception:
        return h_hough, col0_hough, False


# ---------------------------------------------------------------------------
# DELTA-T - ESTIMATIVA DE DIAMETRO — sem alteracoes
# ---------------------------------------------------------------------------
def estimar_diametro_delta_t(arr, col0, row_apex, params):
    v  = params["v_m_per_s"]
    dt = params["dt_s"]
    n  = arr.shape[0]

    trace     = arr[:, col0].astype(float)
    env_trace = np.abs(hilbert(trace))

    win     = 15
    r_start = max(0, row_apex - win)
    r_end   = min(n - 1, row_apex + win)
    row_top = r_start + int(np.argmax(env_trace[r_start:r_end + 1]))
    amp_top = env_trace[row_top]

    if amp_top < 1e-10:
        return 0.0, "baixa"

    sep_min = max(1, int(round(2 * params["dt_min_diam_m"] / (v * dt))))
    sep_max = int(round(2 * params["dt_max_diam_m"] / (v * dt)))
    s_start = row_top + sep_min
    s_end   = min(n - 1, row_top + sep_max)

    if s_start > s_end:
        return 0.0, "baixa"

    env_window = env_trace[s_start:s_end + 1]
    idx_bottom = int(np.argmax(env_window))
    row_bottom = s_start + idx_bottom
    amp_bottom = env_window[idx_bottom]

    confianca = "alta" if amp_bottom >= params["dt_conf_frac"] * amp_top else "baixa"
    delta_t   = (row_bottom - row_top) * dt
    diametro  = delta_t * v / 2.0

    if diametro < params["dt_min_diam_m"] or diametro > params["dt_max_diam_m"]:
        return 0.0, "baixa"

    return round(float(diametro), 3), confianca


# ---------------------------------------------------------------------------
# ANALISES FISICAS V1.1 — MODULO SEPARAVEL
# ---------------------------------------------------------------------------

def _calcular_snr_local(arr, col0, row_apex, janela_sinal=5, janela_ruido=30):
    """
    SNR local: amplitude do envelope no apex vs. desvio padrao do ruido de fundo.
    Ruido estimado a partir da regiao acima do apex (pre-reflexao esperada).
    Retorna float (0 se nao calculavel).
    """
    n_samples, n_traces = arr.shape
    trace     = arr[:, col0].astype(float)
    env_trace = np.abs(hilbert(trace))

    r0 = max(0, row_apex - janela_sinal)
    r1 = min(n_samples - 1, row_apex + janela_sinal)
    amp_sinal = float(np.max(env_trace[r0:r1 + 1]))

    # Ruido: regiao acima do apex onde nao ha reflexao esperada
    r_noise_end = max(0, row_apex - janela_sinal - 5)
    if r_noise_end >= 10:
        noise_region = arr[:r_noise_end, :].astype(float)
        amp_ruido = float(np.std(noise_region)) + 1e-10
    else:
        amp_ruido = float(np.std(arr.astype(float))) + 1e-10

    return round(float(amp_sinal / amp_ruido), 2)


def classificar_material_por_fisica(arr_sem_agc, arr_raw, col0, row_apex, params):
    """
    V1.1 — Classificacao fisica correta usando matrizes sem AGC.

    arr_sem_agc : matriz filtrada ANTES do AGC — fonte principal para amplitude/fase.
                  AGC destroi relacoes de amplitude absolutas, portanto nao usar aqui.
    arr_raw     : matriz bruta (pre-qualquer-filtro) — evidencia independente.
    col0        : indice da coluna do apex detectado.
    row_apex    : indice da amostra do apex.

    Retorna dict com todos os campos de classificacao fisica.

    Nomenclatura V1.1:
      possivel_metalico        — alta amplitude (sem AGC) + inversao de fase
      possivel_galeria_ou_vazio — alta amplitude + sem inversao de fase
      possivel_nao_metalico    — baixa amplitude
      inconclusivo             — amplitude media sem evidencia clara
    """
    thr_metal     = params.get("fis_amp_metal_thr", 0.75)
    thr_nao_metal = params.get("fis_amp_nao_metal_thr", 0.40)
    n_samples     = arr_sem_agc.shape[0]

    # --- Amplitude relativa no dado sem AGC ---
    trace_sem = arr_sem_agc[:, col0].astype(float)
    env_sem   = np.abs(hilbert(trace_sem))
    amp_apex_sem      = env_sem[row_apex]
    amp_global_99_sem = np.percentile(np.abs(arr_sem_agc), 99)
    amp_relativa_sem  = float(amp_apex_sem / (amp_global_99_sem + 1e-10))

    # --- Amplitude relativa no dado bruto (evidencia independente) ---
    amp_relativa_raw = 0.0
    evidencia_raw    = False
    if arr_raw is not None and arr_raw.shape == arr_sem_agc.shape:
        trace_raw         = arr_raw[:, col0].astype(float)
        env_raw           = np.abs(hilbert(trace_raw))
        amp_apex_raw      = env_raw[row_apex]
        amp_global_99_raw = np.percentile(np.abs(arr_raw), 99)
        amp_relativa_raw  = float(amp_apex_raw / (amp_global_99_raw + 1e-10))
        # Evidencia no raw: amplitude acima de metade do limiar nao-metal
        evidencia_raw     = amp_relativa_raw > (thr_nao_metal * 0.5)

    evidencia_sem_agc = amp_relativa_sem > (thr_nao_metal * 0.5)

    # --- Inversao de fase (sinal real antes do envelope) ---
    win = 3
    r0  = max(0, row_apex - win)
    r1  = min(n_samples - 1, row_apex + win)
    janela = trace_sem[r0:r1 + 1]
    fase_consistente = False
    if len(janela) >= 4:
        metade   = len(janela) // 2
        antes    = float(np.mean(janela[:metade]))
        depois   = float(np.mean(janela[metade:]))
        fase_consistente = (antes > 0 and depois < 0) or (antes < 0 and depois > 0)

    # --- SNR local ---
    snr_local = _calcular_snr_local(arr_sem_agc, col0, row_apex)

    # --- Decisao de classificacao ---
    if amp_relativa_sem >= thr_metal and fase_consistente:
        tipo_sugerido  = "possivel_metalico"
        confianca_tipo = "alta"
    elif amp_relativa_sem >= thr_metal and not fase_consistente:
        tipo_sugerido  = "possivel_galeria_ou_vazio"
        confianca_tipo = "media"
    elif amp_relativa_sem < thr_nao_metal:
        tipo_sugerido  = "possivel_nao_metalico"
        confianca_tipo = "alta"
    else:
        # Zona intermediaria — usa inversao de fase como desempate
        if fase_consistente:
            tipo_sugerido  = "possivel_metalico"
            confianca_tipo = "baixa"
        else:
            tipo_sugerido  = "inconclusivo"
            confianca_tipo = "baixa"

    return {
        "tipo_material":              tipo_sugerido,
        "confianca_tipo":             confianca_tipo,
        "amplitude_relativa_sem_agc": round(amp_relativa_sem, 3),
        "amplitude_relativa_raw":     round(amp_relativa_raw, 3),
        "fase_consistente":           fase_consistente,
        "evidencia_raw":              evidencia_raw,
        "evidencia_sem_agc":          evidencia_sem_agc,
        "snr_local":                  snr_local,
    }


def analisar_espectro_solo(arr, params):
    """Detecta degradacao espectral com profundidade via FFT por faixas. — sem alteracoes"""
    n_amostras = arr.shape[0]
    dt         = params["dt_s"]
    n_janelas  = 4
    tam_janela = n_amostras // n_janelas

    if tam_janela < 16:
        return {"freq_camadas_mhz": [], "atenuacao_severa": False, "prof_confiavel_frac": 1.0}

    freq_por_camada = []
    for i in range(n_janelas):
        ini      = i * tam_janela
        fim      = ini + tam_janela
        janela   = arr[ini:fim, :].mean(axis=1).astype(float)
        espectro = np.abs(rfft(janela))
        freqs    = rfftfreq(len(janela), d=dt)
        idx_pico = int(np.argmax(espectro[1:])) + 1
        freq_por_camada.append(round(float(freqs[idx_pico]) / 1e6, 1))

    f0   = freq_por_camada[0] if freq_por_camada[0] > 0 else 1.0
    fult = freq_por_camada[-1] if freq_por_camada[-1] > 0 else 1.0
    queda = f0 / fult if fult > 0 else 999.0

    prof_confiavel_frac = 1.0
    for i, f in enumerate(freq_por_camada):
        if f < f0 * 0.5:
            prof_confiavel_frac = i / n_janelas
            break

    return {
        "freq_camadas_mhz":    freq_por_camada,
        "atenuacao_severa":    queda > 2.0,
        "prof_confiavel_frac": prof_confiavel_frac,
    }


def _calcular_confidence_score(fit_ok, score_hough, evidencia_raw, evidencia_sem_agc,
                                snr_local, diam_confianca, confianca_tipo, depth_m=None):
    """
    Score composto 0-100. Combina evidencias geometricas e fisicas.

    Criterios e pesos:
      fit_ok           : +25  (curve fitting convergiu — maior evidencia geometrica)
      score_hough>=0.6 : +15  (acumulador Hough alto)
      score_hough>=0.4 : +8   (acumulador medio)
      evidencia_raw    : +15  (alvo existe no dado bruto, pre-filtros)
      evidencia_sem_agc: +15  (alvo com amplitude relevante sem AGC)
      snr_local>=3.0   : +15  (relacao sinal/ruido boa)
      snr_local>=1.5   : +8   (SNR moderado)
      diam_confianca   : +10  (diametro estimado com alta confianca)
      confianca_tipo   : +5   (classificacao fisica alta)

    Penalidade: alvo raso (depth_m < 0.25) sem fit -> score capeado em 35 (baixa).

    Retorna DOIS labels:
      confidence_label_tecnico  : reflexo direto do score numerico
      confidence_label_relatorio: exige fit_ok + diam_alta + evidencia_raw + evidencia_sem_agc
                                  para atingir "alta". Sem evidencia dupla ou sem base
                                  geometrica, maximo e "media".

    Labels: alta (>=70) | media (40-69) | baixa (<40)
    """
    score   = 0
    motivos = []

    if fit_ok:
        score += 25
        motivos.append("fit_ok")

    if score_hough >= 0.6:
        score += 15
        motivos.append("hough_alto")
    elif score_hough >= 0.4:
        score += 8
        motivos.append("hough_medio")

    if evidencia_raw:
        score += 15
        motivos.append("evidencia_raw")

    if evidencia_sem_agc:
        score += 15
        motivos.append("evidencia_sem_agc")

    if snr_local >= 3.0:
        score += 15
        motivos.append("snr_alto")
    elif snr_local >= 1.5:
        score += 8
        motivos.append("snr_medio")

    if diam_confianca == "alta":
        score += 10
        motivos.append("diam_alta")

    if confianca_tipo == "alta":
        score += 5
        motivos.append("fisica_alta")

    score = min(score, 100)

    # Penalidade: alvo raso sem fit (provavel ruido superficial)
    if depth_m is not None and float(depth_m) < 0.25 and not fit_ok:
        score = min(score, 35)
        motivos.append("penalidade_raso_sem_fit")

    # Label tecnico: puro reflexo do score
    if score >= 70:
        label_tec = "alta"
        status    = "confirmado"
    elif score >= 40:
        label_tec = "media"
        status    = "possivel"
    else:
        label_tec = "baixa"
        status    = "incerto"

    # Label relatorio: exige as 4 condicoes para "alta"
    #   fit_ok=True + diam_confianca=alta + evidencia_raw=True + evidencia_sem_agc=True
    # Sem qualquer uma delas, maximo e "media"
    tem_evidencia_dupla  = evidencia_raw and evidencia_sem_agc
    tem_base_geometrica  = fit_ok and (diam_confianca == "alta")
    if tem_evidencia_dupla and tem_base_geometrica:
        label_rel = label_tec          # segue o score normalmente
    else:
        label_rel = "media" if label_tec == "alta" else label_tec

    motivo_str = "; ".join(motivos) if motivos else "sem_evidencias"
    return score, label_tec, label_rel, status, motivo_str


def enriquecer_deteccoes_fisica(arr_detector, arr_sem_agc, arr_raw, deteccoes, params):
    """
    V1.1 — Enriquece o DataFrame de deteccoes com analises fisicas usando 3 matrizes.

    Parametros:
      arr_detector : matriz com AGC — para geometria (Hough ja rodou nesta)
      arr_sem_agc  : matriz sem AGC — fonte correta para amplitude e fase
      arr_raw      : matriz bruta   — evidencia independente pre-filtros
      deteccoes    : DataFrame com deteccoes geometricas (output de detectar_hiperboles)
      params       : dicionario de parametros

    Colunas adicionadas:
      tipo_material, confianca_tipo,
      amplitude_relativa_sem_agc, amplitude_relativa_raw,
      fase_consistente, evidencia_raw, evidencia_sem_agc, snr_local,
      confidence_score_0_100, confidence_label, status_interpretacao, motivo_confianca

    Retorna: (deteccoes_enriquecido, espectro_solo)
    """
    COLUNAS_FISICA = [
        "tipo_material", "confianca_tipo",
        "amplitude_relativa_sem_agc", "amplitude_relativa_raw",
        "fase_consistente", "evidencia_raw", "evidencia_sem_agc", "snr_local",
        "confidence_score_0_100",
        "confidence_label_tecnico", "confidence_label_relatorio",
        "confidence_label",          # alias de relatorio (backward compat — mais rigoroso)
        "status_interpretacao", "motivo_confianca",
    ]

    if not params.get("fis_ativo", True):
        df = deteccoes.copy()
        for col in COLUNAS_FISICA:
            df[col] = "N/A"
        return df, {}

    v  = params["v_m_per_s"]
    dt = params["dt_s"]
    dx = params["dx_m"]

    # Usa arr_sem_agc como referencia de shape; fallback para arr_detector
    arr_fis = arr_sem_agc if arr_sem_agc is not None else arr_detector

    resultados = []
    for _, row in deteccoes.iterrows():
        col0 = int(round(row["x_m"] / dx))
        col0 = max(0, min(arr_fis.shape[1] - 1, col0))
        row_apex = int(round((2.0 * row["depth_m"] / v) / dt))
        row_apex = max(0, min(arr_fis.shape[0] - 1, row_apex))
        fis = classificar_material_por_fisica(arr_fis, arr_raw, col0, row_apex, params)
        # Analise espectral do traco central (usa arr_sem_agc — amplitudes preservadas)
        try:
            freq_dom, freq_cen, razao_ab = _espectro_alvo(arr_fis, col0, dt)
        except Exception:
            freq_dom, freq_cen, razao_ab = 0.0, 0.0, 0.0
        fis["freq_dominante_mhz"]  = freq_dom
        fis["freq_centroide_mhz"]  = freq_cen
        fis["razao_alta_baixa"]    = razao_ab
        resultados.append(fis)

    df = deteccoes.copy()
    campos_fis = [
        "tipo_material", "confianca_tipo", "amplitude_relativa_sem_agc",
        "amplitude_relativa_raw", "fase_consistente", "evidencia_raw",
        "evidencia_sem_agc", "snr_local",
        "freq_dominante_mhz", "freq_centroide_mhz", "razao_alta_baixa",
    ]
    for campo in campos_fis:
        df[campo] = [r[campo] for r in resultados]

    # Downgrades pos-fisica — aplicados ANTES do score composto
    # (1) confianca_tipo: sem evidencia dupla nao pode ser "alta"
    # (2) diam_confianca: sem fit ou sem evidencia dupla e rebaixada para "baixa"
    for idx in df.index:
        ev_raw = bool(df.at[idx, "evidencia_raw"])
        ev_sem = bool(df.at[idx, "evidencia_sem_agc"])
        fit    = bool(df.at[idx, "fit_ok"])
        sem_dupla = not ev_raw and not ev_sem
        if sem_dupla and df.at[idx, "confianca_tipo"] == "alta":
            df.at[idx, "confianca_tipo"] = "baixa"
        if not fit or sem_dupla:
            df.at[idx, "diam_confianca"] = "baixa"

    # Score composto
    scores, labels_tec, labels_rel, statuses, motivos = [], [], [], [], []
    for _, row_df in df.iterrows():
        sc, lb_tec, lb_rel, st, mot = _calcular_confidence_score(
            fit_ok            = bool(row_df.get("fit_ok", False)),
            score_hough       = float(row_df.get("score", 0)),
            evidencia_raw     = bool(row_df.get("evidencia_raw", False)),
            evidencia_sem_agc = bool(row_df.get("evidencia_sem_agc", False)),
            snr_local         = float(row_df.get("snr_local", 0)),
            diam_confianca    = str(row_df.get("diam_confianca", "baixa")),
            confianca_tipo    = str(row_df.get("confianca_tipo", "baixa")),
            depth_m           = row_df.get("depth_m", None),
        )
        scores.append(sc)
        labels_tec.append(lb_tec)
        labels_rel.append(lb_rel)
        statuses.append(st)
        motivos.append(mot)

    df["confidence_score_0_100"]    = scores
    df["confidence_label_tecnico"]  = labels_tec
    df["confidence_label_relatorio"]= labels_rel
    df["confidence_label"]          = labels_rel   # backward compat — alias de relatorio
    df["status_interpretacao"]      = statuses
    df["motivo_confianca"]          = motivos

    # Espectro do solo roda no arr_detector (AGC ok para espectral)
    espectro = analisar_espectro_solo(arr_detector, params)

    # Adicionar velocity info ao espectro (para index_projeto.csv)
    if "velocity_usada_mns" in df.columns and not df.empty:
        espectro["velocity_usada_projeto_mns"]    = round(float(df["velocity_usada_mns"].iloc[0]), 4)
        espectro["velocity_estimada_projeto_mns"] = round(float(df["velocity_estimada_mns"].iloc[0]), 4)

    return df, espectro


# ---------------------------------------------------------------------------
# ESTIMATIVA AUTOMATICA DE VELOCITY (semblance simplificado)
# ---------------------------------------------------------------------------
def estimar_velocity(arr_sem_agc, params):
    """
    Estima a velocity de propagacao no solo por semblance simplificado.

    Varre velocidades de 0.06 a 0.16 m/ns e mede quanto a hiperbole mais forte
    "colapsa" (maior coerencia ao longo da curva teorica).

    Parametros:
      arr_sem_agc : array sem AGC (amplitudes fisicas preservadas)
      params      : dict com dt_s, dx_m, h_min_m, h_max_m, col_search_half

    Retorna: (velocity_estimada_mns, confidence 0-1)
    """
    from scipy.signal import hilbert as _hilbert

    velocities = np.arange(0.06, 0.165, 0.005)
    dt       = params["dt_s"]
    dx       = params["dx_m"]
    h_min    = params.get("h_min_m", 0.10)
    h_max    = params.get("h_max_m", 3.00)
    col_half = min(params.get("col_search_half", 80), 60)
    n_samples, n_traces = arr_sem_agc.shape

    env      = np.abs(_hilbert(arr_sem_agc, axis=0))
    env_norm = env / (env.max() + 1e-10)

    # Apex mais forte do envelope
    row0, col0 = np.unravel_index(np.argmax(env_norm), env_norm.shape)

    scores = []
    for v_mns in velocities:
        v   = v_mns * 1e9          # m/s
        h   = row0 * dt * v / 2.0  # profundidade estimada para este v

        if not (h_min <= h <= h_max):
            scores.append(0.0)
            continue

        score  = 0.0
        n_pts  = 0
        for dc in range(-col_half, col_half + 1, 2):   # passo 2 para velocidade
            c = col0 + dc
            if not (0 <= c < n_traces):
                continue
            t_hyp   = (2.0 / v) * np.sqrt(h**2 + (dc * dx)**2)
            row_hyp = int(round(t_hyp / dt))
            if 0 <= row_hyp < n_samples:
                score += env_norm[row_hyp, c]
                n_pts += 1

        scores.append(score / max(n_pts, 1))

    scores_arr = np.array(scores)
    if scores_arr.max() < 1e-10:
        return round(float(params["v_m_per_s"] / 1e9), 4), 0.0

    best_idx   = int(np.argmax(scores_arr))
    v_est      = round(float(velocities[best_idx]), 4)
    # confidence: quao destacado e o pico em relacao ao resto
    scores_n   = scores_arr / scores_arr.max()
    confidence = round(float(1.0 - float(np.median(scores_n))), 3)
    return v_est, confidence


# ---------------------------------------------------------------------------
# ANALISE ESPECTRAL DE UM ALVO INDIVIDUAL
# ---------------------------------------------------------------------------
def _espectro_alvo(arr_sem_agc, col0, dt):
    """
    FFT do traco central do alvo no dado sem AGC.

    Retorna: (freq_dominante_mhz, freq_centroide_mhz, razao_alta_baixa)
    """
    from scipy.fft import rfft as _rfft, rfftfreq as _rfftfreq

    col0  = max(0, min(arr_sem_agc.shape[1] - 1, col0))
    trace = arr_sem_agc[:, col0].astype(float)
    n     = len(trace)

    freqs    = _rfftfreq(n, d=dt)          # Hz
    spectrum = np.abs(_rfft(trace))

    # Frequencia de pico (ignora DC)
    idx_peak       = int(np.argmax(spectrum[1:])) + 1
    freq_dominante = round(float(freqs[idx_peak]) / 1e6, 2)

    # Centroide espectral
    total         = float(spectrum.sum()) + 1e-10
    freq_centroide = round(float(np.sum(freqs * spectrum) / total) / 1e6, 2)

    # Razao alta/baixa (threshold 200 MHz)
    thresh     = 200e6
    pow_high   = float(spectrum[freqs > thresh].sum())
    pow_low    = float(spectrum[freqs <= thresh].sum())
    razao      = round(pow_high / (pow_low + 1e-10), 4)

    return freq_dominante, freq_centroide, razao


# ---------------------------------------------------------------------------
# FUNCAO PRINCIPAL DE DETECCAO
# ---------------------------------------------------------------------------
def detectar_hiperboles(arr_processado, params=None, top_n=30):
    """
    Pipeline de deteccao: Hough -> NMS -> CurveFit -> DeltaT.
    arr_processado: matriz COM AGC (visual/detector).
    Analises fisicas chamadas separadamente via enriquecer_deteccoes_fisica().
    Retorna: (deteccoes_df, accum, depths)
    """
    if params is None:
        params = DEFAULT_PARAMS

    # Estimar velocity automaticamente (semblance)
    velocity_estimada_mns, vel_conf = estimar_velocity(arr_processado, params)
    velocity_preset_mns = params["v_m_per_s"] / 1e9
    # Usar estimativa se confianca >= 0.3 e diferenca relevante (> 0.005 m/ns)
    if vel_conf >= 0.3 and abs(velocity_estimada_mns - velocity_preset_mns) > 0.005:
        params = dict(params)
        params["v_m_per_s"] = velocity_estimada_mns * 1e9
        velocity_fonte = "estimada"
        velocity_usada_mns = velocity_estimada_mns
    else:
        velocity_fonte = "preset"
        velocity_usada_mns = velocity_preset_mns

    dx = params["dx_m"]
    dt = params["dt_s"]
    v  = params["v_m_per_s"]
    col_search_half = params.get("col_search_half", 80)

    accum, depths = hough_hiperbola(arr_processado, params)
    peaks = nms_hough(accum, depths, dx, params["nms_radius_m"])
    peaks = peaks[:top_n]

    from scipy.signal import hilbert as _hilbert

    def _medir_largura_hiperbole(arr, col0, h, v, dx, dt, amp_frac=0.25):
        """
        Mede a largura real do arco da hipérbole para um dado alvo.
        Percorre colunas à esquerda e direita do apex, seguindo a curva teórica,
        e mede até onde a amplitude fica acima de amp_frac * amp_apex.
        Retorna largura em metros.
        """
        n_samples, n_traces = arr.shape
        env = np.abs(_hilbert(arr, axis=0))

        # amplitude no apex
        row_apex = int(round((2 * h / v) / dt))
        row_apex = max(0, min(n_samples - 1, row_apex))
        amp_apex = env[row_apex, col0] if 0 <= col0 < n_traces else 0
        if amp_apex < 1e-10:
            return round(col_search_half * dx * 2, 3)  # fallback

        threshold = amp_frac * amp_apex
        col_left, col_right = col0, col0

        # expandir para a esquerda
        for c in range(col0 - 1, max(-1, col0 - col_search_half - 1), -1):
            row_c = int(round((2 / v) * np.sqrt(max(h**2 + ((c - col0) * dx)**2, 0)) / dt))
            row_c = max(0, min(n_samples - 1, row_c))
            if env[row_c, c] >= threshold:
                col_left = c
            else:
                break

        # expandir para a direita
        for c in range(col0 + 1, min(n_traces, col0 + col_search_half + 1)):
            row_c = int(round((2 / v) * np.sqrt(max(h**2 + ((c - col0) * dx)**2, 0)) / dt))
            row_c = max(0, min(n_samples - 1, row_c))
            if env[row_c, c] >= threshold:
                col_right = c
            else:
                break

        largura = round((col_right - col_left) * dx, 3)
        return max(largura, dx * 2)  # mínimo de 2 traços

    rows_out = []
    for rank, (col0_hough, d_idx, score) in enumerate(peaks, start=1):
        h_hough = depths[d_idx]
        h_ref, col0_ref, fit_ok = refinar_profundidade_curvefitting(
            arr_processado, col0_hough, h_hough, params
        )
        row_apex = int(round((2 * h_ref / v) / dt))
        row_apex = max(0, min(arr_processado.shape[0] - 1, row_apex))
        diam, confianca = estimar_diametro_delta_t(
            arr_processado, col0_ref, row_apex, params
        )
        prof_topo_m = round(h_ref - diam / 2, 3) if diam > 0 else h_ref
        altura_hiperbole_m = round(diam * 1.5, 3) if diam > 0 else round(h_ref * 0.8, 3)

        # largura real medida por alvo (não mais valor global fixo)
        largura_hiperbole_m = _medir_largura_hiperbole(
            arr_processado, col0_ref, h_ref, v, dx, dt, amp_frac=0.25
        )
        if largura_hiperbole_m < 1.5:
            tipo_tamanho = "pequena"
        elif largura_hiperbole_m <= 3.0:
            tipo_tamanho = "media"
        else:
            tipo_tamanho = "grande"

        rows_out.append({
            "rank":                    rank,
            "x_m":                     round(col0_ref * dx, 2),
            "depth_m":                 h_ref,
            "depth_hough_m":           round(h_hough, 3),
            "fit_ok":                  fit_ok,
            "diam_est_m":              diam,
            "diam_confianca":          confianca,
            "score":                   round(score, 3),
            "prof_topo_m":             prof_topo_m,
            "largura_hiperbole_m":     largura_hiperbole_m,
            "altura_hiperbole_m":      altura_hiperbole_m,
            "tipo_tamanho":            tipo_tamanho,
            # Velocity — mesma para todos os alvos do DZT
            "velocity_usada_mns":      velocity_usada_mns,
            "velocity_estimada_mns":   velocity_estimada_mns,
            "velocity_fonte":          velocity_fonte,
        })

    return pd.DataFrame(rows_out), accum, depths


# ---------------------------------------------------------------------------
# VISUALIZACAO V1.1
# ---------------------------------------------------------------------------
# Mapa de cores atualizado com nomenclatura V1.1 + backward compat V1.0
_COR_MATERIAL = {
    # V1.1 — nomenclatura possivel_*
    "possivel_metalico":         "#FF4444",   # vermelho
    "possivel_nao_metalico":     "#44AAFF",   # azul
    "possivel_galeria_ou_vazio": "#FF9900",   # laranja
    "inconclusivo":              "#CCCCCC",   # cinza
    # V1.0 — backward compat
    "metal":      "#FF4444",
    "nao_metal":  "#44AAFF",
    "galeria_ar": "#FF9900",
    "N/A":        "#FFD700",   # amarelo
}

_LEGENDA_MATERIAL = {
    "possivel_metalico":         "Possivel metalico",
    "possivel_nao_metalico":     "Possivel nao-metalico",
    "possivel_galeria_ou_vazio": "Possivel galeria/vazio",
    "inconclusivo":              "Inconclusivo",
    "metal":      "Metal (V1.0)",
    "nao_metal":  "Nao-metal (V1.0)",
    "galeria_ar": "Galeria (V1.0)",
    "N/A":        "Alvo",
}


def plotar_deteccoes(arr_processado, deteccoes, params, output_path=None,
                     apenas_alta_confianca=False):
    """
    Radargrama anotado com hiperboles detectadas.
    V1.1: suporte a filtro de alta confianca (apenas_alta_confianca=True).

    Cor do marcador: tipo de material (vermelho=metalico, azul=nao-metalico, laranja=galeria)
    Arco: fit convergido (verde) ou Hough (laranja)
    Score no label: confidence_score_0_100 se disponivel
    """
    v         = params["v_m_per_s"]
    dt        = params["dt_s"]
    dx        = params["dx_m"]
    n_samples, n_traces = arr_processado.shape
    depth_max = n_samples * dt * v / 2
    dist_max  = n_traces * dx

    # Filtro de confianca
    df_plot = deteccoes.copy()
    if apenas_alta_confianca and "confidence_score_0_100" in df_plot.columns:
        df_plot = df_plot[df_plot["confidence_score_0_100"] >= 70]
        if df_plot.empty:
            # Nada para plotar — salva imagem em branco com aviso
            fig, ax = plt.subplots(figsize=(18, 7))
            clip    = np.percentile(np.abs(arr_processado), 98)
            arr_viz = np.clip(arr_processado, -clip, clip)
            ax.imshow(arr_viz, cmap="gray", aspect="auto", vmin=-clip, vmax=clip,
                      extent=[0, dist_max, depth_max, 0])
            ax.set_title("Alta Confianca — Nenhum alvo com score >= 70", fontsize=11)
            plt.tight_layout()
            if output_path:
                from pathlib import Path as _Path
                _Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
                plt.close()
            else:
                plt.show()
            return

    clip    = np.percentile(np.abs(arr_processado), 98)
    arr_viz = np.clip(arr_processado, -clip, clip)

    titulo_sufixo = " [Alta Confianca >= 70]" if apenas_alta_confianca else " [Todos os Candidatos]"
    fig, ax = plt.subplots(figsize=(18, 7))
    ax.imshow(arr_viz, cmap="gray", aspect="auto", vmin=-clip, vmax=clip,
              extent=[0, dist_max, depth_max, 0])
    ax.set_xlabel("Distancia (m)", fontsize=11)
    ax.set_ylabel("Profundidade estimada (m)", fontsize=11)
    ax.set_title(f"Deteccao de Alvos — Hough + CurveFit + DeltaT + Fisica{titulo_sufixo}",
                 fontsize=12, fontweight="bold")

    tem_fisica = ("tipo_material" in df_plot.columns and
                  not df_plot.empty and
                  str(df_plot["tipo_material"].iloc[0]) != "N/A")
    tem_score  = "confidence_score_0_100" in df_plot.columns

    for _, row in df_plot.iterrows():
        x0        = row["x_m"]
        h         = row["depth_m"]
        diam      = row["diam_est_m"]
        conf      = row["diam_confianca"]
        fitok     = row["fit_ok"]
        tipo      = str(row.get("tipo_material", "N/A"))
        conf_tipo = str(row.get("confianca_tipo", "N/A"))
        sc        = row.get("confidence_score_0_100", "")

        cor_apex = _COR_MATERIAL.get(tipo, "#FFD700")
        borda_lw = 1.8 if conf == "alta" else 0.7
        cor_arco = "#00FF88" if fitok else "#FF8C00"

        ax.plot(x0, h, "o", color=cor_apex, markersize=8,
                markeredgecolor="white", markeredgewidth=borda_lw, zorder=5)

        x_range = np.linspace(max(0, x0 - 3.0), min(dist_max, x0 + 3.0), 300)
        t_curve = (2.0 / v) * np.sqrt(h**2 + (x_range - x0)**2)
        d_curve = t_curve * v / 2.0
        mask    = d_curve < depth_max
        ax.plot(x_range[mask], d_curve[mask], "-", color=cor_arco,
                alpha=0.75, linewidth=1.2, zorder=4)

        diam_str  = f"{diam*100:.0f}cm ({conf[0].upper()})" if diam > 0 else "diam N/D"
        tipo_str  = f" | {tipo[:4].upper()}({conf_tipo[0].upper()})" if tem_fisica and tipo != "N/A" else ""
        sc_str    = f" sc={int(sc)}" if tem_score and str(sc) not in ("", "N/A") else ""
        label     = f"#{row['rank']}  {h:.2f}m  {diam_str}{tipo_str}{sc_str}"
        ax.text(x0 + 0.08, h - 0.08, label, color="white", fontsize=6.5,
                bbox=dict(boxstyle="round,pad=0.15", fc="black", alpha=0.6), zorder=6)

    from matplotlib.lines import Line2D
    legenda = []
    if tem_fisica:
        tipos_presentes = df_plot["tipo_material"].unique()
        for k in ["possivel_metalico", "possivel_nao_metalico",
                  "possivel_galeria_ou_vazio", "inconclusivo",
                  "metal", "nao_metal", "galeria_ar", "N/A"]:
            if k in tipos_presentes:
                legenda.append(Line2D([0], [0], marker="o", color="w",
                                      markerfacecolor=_COR_MATERIAL.get(k, "#FFD700"),
                                      markersize=8, label=_LEGENDA_MATERIAL.get(k, k)))
    else:
        legenda.append(Line2D([0], [0], marker="o", color="w",
                              markerfacecolor="#FFD700", markersize=8, label="Alvo"))

    legenda += [
        Line2D([0], [0], color="#00FF88", lw=1.5, label="Fit convergido"),
        Line2D([0], [0], color="#FF8C00", lw=1.5, label="Hough (sem fit)"),
    ]
    ax.legend(handles=legenda, loc="lower right", fontsize=8,
              facecolor="black", labelcolor="white", framealpha=0.7)

    plt.tight_layout()
    if output_path:
        from pathlib import Path as _Path
        _Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(str(output_path), dpi=150, bbox_inches="tight")
        plt.close()
    else:
        plt.show()
