"""
Fase 4 -- testes de aceite do gpr_engine.flows.

Valida com arrays sinteticos:
  - process_flows retorna FlowArrays com todos os 5 arrays
  - Todos os arrays sao float32 e preservam shape
  - Input arr_raw nao e modificado in-place
  - Nenhum NaN/Inf em nenhum array
  - Bandpass ON funciona
  - Bandpass OFF via bandpass_low_mhz=0 funciona
  - Bandpass OFF via bandpass_enabled=False funciona
  - Bandpass OFF nao requer samp_freq_hz
  - arr_sem_agc e arr_relatorio sao diferentes (AGC os distingue)
  - arr_preview_radan usa caminho diferente do arr_relatorio
  - build_* individuais sao consistentes com process_flows
  - ValueError quando bandpass ON e samp_freq_hz ausente
  - Nenhum import de GPRPy

Uso:
  python -m gpr_engine._test_phase4
"""
from __future__ import annotations

import sys
from pathlib import Path

_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

import numpy as np


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"  [FAIL] {msg}{suffix}", file=sys.stderr)


def _section(name: str) -> None:
    print(f"\n-- {name} --")


N_SAMPLES = 256
N_TRACES = 50
SAMP_FREQ = 10.0e9  # 10 GHz -- tipico GSSI 270 MHz

BASE_CONFIG: dict = {
    "dewow_window":       5,
    "bandpass_low_mhz":   80.0,
    "bandpass_high_mhz":  500.0,
    "bandpass_order":     5,
    "bandpass_tipo":      "butterworth",
    "bgremoval_traces":   30,
    "tpow_power":         0.5,
    "agc_window":         150,
    "agc_window_preview": 80,
    "samp_freq_hz":       SAMP_FREQ,
}


def _make(seed: int = 42) -> np.ndarray:
    """Array sintetico realista (256 x 50) com distribuicao normal."""
    return np.random.default_rng(seed).standard_normal(
        (N_SAMPLES, N_TRACES)
    ).astype(np.float32)


def _check_array(arr: np.ndarray, name: str, expected_shape: tuple) -> bool:
    ok = True
    if arr.shape != expected_shape:
        _fail(f"{name} shape {arr.shape} != {expected_shape}"); ok = False
    else:
        _ok(f"{name}: shape {arr.shape}")
    if arr.dtype != np.float32:
        _fail(f"{name} dtype={arr.dtype}, esperado float32"); ok = False
    else:
        _ok(f"{name}: dtype == float32")
    n_bad = int(np.sum(~np.isfinite(arr)))
    if n_bad:
        _fail(f"{name}: {n_bad} valores NaN/Inf"); ok = False
    else:
        _ok(f"{name}: sem NaN/Inf")
    return ok


# ---------------------------------------------------------------------------
# 1. imports
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    _section("imports")
    try:
        from gpr_engine.flows import (  # noqa: F401
            FlowArrays,
            build_base_filtered_flow,
            build_scientific_flow,
            build_report_flow,
            build_radan_like_flow,
            process_flows,
        )
    except Exception as exc:
        _fail("importar gpr_engine.flows", str(exc))
        return False
    _ok("gpr_engine.flows importa FlowArrays + 5 funcoes esperadas")

    gprpy = [m for m in sys.modules if "gprpy" in m.lower()]
    if gprpy:
        _fail(f"GPRPy importado: {gprpy}")
        return False
    _ok("GPRPy nao importado por gpr_engine.flows")
    return True


# ---------------------------------------------------------------------------
# 2. process_flows -- retorno completo
# ---------------------------------------------------------------------------

def test_process_flows_complete() -> bool:
    _section("process_flows -- retorno completo")
    from gpr_engine.flows import FlowArrays, process_flows

    arr_raw = _make()
    snap = arr_raw.copy()
    ok = True

    try:
        result = process_flows(arr_raw, BASE_CONFIG)
    except Exception as exc:
        _fail("process_flows lancou excecao", str(exc))
        return False

    if not isinstance(result, FlowArrays):
        _fail(f"retorno e {type(result).__name__}, esperado FlowArrays"); return False
    _ok("process_flows retorna FlowArrays")

    shape = (N_SAMPLES, N_TRACES)
    for field_name in ("arr_dewow_bp", "arr_cientifico", "arr_sem_agc",
                       "arr_relatorio", "arr_preview_radan"):
        arr = getattr(result, field_name)
        ok &= _check_array(arr, field_name, shape)

    if not np.array_equal(arr_raw, snap):
        _fail("arr_raw modificado in-place"); ok = False
    else:
        _ok("arr_raw nao modificado in-place")

    return ok


# ---------------------------------------------------------------------------
# 3. bandpass ON vs OFF
# ---------------------------------------------------------------------------

def test_bandpass_on() -> bool:
    _section("bandpass ON")
    from gpr_engine.flows import build_base_filtered_flow

    arr_raw = _make(seed=1)
    config = {**BASE_CONFIG}  # bandpass ON por default
    ok = True

    try:
        result = build_base_filtered_flow(arr_raw, config)
    except Exception as exc:
        _fail("build_base_filtered_flow (ON) lancou excecao", str(exc)); return False

    ok &= _check_array(result, "arr_dewow_bp (bandpass ON)", (N_SAMPLES, N_TRACES))

    # Com bandpass, o resultado deve diferir do simples dewow
    from gpr_engine.filters import dewow as _dewow
    arr_dewow_only = _dewow(arr_raw, window=5)
    if not np.allclose(result, arr_dewow_only):
        _ok("bandpass ON: arr_dewow_bp difere de dewow puro (filtro aplicado)")
    else:
        _fail("bandpass ON: arr_dewow_bp identico ao dewow puro (bandpass sem efeito?)"); ok = False

    return ok


def test_bandpass_off_lowmhz_zero() -> bool:
    _section("bandpass OFF via bandpass_low_mhz=0")
    from gpr_engine.flows import build_base_filtered_flow

    arr_raw = _make(seed=2)
    config = {**BASE_CONFIG, "bandpass_low_mhz": 0}
    # samp_freq_hz nao deve ser necessario quando bandpass OFF
    config_no_freq = {k: v for k, v in config.items() if k != "samp_freq_hz"}
    ok = True

    try:
        result = build_base_filtered_flow(arr_raw, config_no_freq)
    except Exception as exc:
        _fail("bandpass OFF: lancou excecao inesperada", str(exc)); return False

    ok &= _check_array(result, "arr_dewow_bp (bp OFF / lowmhz=0)", (N_SAMPLES, N_TRACES))

    # Sem bandpass, resultado deve ser igual ao dewow puro
    from gpr_engine.filters import dewow as _dewow
    arr_dewow_only = _dewow(arr_raw, window=5)
    if np.allclose(result, arr_dewow_only):
        _ok("bandpass OFF (lowmhz=0): arr_dewow_bp == dewow puro")
    else:
        _fail("bandpass OFF (lowmhz=0): arr_dewow_bp difere de dewow puro"); ok = False

    return ok


def test_bandpass_off_flag() -> bool:
    _section("bandpass OFF via bandpass_enabled=False")
    from gpr_engine.flows import build_base_filtered_flow

    arr_raw = _make(seed=3)
    config_no_freq = {k: v for k, v in BASE_CONFIG.items() if k != "samp_freq_hz"}
    config_no_freq["bandpass_enabled"] = False
    ok = True

    try:
        result = build_base_filtered_flow(arr_raw, config_no_freq)
    except Exception as exc:
        _fail("bandpass OFF (flag): lancou excecao inesperada", str(exc)); return False

    ok &= _check_array(result, "arr_dewow_bp (bp OFF / flag)", (N_SAMPLES, N_TRACES))

    from gpr_engine.filters import dewow as _dewow
    arr_dewow_only = _dewow(arr_raw, window=5)
    if np.allclose(result, arr_dewow_only):
        _ok("bandpass OFF (flag): arr_dewow_bp == dewow puro")
    else:
        _fail("bandpass OFF (flag): arr_dewow_bp difere de dewow puro"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. ValueError quando bandpass ON e samp_freq_hz ausente
# ---------------------------------------------------------------------------

def test_valueerror_missing_samp_freq() -> bool:
    _section("ValueError: bandpass ON sem samp_freq_hz")
    from gpr_engine.flows import build_base_filtered_flow

    arr_raw = _make(seed=4)
    config_no_freq = {k: v for k, v in BASE_CONFIG.items() if k != "samp_freq_hz"}
    # bandpass_low_mhz=80 (ON) e samp_freq_hz ausente -- deve levantar ValueError
    ok = True

    try:
        build_base_filtered_flow(arr_raw, config_no_freq)
        _fail("deveria ter lancado ValueError"); ok = False
    except ValueError as exc:
        _ok(f"ValueError levantado corretamente: {str(exc)[:60]}")
    except Exception as exc:
        _fail(f"excecao incorreta: {type(exc).__name__}: {exc}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. Fluxo relatorio: arr_sem_agc != arr_relatorio
# ---------------------------------------------------------------------------

def test_report_flow_sem_agc_vs_relatorio() -> bool:
    _section("fluxo relatorio: arr_sem_agc != arr_relatorio")
    from gpr_engine.flows import build_report_flow

    arr_raw = _make(seed=5)
    from gpr_engine.filters import dewow as _dewow
    arr_dewow_bp = _dewow(arr_raw, window=5)
    ok = True

    arr_sem_agc, arr_relatorio = build_report_flow(arr_dewow_bp, BASE_CONFIG)

    ok &= _check_array(arr_sem_agc, "arr_sem_agc", (N_SAMPLES, N_TRACES))
    ok &= _check_array(arr_relatorio, "arr_relatorio", (N_SAMPLES, N_TRACES))

    # AGC normaliza amplitude -- os arrays devem diferir numericamente
    if not np.allclose(arr_sem_agc, arr_relatorio):
        _ok("arr_sem_agc != arr_relatorio (AGC aplica normalizacao)")
    else:
        _fail("arr_sem_agc == arr_relatorio (AGC nao teve efeito?)"); ok = False

    # arr_relatorio deve ter amplitude mais homogenea (menor std por linha)
    std_sem_agc = float(arr_sem_agc.std(axis=1).std())
    std_relatorio = float(arr_relatorio.std(axis=1).std())
    if std_relatorio < std_sem_agc:
        _ok(f"arr_relatorio mais homogeneo: std_por_linha {std_sem_agc:.3f} -> {std_relatorio:.3f}")
    else:
        _fail(f"AGC nao reduziu variacao: {std_sem_agc:.3f} -> {std_relatorio:.3f}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 6. Preview usa caminho diferente do relatorio
# ---------------------------------------------------------------------------

def test_preview_vs_relatorio() -> bool:
    _section("arr_preview_radan vs arr_relatorio")
    from gpr_engine.flows import process_flows

    arr_raw = _make(seed=6)
    result = process_flows(arr_raw, BASE_CONFIG)
    ok = True

    # Preview: dewow_bp -> AGC(80) -- sem bgremoval/tpow
    # Relatorio: dewow_bp -> bgremoval -> tpow -> AGC(150)
    # Caminhos completamente distintos: arrays devem diferir
    if not np.allclose(result.arr_preview_radan, result.arr_relatorio):
        _ok("arr_preview_radan != arr_relatorio (caminhos distintos)")
    else:
        _fail("arr_preview_radan == arr_relatorio (processamentos distintos deveriam diferir)"); ok = False

    # Preview tambem deve diferir do cientifico
    if not np.allclose(result.arr_preview_radan, result.arr_cientifico):
        _ok("arr_preview_radan != arr_cientifico")
    else:
        _fail("arr_preview_radan == arr_cientifico"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 7. Consistencia: build_* individuais == process_flows
# ---------------------------------------------------------------------------

def test_individual_builds_consistent() -> bool:
    _section("consistencia: build_* individuais == process_flows")
    from gpr_engine.flows import (
        build_base_filtered_flow,
        build_report_flow,
        build_radan_like_flow,
        build_scientific_flow,
        process_flows,
    )

    arr_raw = _make(seed=7)
    ok = True

    # Resultado de process_flows
    result = process_flows(arr_raw, BASE_CONFIG)

    # Resultado calculado passo a passo
    arr_db = build_base_filtered_flow(arr_raw, BASE_CONFIG)
    arr_c = build_scientific_flow(arr_db, BASE_CONFIG)
    arr_sa, arr_r = build_report_flow(arr_db, BASE_CONFIG)
    arr_p = build_radan_like_flow(arr_db, BASE_CONFIG)

    checks = [
        ("arr_dewow_bp",       arr_db, result.arr_dewow_bp),
        ("arr_cientifico",     arr_c,  result.arr_cientifico),
        ("arr_sem_agc",        arr_sa, result.arr_sem_agc),
        ("arr_relatorio",      arr_r,  result.arr_relatorio),
        ("arr_preview_radan",  arr_p,  result.arr_preview_radan),
    ]

    for name, individual, from_flows in checks:
        if np.array_equal(individual, from_flows):
            _ok(f"build individual == process_flows: {name}")
        else:
            _fail(f"build individual != process_flows: {name}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 8. agc_window_preview separado do agc_window
# ---------------------------------------------------------------------------

def test_preview_window_separate() -> bool:
    _section("agc_window_preview separado do agc_window")
    from gpr_engine.flows import process_flows

    arr_raw = _make(seed=8)
    ok = True

    # Config com janelas muito diferentes para maximizar diferenca
    config_a = {**BASE_CONFIG, "agc_window": 50, "agc_window_preview": 200}
    config_b = {**BASE_CONFIG, "agc_window": 200, "agc_window_preview": 50}

    result_a = process_flows(arr_raw, config_a)
    result_b = process_flows(arr_raw, config_b)

    # Trocar as janelas deve produzir previews diferentes entre si
    if not np.allclose(result_a.arr_preview_radan, result_b.arr_preview_radan):
        _ok("agc_window_preview afeta arr_preview_radan independentemente de agc_window")
    else:
        _fail("agc_window_preview nao afeta arr_preview_radan"); ok = False

    # E relatórios diferentes entre si
    if not np.allclose(result_a.arr_relatorio, result_b.arr_relatorio):
        _ok("agc_window afeta arr_relatorio independentemente de agc_window_preview")
    else:
        _fail("agc_window nao afeta arr_relatorio"); ok = False

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 4 -- testes de aceite (flows.py)")
    print("=" * 60)

    results = [
        test_imports(),
        test_process_flows_complete(),
        test_bandpass_on(),
        test_bandpass_off_lowmhz_zero(),
        test_bandpass_off_flag(),
        test_valueerror_missing_samp_freq(),
        test_report_flow_sem_agc_vs_relatorio(),
        test_preview_vs_relatorio(),
        test_individual_builds_consistent(),
        test_preview_window_separate(),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado: {passed}/{total} grupos passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
