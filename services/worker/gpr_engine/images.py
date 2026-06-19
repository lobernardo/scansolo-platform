"""
Modulo de imagens PNG para o ScanSOLO GPR Engine.

Converte arrays numpy (saida de flows.py) em imagens PNG
compativeis com o pipeline atual:

  _bruta.png                        -> render_raw_image
  _radargrama_cientifico.png        -> render_scientific_image
  _radargrama_relatorio.png         -> render_report_image
  _radargrama_preview_radan_5m.png  -> render_radan_like_preview

Todas as funcoes:
  - Nao importam GPRPy nem dependem de pipeline_v1.py
  - Usam matplotlib Agg (nao interativo)
  - Criam o diretorio pai automaticamente
  - Nao modificam o array de entrada
  - Protegem contra NaN/Inf e array constante

Eixos: X = distancia horizontal (m), Y = profundidade (m), 0 no topo.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # nao interativo -- deve preceder import pyplot
import matplotlib.pyplot as plt
import numpy as np


# ---------------------------------------------------------------------------
# Helpers internos de normalizacao
# ---------------------------------------------------------------------------

def _sanitize_arr(arr: np.ndarray) -> np.ndarray:
    """
    Retorna copia float32 com NaN e Inf substituidos por 0.
    Nunca modifica o array original.
    """
    out = np.array(arr, dtype=np.float32)
    mask = ~np.isfinite(out)
    if mask.any():
        out[mask] = 0.0
    return out


def _compute_vrange(data: np.ndarray, contrast: float) -> tuple[float, float]:
    """
    Calcula vmin/vmax para imshow via clipping de percentil robusto.

    Formula:
      vm = percentil-99 dos valores absolutos finitos
      vmin = -vm / contrast
      vmax = +vm / contrast

    Casos especiais:
      - Array vazio ou somente NaN/Inf -> (-1.0, 1.0)
      - Array constante (vm=0)         -> (-1.0, 1.0)

    :param data:     Array 2-D (valores finitos ja esperados, mas tolerado)
    :param contrast: Fator divisor do intervalo (preset padrao: 2.5)
    :returns:        (vmin, vmax) como floats
    """
    finite = data[np.isfinite(data)].ravel()
    if len(finite) == 0:
        return -1.0, 1.0
    vm = float(np.percentile(np.abs(finite), 99))
    if vm == 0.0:
        return -1.0, 1.0
    c = max(0.1, float(contrast))
    return -vm / c, vm / c


# ---------------------------------------------------------------------------
# Funcao principal de renderizacao
# ---------------------------------------------------------------------------

def render_radargram(
    arr: np.ndarray,
    output_path: str | Path,
    dist_total_m: float,
    depth_max_m: float,
    title: str | None = None,
    colormap: str = "gray",
    contrast: float = 2.5,
    dpi: int = 150,
    footer_text: str | None = None,
    markers: list[dict[str, Any]] | None = None,
) -> Path:
    """
    Renderiza um radargrama GPR como PNG.

    Normalizacao visual:
      vmin/vmax = +/-percentil-99(|arr|) / contrast
      Array constante -> range (-1.0, 1.0) para imagem valida

    Eixo X: distancia horizontal (0 a dist_total_m).
    Eixo Y: profundidade (0 a depth_max_m), invertido (0 no topo).

    :param arr:          Array 2-D GPR (n_samples x n_traces)
    :param output_path:  Caminho de saida .png (dir pai criado automaticamente)
    :param dist_total_m: Distancia total da linha em metros (eixo X)
    :param depth_max_m:  Profundidade maxima em metros (eixo Y)
    :param title:        Titulo do grafico (None = sem titulo)
    :param colormap:     Colormap matplotlib (padrao: "gray")
    :param contrast:     Fator de contraste visual (padrao: 2.5)
    :param dpi:          Resolucao do PNG (padrao: 150)
    :param footer_text:  Rodape em laranja (ex: aviso preview RADAN)
    :param markers:      Lista de dicts {x_m, label, color} para anotacoes
    :returns:            Path do arquivo PNG salvo
    """
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    arr_clean = _sanitize_arr(arr)
    vmin, vmax = _compute_vrange(arr_clean, contrast)

    dist_m = max(float(dist_total_m), 1e-3)
    depth_m = max(float(depth_max_m), 1e-3)

    fig, ax = plt.subplots(figsize=(10, 4))

    ax.imshow(
        arr_clean,
        cmap=colormap,
        vmin=vmin,
        vmax=vmax,
        aspect="auto",
        extent=[0.0, dist_m, depth_m, 0.0],
        origin="upper",
    )
    ax.set_ylim(depth_m, 0.0)
    ax.set_xlim(0.0, dist_m)
    ax.set_xlabel("Distance (m)")
    ax.set_ylabel("Depth (m)")

    if title:
        ax.set_title(title)

    if markers:
        for m in markers:
            x_m = float(m.get("x_m", 0.0))
            color = str(m.get("color", "red"))
            label = m.get("label", None)
            ax.axvline(x=x_m, color=color, linewidth=1.0, alpha=0.8, label=label)

    if footer_text:
        fig.text(
            0.5, 0.005,
            str(footer_text),
            ha="center", va="bottom",
            fontsize=7,
            color="darkorange",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.85),
        )

    fig.savefig(str(out_path), dpi=int(dpi), bbox_inches="tight")
    plt.close(fig)

    return out_path


# ---------------------------------------------------------------------------
# Funcoes de conveniencia por tipo de imagem
# ---------------------------------------------------------------------------

def render_raw_image(
    arr_raw: np.ndarray,
    output_path: str | Path,
    dist_total_m: float,
    depth_max_m: float,
    **kwargs: Any,
) -> Path:
    """
    Radargrama bruto (sem filtros -- _bruta.png).

    Wrapper de render_radargram com title="Raw".
    """
    kwargs.setdefault("title", "Raw")
    return render_radargram(arr_raw, output_path, dist_total_m, depth_max_m, **kwargs)


def render_scientific_image(
    arr_cientifico: np.ndarray,
    output_path: str | Path,
    dist_total_m: float,
    depth_max_m: float,
    **kwargs: Any,
) -> Path:
    """
    Radargrama cientifico (dewow+bp+tpow, sem AGC -- _radargrama_cientifico.png).

    Wrapper de render_radargram com title="Scientific".
    """
    kwargs.setdefault("title", "Scientific")
    return render_radargram(arr_cientifico, output_path, dist_total_m, depth_max_m, **kwargs)


def render_report_image(
    arr_relatorio: np.ndarray,
    output_path: str | Path,
    dist_total_m: float,
    depth_max_m: float,
    **kwargs: Any,
) -> Path:
    """
    Radargrama de relatorio com AGC (_radargrama_relatorio.png / _processada.png).

    Wrapper de render_radargram com title="Report".
    """
    kwargs.setdefault("title", "Report")
    return render_radargram(arr_relatorio, output_path, dist_total_m, depth_max_m, **kwargs)


def render_radan_like_preview(
    arr_preview: np.ndarray,
    output_path: str | Path,
    dist_total_m: float,
    depth_max_m: float,
    footer_text: str | None = None,
    **kwargs: Any,
) -> Path:
    """
    Preview RADAN-like (_radargrama_preview_radan_5m.png).

    Wrapper de render_radargram. footer_text opcional (aviso laranja no rodape).
    Sem hardcode: o chamador passa o texto de aviso quando necessario.
    """
    kwargs.setdefault("title", "Preview RADAN")
    return render_radargram(
        arr_preview, output_path, dist_total_m, depth_max_m,
        footer_text=footer_text, **kwargs,
    )
