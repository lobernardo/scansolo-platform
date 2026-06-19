"""
Fase 5 -- testes de aceite do gpr_engine.images.

Valida com arrays sinteticos:
  - render_radargram salva PNG existente e nao vazio
  - funciona com array normal
  - funciona com array constante
  - funciona com NaN/Inf no input
  - cria diretorio pai automaticamente
  - aceita colormap gray e outros
  - aceita dpi configuravel
  - extent nao crasha com dist_total_m/depth_max_m validos
  - input original nao e modificado
  - todas as funcoes de conveniencia funcionam
  - footer_text renderiza sem crash
  - markers aceitos sem crash
  - nenhum import de GPRPy

Uso:
  python -m gpr_engine._test_phase5
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

import numpy as np


# ---------------------------------------------------------------------------
# Constantes e helpers
# ---------------------------------------------------------------------------

N_SAMPLES = 128
N_TRACES  = 40
DIST_M    = 8.5
DEPTH_M   = 3.0

_PNG_SIG = b"\x89PNG\r\n\x1a\n"  # assinatura padrao PNG RFC 2083


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"  [FAIL] {msg}{suffix}", file=sys.stderr)


def _section(name: str) -> None:
    print(f"\n-- {name} --")


def _make(seed: int = 42) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(
        (N_SAMPLES, N_TRACES)
    ).astype(np.float32)


def _tmpdir() -> Path:
    return Path(tempfile.mkdtemp())


def _is_valid_png(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with open(path, "rb") as fh:
        sig = fh.read(8)
    return sig == _PNG_SIG


# ---------------------------------------------------------------------------
# 1. Imports e ausencia de GPRPy
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    _section("imports")
    ok = True
    try:
        from gpr_engine.images import (  # noqa: F401
            render_radargram,
            render_raw_image,
            render_scientific_image,
            render_report_image,
            render_radan_like_preview,
        )
    except Exception as exc:
        _fail("importar gpr_engine.images", str(exc)); return False
    _ok("gpr_engine.images importa 5 funcoes esperadas")

    gprpy = [m for m in sys.modules if "gprpy" in m.lower()]
    if gprpy:
        _fail(f"GPRPy importado: {gprpy}"); ok = False
    else:
        _ok("GPRPy nao importado por gpr_engine.images")
    return ok


# ---------------------------------------------------------------------------
# 2. Render basico -- PNG valido e nao vazio
# ---------------------------------------------------------------------------

def test_render_basic() -> bool:
    _section("render_radargram basico")
    from gpr_engine.images import render_radargram

    out = _tmpdir() / "basic.png"
    arr = _make()
    ok = True

    try:
        result = render_radargram(arr, out, DIST_M, DEPTH_M)
    except Exception as exc:
        _fail("render_radargram lancou excecao", str(exc)); return False

    if result == out:
        _ok("retorna Path do arquivo de saida")
    else:
        _fail(f"retorno {result} != {out}"); ok = False

    if out.exists():
        _ok(f"arquivo criado: {out.name}")
    else:
        _fail("arquivo PNG nao foi criado"); ok = False

    if out.stat().st_size > 0:
        _ok(f"tamanho > 0: {out.stat().st_size} bytes")
    else:
        _fail("arquivo PNG vazio"); ok = False

    if _is_valid_png(out):
        _ok("assinatura PNG valida")
    else:
        _fail("assinatura PNG invalida"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 3. Array constante -- nao crasha
# ---------------------------------------------------------------------------

def test_constant_array() -> bool:
    _section("array constante")
    from gpr_engine.images import render_radargram

    out = _tmpdir() / "constant.png"
    arr = np.full((N_SAMPLES, N_TRACES), 3.14, dtype=np.float32)
    ok = True

    try:
        render_radargram(arr, out, DIST_M, DEPTH_M)
    except Exception as exc:
        _fail("array constante: excecao inesperada", str(exc)); return False
    _ok("array constante: sem excecao")

    if _is_valid_png(out):
        _ok("array constante: PNG valido")
    else:
        _fail("array constante: PNG invalido ou vazio"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. Array com NaN e Inf -- nao crasha
# ---------------------------------------------------------------------------

def test_nan_inf_array() -> bool:
    _section("array com NaN e Inf")
    from gpr_engine.images import render_radargram

    ok = True
    arr = _make(seed=10).copy()
    arr[0, 0] = float("nan")
    arr[1, 0] = float("inf")
    arr[2, 0] = float("-inf")

    out = _tmpdir() / "nan_inf.png"
    try:
        render_radargram(arr, out, DIST_M, DEPTH_M)
    except Exception as exc:
        _fail("NaN/Inf: excecao inesperada", str(exc)); return False
    _ok("NaN/Inf: sem excecao")

    if _is_valid_png(out):
        _ok("NaN/Inf: PNG valido")
    else:
        _fail("NaN/Inf: PNG invalido ou vazio"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. Criacao automatica do diretorio pai
# ---------------------------------------------------------------------------

def test_parent_dir_created() -> bool:
    _section("criacao automatica do diretorio pai")
    from gpr_engine.images import render_radargram

    base = _tmpdir()
    out = base / "deep" / "subdir" / "radargram.png"
    assert not out.parent.exists(), "diretorio ja existia antes do teste"
    ok = True

    try:
        render_radargram(_make(), out, DIST_M, DEPTH_M)
    except Exception as exc:
        _fail("criacao de dir pai: excecao", str(exc)); return False

    if out.parent.exists():
        _ok("diretorio pai criado automaticamente")
    else:
        _fail("diretorio pai NAO foi criado"); ok = False

    if _is_valid_png(out):
        _ok("PNG gerado no diretorio criado")
    else:
        _fail("PNG nao encontrado no diretorio criado"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 6. Colormap configuravel
# ---------------------------------------------------------------------------

def test_colormap_options() -> bool:
    _section("colormap configuravel")
    from gpr_engine.images import render_radargram

    ok = True
    arr = _make(seed=20)
    base = _tmpdir()

    for cmap in ("gray", "seismic", "viridis", "RdBu"):
        out = base / f"cmap_{cmap}.png"
        try:
            render_radargram(arr, out, DIST_M, DEPTH_M, colormap=cmap)
        except Exception as exc:
            _fail(f"colormap={cmap}: excecao", str(exc)); ok = False; continue
        if _is_valid_png(out):
            _ok(f"colormap={cmap}: PNG valido")
        else:
            _fail(f"colormap={cmap}: PNG invalido"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 7. DPI configuravel
# ---------------------------------------------------------------------------

def test_dpi_configurable() -> bool:
    _section("dpi configuravel")
    from gpr_engine.images import render_radargram

    ok = True
    arr = _make(seed=30)
    base = _tmpdir()

    for dpi in (72, 150, 300):
        out = base / f"dpi_{dpi}.png"
        try:
            render_radargram(arr, out, DIST_M, DEPTH_M, dpi=dpi)
        except Exception as exc:
            _fail(f"dpi={dpi}: excecao", str(exc)); ok = False; continue
        if _is_valid_png(out):
            _ok(f"dpi={dpi}: PNG valido ({out.stat().st_size} bytes)")
        else:
            _fail(f"dpi={dpi}: PNG invalido"); ok = False

    # DPI maior deve gerar imagem com mais pixels (lido do cabecalho PNG)
    import struct

    def _png_dims(p: Path) -> tuple[int, int]:
        with open(p, "rb") as fh:
            fh.read(8)   # assinatura PNG
            fh.read(4)   # tamanho do chunk IHDR
            fh.read(4)   # "IHDR"
            w = struct.unpack(">I", fh.read(4))[0]
            h = struct.unpack(">I", fh.read(4))[0]
        return w, h

    w72,  h72  = _png_dims(base / "dpi_72.png")
    w300, h300 = _png_dims(base / "dpi_300.png")
    if w300 > w72 and h300 > h72:
        _ok(f"dpi=300 ({w300}x{h300}px) > dpi=72 ({w72}x{h72}px): DPI afeta pixels")
    else:
        _fail(f"dpi=300 ({w300}x{h300}px) nao maior que dpi=72 ({w72}x{h72}px)"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 8. Varios valores de dist_total_m e depth_max_m
# ---------------------------------------------------------------------------

def test_extent_values() -> bool:
    _section("dist_total_m e depth_max_m variados")
    from gpr_engine.images import render_radargram

    ok = True
    arr = _make(seed=40)
    base = _tmpdir()

    cases = [
        (5.0,   3.0,  "typical"),
        (100.0, 10.0, "large"),
        (0.5,   0.2,  "small"),
        (0.0,   3.0,  "dist_zero"),
        (5.0,   0.0,  "depth_zero"),
    ]
    for dist, depth, label in cases:
        out = base / f"extent_{label}.png"
        try:
            render_radargram(arr, out, dist, depth)
        except Exception as exc:
            _fail(f"{label} dist={dist} depth={depth}: excecao", str(exc)); ok = False; continue
        if _is_valid_png(out):
            _ok(f"{label}: PNG valido")
        else:
            _fail(f"{label}: PNG invalido"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 9. Input nao modificado
# ---------------------------------------------------------------------------

def test_input_not_modified() -> bool:
    _section("input nao modificado")
    from gpr_engine.images import render_radargram

    arr = _make(seed=50)
    snap = arr.copy()
    out = _tmpdir() / "immut.png"
    ok = True

    # Array com NaN para testar que a sanitizacao interna nao vaza
    arr_with_nan = arr.copy()
    arr_with_nan[5, 5] = float("nan")
    snap_nan = arr_with_nan.copy()

    render_radargram(arr, out, DIST_M, DEPTH_M)
    if np.array_equal(arr, snap):
        _ok("arr sem NaN: nao modificado")
    else:
        _fail("arr sem NaN: modificado in-place"); ok = False

    render_radargram(arr_with_nan, out, DIST_M, DEPTH_M)
    if np.array_equal(arr_with_nan, snap_nan, equal_nan=True):
        _ok("arr com NaN: nao modificado")
    else:
        _fail("arr com NaN: modificado in-place"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 10. Funcoes de conveniencia
# ---------------------------------------------------------------------------

def test_convenience_wrappers() -> bool:
    _section("funcoes de conveniencia")
    from gpr_engine.images import (
        render_raw_image,
        render_report_image,
        render_scientific_image,
        render_radan_like_preview,
    )

    arr = _make(seed=60)
    base = _tmpdir()
    ok = True

    wrappers = [
        ("render_raw_image",         render_raw_image,         {}),
        ("render_scientific_image",  render_scientific_image,  {}),
        ("render_report_image",      render_report_image,      {}),
        ("render_radan_like_preview",render_radan_like_preview,{"footer_text": "WARNING: preview only"}),
    ]

    for name, fn, extra in wrappers:
        out = base / f"{name}.png"
        try:
            fn(arr, out, DIST_M, DEPTH_M, **extra)
        except Exception as exc:
            _fail(f"{name}: excecao", str(exc)); ok = False; continue
        if _is_valid_png(out):
            _ok(f"{name}: PNG valido")
        else:
            _fail(f"{name}: PNG invalido"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 11. footer_text renderiza sem crash
# ---------------------------------------------------------------------------

def test_footer_text() -> bool:
    _section("footer_text")
    from gpr_engine.images import render_radargram

    out = _tmpdir() / "footer.png"
    ok = True
    try:
        render_radargram(
            _make(seed=70), out, DIST_M, DEPTH_M,
            footer_text="AVISO: preview RADAN 5m -- nao usar como radargrama cientifico"
        )
    except Exception as exc:
        _fail("footer_text: excecao", str(exc)); return False
    if _is_valid_png(out):
        _ok("footer_text: PNG valido")
    else:
        _fail("footer_text: PNG invalido"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 12. markers aceitos sem crash
# ---------------------------------------------------------------------------

def test_markers() -> bool:
    _section("markers")
    from gpr_engine.images import render_radargram

    out = _tmpdir() / "markers.png"
    ok = True
    markers = [
        {"x_m": 1.5, "color": "red",   "label": "alvo 1"},
        {"x_m": 4.0, "color": "blue",  "label": "alvo 2"},
        {"x_m": 7.2, "color": "green"},
    ]
    try:
        render_radargram(_make(seed=80), out, DIST_M, DEPTH_M, markers=markers)
    except Exception as exc:
        _fail("markers: excecao", str(exc)); return False
    if _is_valid_png(out):
        _ok("markers: PNG valido")
    else:
        _fail("markers: PNG invalido"); ok = False

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 5 -- testes de aceite (images.py)")
    print("=" * 60)

    results = [
        test_imports(),
        test_render_basic(),
        test_constant_array(),
        test_nan_inf_array(),
        test_parent_dir_created(),
        test_colormap_options(),
        test_dpi_configurable(),
        test_extent_values(),
        test_input_not_modified(),
        test_convenience_wrappers(),
        test_footer_text(),
        test_markers(),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado: {passed}/{total} grupos passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
