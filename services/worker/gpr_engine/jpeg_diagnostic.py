"""
JPEG Diagnostic Tool — paridade visual DZT vs referência RADAN.

Uso:
  python -m gpr_engine.jpeg_diagnostic \\
      --dzt   PATH_TO_FILE.DZT \\
      --ref   PATH_TO_REFERENCE.JPG \\
      --out   ./diag_output \\
      [--velocity 0.10] \\
      [--depth-max 5.0] \\
      [--top-n 5]

Outputs em <out>/:
  <stem>_ref.png                — referência redimensionada para comparação
  <stem>_<recipe>.png           — cada receita renderizada
  <stem>_qa_metrics.json        — correlações + ranking top-N
  <stem>_ranking.txt            — relatório human-readable

Receitas testadas (fixas, nunca hardcoded para um cliente específico):
  raw_linear        — arr_raw, normalizacao linear_percentile
  raw_symlog        — arr_raw, SymLogNorm
  scientific_linear — arr_dewow_bp_tpow, linear_percentile
  scientific_symlog — arr_dewow_bp_tpow, SymLogNorm
  readgssi_ref      — arr_raw com bgremoval_readgssi, SymLogNorm (idêntico ao readgssi)
  report_linear     — arr_relatorio (bgr+tpow+agc), linear_percentile
  report_symlog     — arr_relatorio, SymLogNorm
  inverted_*        — variantes com polarity=inverted (cmap_r)

Métrica: correlacao de Pearson pixel-a-pixel (resize ref para mesmo shape das PNGs geradas).
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from PIL import Image

# gpr_engine imports
from gpr_engine.reader import DZTReader
from gpr_engine.filters import (
    dewow as apply_dewow,
    bandpass as apply_bandpass,
    bgremoval as apply_bgremoval,
    tpow as apply_tpow,
    agc as apply_agc,
    bgremoval_readgssi,
)
from gpr_engine.images import render_radargram, render_radargram_readgssi_reference


# ---------------------------------------------------------------------------
# Receitas de renderização
# ---------------------------------------------------------------------------

_RECIPES: list[dict] = [
    {"name": "raw_linear",          "array": "raw",        "normalization": "linear_percentile", "polarity": "normal"},
    {"name": "raw_linear_inv",      "array": "raw",        "normalization": "linear_percentile", "polarity": "inverted"},
    {"name": "raw_symlog",          "array": "raw",        "normalization": "symlog",            "polarity": "normal"},
    {"name": "raw_symlog_inv",      "array": "raw",        "normalization": "symlog",            "polarity": "inverted"},
    {"name": "dewow_linear",        "array": "dewow",      "normalization": "linear_percentile", "polarity": "normal"},
    {"name": "dewow_symlog",        "array": "dewow",      "normalization": "symlog",            "polarity": "normal"},
    {"name": "scientific_linear",   "array": "scientific", "normalization": "linear_percentile", "polarity": "normal"},
    {"name": "scientific_linear_inv","array": "scientific", "normalization": "linear_percentile", "polarity": "inverted"},
    {"name": "scientific_symlog",   "array": "scientific", "normalization": "symlog",            "polarity": "normal"},
    {"name": "scientific_tpow",     "array": "scientific", "normalization": "linear_percentile", "polarity": "normal"},
    {"name": "report_linear",       "array": "report",     "normalization": "linear_percentile", "polarity": "normal"},
    {"name": "report_symlog",       "array": "report",     "normalization": "symlog",            "polarity": "normal"},
    {"name": "readgssi_ref",        "array": "readgssi",   "normalization": "readgssi",          "polarity": "normal"},
]


# ---------------------------------------------------------------------------
# Métricas
# ---------------------------------------------------------------------------

def _pearson_corr(a: np.ndarray, b: np.ndarray) -> float:
    """Correlação de Pearson pixel-a-pixel entre dois arrays 2D do mesmo shape."""
    a_flat = a.flatten().astype(np.float64)
    b_flat = b.flatten().astype(np.float64)
    if a_flat.std() < 1e-9 or b_flat.std() < 1e-9:
        return 0.0
    return float(np.corrcoef(a_flat, b_flat)[0, 1])


def _load_gray(path: Path, target_shape: tuple[int, int] | None = None) -> np.ndarray:
    """Carrega imagem como array float64 em escala de cinza; redimensiona opcionalmente."""
    img = Image.open(path).convert("L")
    if target_shape is not None:
        # target_shape = (height, width); PIL.resize = (width, height)
        img = img.resize((target_shape[1], target_shape[0]), Image.LANCZOS)
    return np.array(img, dtype=np.float64)


def _load_png_gray(path: Path, target_shape: tuple[int, int]) -> np.ndarray:
    return _load_gray(path, target_shape)


# ---------------------------------------------------------------------------
# Construção de arrays de cada estágio
# ---------------------------------------------------------------------------

def _build_arrays(
    arr_raw: np.ndarray,
    velocity_mns: float,
    twtt_max_ns: float,
    samp_freq_hz: float,
    config: dict,
) -> dict[str, np.ndarray]:
    """Constrói todos os arrays de estágio a partir do raw."""
    dewow_window = int(config.get("dewow_window", 5))
    bp_low   = float(config.get("bandpass_low_mhz",  80))
    bp_high  = float(config.get("bandpass_high_mhz", 500))
    bp_order = int(config.get("bandpass_order", 5))
    bgr_win  = int(config.get("bgremoval_traces", 30))
    tpow_pow = float(config.get("tpow_power", 0.5))
    agc_win  = int(config.get("agc_window", 150))

    arr_dewow = apply_dewow(arr_raw, dewow_window)
    if bp_low > 0:
        arr_bp = apply_bandpass(arr_dewow, samp_freq_hz, bp_low, bp_high, bp_order)
    else:
        arr_bp = arr_dewow.copy()

    arr_scientific = apply_tpow(arr_bp.copy(), tpow_pow)

    arr_bgr       = apply_bgremoval(arr_bp.copy(), bgr_win)
    arr_sem_agc   = apply_tpow(arr_bgr.copy(), tpow_pow)
    arr_report    = apply_agc(arr_sem_agc.copy(), agc_win)

    arr_readgssi  = bgremoval_readgssi(arr_raw, window=0)

    return {
        "raw":        arr_raw,
        "dewow":      arr_dewow,
        "scientific": arr_scientific,
        "report":     arr_report,
        "readgssi":   arr_readgssi,
    }


# ---------------------------------------------------------------------------
# Renderização de uma receita → PNG
# ---------------------------------------------------------------------------

def _render_recipe(
    recipe: dict,
    arrays: dict[str, np.ndarray],
    out_path: Path,
    dist_total_m: float,
    depth_max_m: float,
    dpi: int = 150,
) -> Path:
    arr = arrays[recipe["array"]]
    if recipe["normalization"] == "readgssi":
        return render_radargram_readgssi_reference(
            arr, out_path,
            dist_total_m=dist_total_m,
            depth_max_m=depth_max_m,
            dpi=dpi,
            title=recipe["name"],
        )
    else:
        return render_radargram(
            arr, out_path,
            dist_total_m=dist_total_m,
            depth_max_m=depth_max_m,
            normalization=recipe["normalization"],
            polarity=recipe["polarity"],
            dpi=dpi,
            title=recipe["name"],
        )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def run_diagnostic(
    dzt_path: Path,
    ref_path: Path,
    out_dir: Path,
    velocity_mns: float = 0.10,
    depth_max_m: float | None = None,
    top_n: int = 5,
    config: dict | None = None,
) -> dict:
    """
    Executa diagnóstico completo de paridade visual entre DZT e JPEG de referência.

    :returns: dict com ranking completo e metadados.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = config or {}
    stem = dzt_path.stem

    # 1. Ler DZT
    reader = DZTReader()
    dzt = reader.read(dzt_path)
    arr_raw = dzt.arr_raw
    twtt_max_ns = float(dzt.twtt_max_ns)
    samp_freq_hz = float(dzt.samp_freq_hz)
    dist_total_m = float(dzt.dist_total_m)

    physical_depth_m = twtt_max_ns * velocity_mns / 2.0
    if depth_max_m is None:
        depth_max_m = physical_depth_m

    print(f"[diag] DZT: {dzt_path.name}")
    print(f"       antfreq={dzt.antfreq_mhz} MHz  traces={dzt.n_traces}  samples={dzt.n_samples}")
    print(f"       twtt_max={twtt_max_ns:.2f} ns  dist={dist_total_m:.2f} m  depth={physical_depth_m:.3f} m")

    # 2. Construir arrays
    arrays = _build_arrays(arr_raw, velocity_mns, twtt_max_ns, samp_freq_hz, cfg)

    # 3. Renderizar referência como PNG (para comparação com shape uniforme)
    ref_img_path = out_dir / f"{stem}_ref.png"
    ref_pil = Image.open(ref_path).convert("L")
    ref_pil.save(str(ref_img_path))
    ref_size = (ref_pil.height, ref_pil.width)
    print(f"       ref={ref_path.name}  size={ref_pil.size}")

    # 4. Renderizar e medir cada receita
    results = []
    for recipe in _RECIPES:
        recipe_path = out_dir / f"{stem}_{recipe['name']}.png"
        try:
            _render_recipe(recipe, arrays, recipe_path, dist_total_m, depth_max_m)
        except Exception as exc:
            print(f"  [SKIP] {recipe['name']}: {exc}")
            continue

        # Correlação com a referência
        try:
            recipe_arr  = _load_png_gray(recipe_path, ref_size)
            ref_arr     = _load_gray(ref_path, ref_size)
            corr = _pearson_corr(recipe_arr, ref_arr)
        except Exception as exc:
            print(f"  [WARN] corr {recipe['name']}: {exc}")
            corr = 0.0

        results.append({
            "recipe":  recipe["name"],
            "array":   recipe["array"],
            "norm":    recipe["normalization"],
            "polarity":recipe["polarity"],
            "corr":    round(corr, 6),
            "png":     str(recipe_path),
        })
        print(f"  {recipe['name']:30s}  corr={corr:+.4f}")

    # 5. Ranking
    ranked = sorted(results, key=lambda r: r["corr"], reverse=True)
    top = ranked[:top_n]

    # 6. Relatório human-readable
    report_lines = [
        f"JPEG Diagnostic — {stem}",
        f"DZT:       {dzt_path}",
        f"Referencia:{ref_path}",
        f"Data:      {datetime.now(timezone.utc).isoformat()}",
        f"velocity:  {velocity_mns} m/ns",
        f"depth_max: {depth_max_m:.3f} m (fisica={physical_depth_m:.3f} m)",
        "",
        f"TOP {top_n} RECEITAS (por correlação de Pearson pixel-a-pixel):",
    ]
    for i, r in enumerate(top, 1):
        report_lines.append(
            f"  #{i}: {r['recipe']:30s}  corr={r['corr']:+.4f}"
        )
    report_lines += [
        "",
        "RANKING COMPLETO:",
    ]
    for r in ranked:
        report_lines.append(
            f"  {r['recipe']:30s}  corr={r['corr']:+.4f}  array={r['array']}  "
            f"norm={r['norm']}  pol={r['polarity']}"
        )

    report_path = out_dir / f"{stem}_ranking.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"\n[diag] Relatório: {report_path}")

    # 7. qa_metrics.json
    metrics = {
        "dzt":            str(dzt_path),
        "ref":            str(ref_path),
        "stem":           stem,
        "timestamp_utc":  datetime.now(timezone.utc).isoformat(),
        "antfreq_mhz":    dzt.antfreq_mhz,
        "n_traces":       dzt.n_traces,
        "n_samples":      dzt.n_samples,
        "dist_total_m":   dist_total_m,
        "physical_depth_m": physical_depth_m,
        "display_depth_m":  depth_max_m,
        "velocity_mns":   velocity_mns,
        "top_n":          top_n,
        "top":            top,
        "ranking":        ranked,
    }
    metrics_path = out_dir / f"{stem}_qa_metrics.json"
    metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[diag] Métricas: {metrics_path}")
    print(f"\n[diag] Melhor receita: {ranked[0]['recipe']}  corr={ranked[0]['corr']:+.4f}")

    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Diagnóstico de paridade visual DZT vs referência RADAN.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--dzt",      required=True,  type=Path, help="Arquivo .DZT de entrada")
    p.add_argument("--ref",      required=True,  type=Path, help="JPEG/PNG de referência (ex: output RADAN)")
    p.add_argument("--out",      required=True,  type=Path, help="Diretório de saída")
    p.add_argument("--velocity", default=0.10,   type=float, help="Velocity em m/ns (padrão: 0.10)")
    p.add_argument("--depth-max",default=None,   type=float, dest="depth_max", help="Profundidade máxima display (m)")
    p.add_argument("--top-n",    default=5,      type=int,   help="Top N receitas no relatório (padrão: 5)")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_diagnostic(
        dzt_path=args.dzt.resolve(),
        ref_path=args.ref.resolve(),
        out_dir=args.out.resolve(),
        velocity_mns=args.velocity,
        depth_max_m=args.depth_max,
        top_n=args.top_n,
    )
