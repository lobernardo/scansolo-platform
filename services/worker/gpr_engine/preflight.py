"""
preflight.py — Leitura de metadados DZT e recomendação de configuração.

Segue o fluxo do readgssi: primeiro ler o DZT e seus metadados reais,
depois recomendar configuração, e só então processar.

Funcoes publicas:
  extract_dzt_metadata(dzt_path) -> dict
    Le o DZT via DZTReader e retorna metadados relevantes para
    orientar a escolha de preset e configuracao de processamento.

  recommend_processing_config(metadata, selected_preset, project_config) -> dict
    Recebe os metadados extraidos e o preset/config escolhido pelo usuario
    e retorna recomendacoes fundamentadas nos dados reais do DZT.

Regras de recomendacao:
  - Mismatch de frequencia: |detected - preset| > 30 MHz -> frequency_mismatch=True
  - Velocity do header valida (0.04–0.20 m/ns) -> recomendar header velocity
  - velocity fora desse range -> manter 0.10 m/ns (standard)
  - visual_profile recomendado: sempre "readgssi_reference" para readgssi_engine
  - depth_preview_m: 5.0 apenas como escala visual (nao profundidade fisica)
  - engine recomendado: sempre "readgssi_engine"

Nao altera nenhum arquivo de producao (pipeline_v1.py, job_gpr.py,
scansolo_adapter.py, pipeline.py, frontend, migrations, Dockerfile).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from gpr_engine.reader import DZTReader

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_VELOCITY_STANDARD_MNS: float = 0.10
_VELOCITY_VALID_MIN:   float  = 0.04
_VELOCITY_VALID_MAX:   float  = 0.20
_FREQ_MISMATCH_THR:    int    = 30    # MHz
_DEPTH_PREVIEW_M:      float  = 5.0

# Familias de preset mapeadas por faixa de frequencia (MHz)
_FREQ_FAMILIES: list[tuple[int, int, str]] = [
    (10,  220, "100mhz"),
    (220, 320, "270mhz"),
    (320, 450, "400mhz"),
    (450, 600, "500mhz"),
    (600, 900, "800mhz"),
    (900, 2500, "1ghz"),
]


# ---------------------------------------------------------------------------
# Funcao principal de extracao
# ---------------------------------------------------------------------------

def extract_dzt_metadata(dzt_path: str | Path) -> dict:
    """
    Le um arquivo DZT via DZTReader e extrai metadados relevantes.

    Retorna um dict com campos de identificacao, geometria do levantamento,
    parametros fisicos e lista de warnings sobre qualidade do header.

    Campos retornados:
      dzt_filename, dzt_sha256,
      antenna_freq_mhz_detected, velocity_header_mns, epsr_header,
      twtt_max_ns, timezero_sample, n_traces, n_samples,
      dist_total_m, samp_freq_hz, dt_ns, rhf_spm, rhf_sps, modo_coleta,
      depth_real_m_from_header_velocity,
      depth_real_m_from_standard_velocity,
      header_confidence,  -- "alta" | "media" | "baixa"
      warnings            -- lista de strings com avisos de qualidade

    :param dzt_path: Caminho para o arquivo .DZT.
    :returns:        Dict com metadados + header_confidence + warnings.
    :raises FileNotFoundError: Se o arquivo nao existir.
    """
    dzt_path = Path(dzt_path)

    if not dzt_path.exists():
        raise FileNotFoundError(f"DZT nao encontrado: {dzt_path}")

    reader  = DZTReader(verbose=False)
    dzt     = reader.read(dzt_path)
    warnings: list[str] = []

    # ── Warnings de qualidade do header ─────────────────────────────────────

    if dzt.antfreq_mhz == 0:
        warnings.append(
            "Frequencia da antena nao detectada no header DZT. "
            "Verificar campo 'antfreq' no arquivo."
        )

    if dzt.timezero_sample >= dzt.n_samples:
        warnings.append(
            f"timezero_sample={dzt.timezero_sample} >= n_samples={dzt.n_samples}: "
            "valor do header provavelmente de configuracao de hardware diferente. "
            "readgssi usa rh_zero como fallback — offset de profundidade pode ocorrer."
        )

    vel = dzt.wave_speed_mns
    if vel <= 0.03 or vel > 0.35:
        warnings.append(
            f"velocity_header_mns={vel:.6f} fora do range esperado (0.03–0.35 m/ns). "
            "Verificar constante dieletrica (rhf_epsr) no header."
        )

    if dzt.dist_total_m <= 0:
        warnings.append(
            "Distancia horizontal calculada e zero. "
            "rhf_spm nao configurado — distancia estimada por velocidade de operador."
        )

    if dzt.modo_coleta == "tempo":
        warnings.append(
            "Coleta por TEMPO (rhf_spm=0): distancia estimada com velocidade de operador "
            "1.2 m/s. Posicoes horizontais sao aproximadas."
        )

    # ── Profundidade em dois cenarios ────────────────────────────────────────

    depth_from_header_v = round(dzt.twtt_max_ns * dzt.wave_speed_mns / 2.0, 4)
    depth_from_std_v    = round(dzt.twtt_max_ns * _VELOCITY_STANDARD_MNS / 2.0, 4)

    # ── Confianca do header ──────────────────────────────────────────────────
    #
    # Contamos issues por gravidade:
    #   antfreq desconhecido (+2) — impossivel recomendar preset correto
    #   velocity invalida (+2)    — profundidade calculada incorreta
    #   timezero fora do array (+1) — offset de profundidade provavel
    #   dist zero (+1)           — posicoes horizontais incorretas
    #
    # alta:  0 issues
    # media: 1 issue (geralmente apenas timezero fora do range)
    # baixa: >= 2 issues

    issues = 0
    if dzt.antfreq_mhz == 0:
        issues += 2
    if dzt.timezero_sample >= dzt.n_samples:
        issues += 1
    if vel <= 0.03 or vel > 0.35:
        issues += 2
    if dzt.dist_total_m <= 0:
        issues += 1

    header_confidence: str
    if issues == 0:
        header_confidence = "alta"
    elif issues == 1:
        header_confidence = "media"
    else:
        header_confidence = "baixa"

    return {
        # -- Identidade -------------------------------------------------------
        "dzt_filename":  dzt.dzt_filename,
        "dzt_sha256":    dzt.dzt_sha256,
        # -- Antena e velocidade ----------------------------------------------
        "antenna_freq_mhz_detected":          dzt.antfreq_mhz,
        "velocity_header_mns":                round(dzt.wave_speed_mns, 6),
        "epsr_header":                        round(dzt.rhf_epsr, 4),
        # -- Eixo de tempo ----------------------------------------------------
        "twtt_max_ns":                        round(dzt.twtt_max_ns, 4),
        "timezero_sample":                    dzt.timezero_sample,
        "n_traces":                           dzt.n_traces,
        "n_samples":                          dzt.n_samples,
        "dt_ns":                              round(dzt.dt_ns, 6),
        "samp_freq_hz":                       int(dzt.samp_freq_hz),
        # -- Eixo de espaco ---------------------------------------------------
        "dist_total_m":                       round(dzt.dist_total_m, 4),
        "rhf_spm":                            round(dzt.rhf_spm, 4),
        "rhf_sps":                            round(dzt.rhf_sps, 4),
        "modo_coleta":                        dzt.modo_coleta,
        # -- Profundidade em dois cenarios ------------------------------------
        "depth_real_m_from_header_velocity":  depth_from_header_v,
        "depth_real_m_from_standard_velocity": depth_from_std_v,
        # -- Qualidade --------------------------------------------------------
        "header_confidence": header_confidence,
        "warnings":          warnings,
    }


# ---------------------------------------------------------------------------
# Funcao de recomendacao
# ---------------------------------------------------------------------------

def recommend_processing_config(
    metadata: dict,
    selected_preset: dict | None = None,
    project_config: dict | None = None,
) -> dict:
    """
    Gera recomendacoes de configuracao de processamento com base nos metadados
    extraidos do DZT e no preset/config escolhidos pelo usuario na UI.

    Regras:
      - frequency_mismatch = True se |detected - preset_freq| > 30 MHz
      - recommended_velocity_mns: usa header se 0.04–0.20 m/ns; senao 0.10
      - recommended_engine: sempre "readgssi_engine"
      - recommended_visual_profile: sempre "readgssi_reference"
      - recommended_depth_preview_m: sempre 5.0 (escala visual, nao fisica)

    :param metadata:        Dict retornado por extract_dzt_metadata().
    :param selected_preset: Dict do preset escolhido na UI (campos: name,
                            antenna_freq_mhz, parameters). Pode ser None.
    :param project_config:  Dict de overrides do projeto (processing_config).
                            Pode ser None.
    :returns:               Dict com recomendacoes e lista de warnings.
    """
    warnings: list[str] = []
    selected_preset = selected_preset or {}
    project_config  = project_config or {}

    detected_freq: int  = int(metadata.get("antenna_freq_mhz_detected") or 0)
    velocity_hdr:  float = float(metadata.get("velocity_header_mns") or 0.0)

    # ── Frequencia do preset selecionado ─────────────────────────────────────
    # Suporta dois formatos:
    #   1. selected_preset["antenna_freq_mhz"]   (campo direto)
    #   2. selected_preset["parameters"]["antfreq"] (preset do banco)
    preset_freq: int = 0
    if "antenna_freq_mhz" in selected_preset:
        preset_freq = int(selected_preset["antenna_freq_mhz"] or 0)
    elif "parameters" in selected_preset:
        # fallback: campo antfreq dentro de parameters (nao existe ainda, mas seguro)
        preset_freq = int(
            (selected_preset["parameters"] or {}).get("antenna_freq_mhz", 0)
        )

    # ── Mismatch de frequencia ────────────────────────────────────────────────
    frequency_mismatch = False
    if detected_freq > 0 and preset_freq > 0:
        diff = abs(detected_freq - preset_freq)
        if diff > _FREQ_MISMATCH_THR:
            frequency_mismatch = True
            warnings.append(
                f"Frequencia detectada ({detected_freq} MHz) difere do preset "
                f"selecionado ({preset_freq} MHz) em {diff} MHz "
                f"(limite: {_FREQ_MISMATCH_THR} MHz). "
                f"Recomendado: usar preset da familia {detected_freq} MHz ou criar um novo."
            )
    elif detected_freq > 0 and preset_freq == 0:
        warnings.append(
            f"Preset nao especificado. Frequencia detectada no DZT: {detected_freq} MHz. "
            "Selecione ou crie um preset adequado antes de processar."
        )
    elif detected_freq == 0:
        warnings.append(
            "Frequencia da antena nao detectada no header DZT — impossivel verificar "
            "compatibilidade com o preset selecionado."
        )

    # ── Velocity recomendada ─────────────────────────────────────────────────
    vel_from_header = _VELOCITY_VALID_MIN <= velocity_hdr <= _VELOCITY_VALID_MAX
    if vel_from_header:
        recommended_velocity = velocity_hdr
    else:
        recommended_velocity = _VELOCITY_STANDARD_MNS
        if velocity_hdr > 0 and not vel_from_header:
            warnings.append(
                f"velocity_header_mns={velocity_hdr:.4f} fora do range util "
                f"({_VELOCITY_VALID_MIN}–{_VELOCITY_VALID_MAX} m/ns). "
                f"Usando velocity padrao {_VELOCITY_STANDARD_MNS} m/ns."
            )

    # ── Familia de preset recomendada ─────────────────────────────────────────
    recommended_preset_family: str | None = None
    if detected_freq > 0:
        for lo, hi, family in _FREQ_FAMILIES:
            if lo <= detected_freq < hi:
                recommended_preset_family = family
                break
        if recommended_preset_family is None:
            warnings.append(
                f"Frequencia {detected_freq} MHz fora das familias de preset conhecidas "
                f"({[f for _, _, f in _FREQ_FAMILIES]}). Criar preset personalizado."
            )
        elif frequency_mismatch and preset_freq > 0:
            warnings.append(
                f"Familia recomendada: '{recommended_preset_family}' "
                f"(baseado em {detected_freq} MHz)."
            )

    # ── Depth preview vs depth real ───────────────────────────────────────────
    depth_real = float(metadata.get("depth_real_m_from_header_velocity") or 0.0)
    if 0 < depth_real < _DEPTH_PREVIEW_M:
        warnings.append(
            f"depth_real_fisica={depth_real:.2f} m < depth_preview={_DEPTH_PREVIEW_M} m. "
            "O preview visual de 5 m usa escala de display (stretch/zeropad), "
            "nao profundidade fisica real."
        )

    # ── Timezero out of range (repassa do metadata) ───────────────────────────
    for w in metadata.get("warnings", []):
        if "timezero" in w.lower():
            warnings.append(
                "timezero fora do range de amostras: offset de profundidade possivel. "
                "Verificar time-zero no software de aquisicao (RADAN/SIR)."
            )
            break

    return {
        # -- Mismatch de frequencia -------------------------------------------
        "frequency_mismatch":          frequency_mismatch,
        "selected_preset_freq_mhz":    preset_freq,
        "detected_freq_mhz":           detected_freq,
        "recommended_antenna_freq_mhz": detected_freq if detected_freq > 0 else preset_freq,
        "recommended_preset_family":   recommended_preset_family,
        # -- Velocity ---------------------------------------------------------
        "recommended_velocity_mns":    round(recommended_velocity, 6),
        "velocity_from_header":        vel_from_header,
        # -- Engine e perfil visual -------------------------------------------
        "recommended_engine":          "readgssi_engine",
        "recommended_visual_profile":  "readgssi_reference",
        "recommended_depth_preview_m": _DEPTH_PREVIEW_M,
        # -- Qualidade --------------------------------------------------------
        "header_confidence":           metadata.get("header_confidence", "baixa"),
        "warnings":                    warnings,
    }
