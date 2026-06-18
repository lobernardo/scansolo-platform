# GPR Pipeline — Referência Técnica
> Objetivo: Documentação completa do `pipeline_v1.py` — sequência de processamento, matrizes, parâmetros e configuração.
> Contexto: `services/worker/pipeline/pipeline_v1.py` v2.0.0 (atualizado 2026-06-12). Leia junto com [PRESETS_E_FILTROS.md](PRESETS_E_FILTROS.md).

---

## Arquitetura v2.0.0 — Três Fluxos Separados

```
DZT → raw → dewow+bp → [bifurcação]
                         |
              [tpow manual]   [bgremoval → tpow → AGC]
                   |                   |
           arr_cientifico        arr_relatorio
        (para Amilson/detector)   (para cliente/PDF)
```

| Fluxo | Pipeline | Saída | Finalidade |
|---|---|---|---|
| Científico | raw→dewow→bp→tpow | `_radargrama_cientifico.png` | Revisão técnica (Amilson) |
| Relatório | raw→dewow→bp→bgremoval→tpow→AGC | `_radargrama_relatorio.png` / `_processada.png` | Cliente/PDF |
| Detector | controlado por `detector_input_mode` (default: `raw`) | `_anotada_completa.png` | Hough+CurveFit+DeltaT |
| Preview RADAN | arr_dewow_bp (cópia) → AGC(80) | `_radargrama_preview_radan_5m.png` | Comparação visual com RADAN (5m fixo) |

**Mudança principal v2.0.0:** detector opera sobre `arr_raw` por padrão (82% CurveFit em PATIO)
vs. v1.2.0 que usava `arr_proc+AGC` (24% CurveFit, 46% falsos positivos).

---

## Sequência por DZT (13 passos)

1. Leitura via GPRPy → `_bruta.png` + `raw.npy`
2. **SNR gate raw** → decide modo: `minimo` / `padrao` / `agressivo`
3. **Dewow + Bandpass** → `arr_dewow_bp` — bandpass aplicado se `bandpass_low_mhz > 0`; desativado se `bandpass_low_mhz=0` (decisão explícita, não automática)
4. **Fluxo Científico:** `arr_dewow_bp` → tpow manual → `arr_cientifico` → `_radargrama_cientifico.png` + SNR cientifico
5. **Fluxo Relatório:** `arr_dewow_bp` → bgremoval → tpow → `arr_sem_agc` → SNR relatorio → AGC → `_radargrama_relatorio.png` + `_processada.png` (alias)
6. **Seleção detector** via `detector_input_mode` → `arr_detector`
7. **Migração F-K Kirchhoff** (numpy próprio) → `_migrada.png`
8. **IA de imagem** gpt-image-1 (off por padrão — `--sem-ia-imagem` sempre passado pelo worker)
9. **Detector:** Hough → CurveFit → DeltaT + física — entrada = `arr_detector`; filtro `det_depth_min_m=0.30m`
10. **Score filter** ≥30; anotações desenhadas sobre `arr_cientifico` (não sobre arr_proc)
11. **Velocity** por semblance; **Espectro** por alvo
12. **Preview RADAN 5m**: `arr_dewow_bp` (cópia independente) → AGC(window=80) → PNG com footer laranja; velocity = `preset["velocity_mns"]` (direto do preset); profundidade = `twtt_max_ns × velocity / 2`; campos `preview_depth_m` + `preview_velocity_mns` em `index_projeto.csv`
13. Outputs: `_anotada_completa.png` + `_anotada_alta_confianca.png` + `_radargrama_preview_radan_5m.png` + `_alvos.csv` + `index_projeto.csv` + `config_used.json`

---

## Matrizes numpy — finalidades separadas

| Arquivo | Conteúdo | Uso |
|---|---|---|
| `raw.npy` | Bruta pré-qualquer-filtro | Auditoria, ML futuro, evidência independente |
| `radargrama_cientifico.npy` | dewow+bp+tpow, sem AGC/bgremoval | Base das imagens anotadas; revisão Amilson |
| `processado_sem_agc.npy` | bgremoval+tpow, sem AGC | Análise física: amplitude/fase/classificação material |
| `processado_visual.npy` | Com AGC completo | Backward compat |
| `processado.npy` | Alias de `processado_visual.npy` | Backward compat |

---

## VELOCITY_POR_SOLO (v2.0.0 — derivado de v = c/√εr)

| Tipo de solo | velocity_mns | εr ref | Fonte |
|---|---|---|---|
| `standard` | 0.100 | 7–10 | USACE 1995, GuidelineGEO |
| `arenoso` | 0.130 | 4–6 | Daniels 2004, CLU-IN |
| `argiloso` | 0.070 | 14–22 | Reynolds 1997 |
| `umido` | 0.060 | 22–35 | USACE |
| `pedregoso` | 0.115 | 5–8 | EOAS UBC |

A1 em `main()`: aplica `VELOCITY_POR_SOLO[tipo_solo]` antes dos filtros_customizados. Se `velocity_mns` estiver explicitamente em `filtros_customizados`, prevalece.

---

## Bandpass — dois modos disponíveis

`aplicar_bandpass(prof, low_mhz, high_mhz, order, bandpass_tipo="butterworth")`

| `bandpass_tipo` | Implementação | Quando usar |
|---|---|---|
| `"butterworth"` | Butterworth SOS via `scipy.signal.butter` + `sosfiltfilt` (loop por traço) | Default — boa atenuação fora da banda |
| `"triangular"` | FIR `firwin2` com resposta triangular `fl→fc→fh` + `filtfilt` em bloco | Vazios, galerias, concreto armado — menos ringing em reflexões largas/múltiplas |

`numtaps` do FIR: `max(101, ceil(fs/fl) × 3) | 1` — garante ímpar e resolução em baixas frequências.

Presets com `"triangular"` por default: `270mhz_void`, `270mhz_concrete`.

**Desativar bandpass:** setar `bandpass_low_mhz=0` no preset ou `processing_config`. Convenção verificada no pipeline na linha 1220 de `pipeline_v1.py`. `bandpass_aplicado` fica `"desativado"` no `pipeline_metrics.json`.

---

## Preset base `270mhz`

```python
{
    "dewow_window":          5,
    "bandpass_low_mhz":      80,
    "bandpass_high_mhz":     500,
    "bandpass_order":        5,
    "bandpass_tipo":         "butterworth",   # "butterworth" (SOS) ou "triangular" (FIR firwin2)
    "bgremoval_traces":      30,
    "tpow_power":            0.5,
    "agc_window":            150,
    "velocity_mns":          0.1,   # sobrescrito por A1 via VELOCITY_POR_SOLO
    "contrast":              2.5,
    "colormap":              "gray",
    "dpi":                   150,
    "det_amp_threshold":     0.50,
    "det_h_min_m":           0.10,
    "det_h_max_m":           3.00,
    "det_top_n":             25,
    "det_min_score_csv":     30,
    "det_min_score_plot":    40,
    "fis_ativo":             True,
    "fis_amp_metal_thr":     0.65,   # metal/cabo: R→0.90–1.0 vs vazio≈0.50 (Fresnel, εr_solo=9)
    "fis_amp_nao_metal_thr": 0.22,   # PVC/PE: R≈0.27, HDPE: R≈0.33 (Fresnel)
    "detector_input_mode":   "raw",  # v2.0.0 — melhor CurveFit (82%)
    "det_depth_min_m":       0.30,   # v2.0.0 — elimina airwave
}
```

---

## Presets disponíveis (`--preset`)

| Nome | Diferenças do base | Uso típico |
|---|---|---|
| `270mhz` | — (base) | PATIO padrão, solo misto |
| `270mhz_clay` | v=0.07, bgremoval=20, tpow=0.70 | Solo argiloso/úmido |
| `270mhz_sandy` | v=0.13, agc_window=200 | Solo arenoso/seco |
| `270mhz_deep` | tpow=0.80, agc=100, det_h_max=5.0 | Alvos 3–5 m |
| `270mhz_void` | fis_amp_metal=0.30, fis_amp_nao_metal=0.45 | Vazios e galerias |
| `270mhz_concrete` | v=0.107, det_h_max=0.50, dewow=3 | Laje/piso de concreto |
| `default` | preset genérico (standalone, não herdado) | Fallback |

Os 5 derivados são criados via `{**PRESETS["270mhz"], **overrides}` em nível de módulo. Os mesmos 6 presets estão seedados em `gpr_presets` (banco).

---

## SNR gate — limiares por tipo de solo

`SNR_LIMIARES` — razão S/sigma Hilbert per-trace (janela ruído = 95% das amostras):

| Solo | limiar_minimo (→MINIMO) | limiar_padrao (→PADRAO) |
|---|---|---|
| standard / arenoso | 30.0 | 4.0 |
| argiloso | 20.0 | 3.5 |
| umido | 15.0 | 3.0 |
| pedregoso | 35.0 | 6.0 |

Comportamento por modo:
- `minimo` — tpow fixo em 0.3 (independente do valor do preset), AGC janela×2 (cap 300)
- `padrao` — preset base
- `agressivo` — tpow×1.5 (cap 1.2), AGC janela÷2

Valores SNR calibrados: PATIO_001=20.6dB, PATIO_002=17.5dB, PATIO_003=18.7dB, PATIO_004=17.5dB — todos em modo PADRAO.

---

## SNR medido em 3 pontos (v2.0.0)

| Campo `index_projeto.csv` | Estágio | Observação |
|---|---|---|
| `snr_raw_db` | Dado bruto | Governa modo (minimo/padrao/agressivo) |
| `snr_cientifico_db` | Após dewow+bp+tpow | Sempre > snr_raw (+5-6 dB em PATIO) |
| `snr_relatorio_db` | Após bgremoval+tpow (pré-AGC) | Sempre << snr_raw — bgremoval remove fundo+sinal |

---

## Flags CLI do pipeline

```
--sem-detector          pula detecção de hipérboles
--sem-fisica            pula análises físicas (material/espectro), mantém detecção geométrica
--sem-ia-imagem         pula gpt-image-1
--sem-migracao          pula migração Kirchhoff
--filter-config <json>  override de parâmetros do preset em JSON
--solo {standard,arenoso,argiloso,umido,pedregoso}
--preset {270mhz,270mhz_clay,270mhz_sandy,270mhz_deep,270mhz_void,270mhz_concrete,default}
--detector-input {raw,raw_dewow_bandpass,sem_agc,proc_agc_atual}  [v2.0.0]
```

---

## Colunas CSV de alvos (por alvo)

**Geométricas:** rank, x_m, depth_m, depth_hough_m, fit_ok, diam_est_m, diam_confianca, score
**Morfológicas:** prof_topo_m, largura_hiperbole_m, altura_hiperbole_m, tipo_tamanho
**Velocity:** velocity_usada_mns, velocity_estimada_mns, velocity_fonte
**Física:** tipo_material, confianca_tipo, amplitude_relativa_*, fase_consistente, evidencia_raw/sem_agc, snr_local
**Espectral:** freq_dominante_mhz, freq_centroide_mhz, razao_alta_baixa
**Score:** confidence_score_0_100, confidence_label_tecnico, confidence_label_relatorio, status_interpretacao, motivo_confianca

---

## pipeline_metrics.json — campos (Fase 11 + 15)

Salvo em `gpr-tabelas/{project_id}/{run_id}/{profile_id[:8]}/{stem}_pipeline_metrics.json`.
URL signed (10 anos) em `gpr_profiles.metricas_pipeline_url`.

Campos relevantes adicionados na Fase 15:
- `bandpass_aplicado`: `"desativado"` | `"80-500 MHz"` (ou outro range)
- `bandpass_low_mhz_usado`: 0 se desativado
- `bandpass_high_mhz_usado`, `bandpass_order_usado`, `bandpass_tipo_usado`
- `detector_input_mode`: modo de entrada do detector (`"raw"` por padrão)

Esses campos cobrem o **primeiro processamento** — `filtros_customizados` só existe no reprocessamento.

---

## KB_ScansoloPlataform

Diretório raiz: `KB_ScansoloPlataform/` (commitado; benchmark_real/ e PDFs excluídos via `.gitignore`)

| Arquivo/Pasta | Conteúdo |
|---|---|
| `KB_MASTER.md` | Referência consolidada: literatura GPR, εr por material, coeficientes Fresnel, velocity vs. solo |
| `GROUND_TRUTH/README_AMILSON.md` | Instruções para Amilson preencher validações manuais |
| `GROUND_TRUTH/template_validacao.csv` | Template CSV para `import_ground_truth.py` |
| `GROUND_TRUTH/PATIO/` | Validações do dataset PATIO (vazio — aguarda preenchimento) |
| `GROUND_TRUTH/HELPER/` | Validações do dataset HELPER (vazio — aguarda preenchimento) |
| `GROUND_TRUTH/CALIBRACAO/` | Alvos de profundidade conhecida para calibrar velocity (vazio) |
