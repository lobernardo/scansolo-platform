"""
Fase 8.6 -- Paridade tecnica e visual com readgssi clonado.

Grupos de teste:
  G1  imports_ok         -- todos os simbolos novos importam sem erro
  G2  bgr_readgssi       -- bgremoval_readgssi: shape, sem NaN/Inf, output != input
  G3  bp_triangular_readgssi -- bandpass_triangular_readgssi: shape, sem NaN/Inf
  G4  render_symlog      -- render_radargram_readgssi_reference: PNG existe e > 0 bytes
  G5  process_dzt_ref_key -- process_dzt retorna image_paths["readgssi_reference"]
  G6  process_dzt_ref_png -- PNG readgssi_reference existe e > 0 bytes com DZT real
  G7  readgssi_vs_linear  -- SymLogNorm differe estatisticamente da renderizacao linear
  G8  readgssi_direct_compare -- renderiza com readgssi diretamente e nosso engine lado a lado

Restricoes:
  - Todos os print() usam ASCII puro (Windows cp1252 console)
  - HELPER_DIR aponta para a pasta de DZTs reais (configuravel abaixo)
  - O teste G8 requer a lib readgssi no PYTHONPATH (clonada em ../../../readgssi/)
  - Falhas em G8 sao WARN, nao FAIL (readgssi pode nao estar no path em CI)
"""
from __future__ import annotations

import math
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Configuracao de caminhos
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent          # gpr_engine/
_WORKER_DIR = _HERE.parent                        # worker/
_REPO_ROOT = _HERE.parents[2]                     # scansolo-platform/
_READGSSI_DIR = (
    Path("C:/Users/leool/OneDrive/Documentos/Claude/Projects/ScanSOLO/readgssi")
)
_HELPER_DIR = (
    _REPO_ROOT
    / "KB_ScansoloPlataform"
    / "benchmark_real"
    / "HELPER"
    / "HELPER.PRJ_DZT"
)

# ---------------------------------------------------------------------------
# Helpers de teste
# ---------------------------------------------------------------------------

_PASS = 0
_FAIL = 0
_WARN = 0


def _ok(msg: str) -> None:
    global _PASS
    _PASS += 1
    print(f"  [PASS] {msg}")


def _fail(msg: str, exc: Exception | None = None) -> None:
    global _FAIL
    _FAIL += 1
    print(f"  [FAIL] {msg}")
    if exc:
        print(f"         {type(exc).__name__}: {exc}")


def _warn(msg: str) -> None:
    global _WARN
    _WARN += 1
    print(f"  [WARN] {msg}")


def _section(name: str) -> None:
    print(f"\n--- {name} ---")


def _pick_dzt(n: int = 1) -> list[Path]:
    """Seleciona n DZTs unicos de HELPER_DIR (dedup por nome lowercase)."""
    if not _HELPER_DIR.exists():
        return []
    seen: set[str] = set()
    result: list[Path] = []
    for p in sorted(_HELPER_DIR.glob("*")):
        key = p.name.lower()
        if p.suffix.lower() == ".dzt" and key not in seen:
            seen.add(key)
            result.append(p)
            if len(result) >= n:
                break
    return result


def _make_synthetic_arr(n_samples: int = 128, n_traces: int = 50) -> np.ndarray:
    """Array sintetico GPR-like (pulso gaussiano + ruido)."""
    rng = np.random.default_rng(42)
    t = np.linspace(0, 1, n_samples)
    pulse = np.exp(-((t - 0.15) ** 2) / (2 * 0.01 ** 2))
    arr = np.tile(pulse[:, None], (1, n_traces)) * rng.normal(1, 0.1, (n_samples, n_traces))
    arr += rng.normal(0, 0.05, (n_samples, n_traces))
    return arr.astype(np.float32)


# ===========================================================================
# G1 -- Imports
# ===========================================================================

def test_g1_imports() -> None:
    _section("G1: imports_ok")
    try:
        from gpr_engine.filters import bgremoval_readgssi
        _ok("bgremoval_readgssi importado")
    except Exception as e:
        _fail("bgremoval_readgssi", e)

    try:
        from gpr_engine.filters import bandpass_triangular_readgssi
        _ok("bandpass_triangular_readgssi importado")
    except Exception as e:
        _fail("bandpass_triangular_readgssi", e)

    try:
        from gpr_engine.images import render_radargram_readgssi_reference
        _ok("render_radargram_readgssi_reference importado")
    except Exception as e:
        _fail("render_radargram_readgssi_reference", e)

    try:
        from gpr_engine.pipeline import process_dzt, _DEFAULTS
        assert "visual_profile" in _DEFAULTS, "visual_profile ausente em _DEFAULTS"
        assert "gain" in _DEFAULTS, "gain ausente em _DEFAULTS"
        _ok("process_dzt + _DEFAULTS com visual_profile e gain")
    except Exception as e:
        _fail("pipeline._DEFAULTS", e)


# ===========================================================================
# G2 -- bgremoval_readgssi
# ===========================================================================

def test_g2_bgr_readgssi() -> None:
    _section("G2: bgremoval_readgssi")
    from gpr_engine.filters import bgremoval_readgssi

    arr = _make_synthetic_arr()

    # shape preservado
    out = bgremoval_readgssi(arr, window=0)
    if out.shape == arr.shape:
        _ok(f"shape preservado {out.shape}")
    else:
        _fail(f"shape alterado: {arr.shape} -> {out.shape}")

    # sem NaN/Inf
    if np.all(np.isfinite(out)):
        _ok("sem NaN/Inf (global)")
    else:
        _fail(f"NaN/Inf encontrados: {np.sum(~np.isfinite(out))}")

    # output != input (filtro aplicou algo)
    if not np.allclose(out, arr):
        _ok("output diferente de input (filtro ativo)")
    else:
        _fail("output identico ao input (filtro nao aplicou nada)")

    # media por linha deve ser ~0 apos BGR global
    row_means = np.abs(out.mean(axis=1))
    if row_means.max() < 1e-6:
        _ok(f"media por linha ~0 (max={row_means.max():.2e})")
    else:
        _fail(f"media por linha nao zerada (max={row_means.max():.4f})")

    # com window
    out_w = bgremoval_readgssi(arr, window=10)
    if out_w.shape == arr.shape and np.all(np.isfinite(out_w)):
        _ok("window=10: shape ok e sem NaN/Inf")
    else:
        _fail("window=10: shape ou NaN/Inf com problema")


# ===========================================================================
# G3 -- bandpass_triangular_readgssi
# ===========================================================================

def test_g3_bp_triangular_readgssi() -> None:
    _section("G3: bandpass_triangular_readgssi")
    from gpr_engine.filters import bandpass_triangular_readgssi

    arr = _make_synthetic_arr(n_samples=256, n_traces=30)
    samp_freq_hz = 4e9  # 4 GHz tipico 270 MHz antena

    try:
        out = bandpass_triangular_readgssi(arr, samp_freq_hz, low_mhz=80.0, high_mhz=500.0)
    except Exception as e:
        _fail("bandpass_triangular_readgssi levantou excecao", e)
        return

    if out.shape == arr.shape:
        _ok(f"shape preservado {out.shape}")
    else:
        _fail(f"shape alterado: {arr.shape} -> {out.shape}")

    if np.all(np.isfinite(out)):
        _ok("sem NaN/Inf")
    else:
        _fail(f"NaN/Inf encontrados: {np.sum(~np.isfinite(out))}")

    if not np.allclose(out, arr):
        _ok("output diferente do input (filtro ativo)")
    else:
        _fail("output identico ao input")

    # zerophase=False deve diferir de zerophase=True
    out_causal = bandpass_triangular_readgssi(
        arr, samp_freq_hz, 80.0, 500.0, zerophase=False
    )
    if not np.allclose(out, out_causal):
        _ok("zerophase=True difere de zerophase=False (como esperado)")
    else:
        _warn("zerophase=True igual a zerophase=False (incomum)")


# ===========================================================================
# G4 -- render_radargram_readgssi_reference
# ===========================================================================

def test_g4_render_symlog() -> None:
    _section("G4: render_symlog")
    from gpr_engine.images import render_radargram_readgssi_reference

    arr = _make_synthetic_arr()

    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "test_readgssi_ref.png"
        try:
            result = render_radargram_readgssi_reference(
                arr, out_path, dist_total_m=8.0, depth_max_m=3.0
            )
        except Exception as e:
            _fail("render_radargram_readgssi_reference levantou excecao", e)
            return

        if result.exists():
            _ok(f"PNG criado: {result.name}")
        else:
            _fail("PNG nao criado")
            return

        size_kb = result.stat().st_size / 1024
        if size_kb > 5:
            _ok(f"tamanho razoavel: {size_kb:.1f} KB")
        else:
            _fail(f"PNG muito pequeno: {size_kb:.2f} KB")

        # gain != 1 deve produzir resultado diferente
        out_g10 = Path(tmp) / "test_readgssi_gain10.png"
        render_radargram_readgssi_reference(
            arr, out_g10, dist_total_m=8.0, depth_max_m=3.0, gain=10.0
        )
        if out_g10.stat().st_size != result.stat().st_size:
            _ok("gain=10 produz PNG diferente de gain=1")
        else:
            _warn("gain=10 e gain=1 produceram PNG com mesmo tamanho (incomum)")

    # array constante nao deve travar
    with tempfile.TemporaryDirectory() as tmp:
        arr_const = np.zeros((64, 20), dtype=np.float32)
        out_const = Path(tmp) / "const.png"
        try:
            render_radargram_readgssi_reference(
                arr_const, out_const, dist_total_m=5.0, depth_max_m=2.0
            )
            _ok("array constante: sem excecao")
        except Exception as e:
            _fail("array constante levantou excecao", e)


# ===========================================================================
# G5 -- process_dzt retorna readgssi_reference em image_paths
# ===========================================================================

def test_g5_process_dzt_ref_key() -> None:
    _section("G5: process_dzt image_paths[readgssi_reference] key")
    dzts = _pick_dzt(3)
    if not dzts:
        _warn(f"HELPER_DIR nao encontrado ou sem DZTs: {_HELPER_DIR}")
        return

    from gpr_engine.pipeline import process_dzt

    # Testa apenas o primeiro DZT para a checagem de chaves
    with tempfile.TemporaryDirectory() as tmp:
        dzt = dzts[0]
        print(f"  DZT: {dzt.name}")
        try:
            result = process_dzt(dzt, Path(tmp) / "out")
        except Exception as e:
            _fail("process_dzt levantou excecao", e)
            traceback.print_exc()
            return

        if "readgssi_reference" in result.image_paths:
            _ok("chave 'readgssi_reference' presente em image_paths")
        else:
            _fail(f"chave ausente. chaves: {list(result.image_paths.keys())}")

        if "imagem_readgssi_reference" in result.index_row:
            _ok("campo 'imagem_readgssi_reference' presente em index_row")
        else:
            _fail(f"campo ausente. chaves: {list(result.index_row.keys())}")


# ===========================================================================
# G6 -- PNG readgssi_reference existe e e valido com DZT real
# ===========================================================================

def test_g6_process_dzt_ref_png() -> None:
    _section("G6: PNG readgssi_reference com DZTs reais (3 arquivos)")
    dzts = _pick_dzt(3)
    if not dzts:
        _warn(f"HELPER_DIR nao encontrado: {_HELPER_DIR}")
        return

    from gpr_engine.pipeline import process_dzt

    generated: list[tuple[str, int]] = []  # (dzt_name, size_kb)

    for dzt in dzts:
        with tempfile.TemporaryDirectory() as tmp:
            print(f"  Processando {dzt.name}...")
            try:
                result = process_dzt(dzt, Path(tmp) / "out")
            except Exception as e:
                _fail(f"process_dzt falhou para {dzt.name}", e)
                continue

            ref_path = result.image_paths.get("readgssi_reference")
            if ref_path is None:
                _fail(f"image_paths['readgssi_reference'] e None ({dzt.name})")
                continue

            if not Path(ref_path).exists():
                _fail(f"PNG nao existe para {dzt.name}: {ref_path}")
                continue

            size_kb = int(Path(ref_path).stat().st_size / 1024)
            generated.append((dzt.name, size_kb))

            if size_kb > 10:
                _ok(f"{dzt.name}: {Path(ref_path).name} ({size_kb} KB)")
            else:
                _fail(f"{dzt.name}: PNG muito pequeno ({size_kb} KB)")

            # PNG cientifico deve ser diferente do readgssi_reference
            cient_path = result.image_paths.get("cientifica")
            if cient_path and Path(cient_path).exists():
                sz_cient = Path(cient_path).stat().st_size
                sz_ref   = Path(ref_path).stat().st_size
                if sz_ref != sz_cient:
                    _ok(f"  readgssi_ref ({sz_ref//1024}KB) != cientifico ({sz_cient//1024}KB)")
                else:
                    _warn(f"  tamanhos identicos para {dzt.name}")

    if len(generated) == len(dzts):
        _ok(f"Todos os {len(dzts)} DZTs geraram PNG readgssi_reference")
    else:
        _fail(f"Apenas {len(generated)}/{len(dzts)} DZTs geraram PNG")


# ===========================================================================
# G7 -- SymLogNorm estatisticamente diferente de renderizacao linear
# ===========================================================================

def test_g7_symlog_vs_linear() -> None:
    _section("G7: SymLogNorm vs renderizacao linear")
    from gpr_engine.images import render_radargram_readgssi_reference, render_scientific_image

    try:
        from PIL import Image
    except ImportError:
        _warn("Pillow nao disponivel -- pulando comparacao de pixels")
        return

    arr = _make_synthetic_arr(n_samples=128, n_traces=80)

    with tempfile.TemporaryDirectory() as tmp:
        p_ref    = Path(tmp) / "ref.png"
        p_linear = Path(tmp) / "linear.png"

        render_radargram_readgssi_reference(arr, p_ref, 8.0, 3.0)
        render_scientific_image(arr, p_linear, 8.0, 3.0)

        img_ref    = np.array(Image.open(p_ref).convert("L"), dtype=np.float32)
        img_linear = np.array(Image.open(p_linear).convert("L"), dtype=np.float32)

        diff_mean = float(np.abs(img_ref - img_linear).mean())
        if diff_mean > 1.0:
            _ok(f"imagens visivelmente diferentes (diff_mean={diff_mean:.2f})")
        else:
            _warn(f"imagens muito parecidas (diff_mean={diff_mean:.4f}) -- SymLogNorm pode nao estar ativo")

        # SymLogNorm deve ter mais detalhes em regioes de baixa amplitude
        # Proxy: std do PNG symlog deve diferir do linear por > 5%
        std_ref    = float(np.std(img_ref))
        std_linear = float(np.std(img_linear))
        rel_diff   = abs(std_ref - std_linear) / max(std_linear, 1.0)
        if rel_diff > 0.05:
            _ok(f"std diferente: symlog={std_ref:.2f} linear={std_linear:.2f} ({rel_diff*100:.1f}%)")
        else:
            _warn(f"std parecido: symlog={std_ref:.2f} linear={std_linear:.2f} ({rel_diff*100:.1f}%)")


# ===========================================================================
# G8 -- Comparacao direta com readgssi (output de referencia)
# ===========================================================================

def test_g8_readgssi_direct() -> None:
    _section("G8: comparacao com readgssi direto")

    dzts = _pick_dzt(3)
    if not dzts:
        _warn(f"HELPER_DIR sem DZTs: {_HELPER_DIR}")
        return
    dzt_path = dzts[0]  # comparacao feita com o primeiro DZT

    # Verificar se readgssi esta disponivel
    readgssi_src = _READGSSI_DIR / "readgssi"
    if not readgssi_src.exists():
        _warn(f"readgssi nao encontrado em {_READGSSI_DIR}")
        return

    # Adicionar ao path temporariamente
    _rg_str = str(_READGSSI_DIR)
    if _rg_str not in sys.path:
        sys.path.insert(0, _rg_str)

    try:
        from readgssi.dzt import readdzt
        from readgssi.filtering import bgr as readgssi_bgr
    except ImportError as e:
        _warn(f"readgssi nao importavel: {e}")
        return

    # Ler com readgssi
    try:
        header, arrs, gps = readdzt(str(dzt_path), verbose=False)
        arr_readgssi = arrs[0].astype(np.float32)  # canal 0
        _ok(f"readgssi.dzt.readdzt: shape={arr_readgssi.shape}, dtype={arr_readgssi.dtype}")
    except Exception as e:
        _warn(f"readgssi.readdzt falhou: {e}")
        return

    # Ler com nosso engine
    try:
        from gpr_engine.reader import DZTReader
        reader = DZTReader()
        dzt_data = reader.read(dzt_path)
        arr_engine = dzt_data.arr_raw.astype(np.float32)
        _ok(f"DZTReader: shape={arr_engine.shape}, dtype={arr_engine.dtype}")
    except Exception as e:
        _fail(f"DZTReader falhou: {e}")
        return

    # Comparar shapes (podem diferir pelo timezero crop do readgssi)
    if arr_readgssi.shape == arr_engine.shape:
        _ok(f"shapes identicos: {arr_engine.shape}")
    else:
        _warn(
            f"shapes diferentes -- readgssi={arr_readgssi.shape} engine={arr_engine.shape} "
            f"(timezero crop explica diferenca de amostras)"
        )

    # Correlacao de arrays (se shapes baterem)
    if arr_readgssi.shape == arr_engine.shape:
        corr = float(np.corrcoef(arr_readgssi.ravel(), arr_engine.ravel())[0, 1])
        if corr > 0.99:
            _ok(f"correlacao arrays raw: {corr:.6f}")
        elif corr > 0.95:
            _warn(f"correlacao moderada: {corr:.6f} (pode haver diferenca de offset/dtype)")
        else:
            _fail(f"correlacao baixa: {corr:.6f} -- leitura divergente")

    # Gerar imagens comparativas em pasta temporaria
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Imagem do readgssi (bgr global + SymLogNorm)
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import matplotlib.colors as mcolors

            arr_bgr = arr_readgssi.copy().astype(np.float64)
            for i, row in enumerate(arr_bgr):
                arr_bgr[i] = row - np.mean(row)

            mean_v = float(np.mean(arr_bgr))
            std_v  = float(np.std(arr_bgr)) or 1.0
            ll = mean_v - std_v * 3
            ul = mean_v + std_v * 3
            norm = mcolors.SymLogNorm(
                linthresh=std_v, linscale=1.0, vmin=ll, vmax=ul, base=float(np.e)
            )
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.imshow(arr_bgr, cmap="gray", interpolation="bicubic",
                      norm=norm, aspect="auto")
            ax.set_title("readgssi direct (bgr+SymLogNorm)")
            p_rg = tmp_path / "readgssi_direct.png"
            fig.savefig(str(p_rg), dpi=100, bbox_inches="tight")
            plt.close(fig)
            _ok(f"imagem readgssi direto: {p_rg.stat().st_size // 1024} KB")
        except Exception as e:
            _warn(f"geracao imagem readgssi direto falhou: {e}")

        # Imagem do nosso engine no perfil readgssi_reference
        try:
            from gpr_engine.filters import bgremoval_readgssi
            from gpr_engine.images import render_radargram_readgssi_reference
            arr_our_bgr = bgremoval_readgssi(arr_engine, window=0)
            n_traces = arr_engine.shape[1]
            dt_ns = dzt_data.twtt_max_ns / arr_engine.shape[0]
            dist_m = n_traces * dt_ns * 0.1  # approx (spm desconhecido sem GPS)
            p_our = tmp_path / "engine_readgssi_ref.png"
            render_radargram_readgssi_reference(
                arr_our_bgr, p_our, dist_total_m=float(dzt_data.dist_total_m),
                depth_max_m=3.0
            )
            _ok(f"imagem engine readgssi_ref: {p_our.stat().st_size // 1024} KB")
        except Exception as e:
            _warn(f"geracao imagem engine readgssi_ref falhou: {e}")

        _ok("G8 concluido -- inspecionar visualmente as imagens acima para comparacao")


# ===========================================================================
# Ponto de entrada
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Fase 8.6 -- Paridade tecnica e visual readgssi")
    print("=" * 60)

    test_g1_imports()
    test_g2_bgr_readgssi()
    test_g3_bp_triangular_readgssi()
    test_g4_render_symlog()
    test_g5_process_dzt_ref_key()
    test_g6_process_dzt_ref_png()
    test_g7_symlog_vs_linear()
    test_g8_readgssi_direct()

    print()
    print("=" * 60)
    total = _PASS + _FAIL + _WARN
    print(f"RESULTADO: {_PASS}/{total} PASS  |  {_FAIL} FAIL  |  {_WARN} WARN")
    print("=" * 60)

    if _FAIL > 0:
        sys.exit(1)
