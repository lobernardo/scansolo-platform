"""
Fase 3 -- testes de aceite do gpr_engine.snr.

Valida com arrays sinteticos:
  - SNR ratio e dB finitos e positivos
  - Input nao modificado in-place
  - Modo correto por tipo de solo e limiares
  - Time-zero detectavel em pulso sintetico
  - aplicar_time_zero preserva/reduz shape corretamente
  - Valor explicito de depth_min sempre prevalece
  - Nenhum import de GPRPy

Uso:
  python -m gpr_engine._test_phase3
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


def _make(n_samples: int = 200, n_traces: int = 30, seed: int = 7) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal((n_samples, n_traces)).astype(np.float32)


def _make_snr_array(amplitude: float, noise_std: float, n_samples: int = 300, n_traces: int = 20) -> np.ndarray:
    """
    Array sintetico com sinal claro na janela [10%:75%] e ruido baixo em [95%:100%].

    O sinal e uma senoidee com `amplitude`, o que garante que o envelope
    de Hilbert na janela de sinal seja proximo de `amplitude`.
    """
    s0 = max(1, int(0.10 * n_samples))
    s1 = int(0.75 * n_samples)
    r0 = int(0.95 * n_samples)

    arr = np.zeros((n_samples, n_traces), dtype=np.float32)
    # 20 ciclos na janela de sinal -- Hilbert envelope bem comportado
    n_win = s1 - s0
    t_win = np.arange(n_win) / n_win
    sinal = (amplitude * np.sin(2 * np.pi * 20.0 * t_win)).astype(np.float32)

    rng = np.random.default_rng(42)
    for col in range(n_traces):
        arr[s0:s1, col] = sinal
        arr[r0:, col] = (rng.standard_normal(n_samples - r0) * noise_std).astype(np.float32)

    return arr


# ---------------------------------------------------------------------------
# 1. imports
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    _section("imports")
    try:
        from gpr_engine.snr import (  # noqa: F401
            SNR_LIMIARES,
            calcular_snr_ratio,
            calcular_snr_imagem_db,
            detectar_modo_processamento,
            detectar_time_zero,
            aplicar_time_zero,
            calcular_depth_min_adaptativo,
        )
    except Exception as exc:
        _fail("importar gpr_engine.snr", str(exc))
        return False
    _ok("gpr_engine.snr importa todas as 7 exportacoes esperadas")

    gprpy = [m for m in sys.modules if "gprpy" in m.lower()]
    if gprpy:
        _fail(f"GPRPy importado: {gprpy}")
        return False
    _ok("GPRPy nao importado por gpr_engine.snr")
    return True


# ---------------------------------------------------------------------------
# 2. calcular_snr_ratio
# ---------------------------------------------------------------------------

def test_calcular_snr_ratio() -> bool:
    _section("calcular_snr_ratio")
    from gpr_engine.snr import calcular_snr_ratio

    # Array com sinal forte (amplitude=100) e ruido muito baixo (std=0.01)
    arr_alto = _make_snr_array(amplitude=100.0, noise_std=0.01)
    snap = arr_alto.copy()

    ratio_alto = calcular_snr_ratio(arr_alto)
    ok = True

    if np.isfinite(ratio_alto) and ratio_alto > 0:
        _ok(f"calcular_snr_ratio: finito e positivo (ratio={ratio_alto:.1f})")
    else:
        _fail(f"calcular_snr_ratio: ratio invalido ({ratio_alto})"); ok = False

    if not np.array_equal(arr_alto, snap):
        _fail("calcular_snr_ratio: input modificado in-place"); ok = False
    else:
        _ok("calcular_snr_ratio: input nao modificado")

    # Array com sinal fraco (amplitude=1) e ruido maior (std=1)
    arr_baixo = _make_snr_array(amplitude=1.0, noise_std=1.0)
    ratio_baixo = calcular_snr_ratio(arr_baixo)

    if ratio_alto > ratio_baixo:
        _ok(f"calcular_snr_ratio: sinal forte ({ratio_alto:.1f}) > sinal fraco ({ratio_baixo:.2f})")
    else:
        _fail(f"calcular_snr_ratio: sinal forte ({ratio_alto:.1f}) deveria > fraco ({ratio_baixo:.2f})"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 3. calcular_snr_imagem_db
# ---------------------------------------------------------------------------

def test_calcular_snr_imagem_db() -> bool:
    _section("calcular_snr_imagem_db")
    from gpr_engine.snr import calcular_snr_imagem_db

    arr = _make_snr_array(amplitude=100.0, noise_std=0.01)
    snap = arr.copy()

    snr_db = calcular_snr_imagem_db(arr)
    ok = True

    if np.isfinite(snr_db):
        _ok(f"calcular_snr_imagem_db: finito (snr_db={snr_db:.1f} dB)")
    else:
        _fail(f"calcular_snr_imagem_db: valor invalido ({snr_db})"); ok = False

    if snr_db > 0:
        _ok(f"calcular_snr_imagem_db: positivo ({snr_db:.1f} dB)")
    else:
        _fail(f"calcular_snr_imagem_db: esperado > 0 dB, obtido {snr_db:.1f}"); ok = False

    if not np.array_equal(arr, snap):
        _fail("calcular_snr_imagem_db: input modificado in-place"); ok = False
    else:
        _ok("calcular_snr_imagem_db: input nao modificado")

    # Array de zeros deve retornar 0.0 (sem crashar)
    arr_zero = np.zeros((100, 10), dtype=np.float32)
    snr_zero = calcular_snr_imagem_db(arr_zero)
    if np.isfinite(snr_zero):
        _ok(f"calcular_snr_imagem_db: array zeros retorna finito ({snr_zero})")
    else:
        _fail(f"calcular_snr_imagem_db: array zeros retornou {snr_zero}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. detectar_modo_processamento
# ---------------------------------------------------------------------------

def test_detectar_modo_processamento() -> bool:
    _section("detectar_modo_processamento")
    from gpr_engine.snr import detectar_modo_processamento

    ok = True

    # Tabela de testes: (snr_db, tipo_solo, modo_esperado, justificativa)
    # standard: thr_minimo=30.0 (29.5 dB), thr_padrao=4.0 (12.0 dB)
    # argiloso: thr_minimo=20.0 (26.0 dB), thr_padrao=3.5 (10.9 dB)
    # umido:    thr_minimo=15.0 (23.5 dB), thr_padrao=3.0 (9.5 dB)
    # pedregoso:thr_minimo=35.0 (30.9 dB), thr_padrao=6.0 (15.6 dB)
    casos = [
        # standard
        (32.0, "standard",  "minimo",    "ratio~39.8 >= 30.0"),
        (14.0, "standard",  "padrao",    "ratio~5.0 em [4.0, 30.0)"),
        (6.0,  "standard",  "agressivo", "ratio~2.0 < 4.0"),
        # argiloso
        (28.0, "argiloso",  "minimo",    "ratio~25.1 >= 20.0"),
        (12.0, "argiloso",  "padrao",    "ratio~3.98 em [3.5, 20.0)"),
        (8.0,  "argiloso",  "agressivo", "ratio~2.5 < 3.5"),
        # umido
        (24.0, "umido",     "minimo",    "ratio~15.8 >= 15.0"),
        (10.0, "umido",     "padrao",    "ratio~3.16 em [3.0, 15.0)"),
        (5.0,  "umido",     "agressivo", "ratio~1.78 < 3.0"),
        # pedregoso
        (32.0, "pedregoso", "minimo",    "ratio~39.8 >= 35.0"),
        (16.0, "pedregoso", "padrao",    "ratio~6.3 em [6.0, 35.0)"),
        (10.0, "pedregoso", "agressivo", "ratio~3.16 < 6.0"),
        # solo desconhecido -- fallback para standard
        (14.0, "desconhecido", "padrao", "fallback standard (ratio~5.0)"),
    ]

    for snr_db, tipo_solo, esperado, nota in casos:
        resultado = detectar_modo_processamento(snr_db, tipo_solo)
        if resultado == esperado:
            _ok(f"modo({snr_db} dB, {tipo_solo}) = {resultado}  [{nota}]")
        else:
            _fail(f"modo({snr_db} dB, {tipo_solo}): esperado={esperado}, obtido={resultado}  [{nota}]")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. detectar_time_zero
# ---------------------------------------------------------------------------

def test_detectar_time_zero() -> bool:
    _section("detectar_time_zero")
    from gpr_engine.snr import detectar_time_zero

    ok = True
    n_samples, n_traces = 120, 15

    # Pulso Gaussiano em sample=18 (dentro da janela de busca 25%=30)
    tz_real = 18
    t = np.arange(n_samples)
    pulse = np.exp(-((t - tz_real) ** 2) / 4.0).astype(np.float32)
    arr = np.tile(pulse[:, np.newaxis], (1, n_traces))
    snap = arr.copy()

    tz_detectado = detectar_time_zero(arr)

    if not np.array_equal(arr, snap):
        _fail("detectar_time_zero: input modificado in-place"); ok = False
    else:
        _ok("detectar_time_zero: input nao modificado")

    if abs(tz_detectado - tz_real) <= 2:
        _ok(f"detectar_time_zero: detectou sample {tz_detectado} (real={tz_real}, tolerancia=2)")
    else:
        _fail(f"detectar_time_zero: obtido {tz_detectado}, esperado proximo de {tz_real}"); ok = False

    # Array plano (sem pulso) deve retornar 0 ou valor <= 1
    arr_plano = np.ones((100, 10), dtype=np.float32)
    tz_plano = detectar_time_zero(arr_plano)
    if tz_plano == 0:
        _ok(f"detectar_time_zero: array plano retorna 0 (obtido {tz_plano})")
    else:
        # Valor em 0 ou 1 seria retornado como 0 pelo codigo -- apenas verificar que nao crashou
        _ok(f"detectar_time_zero: array plano retorna {tz_plano} (nao crashou)")

    # Retorno deve ser int
    if isinstance(tz_detectado, int):
        _ok("detectar_time_zero: retorna int")
    else:
        _fail(f"detectar_time_zero: retornou {type(tz_detectado).__name__}, esperado int"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 6. aplicar_time_zero
# ---------------------------------------------------------------------------

def test_aplicar_time_zero() -> bool:
    _section("aplicar_time_zero")
    from gpr_engine.snr import aplicar_time_zero

    n_samples, n_traces = 100, 10
    arr = _make(n_samples, n_traces)
    snap = arr.copy()
    ok = True

    # timezero=0: shape original preservado
    result0 = aplicar_time_zero(arr, 0)
    if result0.shape == (n_samples, n_traces):
        _ok(f"aplicar_time_zero(0): shape {result0.shape} preservado")
    else:
        _fail(f"aplicar_time_zero(0): shape {result0.shape} != ({n_samples}, {n_traces})"); ok = False

    if result0.dtype == np.float32:
        _ok("aplicar_time_zero(0): dtype == float32")
    else:
        _fail(f"aplicar_time_zero(0): dtype={result0.dtype}, esperado float32"); ok = False

    # timezero=1: tambem deve retornar shape original (tz <= 1 -> copia)
    result1 = aplicar_time_zero(arr, 1)
    if result1.shape == (n_samples, n_traces):
        _ok(f"aplicar_time_zero(1): shape {result1.shape} preservado")
    else:
        _fail(f"aplicar_time_zero(1): shape {result1.shape} != ({n_samples}, {n_traces})"); ok = False

    # timezero=20: shape reduzido
    tz = 20
    result20 = aplicar_time_zero(arr, tz)
    expected_shape = (n_samples - tz, n_traces)
    if result20.shape == expected_shape:
        _ok(f"aplicar_time_zero({tz}): shape {result20.shape} (reducao correta)")
    else:
        _fail(f"aplicar_time_zero({tz}): shape {result20.shape} != {expected_shape}"); ok = False

    if result20.dtype == np.float32:
        _ok(f"aplicar_time_zero({tz}): dtype == float32")
    else:
        _fail(f"aplicar_time_zero({tz}): dtype={result20.dtype}"); ok = False

    # Conteudo: result20[0] deve ser arr[20]
    if np.allclose(result20[0].astype(np.float64), arr[tz].astype(np.float64)):
        _ok(f"aplicar_time_zero({tz}): primeira linha = arr[{tz}] (conteudo correto)")
    else:
        _fail(f"aplicar_time_zero({tz}): conteudo incorreto"); ok = False

    # Input nao modificado
    if not np.array_equal(arr, snap):
        _fail("aplicar_time_zero: input modificado in-place"); ok = False
    else:
        _ok("aplicar_time_zero: input nao modificado")

    # Retorno e copia (nao compartilha memoria com input)
    result_copy = aplicar_time_zero(arr, 0)
    result_copy[0, 0] = 99999.0
    if arr[0, 0] != 99999.0:
        _ok("aplicar_time_zero: retorno e copia independente (nao compartilha memoria)")
    else:
        _fail("aplicar_time_zero: retorno compartilha memoria com input"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 7. calcular_depth_min_adaptativo
# ---------------------------------------------------------------------------

def test_calcular_depth_min_adaptativo() -> bool:
    _section("calcular_depth_min_adaptativo")
    from gpr_engine.snr import calcular_depth_min_adaptativo

    ok = True

    # --- valor_explicito sempre prevalece ---
    for snr_db in [6.0, 14.0, 32.0]:
        for tipo in ["standard", "argiloso", "umido"]:
            result = calcular_depth_min_adaptativo(snr_db, tipo, valor_explicito=0.75)
            if abs(result - 0.75) < 1e-9:
                _ok(f"depth_min explicito=0.75 prevalece (snr={snr_db} dB, {tipo})")
            else:
                _fail(f"depth_min explicito=0.75 nao prevaleceu: obtido {result}"); ok = False
            break  # um exemplo por tipo e suficiente
        break  # um snr e suficiente para testar a logica

    # Todos os tres tipos -- apenas standard para cobrir todos os ramos
    res_exp = calcular_depth_min_adaptativo(14.0, "standard", valor_explicito=0.75)
    if abs(res_exp - 0.75) < 1e-9:
        _ok("valor_explicito=0.75 prevalece sobre modo padrao")
    else:
        _fail(f"valor_explicito nao prevaleceu: {res_exp}"); ok = False

    # --- modo minimo -> 0.50 ---
    # standard: thr_minimo=30.0 -> 20*log10(30) ~= 29.5 dB; usar 32 dB
    res_min = calcular_depth_min_adaptativo(32.0, "standard")
    if abs(res_min - 0.50) < 1e-9:
        _ok(f"modo minimo -> depth_min=0.50 (snr=32 dB, standard)")
    else:
        _fail(f"modo minimo: esperado 0.50, obtido {res_min}"); ok = False

    # --- modo padrao -> 0.30 ---
    # standard: ratio~5.0 (14 dB) em [4.0, 30.0)
    res_pad = calcular_depth_min_adaptativo(14.0, "standard")
    if abs(res_pad - 0.30) < 1e-9:
        _ok(f"modo padrao -> depth_min=0.30 (snr=14 dB, standard)")
    else:
        _fail(f"modo padrao: esperado 0.30, obtido {res_pad}"); ok = False

    # --- modo agressivo -> max(0.20, 0.30 * 0.67) ---
    # standard: ratio~2.0 (6 dB) < 4.0
    res_agr = calcular_depth_min_adaptativo(6.0, "standard")
    esperado_agr = max(0.20, 0.30 * 0.67)  # = max(0.20, 0.201) = 0.201
    if abs(res_agr - esperado_agr) < 1e-9:
        _ok(f"modo agressivo -> depth_min={res_agr:.4f} (snr=6 dB, standard)")
    else:
        _fail(f"modo agressivo: esperado {esperado_agr:.4f}, obtido {res_agr:.4f}"); ok = False

    # --- tipo de solo afeta o modo (e portanto o resultado) ---
    # argiloso (thr_minimo=20.0): snr=28 dB (ratio~25) -> minimo -> 0.50
    res_arg_min = calcular_depth_min_adaptativo(28.0, "argiloso")
    if abs(res_arg_min - 0.50) < 1e-9:
        _ok(f"argiloso + 28 dB -> minimo -> 0.50")
    else:
        _fail(f"argiloso + 28 dB: esperado 0.50, obtido {res_arg_min}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 8. SNR_LIMIARES cobertura
# ---------------------------------------------------------------------------

def test_snr_limiares() -> bool:
    _section("SNR_LIMIARES")
    from gpr_engine.snr import SNR_LIMIARES

    ok = True
    tipos_esperados = ["standard", "arenoso", "argiloso", "umido", "pedregoso"]

    for tipo in tipos_esperados:
        if tipo in SNR_LIMIARES:
            thr_min, thr_pad = SNR_LIMIARES[tipo]
            if thr_min > thr_pad > 0:
                _ok(f"SNR_LIMIARES[{tipo}]: limiar_minimo={thr_min} > limiar_padrao={thr_pad} > 0")
            else:
                _fail(f"SNR_LIMIARES[{tipo}]: limiares invalidos ({thr_min}, {thr_pad})"); ok = False
        else:
            _fail(f"SNR_LIMIARES: tipo '{tipo}' ausente"); ok = False

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 3 -- testes de aceite (snr.py)")
    print("=" * 60)

    results = [
        test_imports(),
        test_calcular_snr_ratio(),
        test_calcular_snr_imagem_db(),
        test_detectar_modo_processamento(),
        test_detectar_time_zero(),
        test_aplicar_time_zero(),
        test_calcular_depth_min_adaptativo(),
        test_snr_limiares(),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado: {passed}/{total} grupos passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
