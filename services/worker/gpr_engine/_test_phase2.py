"""
Fase 2 — testes de aceite do gpr_engine.filters.

Valida com arrays sintéticos:
  - shape e dtype preservados
  - input array não modificado in-place
  - ausência de NaN/Inf em todo output
  - comportamento esperado de cada filtro (semântica)

Uso:
  python -m gpr_engine._test_phase2
"""
from __future__ import annotations

import sys
from pathlib import Path

# Garante que services/worker/ esteja no path quando executado de qualquer lugar
_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

import numpy as np


# ── helpers de assert ─────────────────────────────────────────────────────────

def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"  [FAIL] {msg}{suffix}", file=sys.stderr)


def _section(name: str) -> None:
    print(f"\n-- {name} --")


def _check_contract(result: np.ndarray, original: np.ndarray, snapshot: np.ndarray, name: str) -> bool:
    """Verifica os três contratos básicos: shape, dtype, input não modificado, sem NaN/Inf."""
    ok = True
    if result.shape != original.shape:
        _fail(f"{name} shape: {result.shape} != {original.shape}"); ok = False
    else:
        _ok(f"{name}: shape {result.shape} preservado")

    if result.dtype != np.float32:
        _fail(f"{name} dtype: {result.dtype}, esperado float32"); ok = False
    else:
        _ok(f"{name}: dtype == float32")

    if not np.array_equal(original, snapshot):
        _fail(f"{name}: input array foi modificado in-place!"); ok = False
    else:
        _ok(f"{name}: input não modificado")

    n_bad = int(np.sum(~np.isfinite(result)))
    if n_bad > 0:
        _fail(f"{name}: {n_bad} valores NaN/Inf no output"); ok = False
    else:
        _ok(f"{name}: nenhum NaN/Inf")

    return ok


def _make(n_samples: int = 200, n_traces: int = 80, seed: int = 42) -> np.ndarray:
    """Array sintético float32 com distribuição normal."""
    return np.random.default_rng(seed).standard_normal((n_samples, n_traces)).astype(np.float32)


# ── 1. imports ────────────────────────────────────────────────────────────────

def test_imports() -> bool:
    _section("imports")
    try:
        from gpr_engine.filters import (  # noqa: F401
            dewow, bandpass_butterworth, bandpass_triangular,
            bandpass, bgremoval, tpow, agc,
        )
    except Exception as exc:
        _fail("importar gpr_engine.filters", str(exc))
        return False
    _ok("gpr_engine.filters importa todas as 7 funções esperadas")

    gprpy = [m for m in sys.modules if "gprpy" in m.lower()]
    if gprpy:
        _fail(f"GPRPy importado por gpr_engine.filters: {gprpy}")
        return False
    _ok("GPRPy não importado por gpr_engine.filters")
    return True


# ── 2. dewow ──────────────────────────────────────────────────────────────────

def test_dewow() -> bool:
    _section("dewow")
    from gpr_engine.filters import dewow

    arr = _make()
    snap = arr.copy()

    result = dewow(arr, window=5)
    ok = _check_contract(result, arr, snap, "dewow(5)")

    # Semantics: cada coluna deve ter média próxima de zero após subtração do DC
    col_means = np.abs(result.mean(axis=0))
    avg_mean = float(col_means.mean())
    if avg_mean < 0.5:
        _ok(f"dewow reduz média por coluna: |mean| = {avg_mean:.5f}")
    else:
        _fail(f"dewow: média por coluna ainda alta = {avg_mean:.4f}"); ok = False

    # window=0 deve retornar cópia do array original sem modificação
    result0 = dewow(arr, window=0)
    if np.allclose(result0, arr.astype(np.float32)):
        _ok("dewow(window=0) retorna cópia inalterada")
    else:
        _fail("dewow(window=0) não preservou valores"); ok = False

    return ok


# ── 3. tpow ───────────────────────────────────────────────────────────────────

def test_tpow() -> bool:
    _section("tpow")
    from gpr_engine.filters import tpow

    arr = np.ones((100, 50), dtype=np.float32)
    snap = arr.copy()

    result = tpow(arr, power=0.5)
    ok = _check_contract(result, arr, snap, "tpow(0.5)")

    # Ganho deve crescer com profundidade
    first = float(result[0].mean())
    last = float(result[-1].mean())
    if first < last:
        _ok(f"tpow: ganho cresce ({first:.4f} -> {last:.4f})")
    else:
        _fail(f"tpow: ganho não cresce ({first:.4f} -> {last:.4f})"); ok = False

    # Amostra 0: t/t_max=0 -> ganho=0
    if abs(float(result[0, 0])) < 1e-6:
        _ok("tpow: amostra[0] = 0.0 (t=0, ganho=0^power=0)")
    else:
        _fail(f"tpow: amostra[0] = {result[0,0]:.6f}, esperado 0.0"); ok = False

    # Amostra -1: t/t_max=1 -> ganho=1
    if abs(float(result[-1, 0]) - 1.0) < 1e-5:
        _ok("tpow: amostra[-1] ~= 1.0 (t=t_max, ganho=1.0)")
    else:
        _fail(f"tpow: amostra[-1] = {result[-1,0]:.6f}, esperado ~=1.0"); ok = False

    # power=0 -> cópia
    result0 = tpow(arr, power=0)
    if np.allclose(result0, arr.astype(np.float32)):
        _ok("tpow(power=0) retorna cópia sem ganho")
    else:
        _fail("tpow(power=0) deveria retornar cópia"); ok = False

    return ok


# ── 4. bgremoval ─────────────────────────────────────────────────────────────

def test_bgremoval() -> bool:
    _section("bgremoval")
    from gpr_engine.filters import bgremoval

    # Array com padrão horizontal dominante (offset por linha)
    rng = np.random.default_rng(99)
    noise = rng.standard_normal((80, 60)).astype(np.float32) * 0.1
    offsets = np.linspace(-5.0, 5.0, 80).astype(np.float32)[:, np.newaxis]
    arr = noise + offsets
    snap = arr.copy()

    # BGR global (window=0)
    result = bgremoval(arr, window=0)
    ok = _check_contract(result, arr, snap, "bgremoval(window=0)")

    # BGR deve remover a média de cada linha: result.mean(axis=1) ~= 0
    row_means_before = float(np.abs(arr.mean(axis=1)).mean())
    row_means_after  = float(np.abs(result.mean(axis=1)).mean())
    if row_means_after < row_means_before * 0.01:
        _ok(f"bgremoval(0): media por linha {row_means_before:.3f} -> {row_means_after:.5f} (~= 0)")
    else:
        _fail(f"bgremoval(0): media {row_means_before:.3f}->{row_means_after:.5f} (esperado <{row_means_before*0.01:.5f})"); ok = False

    # BGR janelado (window=20)
    result_w = bgremoval(arr, window=20)
    ok &= _check_contract(result_w, arr, snap, "bgremoval(window=20)")

    return ok


# ── 5. agc ────────────────────────────────────────────────────────────────────

def test_agc() -> bool:
    _section("agc")
    from gpr_engine.filters import agc

    # Array com amplitude que cresce 100x com profundidade
    rng = np.random.default_rng(7)
    n_samples, n_traces = 200, 80
    depth_gain = np.linspace(0.1, 10.0, n_samples)[:, np.newaxis]
    arr = (rng.standard_normal((n_samples, n_traces)) * depth_gain).astype(np.float32)
    snap = arr.copy()

    result = agc(arr, window=50)
    ok = _check_contract(result, arr, snap, "agc(window=50)")

    # Coeficiente de variação da amplitude por linha deve diminuir (amplitude mais homogênea)
    std_before = arr.std(axis=1)
    std_after = result.std(axis=1)
    cv_before = float(std_before.std() / (std_before.mean() + 1e-10))
    cv_after = float(std_after.std() / (std_after.mean() + 1e-10))
    if cv_after < cv_before:
        _ok(f"agc: coef. variação {cv_before:.3f} -> {cv_after:.3f} (amplitude mais homogênea)")
    else:
        _fail(f"agc: coef. variação {cv_before:.3f} -> {cv_after:.3f} (esperado menor)"); ok = False

    return ok


# ── 6. bandpass_butterworth ───────────────────────────────────────────────────

def test_bandpass_butterworth() -> bool:
    _section("bandpass_butterworth")
    from gpr_engine.filters import bandpass_butterworth

    # Parâmetros realistas: antena 270 MHz, fs=10 GHz, bp 80-500 MHz
    SAMP_FREQ = 10.0e9
    n_samples, n_traces = 256, 50
    t = np.arange(n_samples) / SAMP_FREQ

    # Sinal composto: 270 MHz (in-band) + 1 GHz (out-of-band) + 20 MHz (out-of-band)
    signal_1d = (
        np.sin(2 * np.pi * 270e6 * t) +        # in-band
        0.5 * np.sin(2 * np.pi * 1000e6 * t) + # out-of-band (acima)
        0.5 * np.sin(2 * np.pi * 20e6 * t)     # out-of-band (abaixo)
    ).astype(np.float32)
    arr = np.tile(signal_1d[:, np.newaxis], (1, n_traces))
    snap = arr.copy()

    result = bandpass_butterworth(arr, SAMP_FREQ, 80.0, 500.0, order=5)
    ok = _check_contract(result, arr, snap, "bandpass_butterworth")

    # Verificar seletividade espectral via FFT na 1ª coluna (após transiente de borda)
    mid = n_samples // 4
    col = result[mid:, 0].astype(float)
    fft_mag = np.abs(np.fft.rfft(col))
    freqs = np.fft.rfftfreq(len(col), d=1.0 / SAMP_FREQ)

    in_band  = (freqs >= 80e6) & (freqs <= 500e6)
    out_band = ((freqs > 800e6) | (freqs < 40e6)) & (freqs > 0)

    if np.any(in_band) and np.any(out_band):
        e_in  = float(fft_mag[in_band].mean())
        e_out = float(fft_mag[out_band].mean())
        ratio = e_in / (e_out + 1e-10)
        if ratio > 5.0:
            _ok(f"bandpass_butterworth: in-band/out-of-band = {ratio:.1f}x")
        else:
            _fail(f"bandpass_butterworth: razão in/out = {ratio:.2f} (esperado > 5)"); ok = False

    return ok


# ── 7. bandpass_triangular ────────────────────────────────────────────────────

def test_bandpass_triangular() -> bool:
    _section("bandpass_triangular")
    from gpr_engine.filters import bandpass_triangular

    SAMP_FREQ = 10.0e9
    # n_samples deve ser >> 3 * numtaps para filtfilt; numtaps adaptativo
    # para fs=10GHz e fl=80MHz: numtaps_ideal~=433, cap a (n-1)//3.
    # Usar n_samples=2000 para headroom adequado.
    n_samples, n_traces = 2000, 20
    t = np.arange(n_samples) / SAMP_FREQ

    # Sinal puro 270 MHz (in-band)
    signal_1d = np.sin(2 * np.pi * 270e6 * t).astype(np.float32)
    arr = np.tile(signal_1d[:, np.newaxis], (1, n_traces))
    snap = arr.copy()

    result = bandpass_triangular(arr, SAMP_FREQ, 80.0, 500.0)
    ok = _check_contract(result, arr, snap, "bandpass_triangular")

    # Sinal in-band (270 MHz) deve sobreviver: RMS do output ≥ 30% do input
    rms_in  = float(np.sqrt(np.mean(result[:, 0] ** 2)))
    rms_src = float(np.sqrt(np.mean(arr[:, 0].astype(float) ** 2)))
    if rms_in > rms_src * 0.3:
        _ok(f"bandpass_triangular: sinal 270 MHz preservado (rms {rms_src:.3f}->{rms_in:.3f})")
    else:
        _fail(f"bandpass_triangular: sinal muito atenuado (rms={rms_in:.3f})"); ok = False

    return ok


# ── 8. bandpass dispatcher ────────────────────────────────────────────────────

def test_bandpass_dispatcher() -> bool:
    _section("bandpass (dispatcher)")
    from gpr_engine.filters import bandpass

    arr = _make(128, 10)
    snap = arr.copy()
    SAMP_FREQ = 10.0e9

    r_butter = bandpass(arr, SAMP_FREQ, 80.0, 500.0, tipo="butterworth")
    ok = _check_contract(r_butter, arr, snap, "bandpass(butterworth)")

    r_tri = bandpass(arr, SAMP_FREQ, 80.0, 500.0, tipo="triangular")
    ok &= _check_contract(r_tri, arr, snap, "bandpass(triangular)")

    # Dispatcher com tipo padrão (butterworth)
    r_default = bandpass(arr, SAMP_FREQ, 80.0, 500.0)
    ok &= _check_contract(r_default, arr, snap, "bandpass(default)")

    return ok


# ── ponto de entrada ──────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 2 — testes de aceite (filters.py)")
    print("=" * 60)

    results = [
        test_imports(),
        test_dewow(),
        test_tpow(),
        test_bgremoval(),
        test_agc(),
        test_bandpass_butterworth(),
        test_bandpass_triangular(),
        test_bandpass_dispatcher(),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado: {passed}/{total} grupos passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
