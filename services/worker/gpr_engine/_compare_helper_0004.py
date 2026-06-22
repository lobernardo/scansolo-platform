"""
_compare_helper_0004.py -- Pacote comparativo visual HELPER_0004.DZT (Fase 8.11).

Objetivo:
  Gerar 9 perfis visuais do mesmo arquivo DZT com diferentes configuracoes de
  filtros e normalizacao para diagnosticar por que o radargrama do cliente
  preserva camadas horizontais fortes enquanto o readgssi_reference atual
  remove/enfraquece essas camadas.

Hipotese principal:
  bgremoval_readgssi(window=0) subtrai a media horizontal por profundidade
  (axis=1), eliminando reflexoes horizontais continuas. O cliente provavelmente
  nao aplicou bgremoval ou usou um modo diferente.

Uso:
  cd services/worker
  python -m gpr_engine._compare_helper_0004

Saida:
  KB_ScansoloPlataform/benchmark_real/HELPER/comparativo_HELPER_0004/
    01_raw.png
    02_readgssi_ref_atual.png
    03_readgssi_sem_bgr.png          <- hipotese principal
    04_readgssi_bgr_windowed_30.png
    05_scientific.png
    06_report.png
    07_radan_preview_atual.png
    08_readgssi_sem_bgr_5m_stretch.png
    09_readgssi_sem_bgr_5m_zeropad.png
    contact_sheet.png
    contact_sheet.html
    README_COMPARATIVO.md
"""
from __future__ import annotations

import math
import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

_HERE = Path(__file__).resolve().parent
_WORKER = _HERE.parent
_REPO_ROOT = _HERE.parents[2]

sys.path.insert(0, str(_WORKER))

# ---------------------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------------------

_DZT = (
    _REPO_ROOT
    / "KB_ScansoloPlataform"
    / "benchmark_real"
    / "HELPER"
    / "HELPER.PRJ_DZT"
    / "HELPER_0004.DZT"
)

_OUT_DIR = (
    _REPO_ROOT
    / "KB_ScansoloPlataform"
    / "benchmark_real"
    / "HELPER"
    / "comparativo_HELPER_0004"
)

_VELOCITY_MNS = 0.10  # m/ns — solo standard
_DEPTH_TARGET  = 5.0  # m — escala visual do cliente

_AVISO_STRETCH = (
    "AVISO: escala visual 5 m | profundidade fisica real ≈ {real:.2f} m"
    " | dados esticados no eixo Y"
)
_AVISO_ZEROPAD = (
    "AVISO: 0–{real:.2f} m = dados reais | {real:.2f}–5.0 m = zero-padding"
    " (sem retorno GPR) | profundidade fisica honesta"
)

# ---------------------------------------------------------------------------
# Imports internos do engine (nao alteram nada de producao)
# ---------------------------------------------------------------------------

from gpr_engine.reader   import DZTReader
from gpr_engine.filters  import (
    dewow,
    bandpass,
    bgremoval,
    bgremoval_readgssi,
    tpow,
    agc,
)
from gpr_engine.images   import (
    render_radargram,
    render_radargram_readgssi_reference,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sep(titulo: str) -> None:
    print(f"\n{'='*65}")
    print(f"  {titulo}")
    print("=" * 65)


def _info(label: str, valor: object) -> None:
    print(f"  {label:<28}: {valor}")


def _ok(msg: str) -> None:
    print(f"  [OK]  {msg}")


def _depth_real(twtt_max_ns: float, velocity: float = _VELOCITY_MNS) -> float:
    return round(twtt_max_ns * velocity / 2.0, 4)


def _zeropad_array(arr: np.ndarray, twtt_max_ns: float, dt_ns: float,
                   target_depth_m: float, velocity: float) -> np.ndarray:
    """Estende array com zeros ate profundidade alvo."""
    twtt_target_ns = target_depth_m * 2.0 / velocity
    n_extra = max(0, math.ceil((twtt_target_ns - twtt_max_ns) / dt_ns))
    if n_extra == 0:
        return arr
    pad = np.zeros((n_extra, arr.shape[1]), dtype=np.float32)
    return np.vstack([arr.astype(np.float32), pad])


# ---------------------------------------------------------------------------
# Geracao de cada perfil
# ---------------------------------------------------------------------------

def _gerar_perfis(dzt, depth_real: float, out_dir: Path) -> list[dict]:
    """
    Gera os 9 PNGs de comparacao e retorna lista de metadados por perfil.

    Cada item: {id, label, path, normalizacao, bgr, eixo_y, candidato, notas}
    """
    arr_raw   = dzt.arr_raw
    dist      = dzt.dist_total_m
    sf_hz     = dzt.samp_freq_hz
    twtt_ns   = dzt.twtt_max_ns
    dt_ns     = dzt.dt_ns

    out_dir.mkdir(parents=True, exist_ok=True)
    perfis = []

    # ── 01 raw ───────────────────────────────────────────────────────────────
    p = out_dir / "01_raw.png"
    render_radargram(arr_raw, p, dist, depth_real,
                     title="01 — Raw\n(sem filtro, linear percentil-99)")
    perfis.append(dict(
        id=1, label="01_raw",
        path=p,
        normalizacao="linear percentil-99",
        bgr="nenhum",
        eixo_y=f"real ({depth_real:.2f} m)",
        candidato=False,
        notas="Baseline absoluto — dado bruto sem qualquer processamento.",
    ))
    _ok(f"01_raw.png ({p.stat().st_size // 1024} KB)")

    # ── 02 readgssi_ref_atual ─────────────────────────────────────────────────
    arr_bgr_global = bgremoval_readgssi(arr_raw, window=0)
    p = out_dir / "02_readgssi_ref_atual.png"
    render_radargram_readgssi_reference(arr_bgr_global, p, dist, depth_real,
        title="02 — readgssi_ref atual\n(bgr_global + SymLogNorm)")
    perfis.append(dict(
        id=2, label="02_readgssi_ref_atual",
        path=p,
        normalizacao="SymLogNorm",
        bgr="bgremoval_readgssi(window=0) — media global por linha",
        eixo_y=f"real ({depth_real:.2f} m)",
        candidato=False,
        notas="Estado atual do readgssi_reference. Remove media horizontal "
              "global → camadas horizontais continuas sao suprimidas.",
    ))
    _ok(f"02_readgssi_ref_atual.png ({p.stat().st_size // 1024} KB)")

    # ── 03 readgssi_sem_bgr ── HIPÓTESE PRINCIPAL ─────────────────────────────
    p = out_dir / "03_readgssi_sem_bgr.png"
    render_radargram_readgssi_reference(arr_raw, p, dist, depth_real,
        title="03 — readgssi SEM BGR  ★ HIPOTESE PRINCIPAL ★\n(SymLogNorm, sem bgremoval)")
    perfis.append(dict(
        id=3, label="03_readgssi_sem_bgr",
        path=p,
        normalizacao="SymLogNorm",
        bgr="NENHUM",
        eixo_y=f"real ({depth_real:.2f} m)",
        candidato=True,
        notas="HIPOTESE PRINCIPAL. Sem background removal, camadas horizontais "
              "reais sao preservadas. Deve ser o mais proximo do visual do cliente.",
    ))
    _ok(f"03_readgssi_sem_bgr.png ({p.stat().st_size // 1024} KB)")

    # ── 04 readgssi_bgr_windowed_30 ───────────────────────────────────────────
    arr_bgr_w30 = bgremoval_readgssi(arr_raw, window=30)
    p = out_dir / "04_readgssi_bgr_windowed_30.png"
    render_radargram_readgssi_reference(arr_bgr_w30, p, dist, depth_real,
        title="04 — readgssi bgr janelado 30\n(bgr_global + janela30 + SymLogNorm)")
    perfis.append(dict(
        id=4, label="04_readgssi_bgr_windowed_30",
        path=p,
        normalizacao="SymLogNorm",
        bgr="bgremoval_readgssi(window=30) — media global + janela de 30 tracas",
        eixo_y=f"real ({depth_real:.2f} m)",
        candidato=False,
        notas="ATENCAO: bgremoval_readgssi sempre aplica media global ANTES da janela "
              "(dois passes). Camadas longas (> 30 tracas) parcialmente preservadas; "
              "globais ainda removidas.",
    ))
    _ok(f"04_readgssi_bgr_windowed_30.png ({p.stat().st_size // 1024} KB)")

    # ── 05 scientific ─────────────────────────────────────────────────────────
    arr_dw   = dewow(arr_raw, window=5)
    arr_bp   = bandpass(arr_dw, sf_hz, 80.0, 500.0, order=5, tipo="butterworth")
    arr_sci  = tpow(arr_bp, power=0.5)
    p = out_dir / "05_scientific.png"
    render_radargram(arr_sci, p, dist, depth_real,
                     title="05 — Scientific\n(dewow + bp + tpow, linear percentil-99)")
    perfis.append(dict(
        id=5, label="05_scientific",
        path=p,
        normalizacao="linear percentil-99",
        bgr="nenhum (dewow apenas)",
        eixo_y=f"real ({depth_real:.2f} m)",
        candidato=False,
        notas="Fluxo cientifico atual do gpr_engine (dewow+bp+tpow). "
              "Sem AGC e sem bgremoval.",
    ))
    _ok(f"05_scientific.png ({p.stat().st_size // 1024} KB)")

    # ── 06 report ─────────────────────────────────────────────────────────────
    arr_bgr30 = bgremoval(arr_bp, window=30)
    arr_tp    = tpow(arr_bgr30, power=0.5)
    arr_rep   = agc(arr_tp, window=150)
    p = out_dir / "06_report.png"
    render_radargram(arr_rep, p, dist, depth_real,
                     title="06 — Report\n(dewow + bp + bgr(30) + tpow + AGC(150), linear)")
    perfis.append(dict(
        id=6, label="06_report",
        path=p,
        normalizacao="linear percentil-99",
        bgr="bgremoval(window=30) — running mean 30 tracas",
        eixo_y=f"real ({depth_real:.2f} m)",
        candidato=False,
        notas="Fluxo relatorio atual. BGRemoval janelado (nao global) + AGC. "
              "Camadas muito longas (> 30 tracas) parcialmente removidas.",
    ))
    _ok(f"06_report.png ({p.stat().st_size // 1024} KB)")

    # ── 07 radan_preview_atual ────────────────────────────────────────────────
    arr_agc80 = agc(arr_bp, window=80)
    aviso7 = _AVISO_STRETCH.format(real=depth_real)
    p = out_dir / "07_radan_preview_atual.png"
    render_radargram(arr_agc80, p, dist, _DEPTH_TARGET,
                     title="07 — RADAN Preview atual\n(dewow + bp + AGC(80), eixo Y visual 5 m)",
                     footer_text=aviso7)
    perfis.append(dict(
        id=7, label="07_radan_preview_atual",
        path=p,
        normalizacao="linear percentil-99",
        bgr="nenhum (dewow+bp+AGC apenas)",
        eixo_y=f"VISUAL 5.0 m (STRETCH — dados reais ate {depth_real:.2f} m)",
        candidato=False,
        notas="Preview RADAN do pipeline atual. Eixo Y esticado para 5 m. "
              "AGC(80) melhora contraste mas distorce amplitude relativa.",
    ))
    _ok(f"07_radan_preview_atual.png ({p.stat().st_size // 1024} KB)")

    # ── 08 readgssi_sem_bgr_5m_stretch ── CANDIDATO ──────────────────────────
    aviso8 = _AVISO_STRETCH.format(real=depth_real)
    p = out_dir / "08_readgssi_sem_bgr_5m_stretch.png"
    render_radargram_readgssi_reference(arr_raw, p, dist, _DEPTH_TARGET,
        title="08 — readgssi sem BGR, 5 m stretch  ★\n(SymLogNorm, eixo Y visual 5 m)",
        footer_text=aviso8)
    perfis.append(dict(
        id=8, label="08_readgssi_sem_bgr_5m_stretch",
        path=p,
        normalizacao="SymLogNorm",
        bgr="NENHUM",
        eixo_y=f"VISUAL 5.0 m (STRETCH — dados reais ate {depth_real:.2f} m)",
        candidato=True,
        notas="CANDIDATO: sem BGR + SymLogNorm + eixo Y 5 m por stretch. "
              "Comparar diretamente com o visual do cliente (escala igual). "
              "Profundidade de cada pixel esta distorcida no eixo Y.",
    ))
    _ok(f"08_readgssi_sem_bgr_5m_stretch.png ({p.stat().st_size // 1024} KB)")

    # ── 09 readgssi_sem_bgr_5m_zeropad ── CANDIDATO ──────────────────────────
    arr_padded = _zeropad_array(arr_raw, twtt_ns, dt_ns, _DEPTH_TARGET, _VELOCITY_MNS)
    n_extra = arr_padded.shape[0] - arr_raw.shape[0]
    aviso9 = _AVISO_ZEROPAD.format(real=depth_real)
    p = out_dir / "09_readgssi_sem_bgr_5m_zeropad.png"
    render_radargram_readgssi_reference(arr_padded, p, dist, _DEPTH_TARGET,
        title="09 — readgssi sem BGR, 5 m zeropad  ★\n(SymLogNorm, profundidade fisica honesta)",
        footer_text=aviso9)
    perfis.append(dict(
        id=9, label="09_readgssi_sem_bgr_5m_zeropad",
        path=p,
        normalizacao="SymLogNorm",
        bgr="NENHUM",
        eixo_y=f"5.0 m HONESTO: dados ate {depth_real:.2f} m + {n_extra} amostras zeradas",
        candidato=True,
        notas=f"CANDIDATO: sem BGR + SymLogNorm + zero-padding de {n_extra} amostras. "
              "Profundidade de cada pixel esta CORRETA. Abaixo de {:.2f} m = silencio "
              "(sem retorno GPR detectado).".format(depth_real),
    ))
    _ok(f"09_readgssi_sem_bgr_5m_zeropad.png ({n_extra} amostras de pad, "
        f"{p.stat().st_size // 1024} KB)")

    return perfis


# ---------------------------------------------------------------------------
# Contact sheet matplotlib (3 x 3)
# ---------------------------------------------------------------------------

def _gerar_contact_sheet(perfis: list[dict], depth_real: float, out_dir: Path) -> Path:
    """Gera contact_sheet.png com 3x3 grid dos 9 perfis."""

    n_cols, n_rows = 3, 3
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(24, 12), dpi=120)
    fig.suptitle(
        f"HELPER_0004.DZT — Comparativo visual de 9 perfis  |  "
        f"depth_real={depth_real:.2f} m  |  v={_VELOCITY_MNS} m/ns  |  "
        f"dist={perfis[0]['path'].parent}".split("/")[-1],
        fontsize=11, y=1.01, weight="bold",
    )

    for idx, (perf, ax) in enumerate(zip(perfis, axes.flat)):
        img = plt.imread(str(perf["path"]))
        ax.imshow(img)
        ax.axis("off")
        cor = "#1a7a1a" if perf["candidato"] else "#333"
        estrela = "  ★" if perf["candidato"] else ""
        ax.set_title(
            f"{perf['label']}{estrela}\n"
            f"bgr: {perf['bgr'][:38]}\n"
            f"norm: {perf['normalizacao']}  |  eixo Y: {perf['eixo_y'][:35]}",
            fontsize=6.5, color=cor, pad=3,
        )

    # preenche celulas vazias se n perfis < n_cols*n_rows
    for ax in axes.flat[len(perfis):]:
        ax.axis("off")

    fig.tight_layout(pad=1.2)
    out = out_dir / "contact_sheet.png"
    fig.savefig(str(out), bbox_inches="tight", dpi=120)
    plt.close(fig)
    return out


# ---------------------------------------------------------------------------
# contact_sheet.html
# ---------------------------------------------------------------------------

def _gerar_html(perfis: list[dict], depth_real: float, out_dir: Path) -> Path:
    candidatos = [p for p in perfis if p["candidato"]]
    rows = ""
    for p in perfis:
        cor_fundo = "#efffef" if p["candidato"] else "#fff"
        estrela   = "<strong style='color:#1a7a1a'> ★ CANDIDATO</strong>" if p["candidato"] else ""
        rows += f"""
        <tr style="background:{cor_fundo}">
          <td style="text-align:center; padding:4px">
            <a href="{p['path'].name}" target="_blank">
              <img src="{p['path'].name}" style="max-width:320px; border:1px solid #ccc">
            </a>
          </td>
          <td style="padding:8px; vertical-align:top">
            <b>{p['label']}</b>{estrela}<br>
            <small>
              <b>Normalizacao:</b> {p['normalizacao']}<br>
              <b>BGR:</b> {p['bgr']}<br>
              <b>Eixo Y:</b> {p['eixo_y']}<br>
              <br>
              <em>{p['notas']}</em>
            </small>
          </td>
        </tr>"""

    candidatos_html = "".join(
        f"<li><b>{c['label']}</b> — {c['notas'][:120]}…</li>"
        for c in candidatos
    )

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>Comparativo HELPER_0004.DZT</title>
  <style>
    body {{ font-family: monospace; font-size: 13px; max-width: 900px; margin: 20px auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    tr + tr {{ border-top: 1px solid #ddd; }}
    h1 {{ font-size: 16px; }}
    h2 {{ font-size: 14px; margin-top: 20px; }}
  </style>
</head>
<body>
  <h1>Comparativo Visual — HELPER_0004.DZT</h1>
  <p>
    <b>depth_real:</b> {depth_real:.4f} m &nbsp;|&nbsp;
    <b>velocity:</b> {_VELOCITY_MNS} m/ns &nbsp;|&nbsp;
    <b>depth_visual_cliente:</b> {_DEPTH_TARGET} m (escala display)<br>
    <b>Hipotese:</b> O cliente nao aplica bgremoval (ou aplica de forma diferente).
    Perfis sem BGR devem mostrar camadas horizontais fortes similares ao cliente.
  </p>
  <h2>Candidatos principais</h2>
  <ul>{candidatos_html}</ul>
  <h2>Todos os perfis</h2>
  <table>
    <thead>
      <tr>
        <th>Imagem</th>
        <th>Metadados</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="color:#888; font-size:11px; margin-top:20px">
    Gerado por _compare_helper_0004.py (Fase 8.11 — nenhuma alteracao de producao)
  </p>
</body>
</html>
"""
    out = out_dir / "contact_sheet.html"
    out.write_text(html, encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# README_COMPARATIVO.md
# ---------------------------------------------------------------------------

def _gerar_readme(perfis: list[dict], depth_real: float, out_dir: Path) -> Path:
    linhas = ["# Comparativo Visual — HELPER_0004.DZT\n",
              f"> Gerado por `_compare_helper_0004.py` (Fase 8.11)  \n",
              f"> depth_real = **{depth_real:.4f} m** | velocity = {_VELOCITY_MNS} m/ns "
              f"| depth_visual_cliente = {_DEPTH_TARGET} m (display RADAN)\n\n",
              "## Hipótese principal\n\n",
              "O `bgremoval_readgssi(window=0)` subtrai a **média horizontal global** de cada linha "
              "de profundidade (axis=1). Qualquer reflexão que apareça na mesma profundidade em "
              "todos os traços tem amplitude reduzida para zero. O cliente provavelmente não aplicou "
              "esse filtro no RADAN, preservando as camadas horizontais reais.\n\n",
              "## Resumo dos perfis\n\n",
              "| # | Arquivo | BGR | Normalização | Eixo Y | Candidato |\n",
              "|---|---------|-----|--------------|--------|-----------|\n"]

    for p in perfis:
        c = "★ Sim" if p["candidato"] else "—"
        bgr_short = p['bgr'][:50]
        linhas.append(f"| {p['id']} | `{p['label']}` | {bgr_short} | {p['normalizacao']} "
                      f"| {p['eixo_y'][:40]} | {c} |\n")

    linhas += [
        "\n## O que mostrar ao Amilson\n\n",
        "Mostrar em ordem:\n",
        "1. `08_readgssi_sem_bgr_5m_stretch.png` — escala visual igual à do cliente (5 m)\n",
        "2. `09_readgssi_sem_bgr_5m_zeropad.png` — mesma escala 5 m, profundidade honesta\n",
        "3. `03_readgssi_sem_bgr.png` — escala real (2.47 m), sem BGR\n",
        "4. `02_readgssi_ref_atual.png` — estado atual (com BGR global)\n\n",
        "Pergunta chave: **qual desses perfis preserva as camadas horizontais fortes que aparecem "
        "no radargrama do cliente?**\n\n",
        "## Sobre a profundidade\n\n",
        f"- `rhf_range_ns × velocity / 2 = {depth_real:.4f} m` é a profundidade FISICA do DZT.\n",
        f"- O cliente exibe 5 m provavelmente por configuração de display do RADAN "
        f"(escala independente do range fisico).\n",
        "- Perfis com `stretch` distorcem o eixo Y (aceitavel para comparacao visual).\n",
        "- Perfil `09_zeropad` e honesto: dados reais ate {:.2f} m, vazio abaixo.\n".format(depth_real),
        "\n## Proximos passos\n\n",
        "- Se perfil 03 ou 08 se aproximar do cliente → criar "
        "`visual_profile='readgssi_no_bgr'` como nova opcao (sem alterar o default).\n",
        "- Se a escala de profundidade do cliente for diferente da nossa → verificar se o DZT "
        "do cliente tem `rhf_range_ns` diferente (ex: 100 ns vs 49 ns).\n",
    ]

    out = out_dir / "README_COMPARATIVO.md"
    out.write_text("".join(linhas), encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _sep("Fase 8.11 — Comparativo Visual HELPER_0004.DZT")

    if not _DZT.exists():
        print(f"  [ERRO] DZT nao encontrado: {_DZT}")
        sys.exit(1)

    # ── Leitura do DZT ───────────────────────────────────────────────────────
    print("\n  Lendo DZT...")
    reader = DZTReader(verbose=False)
    dzt = reader.read(_DZT)

    depth_real = _depth_real(dzt.twtt_max_ns, _VELOCITY_MNS)
    twtt_target_ns = _DEPTH_TARGET * 2.0 / _VELOCITY_MNS
    n_extra = max(0, math.ceil((twtt_target_ns - dzt.twtt_max_ns) / dzt.dt_ns))

    _sep("Parametros do DZT")
    _info("Arquivo",               _DZT.name)
    _info("n_tracos",              dzt.n_traces)
    _info("n_samples",             dzt.n_samples)
    _info("dist_total_m",          f"{dzt.dist_total_m:.4f} m")
    _info("twtt_max_ns (rhf_range)", f"{dzt.twtt_max_ns:.2f} ns")
    _info("dt_ns",                 f"{dzt.dt_ns:.4f} ns/amostra")
    _info("samp_freq_hz",          f"{dzt.samp_freq_hz:.0f} Hz")
    _info("antfreq_mhz",           f"{dzt.antfreq_mhz} MHz")
    _info("wave_speed_mns (header)", f"{dzt.wave_speed_mns:.4f} m/ns")
    _info("velocity usada",        f"{_VELOCITY_MNS} m/ns (preset standard)")
    _info("depth_real calculada",  f"{depth_real:.4f} m  [twtt x v / 2]")
    _info("depth_visual_cliente",  f"{_DEPTH_TARGET} m (escala display)")
    _info("zero-pad amostras",     f"{n_extra} amostras para atingir {_DEPTH_TARGET} m")
    _info("modo_coleta",           dzt.modo_coleta)
    _info("timezero_sample",       dzt.timezero_sample)
    _info("has_dzx",               dzt.has_dzx)

    # ── Geracao dos perfis ────────────────────────────────────────────────────
    _sep("Gerando perfis")
    perfis = _gerar_perfis(dzt, depth_real, _OUT_DIR)

    # ── Contact sheet ─────────────────────────────────────────────────────────
    _sep("Gerando contact_sheet.png")
    cs_png = _gerar_contact_sheet(perfis, depth_real, _OUT_DIR)
    _ok(f"contact_sheet.png ({cs_png.stat().st_size // 1024} KB)")

    # ── HTML ──────────────────────────────────────────────────────────────────
    _sep("Gerando contact_sheet.html")
    cs_html = _gerar_html(perfis, depth_real, _OUT_DIR)
    _ok(f"contact_sheet.html ({cs_html.stat().st_size // 1024} KB)")

    # ── README ────────────────────────────────────────────────────────────────
    _sep("Gerando README_COMPARATIVO.md")
    readme = _gerar_readme(perfis, depth_real, _OUT_DIR)
    _ok(f"README_COMPARATIVO.md ({readme.stat().st_size} bytes)")

    # ── Resumo final ──────────────────────────────────────────────────────────
    _sep("Resumo dos outputs")
    print(f"\n  Diretorio de saida:")
    print(f"    {_OUT_DIR}\n")
    for p in perfis:
        estrela = "  <- CANDIDATO PRINCIPAL" if p["candidato"] else ""
        print(f"    {p['path'].name}{estrela}")
    print(f"    contact_sheet.png")
    print(f"    contact_sheet.html  <- abrir no browser")
    print(f"    README_COMPARATIVO.md")

    _sep("Candidatos principais")
    candidatos = [p for p in perfis if p["candidato"]]
    for c in candidatos:
        print(f"\n  {c['label']}")
        print(f"    {c['notas']}")

    _sep("Analise tecnica")
    print("""
  Por que nosso readgssi_reference remove camadas horizontais:
    bgremoval_readgssi(window=0) subtrai f.mean(axis=1) de cada linha.
    Isso elimina a componente constante ao longo dos tracas (= camadas horizontais).
    O cliente provavelmente usa RADAN sem bgremoval, ou com configuracao diferente.

  Por que a profundidade e 2.47 m (nao 5 m):
    rhf_range_ns = {:.2f} ns (do header DZT)
    profundidade = {:.2f} ns * {:.2f} m/ns / 2 = {:.4f} m
    O cliente provavelmente configura a escala de display do RADAN para 5 m
    independentemente do range fisico do DZT.

  Perfis a mostrar ao Amilson em ordem:
    1. 08_readgssi_sem_bgr_5m_stretch.png  (escala visual igual ao cliente)
    2. 09_readgssi_sem_bgr_5m_zeropad.png  (escala 5 m honesta)
    3. 03_readgssi_sem_bgr.png             (escala real, sem BGR)
    4. 02_readgssi_ref_atual.png           (estado atual — referencia)
""".format(dzt.twtt_max_ns, dzt.twtt_max_ns, _VELOCITY_MNS, depth_real))

    _sep("Concluido")
    print(f"  Abrir no browser:")
    print(f"    {cs_html}")
    print()


if __name__ == "__main__":
    main()
