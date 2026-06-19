"""
Fase 1 — testes de aceite do gpr_engine.

Verifica imports, ausência de GPRPy e leitura de DZT real.

Uso:
  # Apenas imports (sempre roda sem arquivos):
  python -m gpr_engine._test_phase1

  # Leitura completa de um DZT real:
  python -m gpr_engine._test_phase1 /caminho/para/PATIO___001.DZT
"""
from __future__ import annotations

import sys
from pathlib import Path

# Garante que services/worker/ esteja no path quando executado diretamente
# de dentro de services/worker/gpr_engine/
_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))


def _ok(msg: str) -> None:
    print(f"[PASS] {msg}")


def _fail(msg: str, exc: BaseException | None = None) -> None:
    detail = f": {exc}" if exc else ""
    print(f"[FAIL] {msg}{detail}", file=sys.stderr)


def _skip(msg: str) -> None:
    print(f"[SKIP] {msg}")


# ── Teste 1: imports sem GPRPy ─────────────────────────────────────────────

def test_imports() -> bool:
    """gpr_engine importa sem tocar GPRPy no sys.modules."""
    before = set(sys.modules.keys())

    try:
        from gpr_engine._types import DZTData  # noqa: F401
        from gpr_engine.reader import DZTReader, DZTReadError  # noqa: F401
        from gpr_engine import DZTReader as _R, DZTData as _D  # noqa: F401
    except Exception as exc:
        _fail("importar gpr_engine", exc)
        return False
    _ok("gpr_engine._types, gpr_engine.reader e gpr_engine importam sem erro")

    after = set(sys.modules.keys())
    gprpy_mods = [m for m in (after - before) if "gprpy" in m.lower()]
    if gprpy_mods:
        _fail(f"GPRPy foi importado (não deveria): {gprpy_mods}")
        return False
    _ok("GPRPy ausente em sys.modules após importar gpr_engine")
    return True


# ── Teste 2: instanciação do DZTReader ────────────────────────────────────

def test_instantiation() -> bool:
    """DZTReader instancia com parâmetros padrão e customizados."""
    try:
        from gpr_engine.reader import DZTReader

        r1 = DZTReader()
        assert r1.velocidade_operador_ms == 1.2, f"esperado 1.2, obtido {r1.velocidade_operador_ms}"
        assert r1.verbose is False, f"esperado False, obtido {r1.verbose}"

        r2 = DZTReader(velocidade_operador_ms=0.8, verbose=True)
        assert r2.velocidade_operador_ms == 0.8
        assert r2.verbose is True
    except Exception as exc:
        _fail("DZTReader instanciação", exc)
        return False
    _ok("DZTReader() instancia com parâmetros padrão e customizados")
    return True


# ── Teste 3: leitura de DZT real ─────────────────────────────────────────

def test_read_dzt(dzt_path: Path) -> bool:
    """DZTReader.read() retorna DZTData correto para arquivo real."""
    import numpy as np
    from gpr_engine.reader import DZTReader
    from gpr_engine._types import DZTData

    reader = DZTReader(verbose=False)
    try:
        data = reader.read(dzt_path)
    except Exception as exc:
        _fail(f"DZTReader.read({dzt_path.name})", exc)
        return False

    ok = True

    # --- tipo retornado ---
    if not isinstance(data, DZTData):
        _fail(f"tipo retornado é {type(data).__name__}, esperado DZTData")
        ok = False
    else:
        _ok("tipo retornado é DZTData")

    # --- arr_raw deve ser ndarray (não np.matrix) ---
    if type(data.arr_raw) is not np.ndarray:
        _fail(f"arr_raw é {type(data.arr_raw).__name__}, esperado np.ndarray")
        ok = False
    else:
        _ok("arr_raw é np.ndarray (não np.matrix)")

    # --- dtype float32 ---
    if data.arr_raw.dtype != np.float32:
        _fail(f"arr_raw.dtype == {data.arr_raw.dtype}, esperado float32")
        ok = False
    else:
        _ok("arr_raw.dtype == float32")

    # --- consistência de shape ---
    expected_shape = (data.n_samples, data.n_traces)
    if data.arr_raw.shape != expected_shape:
        _fail(f"shape arr_raw {data.arr_raw.shape} != ({data.n_samples}, {data.n_traces})")
        ok = False
    else:
        _ok(f"arr_raw.shape == ({data.n_samples}, {data.n_traces})  [amostras × traços]")

    # --- metadados positivos ---
    checks = [
        (data.twtt_max_ns > 0,       f"twtt_max_ns = {data.twtt_max_ns:.2f} ns"),
        (data.dt_ns > 0,             f"dt_ns = {data.dt_ns:.4f} ns"),
        (data.samp_freq_hz > 0,      f"samp_freq_hz = {data.samp_freq_hz:.3e} Hz"),
        (data.dist_total_m > 0,      f"dist_total_m = {data.dist_total_m:.2f} m  (modo: {data.modo_coleta})"),
        (data.antfreq_mhz >= 0,      f"antfreq_mhz = {data.antfreq_mhz} MHz"),
        (data.rhf_epsr > 0,          f"rhf_epsr = {data.rhf_epsr}"),
        (data.wave_speed_mns > 0,    f"wave_speed_mns = {data.wave_speed_mns:.4f} m/ns"),
        (data.dzt_filename != "",    f"dzt_filename = '{data.dzt_filename}'"),
        (len(data.dzt_sha256) == 64, f"dzt_sha256 = {data.dzt_sha256[:16]}..."),
    ]
    for condition, msg in checks:
        if condition:
            _ok(msg)
        else:
            _fail(msg)
            ok = False

    # --- arquivos auxiliares ---
    _ok(f"has_dzg = {data.has_dzg}")
    _ok(f"has_dzx = {data.has_dzx},  dzx_marks = {len(data.dzx_marks)} traços")

    return ok


# ── Ponto de entrada ──────────────────────────────────────────────────────

def main() -> int:
    dzt_arg = Path(sys.argv[1]) if len(sys.argv) > 1 else None

    print("=" * 60)
    print("gpr_engine  Fase 1 — testes de aceite")
    print("=" * 60)

    results: list[bool] = [
        test_imports(),
        test_instantiation(),
    ]

    if dzt_arg is not None:
        if not dzt_arg.exists():
            _fail(f"Arquivo DZT não encontrado: {dzt_arg}")
            results.append(False)
        else:
            results.append(test_read_dzt(dzt_arg))
    else:
        _skip("Nenhum caminho DZT fornecido — teste de leitura ignorado")
        _skip("  Uso: python -m gpr_engine._test_phase1 /caminho/PATIO___001.DZT")

    print("=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado: {passed}/{total} passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
