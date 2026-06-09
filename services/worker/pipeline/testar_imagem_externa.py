"""
testar_imagem_externa.py — Roda detecção + interpretação GPT-4o em radargrama JPG/PNG externo.

Uso:
    python testar_imagem_externa.py <imagem.jpg> [--depth-max 5.0] [--dist-max 3.3] [--min-score 30]

Contexto: imagens já processadas pelo RADAN (Amilson). Não passam pelo pipeline DZT.
Rodamos só detecção de hipérboles + enriquecimento + plotagem + GPT-4o por alvo.

Parâmetros opcionais:
    --depth-max  Profundidade máxima visível na imagem em metros (padrão: 3.35)
    --dist-max   Distância horizontal máxima em metros (padrão: 20.0 — estimativa)
    --min-score  Score mínimo para mostrar na imagem anotada (padrão: 30)
    --sem-ia     Pula chamada GPT-4o (útil para teste rápido sem gastar tokens)
    --crop       Tenta detectar e recortar a região de dados (remove eixos matplotlib)
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
from pathlib import Path

import pandas as pd

# Fix Windows cp1252 stdout encoding
if hasattr(sys.stdout, "buffer"):
    import io as _io
    sys.stdout = _io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

import numpy as np
from PIL import Image
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# PATH: adiciona services/worker ao sys.path para imports relativos
# ---------------------------------------------------------------------------
_WORKER_DIR = Path(__file__).resolve().parent.parent
if str(_WORKER_DIR) not in sys.path:
    sys.path.insert(0, str(_WORKER_DIR))

load_dotenv(_WORKER_DIR / ".env")

from pipeline.detector_hiperboles import (
    DEFAULT_PARAMS,
    detectar_hiperboles,
    enriquecer_deteccoes_fisica,
    plotar_deteccoes,
)

# ---------------------------------------------------------------------------
# CROP: remove bordas de eixos matplotlib embutidos na imagem
# ---------------------------------------------------------------------------
def _crop_axes_region(img_pil: Image.Image) -> tuple[Image.Image, dict]:
    """
    Imagens do Amilson são renders matplotlib com eixos embutidos.
    Detecta a região de dados via análise de gradiente nas bordas.
    Retorna imagem recortada + info do crop (left, top, right, bottom em px).

    Fallback: se não conseguir detectar, retorna imagem original.
    """
    arr = np.array(img_pil.convert("L"))
    h, w = arr.shape

    # Margins típicas de matplotlib (proporção da imagem)
    # left≈10%, right≈2%, top≈5%, bottom≈12%
    left   = int(w * 0.10)
    right  = int(w * 0.98)
    top    = int(h * 0.06)
    bottom = int(h * 0.88)

    cropped = img_pil.crop((left, top, right, bottom))
    return cropped, {"left": left, "top": top, "right": right, "bottom": bottom, "orig_w": w, "orig_h": h}


# ---------------------------------------------------------------------------
# BGREMOVAL: subtrai media horizontal local para remover reflectores horizontais
# (mesmo principio do bgremoval do pipeline — sem isso o Hough detecta camadas, nao hiperboles)
# ---------------------------------------------------------------------------
def _aplicar_bgremoval(arr: np.ndarray, janela: int = 50) -> np.ndarray:
    """
    Subtrai a media movel horizontal de cada linha (trace-wise background removal).
    janela=0 → subtrai media global da linha (bgremoval total).
    janela>0 → subtrai media movel de 'janela' tracos (preserva hiperboles curtas).
    """
    from scipy.ndimage import uniform_filter1d
    if janela <= 0 or janela >= arr.shape[1]:
        bg = arr.mean(axis=1, keepdims=True)
    else:
        bg = uniform_filter1d(arr, size=janela, axis=1, mode="nearest")
    return arr - bg


# ---------------------------------------------------------------------------
# ENCODE imagem → base64 PNG
# ---------------------------------------------------------------------------
def _encode_b64(img_pil: Image.Image, max_size: tuple[int, int] = (1200, 600)) -> str:
    img = img_pil.copy().convert("RGB")
    img.thumbnail(max_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ---------------------------------------------------------------------------
# PARAMS: ajusta DEFAULT_PARAMS às dimensões reais da imagem
# ---------------------------------------------------------------------------
def _build_params(arr: np.ndarray, depth_max_m: float, dist_max_m: float) -> dict:
    n_samples, n_traces = arr.shape
    v_m_per_s = 1.0e8  # 0.1 m/ns — padrão solo seco

    # dt_s: tempo por sample para bater com depth_max
    # depth = n_samples * dt * v / 2  →  dt = 2 * depth_max / (n_samples * v)
    dt_s = 2.0 * depth_max_m / (n_samples * v_m_per_s)

    # dx_m: distância horizontal por traço
    dx_m = dist_max_m / max(n_traces - 1, 1)

    params = dict(DEFAULT_PARAMS)
    params.update({
        "v_m_per_s":    v_m_per_s,
        "dt_s":         dt_s,
        "dx_m":         dx_m,
        "h_max_m":      depth_max_m * 0.85,   # não busca no ruído do fundo
        "h_min_m":      0.10,
    })
    return params


# ---------------------------------------------------------------------------
# GPT-4o: interpreta cada alvo individualmente
# ---------------------------------------------------------------------------
def _interpretar_alvo_gpt4o(
    client,
    alvo: dict,
    radargram_b64: str,
    arr_full: np.ndarray,
    img_pil: Image.Image,
    params: dict,
    img_name: str,
) -> dict:
    """Monta prompt idêntico ao job_ia.py e chama GPT-4o."""
    from openai import OpenAI

    # Crop ao redor do apex do alvo (± wing)
    crop_b64 = None
    try:
        v   = params["v_m_per_s"]
        dt  = params["dt_s"]
        dx  = params["dx_m"]
        n_s, n_t = arr_full.shape
        H, W = img_pil.size[1], img_pil.size[0]

        col  = int(alvo.get("x_m", 0) / dx)
        row  = int(alvo.get("depth_m", 0) / (n_s * dt * v / 2) * n_s)
        wing = int(n_t * 0.15)

        px_left  = max(0, int((col - wing) * W / n_t))
        px_right = min(W, int((col + wing) * W / n_t))
        px_top   = max(0, int((row - wing) * H / n_s))
        px_bot   = min(H, int((row + wing) * H / n_s))

        crop_img = img_pil.crop((px_left, px_top, px_right, px_bot))
        if crop_img.width > 10 and crop_img.height > 10:
            buf = io.BytesIO()
            crop_img.convert("RGB").save(buf, format="PNG")
            crop_b64 = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        pass

    system_prompt = """\
You are a GPR (Ground Penetrating Radar) expert geophysicist.

Analyze the detected target from a 270MHz GSSI antenna radargram. The crop image shows the \
hyperbolic reflection centered on the target.

In a radargram:
- Horizontal axis = distance along the survey line
- Vertical axis = depth (increasing downward)
- A hyperbolic signature indicates a buried point or cylindrical object
- Brighter/stronger reflections indicate higher dielectric contrast with surrounding soil

Common buried objects in urban/infrastructure surveys:
- tubulacao_agua: water pipe (metal or PVC) — clean strong reflection
- tubulacao_gas: gas pipe (metal) — strong reflection, usually shallow
- tubulacao_esgoto: sewer pipe (concrete/PVC) — larger diameter, moderate reflection
- cabo_eletrico: electrical cable — small diameter, strong metallic reflection
- cabo_telecom: telecom cable — small diameter, may appear in bundles
- galeria_concreto: concrete gallery/culvert — large, double reflection (top+bottom)
- vazio_ar: void/cavity — double reflection surface+bottom
- rocha: rock — irregular shape, variable reflection
- inconclusivo: ambiguous signature

Respond ONLY with a valid JSON object. All description text must be in Brazilian Portuguese:
{
  "ia_tipo_sugerido": "<one of the types listed above>",
  "ia_descricao": "<1-2 sentences describing the detected object in Portuguese>",
  "ia_justificativa_visual": "<visual features in the radargram supporting this interpretation, in Portuguese>",
  "ia_justificativa_tecnica": "<technical reasoning: depth, diameter, signal characteristics, in Portuguese>",
  "ia_confianca": "<alta | media | baixa>",
  "ia_confianca_pct": <integer 0-100>,
  "ia_recomendacao": "<recommended action for field/technical team, in Portuguese>",
  "vai_para_planta_sugerido": true or false,
  "vai_para_relatorio_sugerido": true or false,
  "observacoes": "<additional observations or null>"
}"""

    user_content: list = [{
        "type": "text",
        "text": (
            f"Survey: {img_name} (imagem externa — RADAN processado por Amilson)\n"
            f"File: {img_name}\n\n"
            "Automatic detection parameters:\n"
            f"  Rank: #{alvo.get('rank', '?')}\n"
            f"  Position: {alvo.get('x_m', '?')} m along profile\n"
            f"  Center depth: {alvo.get('depth_m', '?')} m\n"
            f"  Estimated diameter: {alvo.get('diam_est_m', '?')} m "
            f"(confidence: {alvo.get('diam_confianca', '?')})\n"
            f"  Physical classification: {alvo.get('tipo_material', 'N/A')} "
            f"({alvo.get('confianca_tipo', 'N/A')})\n"
            f"  Algorithm score: {alvo.get('confidence_score_0_100', '?')}/100 "
            f"({alvo.get('confidence_label_tecnico', '?')})\n\n"
            "The crop image (if provided) shows the hyperbola region.\n"
            "Return JSON with all description text in Brazilian Portuguese."
        ),
    }]

    if crop_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{crop_b64}", "detail": "high"},
        })

    user_content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/png;base64,{radargram_b64}", "detail": "low"},
    })

    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    raw = response.choices[0].message.content or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"erro": "JSON inválido", "raw": raw[:300]}

    uso = response.usage
    tokens = (uso.prompt_tokens + uso.completion_tokens) if uso else 0
    custo = round(tokens * 2.5 / 1_000_000, 6) if uso else 0

    parsed["_tokens"] = tokens
    parsed["_custo_usd"] = custo
    return parsed


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Testa detecção + GPT-4o em radargrama JPG/PNG externo")
    parser.add_argument("imagem", help="Caminho para o JPG/PNG do radargrama")
    parser.add_argument("--depth-max", type=float, default=3.35, help="Profundidade máx. visível (m)")
    parser.add_argument("--dist-max",  type=float, default=0.0,  help="Distância horizontal máx. (m) — 0=auto")
    parser.add_argument("--h-min",     type=float, default=0.40, help="Profundidade mínima de busca (m) — exclui onda direta")
    parser.add_argument("--min-score", type=int,   default=40,   help="Score geométrico mínimo para anotação (0-100)")
    parser.add_argument("--bgremoval",  type=int, default=50,      help="Janela bgremoval em tracos (0=global, -1=desativado)")
    parser.add_argument("--sem-ia",    action="store_true",       help="Pula GPT-4o")
    parser.add_argument("--crop",      action="store_true",       help="Recorta eixos matplotlib antes de processar")
    args = parser.parse_args()

    img_path = Path(args.imagem).resolve()
    if not img_path.exists():
        print(f"[ERRO] Arquivo não encontrado: {img_path}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  ARQUIVO : {img_path.name}")
    print(f"{'='*70}")

    # --- Etapa 1: Carregar imagem ---
    img_pil = Image.open(img_path)
    crop_info = None

    if args.crop:
        img_pil, crop_info = _crop_axes_region(img_pil)
        print(f"  Crop aplicado: {crop_info}")

    arr = np.array(img_pil.convert("L")).astype(float)
    n_samples, n_traces = arr.shape
    print(f"  Shape original (H×W): {n_samples}×{n_traces} px")

    # Downscale para acelerar Hough: máx 700 amostras × 1500 traços
    MAX_SAMPLES, MAX_TRACES = 700, 1500
    if n_samples > MAX_SAMPLES or n_traces > MAX_TRACES:
        scale_h = MAX_SAMPLES / n_samples
        scale_w = MAX_TRACES  / n_traces
        scale   = min(scale_h, scale_w)
        new_h   = max(64, int(n_samples * scale))
        new_w   = max(64, int(n_traces  * scale))
        img_pil = img_pil.resize((new_w, new_h), Image.LANCZOS)
        arr     = np.array(img_pil.convert("L")).astype(float)
        n_samples, n_traces = arr.shape
        print(f"  Redimensionado para: {n_samples}×{n_traces} px (scale={scale:.2f})")
    else:
        print(f"  Shape (H×W): {n_samples}×{n_traces} px")

    # Estimar dist_max automaticamente: proporção width/height × depth_max × fator típico
    dist_max = args.dist_max
    if dist_max <= 0:
        # Aspecto do radargrama: geralmente 4-6× mais largo que profundo
        aspect = n_traces / n_samples
        dist_max = round(args.depth_max * aspect * 0.65, 2)
        print(f"  dist_max estimado automaticamente: {dist_max} m (aspect={aspect:.2f})")
    else:
        print(f"  dist_max fornecido: {dist_max} m")

    print(f"  depth_max: {args.depth_max} m")

    # --- Etapa 2: Bgremoval (remove reflectores horizontais antes do Hough) ---
    if args.bgremoval >= 0:
        arr = _aplicar_bgremoval(arr, janela=args.bgremoval)
        print(f"  Bgremoval aplicado: janela={args.bgremoval if args.bgremoval > 0 else 'global'} tracos")

    # --- Etapa 3: Parâmetros e detecção ---
    params = _build_params(arr, args.depth_max, dist_max)
    # Para imagens externas: ajusta busca para evitar onda direta e ampliar janela lateral
    params["h_min_m"] = args.h_min
    params["col_search_half"] = min(300, int(n_traces * 0.25))  # 25% da largura, máx 300 traços
    print(f"\n  Params: dt={params['dt_s']:.3e}s  dx={params['dx_m']:.4f}m  "
          f"v={params['v_m_per_s']:.0e}m/s  h_min={params['h_min_m']:.2f}m  h_max={params['h_max_m']:.2f}m")
    print(f"  Rodando detector Hough -> CurveFit -> DeltaT ...")

    deteccoes, _, _ = detectar_hiperboles(arr, params)

    if deteccoes is None or deteccoes.empty:
        print("  [!] Nenhum alvo detectado.")
        return

    # Para imagens externas (sem arrays de amplitude física), calcular score geométrico:
    # fit_ok=True vale 50pts, diam_confianca: alta=30, media=20, baixa=5, score_hough normalizado=20pts
    def _geo_score(row) -> int:
        s = 0
        if row.get("fit_ok", False):
            s += 50
        dc = str(row.get("diam_confianca", "")).lower()
        if dc == "alta":   s += 30
        elif dc == "media": s += 20
        elif dc == "baixa": s += 5
        # Hough score: normaliza pelo top_n (maior score Hough do batch)
        hough = float(row.get("score", 0))
        s += min(20, int(hough * 5))
        return min(100, s)

    deteccoes["confidence_score_0_100"] = deteccoes.apply(_geo_score, axis=1)
    deteccoes["confidence_label_tecnico"] = deteccoes["confidence_score_0_100"].apply(
        lambda s: "alta" if s >= 70 else "media" if s >= 40 else "baixa"
    )

    # Garantir colunas numéricas
    for col in ("depth_m", "x_m", "diam_est_m"):
        if col in deteccoes.columns:
            deteccoes[col] = pd.to_numeric(deteccoes[col], errors="coerce").fillna(0)

    # Filtro por score geométrico
    antes = len(deteccoes)
    deteccoes = deteccoes[deteccoes["confidence_score_0_100"] >= args.min_score].reset_index(drop=True)
    removidos = antes - len(deteccoes)
    if removidos:
        print(f"  Removidos {removidos} alvos abaixo de score {args.min_score}")

    n_alvos = len(deteccoes)
    print(f"\n  ALVOS DETECTADOS: {n_alvos}")

    if n_alvos == 0:
        print("  [!] Nenhum alvo acima do score minimo.")
        print(f"  Dica: tente --min-score 0 para ver todos os candidatos brutos.")
        return

    # --- Etapa 3: Plotar anotada ---
    output_anotada = img_path.parent / (img_path.stem + "_anotada.png")
    plotar_deteccoes(arr, deteccoes, params, output_path=str(output_anotada), min_score=args.min_score)
    print(f"  Imagem anotada salva: {output_anotada.name}")

    # --- Resumo dos alvos ---
    print(f"\n  {'Rank':>4}  {'x(m)':>6}  {'depth(m)':>8}  {'diam(m)':>7}  "
          f"{'geo_score':>9}  {'label':>6}  {'fit_ok':>6}  {'diam_conf':>9}")
    print(f"  {'-'*4}  {'-'*6}  {'-'*8}  {'-'*7}  {'-'*9}  {'-'*6}  {'-'*6}  {'-'*9}")
    for _, row in deteccoes.iterrows():
        print(f"  {int(row.get('rank',0)):>4}  "
              f"{float(row.get('x_m',0)):>6.2f}  "
              f"{float(row.get('depth_m',0)):>8.2f}  "
              f"{float(row.get('diam_est_m',0)):>7.3f}  "
              f"{int(row.get('confidence_score_0_100',0)):>9}  "
              f"{str(row.get('confidence_label_tecnico','?')):>6}  "
              f"{str(row.get('fit_ok','?')):>6}  "
              f"{str(row.get('diam_confianca','?')):>9}")

    if args.sem_ia:
        print("\n  [--sem-ia] Pulando GPT-4o.")
        return

    # --- Etapa 4: GPT-4o por alvo ---
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("\n  [!] OPENAI_API_KEY não encontrada no .env — pulando interpretação.")
        return

    from openai import OpenAI
    client = OpenAI(api_key=api_key)

    radargram_b64 = _encode_b64(img_pil)

    interpretacoes = []
    custo_total = 0.0
    output_txt = img_path.parent / (img_path.stem + "_interpretada.txt")

    print(f"\n  Interpretando {n_alvos} alvo(s) com GPT-4o ...")
    for _, row in deteccoes.iterrows():
        alvo = row.to_dict()
        rank = int(alvo.get("rank", 0))
        print(f"    → Alvo #{rank} (x={alvo.get('x_m',0):.2f}m, depth={alvo.get('depth_m',0):.2f}m) ...", end=" ", flush=True)
        resultado = _interpretar_alvo_gpt4o(
            client, alvo, radargram_b64, arr, img_pil, params, img_path.name
        )
        custo_total += resultado.get("_custo_usd", 0)
        interpretacoes.append({"rank": rank, "alvo": alvo, "ia": resultado})
        tipo = resultado.get("ia_tipo_sugerido", "?")
        conf = resultado.get("ia_confianca", "?")
        pct  = resultado.get("ia_confianca_pct", "?")
        print(f"{tipo} [{conf} {pct}%] — ${resultado.get('_custo_usd',0):.4f}")

    # --- Salvar interpretada.txt ---
    linhas = [
        f"INTERPRETAÇÃO GPT-4o — {img_path.name}",
        f"depth_max={args.depth_max}m  dist_max={dist_max}m  min_score={args.min_score}",
        f"Alvos detectados: {n_alvos}  |  Custo total: ${custo_total:.4f} USD",
        "=" * 70,
    ]
    for item in interpretacoes:
        rank = item["rank"]
        a    = item["alvo"]
        ia   = item["ia"]
        linhas += [
            f"\nAlvo #{rank} — x={a.get('x_m',0):.2f}m | depth={a.get('depth_m',0):.2f}m | "
            f"diam={a.get('diam_est_m',0):.3f}m | score={a.get('confidence_score_0_100',0)}",
            f"  Tipo IA       : {ia.get('ia_tipo_sugerido', '?')}",
            f"  Confiança     : {ia.get('ia_confianca', '?')} ({ia.get('ia_confianca_pct', '?')}%)",
            f"  Descrição     : {ia.get('ia_descricao', '?')}",
            f"  Visual        : {ia.get('ia_justificativa_visual', '?')}",
            f"  Técnico       : {ia.get('ia_justificativa_tecnica', '?')}",
            f"  Recomendação  : {ia.get('ia_recomendacao', '?')}",
            f"  Planta        : {ia.get('vai_para_planta_sugerido', '?')}  |  "
            f"Relatório: {ia.get('vai_para_relatorio_sugerido', '?')}",
            f"  Observações   : {ia.get('observacoes', '—')}",
            f"  Tokens        : {ia.get('_tokens', 0)}  |  Custo: ${ia.get('_custo_usd', 0):.4f}",
        ]

    linhas.append(f"\n{'='*70}")
    linhas.append(f"CUSTO TOTAL: ${custo_total:.4f} USD")

    with open(output_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(linhas))
    print(f"\n  Interpretação salva: {output_txt.name}")
    print(f"  Custo total GPT-4o: ${custo_total:.4f} USD")

    # --- Resumo final no terminal ---
    print(f"\n{'='*70}")
    print(f"  RESUMO FINAL — {img_path.name}")
    print(f"{'='*70}")
    for item in interpretacoes:
        ia = item["ia"]
        a  = item["alvo"]
        print(f"  #{item['rank']:>2} x={a.get('x_m',0):.2f}m depth={a.get('depth_m',0):.2f}m → "
              f"{ia.get('ia_tipo_sugerido','?')} [{ia.get('ia_confianca','?')} {ia.get('ia_confianca_pct','?')}%]")
        print(f"       {ia.get('ia_descricao','')}")
    print(f"\n  Arquivos gerados:")
    print(f"    {output_anotada.name}")
    print(f"    {output_txt.name}")


if __name__ == "__main__":
    main()
