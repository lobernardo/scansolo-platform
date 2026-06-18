# Detector de Hipérboles — Referência Técnica
> Objetivo: Documentação do detector de hipérboles e da ferramenta de validação standalone.
> Contexto: `services/worker/pipeline/detector_hiperboles.py` v1.1 + `testar_imagem_externa.py`.

---

## Detector de hipérboles — `pipeline/detector_hiperboles.py`

Versão: **1.1**

### Fluxo

Hough adaptado → CurveFit (mínimos quadrados) → DeltaT (reflexão topo+fundo) → enriquecimento físico → score composto 0-100

### DEFAULT_PARAMS (calibrados para PATIO 270 MHz)

```python
{
    "v_m_per_s":             1.0e8,       # 0.1 m/ns — solo seco padrão
    "amp_threshold":         0.45,
    "h_min_m":               0.10,
    "h_max_m":               2.80,
    "h_step_m":              0.04,
    "col_search_half":       80,
    "nms_radius_m":          0.50,
    "top_n":                 30,
    "cf_wing_half_m":        2.0,
    "cf_amp_frac":           0.30,
    "dt_min_diam_m":         0.05,
    "dt_max_diam_m":         1.50,
    "dt_conf_frac":          0.20,
    "fis_amp_metal_thr":     0.75,        # [CALIBRAR] com Amilson
    "fis_amp_nao_metal_thr": 0.40,        # [CALIBRAR] com Amilson
}
```

**Nota:** os thresholds `fis_amp_metal_thr` e `fis_amp_nao_metal_thr` nos DEFAULT_PARAMS diferem dos valores do preset `270mhz` (0.65 e 0.22). Os valores do preset prevalecem quando o pipeline roda via worker. Os DEFAULT_PARAMS são usados apenas quando o detector é chamado diretamente sem parâmetros.

### Entradas

- **`arr_proc`**: float32 numpy array (com AGC) — **não** um PNG carregado do disco
- **`arr_sem_agc`**: para amplitude/fase (sem distorção do AGC)
- **`arr_raw`**: evidência independente
- Entrada controlada por `detector_input_mode` no pipeline (default: `"raw"` desde v2.0.0)

### Filtro de profundidade mínima

`det_depth_min_m=0.30m` — elimina airwave/onda direta. Override explícito via `_det_depth_min_m_explicit=True` (Fase 15) impede que o SNR gate adaptativo substitua o valor configurado.

---

## Script de validação — `pipeline/testar_imagem_externa.py`

Ferramenta standalone para testar o detector em imagens JPG já processadas pelo RADAN (output do Amilson). **Não é equivalente ao pipeline completo.**

### O que faz

1. Recebe JPG/PNG processado pelo RADAN
2. Aplica crop de eixos matplotlib (opcional, `--crop`)
3. Aplica bgremoval simplificado (média horizontal por linha)
4. Roda `detectar_hiperboles` + `enriquecer_deteccoes_fisica`
5. Gera `_anotada.png` + chama GPT-4o por alvo → `_interpretada.txt`

### O que NÃO faz (diferenças do pipeline real)

- Não lê DZT bruto — recebe JPG já processado
- Não roda dewow / bandpass / tpow / AGC / migração
- O detector recebe imagem uint8 convertida de JPEG — não o float32 do GPRPy
- Aplica bgremoval extra em cima do que o RADAN já processou
- Parâmetros de escala (depth_max, dist_max) são manuais via CLI, não vêm dos metadados do DZT

### Uso

```bash
python pipeline/testar_imagem_externa.py <imagem.jpg> \
  --depth-max 5.0 --dist-max 8.82 --min-score 40
```

**Flags:** `--depth-max`, `--dist-max`, `--min-score`, `--sem-ia`, `--crop`

### Outputs

Salvos na mesma pasta da imagem de entrada:
- `<stem>_anotada.png` — detector plotado sobre a imagem
- `<stem>_interpretada.txt` — GPT-4o por alvo (tipo, confiança, justificativa técnica, custo)

### Status do dataset HELPAVPA

Dataset: 126 imagens em `HELPAVPA_imagens georada rproc joeg/` (pasta ScanSOLO raiz, fora do repo).
Testadas (2026-06-09): 0001–0013 (13 imagens). Pendentes: 0014–0126 (113 imagens).
