"""
Pipeline v2.0.0 - ScanSOLO GPR
Processamento automatico de arquivos .DZT (Georadar GSSI)

ARQUITETURA v2.0.0 — Tres fluxos separados:

  FLUXO CIENTIFICO (para o geofísico Amilson):
    raw -> dewow -> bandpass -> tpow          -> arr_cientifico
    Sem: bgremoval, AGC. Preserva sinal fisico e refletores horizontais.
    Saida: _radargrama_cientifico.png

  FLUXO RELATORIO (para o cliente final):
    raw -> dewow -> bandpass -> bgremoval -> tpow -> AGC -> arr_relatorio
    Limpo, visual, adequado ao PDF. NAO alimenta o detector.
    Saida: _radargrama_relatorio.png  (alias: _processada.png — compat)

  FLUXO DETECTOR (para Hough + CurveFit + DeltaT):
    Controlado por detector_input_mode:
      raw              -> arr_raw (default — melhor CurveFit, 82% CF em PATIO)
      raw_dewow_bandpass -> arr apos dewow+bp (75% CF — alternativa conservadora)
      sem_agc          -> arr apos bgremoval+tpow (70% CF — atual)
      proc_agc_atual   -> arr com AGC (24% CF — benchmark only)
    + filtro depth_min=0.30m para eliminar candidatos de airwave superficial
    Saida: _anotada.png desenhada sobre _radargrama_cientifico.png

Matrizes numpy por finalidade:
  raw.npy                 : bruta pre-qualquer-filtro (auditoria, ML futuro)
  radargrama_cientifico.npy : dewow+bp+tpow — imagem principal do geofisico
  processado_sem_agc.npy  : bgremoval+tpow — analise fisica de amplitude/fase
  processado_visual.npy   : com AGC — alias compat
  processado.npy          : alias de processado_visual.npy (backward compat)

SNR medido em 3 pontos:
  snr_raw            : dado bruto (governador do modo de processamento)
  snr_cientifico     : apos dewow+bp+tpow (qualidade do fluxo cientifico)
  snr_relatorio      : apos bgremoval+tpow (qualidade antes do AGC visual)

Saidas por DZT:
  01 _bruta.png                  — referencia, pre-filtro
  02 _radargrama_cientifico.png  — imagem principal do geofisico
  03 _radargrama_relatorio.png   — imagem visual para PDF/cliente
     _processada.png             — alias backward compat
  04 _anotada_completa.png       — candidatos sobre radargrama cientifico
     _anotada.png                — alias backward compat
     _anotada_alta_confianca.png
  CSV, config_used.json, pipeline.log

Uso:
  python pipeline_v1.py --input <pasta_dzts> --output <pasta_saida> [--preset 270mhz]
                        [--sem-detector] [--sem-fisica]
                        [--detector-input raw|raw_dewow_bandpass|sem_agc|proc_agc_atual]

Flags opcionais:
  --sem-detector        Pula deteccao de hiperboles
  --sem-fisica          Pula analises fisicas (mantem deteccao geometrica)
  --detector-input MODE Seleciona matriz de entrada do detector (default: raw)
"""

import gc
import os, sys, json, hashlib, shutil, argparse, logging, warnings
from datetime import datetime
from pathlib import Path

os.environ["MPLBACKEND"] = "Agg"

import numpy as np
import pandas as pd
from scipy import signal as sp_signal
from scipy.signal import hilbert
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")
import gprpy.gprpy as gp

# Importa modulo de deteccao (mesmo diretorio)
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from detector_hiperboles import (
        detectar_hiperboles, plotar_deteccoes,
        enriquecer_deteccoes_fisica,
    )
    DETECTOR_DISPONIVEL = True
except ImportError as _e:
    DETECTOR_DISPONIVEL = False
    _import_erro = str(_e)


# ---------------------------------------------------------------------------
# VERSAO DO SCRIPT
# ---------------------------------------------------------------------------
SCRIPT_VERSION = "2.0.0"


# ---------------------------------------------------------------------------
# LIMIARES SNR POR TIPO DE SOLO (S/sigma ratio, nao dB)
# Referencia Amilson: S/sigma=100 (40dB)=limpo, =10 (20dB)=bom, =3 (10dB)=ruidoso
# ---------------------------------------------------------------------------
SNR_LIMIARES = {
    # (limiar_minimo, limiar_padrao) — calibrado para Hilbert per-trace (escala ~40-50% menor que RMS)
    # PATIO_001=9.25, 002=5.44, 003=6.45, 004=4.56 — todos abaixo de 30 -> modo PADRAO
    # limiar_padrao=4.0: PATIO_004 (4.56) fica em PADRAO com margem
    "standard":  (30.0, 4.0),
    "arenoso":   (30.0, 4.0),
    "argiloso":  (20.0, 3.5),
    "umido":     (15.0, 3.0),
    "pedregoso": (35.0, 6.0),
}


# ---------------------------------------------------------------------------
# PRESETS
# ---------------------------------------------------------------------------
PRESETS = {
    "270mhz": {
        "descricao":         "Antena GSSI 270 MHz - padrao ScanSOLO",
        "dewow_window":      5,
        "bandpass_low_mhz":  80,
        "bandpass_high_mhz": 500,
        "bandpass_order":    5,
        "bgremoval_traces":  30,
        "tpow_power":        0.5,
        "agc_window":        150,
        "velocity_mns":      0.1,
        "contrast":          2.5,
        "colormap":          "gray",
        "dpi":               150,
        # Detector de hiperboles
        "det_amp_threshold": 0.50,
        "det_h_min_m":       0.10,
        "det_h_max_m":       3.00,
        "det_h_step_m":      0.04,
        "det_nms_radius_m":  0.50,
        "det_top_n":         25,
        "det_min_score_csv":  30,
        "det_min_score_plot": 40,
        "det_cf_wing_half_m":2.0,
        "det_cf_amp_frac":   0.30,
        "det_dt_min_diam_m": 0.05,
        "det_dt_max_diam_m": 1.50,
        "det_dt_conf_frac":  0.20,
        # Analises fisicas (modulo separavel — False desativa completamente)
        # [CALIBRAR] com Amilson usando ~10 alvos de tipo conhecido antes de producao
        "fis_ativo":             True,
        "fis_amp_metal_thr":     0.75,
        "fis_amp_nao_metal_thr": 0.40,
        # Entrada do detector — v2.0.0
        # raw: melhor CurveFit (82% nos PATIO) — default recomendado
        # raw_dewow_bandpass: alternativa conservadora (75% CF)
        # sem_agc: fluxo anterior sem AGC (70% CF)
        # proc_agc_atual: fluxo com AGC — apenas benchmark (24% CF, 46% falsos positivos)
        "detector_input_mode":   "raw",
        # Profundidade minima dos candidatos — elimina airwave superficial
        # Candidatos com depth_m < det_depth_min_m sao descartados antes do CSV/plot
        "det_depth_min_m":       0.30,
    },
    "default": {
        "descricao":         "Preset generico",
        "dewow_window":      5,
        "bandpass_low_mhz":  80,
        "bandpass_high_mhz": 500,
        "bandpass_order":    5,
        "bgremoval_traces":  30,
        "tpow_power":        0.5,
        "agc_window":        150,
        "velocity_mns":      0.1,
        "contrast":          2.5,
        "colormap":          "gray",
        "dpi":               150,
        "det_amp_threshold": 0.50,
        "det_h_min_m":       0.10,
        "det_h_max_m":       3.00,
        "det_h_step_m":      0.04,
        "det_nms_radius_m":  0.50,
        "det_top_n":         25,
        "det_min_score_csv":  30,
        "det_min_score_plot": 40,
        "det_cf_wing_half_m":2.0,
        "det_cf_amp_frac":   0.30,
        "det_dt_min_diam_m": 0.05,
        "det_dt_max_diam_m": 1.50,
        "det_dt_conf_frac":  0.20,
        "fis_ativo":             True,
        "fis_amp_metal_thr":     0.75,
        "fis_amp_nao_metal_thr": 0.40,
        "detector_input_mode":   "raw",
        "det_depth_min_m":       0.30,
    },
}

PASTAS = {
    "brutas":      "01_Imagens_Brutas",
    "processadas": "02_Imagens_Processadas",
    "historico":   "03_Historico_Processamento",
    "logs":        "04_Logs",
    "alvos":       "05_Tabela_Alvos",
    "dados":       "06_Dados_Numpy",
}


# ---------------------------------------------------------------------------
# BANDPASS — scipy SOS (GPRPy nao tem nativo)
# ---------------------------------------------------------------------------
def aplicar_bandpass(prof, low_mhz, high_mhz, order):
    """
    Filtro Butterworth bandpass via scipy SOS.
    CRITICO: converte np.matrix -> ndarray antes de filtrar.
    prof.data e np.matrix: indexacao de coluna retorna (n,1) em vez de (n,)
    quebrando scipy.signal.sosfiltfilt. np.asarray() corrige isso.
    """
    data    = np.asarray(prof.data)
    n       = data.shape[0]
    dt_ns   = prof.twtt[-1] / (n - 1)
    fs_mhz  = 1000.0 / dt_ns
    nyq_mhz = fs_mhz / 2.0
    low_n   = max(low_mhz  / nyq_mhz, 0.001)
    high_n  = min(high_mhz / nyq_mhz, 0.999)
    sos     = sp_signal.butter(order, [low_n, high_n], btype="band", output="sos")
    out     = np.zeros_like(data, dtype=float)
    for i in range(data.shape[1]):
        out[:, i] = sp_signal.sosfiltfilt(sos, data[:, i].astype(float))
    prof.data = np.matrix(out.astype(np.float64))
    prof.history.append(
        f"# bandpass scipy sos: {low_mhz}-{high_mhz} MHz order={order} fs={fs_mhz:.0f}MHz"
    )


# ---------------------------------------------------------------------------
# TPOW MANUAL — replica GPRPy tpowGain sem modificar prof.data
# ---------------------------------------------------------------------------
def _aplicar_tpow_manual(arr: np.ndarray, power: float) -> np.ndarray:
    """
    Aplica ganho de tempo (t^power) ao array sem modificar o objeto prof.
    Replica o comportamento de GPRPy.tpowGain para uso em copia independente.
    Usado para gerar arr_cientifico (dewow+bp+tpow sem bgremoval).
    """
    if power <= 0:
        return arr.copy()
    n = arr.shape[0]
    if n <= 1:
        return arr.copy()
    gains = (np.arange(n, dtype=float) / max(n - 1, 1)) ** float(power)
    return (arr.astype(float) * gains[:, np.newaxis]).astype(np.float32)


# ---------------------------------------------------------------------------
# SALVAR IMAGEM CIENTIFICA — fluxo sem bgremoval/AGC para geofísico
# ---------------------------------------------------------------------------
def salvar_imagem_cientifica(arr, depth_m, dist_m, caminho, preset, nome_arquivo=""):
    """
    Radargrama cientifico — imagem principal para revisao tecnica do geofisico.

    Pipeline que gerou arr: raw -> dewow -> bandpass -> tpow
    SEM: bgremoval, AGC. Preserva decaimento de amplitude, refletores horizontais,
    relacoes de fase e sinal profundo.

    Diferenca visual vs. radargrama_relatorio: mais ruidoso, mais informacao real.
    """
    contrast = preset.get("contrast", 3.0)
    std = float(np.std(arr))
    if std < 1e-10:
        std = 1.0
    vmin, vmax = -contrast * std, contrast * std

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.imshow(
        arr,
        extent=[0, dist_m, depth_m, 0],
        aspect="auto",
        cmap=preset.get("colormap", "gray"),
        vmin=vmin, vmax=vmax,
        interpolation="nearest",
    )
    ax.set_xlabel("Distancia (m)", fontsize=10)
    ax.set_ylabel("Profundidade (m)", fontsize=10)
    ax.set_xlim(0, dist_m)
    ax.set_ylim(depth_m, 0)
    titulo = (f"{nome_arquivo}  |  Radargrama Cientifico  |  "
              f"{datetime.now().strftime('%Y-%m-%d')}")
    ax.set_title(titulo, fontsize=9, color="#333333", pad=4)
    ax.text(0.01, 0.01,
            "Fluxo: dewow+bandpass+tpow — sem AGC, sem bgremoval",
            transform=ax.transAxes, fontsize=7, color="#888888",
            verticalalignment="bottom")
    plt.tight_layout()
    plt.savefig(str(caminho), format="png", dpi=preset.get("dpi", 150), bbox_inches="tight")
    plt.close("all")


# ---------------------------------------------------------------------------
# UTILIDADES
# ---------------------------------------------------------------------------
def criar_estrutura(pasta_saida):
    caminhos = {}
    for chave, nome in PASTAS.items():
        p = pasta_saida / nome
        p.mkdir(parents=True, exist_ok=True)
        caminhos[chave] = p
    return caminhos


def configurar_log(pasta_log):
    logger = logging.getLogger("pipeline_v1")
    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    # StreamHandler com UTF-8 para evitar UnicodeEncodeError em terminais Windows (cp1252)
    try:
        import io as _io
        _stream = _io.TextIOWrapper(
            sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
        )
    except AttributeError:
        _stream = sys.stdout
    ch = logging.StreamHandler(_stream)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    fh = logging.FileHandler(pasta_log / "pipeline.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    return logger


def salvar_imagem(prof, caminho, preset, titulo=None):
    fig = plt.figure(figsize=(14, 6))
    if hasattr(prof, "marks"):
        prof.marks = []
    prof.prepProfileFig(color=preset["colormap"], contrast=preset["contrast"])
    if titulo:
        plt.suptitle(titulo, fontsize=9, color="#333333",
                     x=0.5, y=0.99, ha="center", va="top")
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(str(caminho), format="png", dpi=preset["dpi"], bbox_inches="tight")
    plt.close("all")


def salvar_imagem_padrao_amilson(arr, depth_m, dist_m, caminho, preset, nome_arquivo="", prof=None):
    """
    Gera imagem no padrao visual Amilson:
      - Titulo simples: nome do arquivo + data
      - Labels em portugues: 'Profundidade (m)' / 'Distancia (m)'
      - SEM AGC: preserva decaimento fisico de amplitude com profundidade
      - Contraste: clip por ±contrast*std
      - Colormap gray, figsize 14x4 pol, dpi configuravel
      - Este e o formato entregue ao Amilson e ao cliente.

    arr           : numpy array 2D shape (n_amostras, n_tracos) — usar arr_sem_agc
    depth_m       : profundidade maxima em metros (eixo Y)
    dist_m        : distancia total em metros (eixo X)
    nome_arquivo  : nome do .DZT para o titulo (ex: 'linha_001.DZT')
    prof          : objeto GPRPy opcional — se fornecido, limpa prof.marks antes de plotar
    """
    if prof is not None and hasattr(prof, "marks"):
        prof.marks = []
    contrast = preset.get("contrast", 3.0)
    std = float(np.std(arr))
    vmin, vmax = -contrast * std, contrast * std

    fig, ax = plt.subplots(figsize=(14, 4))
    ax.imshow(
        arr,
        extent=[0, dist_m, depth_m, 0],
        aspect="auto",
        cmap=preset.get("colormap", "gray"),
        vmin=vmin,
        vmax=vmax,
        interpolation="nearest",
    )
    ax.set_xlabel("Distância (m)", fontsize=10)
    ax.set_ylabel("Profundidade (m)", fontsize=10)
    ax.set_xlim(0, dist_m)
    ax.set_ylim(depth_m, 0)

    # Titulo simples: nome do arquivo + data
    titulo = f"{nome_arquivo}  |  {datetime.now().strftime('%Y-%m-%d')}" if nome_arquivo else datetime.now().strftime('%Y-%m-%d')
    ax.set_title(titulo, fontsize=9, color="#555555", pad=4)

    plt.tight_layout()
    plt.savefig(str(caminho), format="png", dpi=preset.get("dpi", 150), bbox_inches="tight")
    plt.close("all")


def salvar_config_json(pasta_saida, preset, preset_nome, config_hash):
    """Salva config_used.json com todos os parametros + metadata do run."""
    config_data = {
        "script_version":       SCRIPT_VERSION,
        "timestamp":            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "preset_nome":          preset_nome,
        "config_hash":          config_hash,
        # Preset completo
        "descricao":            preset["descricao"],
        "dewow_window":         preset["dewow_window"],
        "bandpass_low_mhz":     preset["bandpass_low_mhz"],
        "bandpass_high_mhz":    preset["bandpass_high_mhz"],
        "bandpass_order":       preset["bandpass_order"],
        "bgremoval_traces":     preset["bgremoval_traces"],
        "tpow_power":           preset["tpow_power"],
        "agc_window":           preset["agc_window"],
        "velocity_mns":         preset["velocity_mns"],
        "contrast":             preset["contrast"],
        "colormap":             preset["colormap"],
        "dpi":                  preset["dpi"],
        # Detector
        "det_amp_threshold":    preset["det_amp_threshold"],
        "det_h_min_m":          preset["det_h_min_m"],
        "det_h_max_m":          preset["det_h_max_m"],
        "det_h_step_m":         preset["det_h_step_m"],
        "det_nms_radius_m":     preset["det_nms_radius_m"],
        "det_top_n":            preset["det_top_n"],
        "det_cf_wing_half_m":   preset["det_cf_wing_half_m"],
        "det_cf_amp_frac":      preset["det_cf_amp_frac"],
        "det_dt_min_diam_m":    preset["det_dt_min_diam_m"],
        "det_dt_max_diam_m":    preset["det_dt_max_diam_m"],
        "det_dt_conf_frac":     preset["det_dt_conf_frac"],
        # Fisica
        "fis_ativo":            preset["fis_ativo"],
        "fis_amp_metal_thr":    preset["fis_amp_metal_thr"],
        "fis_amp_nao_metal_thr":preset["fis_amp_nao_metal_thr"],
        # Velocidade e calibracao
        "velocity_calibrada":   False,
        "metodo_calibracao":    "default",
        "observacao_calibracao":"[CALIBRAR] Confirmar velocity_mns com Amilson usando alvo de posicao e profundidade conhecidas",
    }
    caminho = pasta_saida / "config_used.json"
    with open(str(caminho), "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    return caminho


def _salvar_npy_seguro(arr, caminho):
    """
    Salva array .npy de forma atomica: escreve em arquivo temporario e renomeia.
    Evita arquivos truncados se o processo for interrompido durante a escrita.
    """
    import tempfile
    caminho = Path(caminho)
    fd, tmp = tempfile.mkstemp(dir=str(caminho.parent), suffix=".npy")
    try:
        os.close(fd)
        np.save(tmp, arr)
        os.replace(tmp, str(caminho))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# SNR GATE (v1.2.0)
# ---------------------------------------------------------------------------
def calcular_snr_imagem_db(
    arr_raw: np.ndarray,
    tipo_solo: str = "standard",
) -> tuple:
    """
    SNR por traco com envelope analitico de Hilbert.

    Formula: SNR = max|H[x(t)]| / std[x_ruido(t)]
    Referencia: padrao classico de GPR — pico de envelope / desvio do ruido,
    mediana sobre todos os tracos (robusto a outliers).

    Janela de sinal: 10%-75% das amostras (exclui onda direta do inicio)
    Janela de ruido: 95%-100% das amostras (ultimos 5% — ruido termico genuino, sem reflexoes tardias)

    Retorna: (snr_db, snr_ratio, modo)
      modo: "minimo" | "padrao" | "agressivo"
    """
    n_samples = arr_raw.shape[0]
    s0 = max(1, int(0.10 * n_samples))
    s1 = int(0.75 * n_samples)
    r0 = int(0.95 * n_samples)

    snr_por_traco = []
    for i in range(arr_raw.shape[1]):
        trace = arr_raw[:, i].astype(float)
        envelope = np.abs(hilbert(trace[s0:s1]))
        pico_sinal = float(np.max(envelope))
        ruido_std = float(np.std(trace[r0:])) + 1e-10
        snr_por_traco.append(pico_sinal / ruido_std)

    snr_ratio = float(np.median(snr_por_traco))
    snr_db = round(20.0 * np.log10(snr_ratio) if snr_ratio > 0 else 0.0, 1)

    thr_minimo, thr_padrao = SNR_LIMIARES.get(tipo_solo, SNR_LIMIARES["standard"])

    if snr_ratio >= thr_minimo:
        modo = "minimo"
    elif snr_ratio >= thr_padrao:
        modo = "padrao"
    else:
        modo = "agressivo"

    return snr_db, round(snr_ratio, 2), modo


# ---------------------------------------------------------------------------
# DETECCAO DE ALVOS V1.1
# ---------------------------------------------------------------------------
def _params_detector(prof, preset):
    """Monta dicionario de parametros do detector a partir do prof e preset."""
    n_amostras = prof.data.shape[0]
    n_tracos   = prof.data.shape[1]
    twtt_max   = float(prof.twtt[-1])
    dist_max   = float(prof.profilePos[-1])
    return {
        "v_m_per_s":             preset["velocity_mns"] * 1e9,
        "dt_s":                  (twtt_max / (n_amostras - 1)) * 1e-9,
        "dx_m":                  dist_max / max(n_tracos - 1, 1),
        "amp_threshold":         preset["det_amp_threshold"],
        "h_min_m":               preset["det_h_min_m"],
        "h_max_m":               min(preset["det_h_max_m"], float(prof.depth[-1])),
        "h_step_m":              preset["det_h_step_m"],
        "col_search_half":       int(3.0 * (n_tracos / dist_max)),
        "nms_radius_m":          preset["det_nms_radius_m"],
        "top_n":                 preset["det_top_n"],
        "cf_wing_half_m":        preset["det_cf_wing_half_m"],
        "cf_amp_frac":           preset["det_cf_amp_frac"],
        "dt_min_diam_m":         preset["det_dt_min_diam_m"],
        "dt_max_diam_m":         preset["det_dt_max_diam_m"],
        "dt_conf_frac":          preset["det_dt_conf_frac"],
        # Analises fisicas
        "fis_ativo":             preset.get("fis_ativo", True),
        "fis_amp_metal_thr":     preset.get("fis_amp_metal_thr", 0.75),
        "fis_amp_nao_metal_thr": preset.get("fis_amp_nao_metal_thr", 0.40),
    }


def detectar_e_salvar_alvos(arr_detector, arr_sem_agc, arr_raw, arr_cientifico,
                             prof, preset, nome, caminhos, logger,
                             usar_fisica=True, detector_input_mode="raw"):
    """
    v2.0.0 — Detector com entrada configuravel e anotacao sobre radargrama cientifico.

    Parametros:
      arr_detector        : matriz selecionada por detector_input_mode (Hough + CurveFit)
      arr_sem_agc         : matriz sem AGC (amplitude/fase — analise fisica correta)
      arr_raw             : matriz bruta (evidencia independente)
      arr_cientifico      : matriz cientifico (dewow+bp+tpow) — base das imagens anotadas
      detector_input_mode : raw | raw_dewow_bandpass | sem_agc | proc_agc_atual

    Filtros v2.0.0:
      det_min_score_csv  — remove candidatos abaixo do score minimo
      det_depth_min_m    — remove candidatos rasos (airwave superficial)

    Saida visual:
      _anotada_completa.png e _anotada.png desenhados sobre arr_cientifico
      (preserva informacao geofisica na imagem de revisao)
    """
    _metricas_vazio = {"n_alvos_alta": 0, "n_alvos_media": 0, "n_alvos_baixa": 0,
                       "n_fit_ok": 0, "n_evidencia_raw": 0, "n_evidencia_sem_agc": 0,
                       "n_removidos_depth_min": 0}

    if not DETECTOR_DISPONIVEL:
        logger.warning("  Detector indisponivel — verifique detector_hiperboles.py")
        return 0, None, None, None, {}, _metricas_vazio

    params = _params_detector(prof, preset)
    if not usar_fisica:
        params["fis_ativo"] = False

    logger.info(f"  Detector: entrada={detector_input_mode} | shape={arr_detector.shape}")

    # --- Deteccao geometrica ---
    try:
        deteccoes, accum, depths = detectar_hiperboles(
            arr_detector.astype(float), params, top_n=preset["det_top_n"]
        )
    except Exception as e:
        logger.warning(f"  Deteccao falhou: {e}")
        return 0, None, None, None, {}, _metricas_vazio

    if deteccoes is None or deteccoes.empty:
        logger.info("  Deteccao: nenhum alvo encontrado")
        return 0, None, None, None, {}, _metricas_vazio

    # --- Analises fisicas v2.0 (usa arr_sem_agc + arr_raw — nao distorcidos por AGC) ---
    espectro = {}
    try:
        deteccoes, espectro = enriquecer_deteccoes_fisica(
            arr_detector.astype(float), arr_sem_agc, arr_raw, deteccoes, params
        )
        if params.get("fis_ativo", True) and "tipo_material" in deteccoes.columns:
            n_metal   = (deteccoes["tipo_material"] == "possivel_metalico").sum()
            n_nao_met = (deteccoes["tipo_material"] == "possivel_nao_metalico").sum()
            n_galeria = (deteccoes["tipo_material"] == "possivel_galeria_ou_vazio").sum()
            n_inconcl = (deteccoes["tipo_material"] == "inconclusivo").sum()
            severo    = espectro.get("atenuacao_severa", False)
            logger.info(
                f"  Fisica: {n_metal} metalico | {n_nao_met} nao-metalico | "
                f"{n_galeria} galeria | {n_inconcl} inconclusivo | "
                f"atenuacao_solo={'severa' if severo else 'normal'}"
            )
    except Exception as e:
        logger.warning(f"  Analise fisica falhou (continuando): {e}")

    # ── Filtro por score minimo (remove ruido puro do Hough) ──────────────────
    min_score_csv  = preset.get("det_min_score_csv",  30)
    min_score_plot = preset.get("det_min_score_plot", 40)
    if "confidence_score_0_100" in deteccoes.columns:
        n_antes = len(deteccoes)
        deteccoes = deteccoes[
            deteccoes["confidence_score_0_100"] >= min_score_csv
        ].reset_index(drop=True)
        n_removidos_score = n_antes - len(deteccoes)
        if n_removidos_score > 0:
            logger.info(f"  Alvos removidos por min_score={min_score_csv}: {n_removidos_score}")

    # ── Filtro por profundidade minima — elimina airwave superficial (v2.0.0) ──
    depth_min = float(preset.get("det_depth_min_m", 0.30))
    n_removidos_depth = 0
    if "depth_m" in deteccoes.columns and depth_min > 0:
        n_antes_depth = len(deteccoes)
        deteccoes = deteccoes[
            deteccoes["depth_m"] >= depth_min
        ].reset_index(drop=True)
        n_removidos_depth = n_antes_depth - len(deteccoes)
        if n_removidos_depth > 0:
            logger.info(
                f"  Alvos removidos por depth_min={depth_min}m (airwave): {n_removidos_depth}"
            )

    # Registra modo no CSV para rastreabilidade
    deteccoes["detector_input_mode"] = detector_input_mode

    n_alvos = len(deteccoes)

    # --- Metricas de qualidade ---
    col_rel  = "confidence_label_relatorio"
    col_lab  = col_rel if col_rel in deteccoes.columns else "confidence_label"
    n_alta   = int((deteccoes[col_lab] == "alta").sum())  if col_lab in deteccoes.columns else 0
    n_media  = int((deteccoes[col_lab] == "media").sum()) if col_lab in deteccoes.columns else 0
    n_baixa  = int((deteccoes[col_lab] == "baixa").sum()) if col_lab in deteccoes.columns else 0
    n_fit_ok = int(deteccoes["fit_ok"].sum()) if "fit_ok" in deteccoes else 0
    n_ev_raw = int(deteccoes["evidencia_raw"].sum())     if "evidencia_raw"    in deteccoes.columns else 0
    n_ev_sem = int(deteccoes["evidencia_sem_agc"].sum()) if "evidencia_sem_agc" in deteccoes.columns else 0

    logger.info(
        f"  Alvos: {n_alvos} total | "
        f"alta={n_alta} media={n_media} baixa={n_baixa} | "
        f"fit_ok={n_fit_ok} | ev_raw={n_ev_raw} | ev_sem_agc={n_ev_sem}"
    )

    # --- CSV de alvos ---
    deteccoes.insert(0, "arquivo_dzt", nome + ".DZT")
    path_csv = caminhos["alvos"] / f"{nome}_alvos.csv"
    deteccoes.to_csv(str(path_csv), index=False, encoding="utf-8")

    # --- Imagem anotada sobre radargrama CIENTIFICO (v2.0.0) ---
    # arr_cientifico preserva sinal geofisico — Amilson ve marcacoes sobre imagem honesta
    path_completa = caminhos["processadas"] / f"{nome}_anotada_completa.png"
    nome_completa = None
    try:
        plotar_deteccoes(arr_cientifico, deteccoes, params,
                         output_path=str(path_completa),
                         apenas_alta_confianca=False,
                         min_score=min_score_plot)
        nome_completa = path_completa.name
        path_bcompat = caminhos["processadas"] / f"{nome}_anotada.png"
        shutil.copy2(str(path_completa), str(path_bcompat))
    except Exception as e:
        logger.warning(f"  Imagem anotada_completa falhou: {e}")

    # --- Imagem anotada alta confianca ---
    path_alta = caminhos["processadas"] / f"{nome}_anotada_alta_confianca.png"
    nome_alta = None
    try:
        plotar_deteccoes(arr_cientifico, deteccoes, params,
                         output_path=str(path_alta),
                         apenas_alta_confianca=True)
        nome_alta = path_alta.name
    except Exception as e:
        logger.warning(f"  Imagem anotada_alta_confianca falhou: {e}")

    logger.info(
        f"  CSV: {path_csv.name} | "
        f"img_completa: {nome_completa or 'falhou'} | "
        f"img_alta: {nome_alta or 'nenhum'}"
    )
    metricas = {
        "n_alvos_alta":           n_alta,
        "n_alvos_media":          n_media,
        "n_alvos_baixa":          n_baixa,
        "n_fit_ok":               n_fit_ok,
        "n_evidencia_raw":        n_ev_raw,
        "n_evidencia_sem_agc":    n_ev_sem,
        "n_removidos_depth_min":  n_removidos_depth,
    }
    return n_alvos, path_csv.name, nome_completa, nome_alta, espectro, metricas


# ---------------------------------------------------------------------------
# PROCESSAMENTO DE UM DZT V1.1
# ---------------------------------------------------------------------------
def processar_dzt(arquivo_dzt, caminhos, preset, logger,
                  usar_detector=True, usar_fisica=True, config_hash=None,
                  tipo_solo="standard"):
    nome = arquivo_dzt.stem
    t_inicio = datetime.now()
    logger.info(f"Iniciando: {arquivo_dzt.name}")

    try:
        prof = gp.gprpyProfile(str(arquivo_dzt))
    except Exception as e:
        logger.error(f"  Falha ao ler: {e}")
        return None

    # Normaliza profilePos para intervalo [0, span] com direção positiva.
    # Casos tratados:
    #   - Crescente com offset (ex: -4.5→-2.0m): subtrai offset → 0→2.5m
    #   - Decrescente (ex: 4.5→2.0m ou -2.0→-4.5m): subtrai offset + inverte dados + nega posições
    # Necessário porque:
    #   - extent=[0, dist_m, ...] em salvar_imagem_padrao_amilson exige dist_m > 0
    #   - _params_detector usa dist_max como divisor (dx_m, col_search_half)
    #   - prepProfileFig() usa prof.profilePos para o eixo X da imagem bruta
    _pos = np.asarray(prof.profilePos, dtype=float)
    if len(_pos) > 1:
        _offset = float(_pos[0])
        _pos_rel = _pos - _offset          # desloca para iniciar em 0
        _span    = float(_pos_rel[-1])     # positivo se crescente, negativo se decrescente
        if abs(_span) > 1e-6:
            if _span < 0:
                # Perfil decrescente: inverte horizontalmente os dados para manter
                # esquerda→direita = início→fim da linha de campo, e nega posições.
                _pos_rel  = -_pos_rel
                prof.data = np.matrix(np.asarray(prof.data, dtype=np.float64)[:, ::-1])
                logger.debug(
                    f"  profilePos decrescente: dados invertidos + "
                    f"posições normalizadas 0→{abs(_span):.3f}m"
                )
            elif abs(_offset) > 1e-6:
                logger.debug(
                    f"  profilePos normalizado: offset {_offset:.3f}m removido, "
                    f"span={_span:.3f}m"
                )
            prof.profilePos = _pos_rel

    n_amostras, n_tracos = prof.data.shape
    twtt_max = float(prof.twtt[-1])
    dist_max = abs(float(prof.profilePos[-1]) - float(prof.profilePos[0]))
    dt_ns    = twtt_max / (n_amostras - 1)
    fs_mhz   = 1000.0 / dt_ns
    logger.debug(
        f"  shape={prof.data.shape} twtt={twtt_max:.1f}ns "
        f"dist={dist_max:.2f}m fs={fs_mhz:.0f}MHz"
    )

    # ── 1. ARRAY RAW + IMAGEM BRUTA ─────────────────────────────────────────────
    arr_raw = np.asarray(prof.data).astype(np.float32)
    _salvar_npy_seguro(arr_raw, caminhos["dados"] / f"{nome}_raw.npy")
    logger.debug(f"  raw.npy salvo shape={arr_raw.shape}")

    path_bruta = caminhos["brutas"] / f"{nome}_bruta.png"
    try:
        titulo_bruta = (f"{arquivo_dzt.name}  |  Dado Bruto (sem filtros)  |  "
                        f"{datetime.now().strftime('%Y-%m-%d')}")
        salvar_imagem(prof, path_bruta, preset, titulo=titulo_bruta)
        logger.info(f"  01 Bruta: {path_bruta.name}")
    except Exception as e:
        logger.error(f"  Falha bruta: {e}")
        plt.close("all")
        gc.collect()
        return None

    # ── SNR do dado bruto — governador do processamento ──────────────────────
    snr_db, snr_ratio, modo = calcular_snr_imagem_db(arr_raw, tipo_solo)
    logger.info(
        f"  SNR raw: {snr_db:.1f} dB (S/sig={snr_ratio:.1f}) | "
        f"solo={tipo_solo} | modo={modo.upper()}"
    )

    # ── 2. DEWOW + BANDPASS (comum aos fluxos cientifico, relatorio, detector) ─
    if preset.get("dewow_window", 5) > 0:
        prof.dewow(preset["dewow_window"])
        logger.debug(f"  dewow({preset['dewow_window']})")
    else:
        logger.debug("  dewow desativado (dewow_window=0)")

    bandpass_aplicado = f"{preset['bandpass_low_mhz']}-{preset['bandpass_high_mhz']} MHz"
    if modo == "minimo" and preset.get("bandpass_low_mhz", 0) > 0:
        bandpass_aplicado = "pulado"
        logger.info("  Bandpass: pulado (modo minimo — dado ja limpo, evitar artefatos)")
    elif preset.get("bandpass_low_mhz", 0) > 0:
        try:
            aplicar_bandpass(prof, preset["bandpass_low_mhz"],
                             preset["bandpass_high_mhz"], preset["bandpass_order"])
            logger.debug(f"  bandpass {preset['bandpass_low_mhz']}-{preset['bandpass_high_mhz']}MHz")
        except Exception as e:
            logger.warning(f"  Bandpass falhou (continuando): {e}")
    else:
        bandpass_aplicado = "desativado"

    # Captura arr_dewow_bp — ponto de bifurcacao entre fluxos
    # Este array vai para: detector (raw_dewow_bandpass), base do radargrama_cientifico
    arr_dewow_bp = np.asarray(prof.data).astype(np.float32).copy()
    logger.debug(f"  arr_dewow_bp capturado shape={arr_dewow_bp.shape}")

    # ── 3. FLUXO CIENTIFICO — dewow + bp + tpow, SEM bgremoval, SEM AGC ────────
    tpow_base = preset.get("tpow_power", 0.5)
    if tpow_base > 0:
        if modo == "minimo":
            tpow_usado = 0.3
        elif modo == "agressivo":
            tpow_usado = min(tpow_base * 1.5, 1.2)
        else:
            tpow_usado = tpow_base
    else:
        tpow_usado = 0.0

    # Tpow aplicado manualmente sobre copia — nao modifica prof.data
    if tpow_usado > 0:
        arr_cientifico = _aplicar_tpow_manual(arr_dewow_bp, tpow_usado)
    else:
        arr_cientifico = arr_dewow_bp.copy()

    depth_m_oficial = round(float(prof.twtt[-1]) * preset["velocity_mns"] / 2.0, 2)

    # SNR do fluxo cientifico (mede qualidade do sinal preservado)
    snr_db_cient, snr_ratio_cient, _ = calcular_snr_imagem_db(arr_cientifico, tipo_solo)
    delta_snr_cient = round(snr_db_cient - snr_db, 1)
    logger.info(
        f"  SNR cientifico: {snr_db_cient:.1f} dB (delta={delta_snr_cient:+.1f} vs raw)"
    )

    # Salva npy do fluxo cientifico
    _salvar_npy_seguro(arr_cientifico, caminhos["dados"] / f"{nome}_radargrama_cientifico.npy")

    path_cient = caminhos["processadas"] / f"{nome}_radargrama_cientifico.png"
    try:
        salvar_imagem_cientifica(
            arr_cientifico, depth_m_oficial, dist_max, path_cient, preset,
            nome_arquivo=arquivo_dzt.name
        )
        logger.info(f"  02 Radargrama cientifico: {path_cient.name} (max={depth_m_oficial}m)")
    except Exception as e:
        logger.error(f"  Falha radargrama_cientifico: {e}")
        path_cient = None

    # ── 4. FLUXO RELATORIO — adiciona bgremoval + tpow + AGC ao prof.data ────
    if preset.get("bgremoval_traces", 0) > 0:
        prof.remMeanTrace(preset["bgremoval_traces"])
        logger.debug(f"  bgremoval: remMeanTrace({preset['bgremoval_traces']}) [fluxo relatorio]")
    else:
        logger.debug("  bgremoval desativado (bgremoval_traces=0)")

    if tpow_usado > 0:
        prof.tpowGain(power=tpow_usado)
        logger.debug(f"  tpowGain(power={tpow_usado}) [base={tpow_base}, modo={modo}] [fluxo relatorio]")

    # Captura arr_sem_agc — pos bgremoval+tpow, pre AGC
    # Usado para: analise fisica de amplitude/fase (AGC destroi relacoes absolutas)
    arr_sem_agc = np.asarray(prof.data).astype(np.float32)
    _salvar_npy_seguro(arr_sem_agc, caminhos["dados"] / f"{nome}_processado_sem_agc.npy")
    logger.debug(f"  processado_sem_agc.npy salvo shape={arr_sem_agc.shape}")

    # SNR pos bgremoval+tpow — antes AGC (mede impacto do bgremoval no sinal)
    snr_db_rel, snr_ratio_rel, _ = calcular_snr_imagem_db(arr_sem_agc, tipo_solo)
    delta_snr_rel = round(snr_db_rel - snr_db, 1)
    logger.info(
        f"  SNR relatorio (pre-AGC): {snr_db_rel:.1f} dB (delta={delta_snr_rel:+.1f} vs raw)"
    )

    # Imagem de relatorio (padrao visual Amilson) — SEM AGC mas COM bgremoval
    path_proc = caminhos["processadas"] / f"{nome}_radargrama_relatorio.png"
    path_proc_compat = caminhos["processadas"] / f"{nome}_processada.png"
    try:
        salvar_imagem_padrao_amilson(
            arr_sem_agc, depth_m_oficial, dist_max, path_proc, preset,
            nome_arquivo=arquivo_dzt.name, prof=prof
        )
        # Alias backward compat
        shutil.copy2(str(path_proc), str(path_proc_compat))
        logger.info(f"  03 Radargrama relatorio: {path_proc.name} (max={depth_m_oficial}m)")
    except Exception as e:
        logger.error(f"  Falha radargrama_relatorio: {e}")
        plt.close("all")
        gc.collect()
        return None

    # AGC + setVelocity (fluxo relatorio visual + matrizes de compat)
    agc_base = preset.get("agc_window", 150)
    if modo == "minimo":
        agc_janela = min(agc_base * 2, 300)
    elif modo == "agressivo":
        agc_janela = max(agc_base // 2, 50)
    else:
        agc_janela = agc_base
    prof.agcGain(agc_janela)
    logger.debug(f"  agcGain({agc_janela}) [apenas fluxo relatorio — NAO entra no detector]")

    prof.setVelocity(preset["velocity_mns"])
    depth_max = round(float(prof.depth[-1]), 2)
    logger.debug(f"  setVelocity({preset['velocity_mns']}) -> {depth_max}m")

    arr_proc_save = np.asarray(prof.data).astype(np.float32)
    _salvar_npy_seguro(arr_proc_save, caminhos["dados"] / f"{nome}_processado.npy")
    _salvar_npy_seguro(arr_proc_save, caminhos["dados"] / f"{nome}_processado_visual.npy")
    logger.debug(f"  processado.npy + processado_visual.npy (com AGC) salvos [compat]")

    # ── 5. SELECAO DO ARRAY DO DETECTOR (v2.0.0) ─────────────────────────────
    detector_input_mode = preset.get("detector_input_mode", "raw")
    arr_detector_map = {
        "raw":                arr_raw,
        "raw_dewow_bandpass": arr_dewow_bp,
        "sem_agc":            arr_sem_agc,
        "proc_agc_atual":     arr_proc_save,
    }
    arr_detector = arr_detector_map.get(detector_input_mode, arr_raw)
    logger.info(
        f"  Detector: modo={detector_input_mode} | "
        f"depth_min={preset.get('det_depth_min_m', 0.30)}m | "
        f"arr_shape={arr_detector.shape}"
    )

    # ── 6. DETECCAO + IMAGEM ANOTADA SOBRE RADARGRAMA CIENTIFICO ─────────────
    _met0 = {"n_alvos_alta": 0, "n_alvos_media": 0, "n_alvos_baixa": 0,
             "n_fit_ok": 0, "n_evidencia_raw": 0, "n_evidencia_sem_agc": 0,
             "n_removidos_depth_min": 0}
    n_alvos, csv_alvos, png_completa, png_alta, espectro, metricas = 0, None, None, None, {}, _met0
    if usar_detector:
        n_alvos, csv_alvos, png_completa, png_alta, espectro, metricas = detectar_e_salvar_alvos(
            arr_detector, arr_sem_agc, arr_raw, arr_cientifico,
            prof, preset, nome, caminhos, logger,
            usar_fisica=usar_fisica,
            detector_input_mode=detector_input_mode
        )

    # 6. Historico reproduzivel
    path_hist = caminhos["historico"] / f"{nome}_historico.py"
    try:
        prof.writeHistory(str(path_hist))
    except Exception as e:
        logger.warning(f"  Historico nao salvo: {e}")

    t_fim = datetime.now()
    tempo_s = round((t_fim - t_inicio).total_seconds(), 1)
    logger.debug(f"  Tempo total: {tempo_s}s")

    # Libera arrays grandes e figuras matplotlib antes do próximo DZT.
    # Sem isso, acumulação de memória entre iterações causa MemoryError
    # já na 2ª ou 3ª alocação numpy/matplotlib em projetos com múltiplos DZTs.
    plt.close("all")
    del arr_raw, arr_dewow_bp, arr_cientifico, arr_sem_agc, arr_proc_save, prof
    if usar_detector:
        del arr_detector
    gc.collect()

    return {
        # Identificacao
        "arquivo_dzt":             arquivo_dzt.name,
        "n_tracos":                n_tracos,
        "n_amostras":              n_amostras,
        "twtt_max_ns":             round(twtt_max, 2),
        "profundidade_max_m":      depth_max,
        "distancia_max_m":         round(dist_max, 3),
        "fs_mhz":                  round(fs_mhz, 0),
        # Imagens (v2.0.0 — tres fluxos)
        "imagem_bruta":                  path_bruta.name,
        "imagem_radargrama_cientifico":  path_cient.name if path_cient else "",
        "imagem_radargrama_relatorio":   path_proc.name,
        "imagem_processada":             path_proc_compat.name,  # backward compat = _processada.png
        "imagem_anotada":                png_completa or "",      # backward compat
        "imagem_anotada_completa":       png_completa or "",
        "imagem_anotada_alta":           png_alta or "",          # backward compat
        "imagem_anotada_alta_confianca": png_alta or "",
        # Alvos — contagens
        "n_alvos_detectados":      n_alvos,
        "arquivo_alvos":           csv_alvos or "",
        "n_alvos_alta":            metricas["n_alvos_alta"],
        "n_alvos_media":           metricas["n_alvos_media"],
        "n_alvos_baixa":           metricas["n_alvos_baixa"],
        "n_fit_ok":                metricas["n_fit_ok"],
        "n_evidencia_raw":         metricas["n_evidencia_raw"],
        "n_evidencia_sem_agc":     metricas["n_evidencia_sem_agc"],
        # Arrays numpy (v2.0.0)
        "array_raw_npy":             f"{nome}_raw.npy",
        "array_cientifico_npy":      f"{nome}_radargrama_cientifico.npy",
        "array_proc_npy":            f"{nome}_processado.npy",        # backward compat
        "array_sem_agc_npy":         f"{nome}_processado_sem_agc.npy",
        "array_visual_npy":          f"{nome}_processado_visual.npy",
        # Espectro do solo
        "solo_freq_camadas_mhz":   str(espectro.get("freq_camadas_mhz", [])),
        "solo_atenuacao_severa":   espectro.get("atenuacao_severa", ""),
        "solo_prof_confiavel_frac":espectro.get("prof_confiavel_frac", ""),
        # Configuracao de processamento
        "preset_usado":            preset["descricao"],
        "dewow_window":            preset["dewow_window"],
        "bandpass_mhz":            bandpass_aplicado,
        "bgremoval_traces":        preset["bgremoval_traces"],
        "tpow_power":              tpow_usado,
        "agc_window":              agc_janela,
        # SNR medido em 3 pontos do pipeline (v2.0.0)
        "snr_imagem_db":           snr_db,          # SNR raw — backward compat (v1.2.0)
        "snr_imagem_ratio":        snr_ratio,        # SNR raw ratio — backward compat
        "snr_raw_db":              snr_db,           # SNR raw (alias explicito)
        "snr_raw_ratio":           snr_ratio,
        "snr_cientifico_db":       snr_db_cient,    # SNR apos dewow+bp+tpow
        "snr_cientifico_ratio":    snr_ratio_cient,
        "snr_relatorio_db":        snr_db_rel,       # SNR apos bgremoval+tpow (pre-AGC)
        "snr_relatorio_ratio":     snr_ratio_rel,
        "modo_processamento":      modo,
        "tipo_solo":               tipo_solo,
        # Detector v2.0.0
        "detector_input_mode":     detector_input_mode,
        "n_removidos_depth_min":   metricas.get("n_removidos_depth_min", 0),
        # Velocidade e calibracao
        "velocity_mns":            preset["velocity_mns"],
        "velocity_calibrada":      False,
        "metodo_calibracao":       "default",
        "observacao_calibracao":   "[CALIBRAR] Confirmar com Amilson usando alvo de posicao/profundidade conhecidas",
        "config_hash":             config_hash or "",
        # Metadata
        "status":                  "processado",
        "tempo_processamento_s":   tempo_s,
        "timestamp":               datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=f"Pipeline v{SCRIPT_VERSION} - ScanSOLO GPR")
    parser.add_argument("--input",        default=None)
    parser.add_argument("--output",       default=None)
    parser.add_argument("--preset",       default="270mhz", choices=list(PRESETS.keys()))
    parser.add_argument("--sem-detector", action="store_true",
                        help="Pula deteccao de alvos (so processamento de imagens + .npy)")
    parser.add_argument("--sem-fisica",   action="store_true",
                        help="Pula analises fisicas (material/espectro) mas mantem deteccao geometrica")
    parser.add_argument("--sem-ia-imagem", action="store_true",
                        help="Pula etapa de melhoria por IA de imagem (gpt-image-1)")
    parser.add_argument("--sem-migracao",  action="store_true",
                        help="Pula migracao F-K Kirchhoff")
    parser.add_argument("--filter-config", default=None, metavar="JSON_PATH",
                        help="JSON com chaves que sobrescrevem o preset selecionado")
    parser.add_argument(
        "--solo",
        default="standard",
        choices=list(SNR_LIMIARES.keys()),
        help="Tipo de solo: standard | arenoso | argiloso | umido | pedregoso",
    )
    parser.add_argument(
        "--detector-input",
        default=None,
        choices=["raw", "raw_dewow_bandpass", "sem_agc", "proc_agc_atual"],
        dest="detector_input",
        help="Matriz de entrada do detector (default: raw, melhor CurveFit 82%%)",
    )
    args = parser.parse_args()

    script_dir    = Path(__file__).resolve().parent
    pasta_entrada = Path(args.input)  if args.input  else script_dir.parent / "Exemplos_dados_bruos_georadar"
    pasta_saida   = Path(args.output) if args.output else script_dir / "exemplo_saida"
    preset        = dict(PRESETS[args.preset])  # copia mutavel
    usar_detector = not args.sem_detector
    usar_fisica   = not args.sem_fisica
    tipo_solo     = args.solo

    # CLI override de detector_input_mode (tem precedencia sobre preset e filter-config)
    if args.detector_input:
        preset["detector_input_mode"] = args.detector_input

    # Sobrescrever preset com config customizada (reprocessamento por perfil)
    if args.filter_config:
        try:
            with open(args.filter_config, encoding="utf-8") as _fh:
                _overrides = json.load(_fh)
            preset.update(_overrides)
            logger_root = logging.getLogger()
            logger_root.info(f"filter-config aplicado: {_overrides}")
        except Exception as _e:
            logging.getLogger().warning(f"filter-config ignorado ({_e})")

    caminhos = criar_estrutura(pasta_saida)
    logger   = configurar_log(caminhos["logs"])

    # Config hash para rastreabilidade
    config_str  = json.dumps(preset, sort_keys=True, default=str)
    config_hash = hashlib.md5(config_str.encode()).hexdigest()[:8]

    logger.info("=" * 65)
    logger.info(f"Pipeline v{SCRIPT_VERSION} - ScanSOLO GPR")
    logger.info(f"Entrada      : {pasta_entrada}")
    logger.info(f"Saida        : {pasta_saida}")
    logger.info(f"Preset       : {preset['descricao']}")
    logger.info(f"Config hash  : {config_hash}")
    logger.info(f"Solo         : {tipo_solo}")
    logger.info(f"Detector     : {'ativo (Hough + CurveFit + DeltaT)' if usar_detector and DETECTOR_DISPONIVEL else 'desativado'}")
    logger.info(f"Fisica       : {'ativa (sem AGC — amplitude/fase/SNR/score)' if usar_fisica and usar_detector else 'desativada'}")
    logger.info(f"Matrizes V1.2: raw.npy | sem_agc.npy | visual.npy | processado.npy (compat)")
    logger.info("=" * 65)

    # Salva config_used.json
    try:
        path_cfg = salvar_config_json(pasta_saida, preset, args.preset, config_hash)
        logger.info(f"config_used.json: {path_cfg.name}")
    except Exception as e:
        logger.warning(f"config_used.json nao salvo: {e}")

    # Deduplicação por nome resolvido — no Windows glob("*.DZT") e glob("*.dzt")
    # batem nos mesmos arquivos (filesystem case-insensitive), duplicando o index.
    _seen: set[str] = set()
    dzts: list[Path] = []
    for _p in sorted(pasta_entrada.glob("*.DZT")) + sorted(pasta_entrada.glob("*.dzt")):
        if _p.resolve().name not in _seen:
            _seen.add(_p.resolve().name)
            dzts.append(_p)
    if not dzts:
        logger.error(f"Nenhum .DZT em: {pasta_entrada}")
        sys.exit(1)
    logger.info(f"{len(dzts)} arquivo(s) .DZT encontrado(s)")

    registros, erros = [], 0
    for dzt in dzts:
        resultado = processar_dzt(dzt, caminhos, preset, logger, usar_detector, usar_fisica,
                                  config_hash=config_hash, tipo_solo=tipo_solo)
        if resultado:
            registros.append(resultado)
        else:
            erros += 1
            registros.append({
                "arquivo_dzt": dzt.name, "status": "erro",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    pd.DataFrame(registros).to_csv(
        pasta_saida / "index_projeto.csv", index=False, encoding="utf-8"
    )

    total_alvos = sum(r.get("n_alvos_detectados", 0) for r in registros
                      if isinstance(r.get("n_alvos_detectados"), int))

    logger.info("index_projeto.csv salvo")
    logger.info("=" * 65)
    logger.info(f"Concluido    : {len(registros)-erros} ok  |  {erros} erro(s)  |  {total_alvos} alvo(s)")
    logger.info(f"Saida        : {pasta_saida}")
    logger.info(f"V1.2 outputs : *_processado_sem_agc.npy | *_processado_visual.npy")
    logger.info(f"               *_anotada_completa.png | *_anotada_alta_confianca.png")
    logger.info(f"               config_used.json | confidence_score_0_100 no CSV")
    logger.info(f"               snr_imagem_db | modo_processamento no index_projeto.csv")
    logger.info("=" * 65)
    if erros:
        sys.exit(1)


if __name__ == "__main__":
    main()
