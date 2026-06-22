"""
_test_phase8_10.py -- Rastreabilidade e Pipeline Log do readgssi_engine.

Objetivo (Fase 8.10):
  Garantir que pipeline_metrics.json inclui campos claros para o readgssi_engine:
  - visual_profile, renderer, normalization, background_removal, bgr_window, gain
  - skip_ia, detector_status
  - dewow_window, bandpass_*, bgremoval_traces, tpow_power, agc_window (nivel raiz)
  - velocity_mns, depth_tecnica_m, preview_*

  Comparativo controlado HELPER_0004.DZT:
  - Run A: visual_profile="readgssi_reference" -> normalization=SymLogNorm
  - Run B: sem visual_profile (default)       -> normalization=linear_percentile99
  - Compara: tamanhos de PNG, campos normalization/renderer, skip_ia, SNR

Grupos:
  G1: _bandpass_descricao retorna "desativado" quando bandpass_low_mhz=0
  G2: _bandpass_descricao retorna "80-500 MHz" quando habilitado
  G3: _render_profile_fields para visual_profile="readgssi_reference"
  G4: _render_profile_fields para visual_profile="scientific" (default)
  G5: build_pipeline_metrics inclui visual_profile e normalization no nivel raiz
  G6: build_pipeline_metrics inclui detector_status e skip_ia
  G7: build_pipeline_metrics promove dewow/bandpass/bgr/tpow/agc ao nivel raiz
  G8: Comparativo HELPER_0004.DZT (readgssi_ref vs padrao) -- requer DZT
  G9: Nenhum campo obrigatorio legado foi removido

Uso:
  cd services/worker
  python -m gpr_engine._test_phase8_10
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

_HERE = Path(__file__).resolve().parent
_WORKER = _HERE.parent
_REPO_ROOT = _HERE.parents[2]

sys.path.insert(0, str(_WORKER))

_DZT4 = (
    _REPO_ROOT
    / "KB_ScansoloPlataform"
    / "benchmark_real"
    / "HELPER"
    / "HELPER.PRJ_DZT"
    / "HELPER_0004.DZT"
)

_PASS = 0
_FAIL = 0
_WARN = 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(g: str, msg: str) -> None:
    global _PASS; _PASS += 1
    print(f"  [OK]   {g}: {msg}")

def _fail(g: str, msg: str) -> None:
    global _FAIL; _FAIL += 1
    print(f"  [FAIL] {g}: {msg}")

def _warn(g: str, msg: str) -> None:
    global _WARN; _WARN += 1
    print(f"  [WARN] {g}: {msg}")

def _sep(g: str, titulo: str) -> None:
    print(f"\n-- {g}: {titulo}")

# Campos obrigatorios do JSON que sempre devem existir (legados e novos)
_CAMPOS_OBRIGATORIOS = [
    "dzt_filename", "dzt_sha256", "engine_name", "engine_version", "pipeline_version",
    "modo_processamento", "tipo_solo", "preset_name", "detector_input_mode",
    "det_depth_min_m_usado", "filtros_customizados",
    "n_tracos", "dist_total_m", "profundidade_max_m",
    "snr_raw_db", "snr_raw_ratio", "snr_stages_db",
    "imagem_bruta_ok", "imagem_relatorio_ok", "imagem_anotada_ok",
    "outputs",
    # Novos fase 8.10 — nivel raiz
    "visual_profile", "renderer", "normalization", "background_removal", "bgr_window",
    "gain", "skip_ia", "detector_status",
    # Filtros promovidos ao nivel raiz
    "dewow_window", "bandpass_aplicado", "bandpass_low_mhz_usado",
    "bgremoval_traces", "tpow_power", "agc_window",
    "velocity_mns", "velocity_fonte", "depth_tecnica_m",
]

# ---------------------------------------------------------------------------
# Fixtures minimas para build_pipeline_metrics
# ---------------------------------------------------------------------------

def _make_dzt_data(n_traces: int = 129, twtt_ns: float = 34.1) -> MagicMock:
    d = MagicMock()
    d.dzt_filename = "MOCK.dzt"
    d.dzt_sha256 = "abc123"
    d.n_traces = n_traces
    d.n_samples = 171
    d.dist_total_m = 8.82
    d.twtt_max_ns = twtt_ns
    d.wave_speed_mns = 0.10
    return d

def _base_config(**overrides) -> dict:
    cfg = {
        "dewow_window": 5,
        "bandpass_low_mhz": 80.0,
        "bandpass_high_mhz": 500.0,
        "bandpass_order": 5,
        "bandpass_tipo": "butterworth",
        "bandpass_enabled": True,
        "bgremoval_traces": 30,
        "tpow_power": 0.5,
        "agc_window": 150,
        "agc_window_preview": 80,
        "velocity_mns": 0.10,
        "depth_preview_m": 5.0,
        "detector_input_mode": "raw",
        "det_depth_min_m": 0.30,
        "visual_profile": "scientific",
        "gain": 1.0,
    }
    cfg.update(overrides)
    return cfg


# ============================================================
# G1 -- _bandpass_descricao: bandpass desativado
# ============================================================

def test_g1_bandpass_desativado() -> None:
    _sep("G1", "_bandpass_descricao retorna 'desativado' quando bandpass_low_mhz=0")
    from gpr_engine.metrics import _bandpass_descricao

    descr, low, high = _bandpass_descricao({"bandpass_low_mhz": 0, "bandpass_high_mhz": 500})
    if descr == "desativado" and low == 0.0 and high == 0.0:
        _ok("G1", "bandpass_low_mhz=0 -> 'desativado', low=0, high=0")
    else:
        _fail("G1", f"Inesperado: descr={descr!r} low={low} high={high}")

    descr2, _, _ = _bandpass_descricao({"bandpass_enabled": False, "bandpass_low_mhz": 80.0})
    if descr2 == "desativado":
        _ok("G1", "bandpass_enabled=False -> 'desativado'")
    else:
        _fail("G1", f"bandpass_enabled=False deveria retornar 'desativado', got {descr2!r}")


# ============================================================
# G2 -- _bandpass_descricao: bandpass habilitado
# ============================================================

def test_g2_bandpass_habilitado() -> None:
    _sep("G2", "_bandpass_descricao retorna faixa quando habilitado")
    from gpr_engine.metrics import _bandpass_descricao

    descr, low, high = _bandpass_descricao({"bandpass_low_mhz": 80.0, "bandpass_high_mhz": 500.0})
    if descr == "80-500 MHz" and low == 80.0 and high == 500.0:
        _ok("G2", f"Faixa correta: {descr!r}, low={low}, high={high}")
    else:
        _fail("G2", f"Inesperado: descr={descr!r} low={low} high={high}")

    # faixa custom
    descr3, low3, high3 = _bandpass_descricao({"bandpass_low_mhz": 100.0, "bandpass_high_mhz": 400.0})
    if descr3 == "100-400 MHz":
        _ok("G2", f"Faixa custom: {descr3!r}")
    else:
        _fail("G2", f"Faixa custom incorreta: {descr3!r}")


# ============================================================
# G3 -- _render_profile_fields: readgssi_reference
# ============================================================

def test_g3_render_profile_readgssi() -> None:
    _sep("G3", "_render_profile_fields para visual_profile='readgssi_reference'")
    from gpr_engine.metrics import _render_profile_fields

    cfg = _base_config(visual_profile="readgssi_reference", gain=2.5)
    fields = _render_profile_fields(cfg)

    checks = [
        ("visual_profile", "readgssi_reference"),
        ("renderer",       "readgssi_reference"),
        ("normalization",  "SymLogNorm"),
        ("background_removal", "readgssi_bgr"),
        ("bgr_window",    0),
        ("gain",          2.5),
    ]
    for key, expected in checks:
        val = fields.get(key)
        if val == expected:
            _ok("G3", f"{key}={val!r}")
        else:
            _fail("G3", f"{key}: esperado {expected!r}, got {val!r}")


# ============================================================
# G4 -- _render_profile_fields: default (scientific)
# ============================================================

def test_g4_render_profile_default() -> None:
    _sep("G4", "_render_profile_fields para visual_profile='scientific' (default)")
    from gpr_engine.metrics import _render_profile_fields

    cfg = _base_config()  # visual_profile="scientific"
    fields = _render_profile_fields(cfg)

    checks = [
        ("visual_profile",    "scientific"),
        ("renderer",          "relatorio"),
        ("normalization",     "linear_percentile99"),
        ("background_removal","bgremoval_windowed"),
        ("gain",              1.0),
    ]
    for key, expected in checks:
        val = fields.get(key)
        if val == expected:
            _ok("G4", f"{key}={val!r}")
        else:
            _fail("G4", f"{key}: esperado {expected!r}, got {val!r}")

    # bgr_window deve ser bgremoval_traces do config
    bgr_window = fields.get("bgr_window")
    if bgr_window == 30:
        _ok("G4", f"bgr_window={bgr_window} (= bgremoval_traces)")
    else:
        _fail("G4", f"bgr_window: esperado 30, got {bgr_window!r}")


# ============================================================
# G5 -- build_pipeline_metrics: visual_profile e normalization no nivel raiz
# ============================================================

def test_g5_metrics_visual_profile() -> None:
    _sep("G5", "build_pipeline_metrics inclui visual_profile e normalization no nivel raiz")
    from gpr_engine.metrics import build_pipeline_metrics

    dzt = _make_dzt_data()

    # Modo readgssi_reference
    m_ref = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=_base_config(visual_profile="readgssi_reference"),
        modo_processamento="agressivo",
        snr_raw_db=10.7,
        snr_raw_ratio=3.2,
    )
    for key, expected in [
        ("visual_profile", "readgssi_reference"),
        ("normalization",  "SymLogNorm"),
        ("renderer",       "readgssi_reference"),
    ]:
        val = m_ref.get(key)
        if val == expected:
            _ok("G5", f"readgssi_ref: {key}={val!r}")
        else:
            _fail("G5", f"readgssi_ref: {key} esperado {expected!r}, got {val!r}")

    # Modo default
    m_def = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=_base_config(),  # visual_profile="scientific"
        modo_processamento="padrao",
        snr_raw_db=10.7,
        snr_raw_ratio=3.2,
    )
    for key, expected in [
        ("visual_profile", "scientific"),
        ("normalization",  "linear_percentile99"),
        ("renderer",       "relatorio"),
    ]:
        val = m_def.get(key)
        if val == expected:
            _ok("G5", f"default: {key}={val!r}")
        else:
            _fail("G5", f"default: {key} esperado {expected!r}, got {val!r}")


# ============================================================
# G6 -- build_pipeline_metrics: detector_status e skip_ia
# ============================================================

def test_g6_detector_skip_ia() -> None:
    _sep("G6", "build_pipeline_metrics inclui detector_status e skip_ia")
    from gpr_engine.metrics import build_pipeline_metrics

    dzt = _make_dzt_data()

    m = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=_base_config(skip_ia=True),
        modo_processamento="agressivo",
        snr_raw_db=10.7,
        snr_raw_ratio=3.2,
    )
    if m.get("detector_status") == "skipped_not_integrated":
        _ok("G6", "detector_status='skipped_not_integrated'")
    else:
        _fail("G6", f"detector_status: got {m.get('detector_status')!r}")

    if m.get("skip_ia") is True:
        _ok("G6", "skip_ia=True")
    else:
        _fail("G6", f"skip_ia: esperado True, got {m.get('skip_ia')!r}")

    # skip_ia=False quando nao configurado
    m2 = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=_base_config(),  # sem skip_ia
        modo_processamento="padrao",
        snr_raw_db=10.7,
        snr_raw_ratio=3.2,
    )
    if m2.get("skip_ia") is False:
        _ok("G6", "skip_ia=False quando ausente no config")
    else:
        _fail("G6", f"skip_ia deveria ser False, got {m2.get('skip_ia')!r}")


# ============================================================
# G7 -- build_pipeline_metrics: filtros no nivel raiz
# ============================================================

def test_g7_filtros_nivel_raiz() -> None:
    _sep("G7", "build_pipeline_metrics promove filtros ao nivel raiz (sem n/d no PipelineLog)")
    from gpr_engine.metrics import build_pipeline_metrics

    cfg = _base_config(
        dewow_window=7,
        bgremoval_traces=40,
        tpow_power=0.8,
        agc_window=120,
        agc_window_preview=90,
        velocity_mns=0.13,
        depth_preview_m=3.5,
    )
    dzt = _make_dzt_data()
    m = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=cfg,
        modo_processamento="padrao",
        snr_raw_db=15.0,
        snr_raw_ratio=4.5,
    )

    checks = [
        ("dewow_window",        7),
        ("bgremoval_traces",    40),
        ("tpow_power",          0.8),
        ("agc_window",          120),
        ("agc_window_preview",  90),
        ("velocity_mns",        0.13),
        ("velocity_fonte",      "config"),
        ("bandpass_aplicado",   "80-500 MHz"),
        ("bandpass_low_mhz_usado",  80.0),
        ("bandpass_high_mhz_usado", 500.0),
        ("bandpass_order_usado",    5),
        ("bandpass_tipo_usado",     "butterworth"),
        ("depth_preview_m",         3.5),
        ("preview_visual_depth_configurado", True),  # 3.5 != 5.0 default
        ("preview_velocity_mns",    0.13),
    ]
    for key, expected in checks:
        val = m.get(key)
        if val == expected:
            _ok("G7", f"{key}={val!r}")
        else:
            _fail("G7", f"{key}: esperado {expected!r}, got {val!r}")

    # depth_tecnica_m deve ser n_tracos * twtt * velocity / 2
    dtm = m.get("depth_tecnica_m")
    prof = m.get("profundidade_max_m")
    if dtm is not None and abs(dtm - prof) < 1e-9:
        _ok("G7", f"depth_tecnica_m={dtm} == profundidade_max_m={prof}")
    else:
        _fail("G7", f"depth_tecnica_m={dtm} != profundidade_max_m={prof}")

    # preview_depth_real_m deve ser profundidade_max_m
    pdr = m.get("preview_depth_real_m")
    if pdr is not None and abs(pdr - prof) < 1e-9:
        _ok("G7", f"preview_depth_real_m={pdr} == profundidade_max_m")
    else:
        _fail("G7", f"preview_depth_real_m={pdr} != profundidade_max_m={prof}")


# ============================================================
# G8 -- Comparativo HELPER_0004.DZT (requer DZT real)
# ============================================================

def test_g8_comparativo_helper_0004() -> None:
    _sep("G8", "Comparativo HELPER_0004.DZT: readgssi_reference vs padrao")

    if not _DZT4.exists():
        _warn("G8", f"HELPER_0004.DZT nao encontrado: {_DZT4} -- pulando")
        return

    from gpr_engine.pipeline import process_dzt

    results: dict[str, dict] = {}

    for label, extra_cfg in [
        ("readgssi_ref", {"visual_profile": "readgssi_reference", "skip_ia": True}),
        ("padrao",       {"skip_ia": True}),
    ]:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = process_dzt(
                dzt_path=_DZT4,
                output_dir=Path(tmpdir),
                config={**extra_cfg},
                tipo_solo="standard",
                stem=_DZT4.stem,
            )
            # Lê o JSON gerado
            m = json.loads(Path(result.metrics_path).read_text(encoding="utf-8"))
            # Captura tamanhos de imagens relevantes
            processada_size = (
                Path(result.image_paths.get("processada", "")).stat().st_size
                if result.image_paths.get("processada") and Path(result.image_paths["processada"]).exists()
                else 0
            )
            ref_size = (
                Path(result.image_paths.get("readgssi_reference", "")).stat().st_size
                if result.image_paths.get("readgssi_reference") and Path(result.image_paths["readgssi_reference"]).exists()
                else 0
            )
            results[label] = {
                "metrics":        m,
                "processada_kb":  processada_size // 1024,
                "ref_kb":         ref_size // 1024,
            }
        print(f"    [{label}] processamento concluido")

    # Comparar campos chave
    print()
    for label, data in results.items():
        m = data["metrics"]
        print(f"    [{label}]")
        print(f"      visual_profile    : {m.get('visual_profile')!r}")
        print(f"      renderer          : {m.get('renderer')!r}")
        print(f"      normalization     : {m.get('normalization')!r}")
        print(f"      background_removal: {m.get('background_removal')!r}")
        print(f"      bgr_window        : {m.get('bgr_window')!r}")
        print(f"      gain              : {m.get('gain')!r}")
        print(f"      skip_ia           : {m.get('skip_ia')!r}")
        print(f"      detector_status   : {m.get('detector_status')!r}")
        print(f"      dewow_window      : {m.get('dewow_window')!r}")
        print(f"      bandpass_aplicado : {m.get('bandpass_aplicado')!r}")
        print(f"      bgremoval_traces  : {m.get('bgremoval_traces')!r}")
        print(f"      tpow_power        : {m.get('tpow_power')!r}")
        print(f"      agc_window        : {m.get('agc_window')!r}")
        print(f"      velocity_mns      : {m.get('velocity_mns')!r}")
        print(f"      depth_tecnica_m   : {m.get('depth_tecnica_m')!r}")
        print(f"      snr_raw_db        : {m.get('snr_raw_db')!r}")
        print(f"      modo_processamento: {m.get('modo_processamento')!r}")
        print(f"      processada.png    : {data['processada_kb']} KB")
        print(f"      readgssi_ref.png  : {data['ref_kb']} KB")
        print()

    # Verificacoes de corretude
    ref_m = results["readgssi_ref"]["metrics"]
    pad_m = results["padrao"]["metrics"]

    if ref_m.get("normalization") == "SymLogNorm":
        _ok("G8", "readgssi_ref: normalization=SymLogNorm")
    else:
        _fail("G8", f"readgssi_ref: normalization={ref_m.get('normalization')!r}")

    if pad_m.get("normalization") == "linear_percentile99":
        _ok("G8", "padrao: normalization=linear_percentile99")
    else:
        _fail("G8", f"padrao: normalization={pad_m.get('normalization')!r}")

    # snr_raw deve ser identico (mesmo DZT)
    snr_ref = ref_m.get("snr_raw_db")
    snr_pad = pad_m.get("snr_raw_db")
    if snr_ref is not None and snr_pad is not None and abs(snr_ref - snr_pad) < 0.01:
        _ok("G8", f"snr_raw_db identico nos dois modos: {snr_ref:.1f} dB")
    else:
        _warn("G8", f"snr_raw_db divergiu: ref={snr_ref}, padrao={snr_pad}")

    # Processada PNG deve ter tamanhos diferentes (SymLogNorm vs linear)
    sz_ref = results["readgssi_ref"]["processada_kb"]
    sz_pad = results["padrao"]["processada_kb"]
    if sz_ref != sz_pad:
        _ok("G8", f"processada.png: readgssi_ref={sz_ref} KB vs padrao={sz_pad} KB (diferentes)")
    else:
        _warn("G8", f"processada.png com mesmo tamanho ({sz_ref} KB) nos dois modos")

    # detector_status identico em ambos
    for label, data in results.items():
        ds = data["metrics"].get("detector_status")
        if ds == "skipped_not_integrated":
            _ok("G8", f"{label}: detector_status='skipped_not_integrated'")
        else:
            _fail("G8", f"{label}: detector_status={ds!r}")


# ============================================================
# G9 -- Campos obrigatorios legados nao removidos
# ============================================================

def test_g9_campos_obrigatorios() -> None:
    _sep("G9", "Todos os campos obrigatorios presentes (legados + novos Fase 8.10)")
    from gpr_engine.metrics import build_pipeline_metrics

    dzt = _make_dzt_data()
    m = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=_base_config(skip_ia=True, visual_profile="readgssi_reference"),
        modo_processamento="agressivo",
        snr_raw_db=10.7,
        snr_raw_ratio=3.2,
        snr_stages_db={"raw": 10.7, "dewow_bp": 16.3},
        image_paths=None,
        array_paths=None,
    )

    # Serializa para JSON e deserializa (valida que nao tem tipos nao-serializaveis)
    try:
        import json as _json
        from gpr_engine.metrics import _to_serializable
        roundtrip = _json.loads(
            _json.dumps(m, default=_to_serializable, ensure_ascii=False)
        )
        _ok("G9", "JSON serialization round-trip ok")
    except Exception as e:
        _fail("G9", f"JSON serialization falhou: {e}")
        return

    ausentes = [k for k in _CAMPOS_OBRIGATORIOS if k not in roundtrip]
    if not ausentes:
        _ok("G9", f"Todos {len(_CAMPOS_OBRIGATORIOS)} campos obrigatorios presentes")
    else:
        _fail("G9", f"Campos ausentes: {ausentes}")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 65)
    print("  _test_phase8_10.py -- Rastreabilidade readgssi_engine")
    print("=" * 65)

    test_g1_bandpass_desativado()
    test_g2_bandpass_habilitado()
    test_g3_render_profile_readgssi()
    test_g4_render_profile_default()
    test_g5_metrics_visual_profile()
    test_g6_detector_skip_ia()
    test_g7_filtros_nivel_raiz()
    test_g8_comparativo_helper_0004()
    test_g9_campos_obrigatorios()

    print(f"\n{'='*65}")
    print(f"  RESULTADO: {_PASS} PASS | {_FAIL} FAIL | {_WARN} WARN")
    print("=" * 65)
    if _FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
