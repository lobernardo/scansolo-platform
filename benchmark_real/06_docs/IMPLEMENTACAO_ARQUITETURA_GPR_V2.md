# Implementacao da Arquitetura GPR v2.0.0
> Gerado em: 2026-06-12
> Pipeline versao: 2.0.0
> Referencia: pipeline_v1.py (nome mantido por compat com worker)

---

## Resumo Executivo

A versao v2.0.0 do pipeline GPR da ScanSOLO introduz tres fluxos de processamento separados
a partir do mesmo dado bruto DZT. A mudanca principal e o detector de hiperboles: passa a
operar sobre o dado RAW (bruto) em vez do dado com AGC, aumentando a taxa de CurveFit de
24% para 82% nos 4 DZTs PATIO testados.

### Antes (v1.2.0)
- 1 fluxo: raw -> dewow -> bp -> bgremoval -> tpow -> AGC -> arr_proc
- Detector recebia arr_proc (com AGC) -> 24% CurveFit, 46% falsos positivos
- Imagem entregue ao Amilson = mesma do detector (com AGC)

### Depois (v2.0.0)
- 3 fluxos separados:
  1. CIENTIFICO: raw -> dewow -> bp -> tpow -> arr_cientifico (para Amilson)
  2. RELATORIO: raw -> dewow -> bp -> bgremoval -> tpow -> AGC -> arr_relatorio (para cliente)
  3. DETECTOR: controlado por detector_input_mode (default: raw -> 82% CurveFit)
- Anotacoes desenhadas sobre radargrama_cientifico (nao sobre arr_proc)

---

## 1. Motivacao — Benchmark de Entrada do Detector

### Resultados do benchmark (4 DZTs PATIO, 2026-06-12)

| Versao | n_cand medio | score_med | CF% | Falsos positivos* |
|--------|-------------|-----------|-----|-------------------|
| RAW | 28.8 | 56.8 | 82% | baixo |
| Raw+Dewow+BP | 21.0 | 51.6 | 75% | baixo |
| sem_AGC (bgremoval+tpow) | 26.0 | 42.7 | 70% | medio |
| proc+AGC (v1.2.0) | 28.2 | 28.0 | 24% | ALTO (46%**) |

*classificados via _classificador_candidatos.py (top-50 por versao)
**22/50 candidatos = airwave superficial com depth<=0.18m equalizados pelo AGC

### Por que arr_raw e melhor para o detector?

O AGC (Automatic Gain Control) e essencial para visualizacao — equaliza o decaimento de
amplitude em profundidade, tornando a imagem visualmente uniforme. Mas essa equalizacao
distorce o formato das hiperboles:

- Apice da hiperbole (sinal forte) e comprimido pelo AGC
- Cauda (sinal fraco) e amplificada
- O CurveFit (minimos quadrados) falha porque o shape real foi destruido

No dado RAW, as hiperboles tem o formato fisico correto (parabola de reflexao com amplitude
naturalmente decrescente nas asas). O CurveFit converge com 82% de taxa.

### Por que Raw+Dewow virava 0 candidatos?

O Dewow remove o offset DC (componente de frequencia zero). Apos dewow puro, a media de
cada traco e zerada. O limiar de amplitude do Hough (`amp_threshold=0.45`) e calculado como
fracao do valor absoluto maximo. Com o DC removido e sem outros filtros, a amplitude
absoluta dos tracos cai, e muitos pixels que antes passavam pelo limiar agora ficam abaixo.
Resultado: nenhum candidato passa o gate de amplitude do Hough. Solucao: usar RAW direto
ou adicionar bandpass apos o dewow (Raw+Dewow+BP tem 75% CF).

---

## 2. Arquitetura v2.0.0

### 2.1 Os tres fluxos

```
DZT (bruto)
    |
    +-- arr_raw  ---[dewow+bp]--> arr_dewow_bp
    |                                   |
    |          [tpow manual]            |  [bgremoval] -> arr_sem_agc_pos_bg
    |               |                  |       |
    |           arr_cientifico       [tpow]    |
    |           (dewow+bp+tpow)        |       |
    |           SEM bgremoval       arr_sem_agc (bgremoval+tpow)
    |           SEM AGC                |       |
    |                              [AGC] -> arr_proc_save
    |
    +-- FLUXO DETECTOR: selecionado por detector_input_mode
         default = arr_raw (82% CurveFit)

Saidas por DZT:
  _bruta.png                    <- arr_raw visualizado
  _radargrama_cientifico.png    <- arr_cientifico (dewow+bp+tpow, SEM AGC/bgremoval)
  _radargrama_relatorio.png     <- arr_sem_agc visualizado (COM bgremoval, SEM AGC)
  _processada.png               <- alias _radargrama_relatorio.png (backward compat)
  _anotada_completa.png         <- candidatos desenhados sobre _radargrama_cientifico
  _anotada_alta_confianca.png
  _alvos.csv
```

### 2.2 SNR medido em 3 pontos

| Campo index_projeto.csv | Significado |
|------------------------|-------------|
| snr_raw_db | SNR do dado bruto — governa modo (minimo/padrao/agressivo) |
| snr_cientifico_db | SNR apos dewow+bp+tpow — qualidade do fluxo cientifico |
| snr_relatorio_db | SNR apos bgremoval+tpow (pre-AGC) — impacto do bgremoval |

Observacao PATIO v2.0.0:
- snr_cientifico sempre > snr_raw (dewow+bp melhora SNR: +5.5 a +6.3 dB)
- snr_relatorio sempre << snr_raw (bgremoval remove sinal junto com fundo)
- O delta negativo do snr_relatorio NAO indica problemas — e esperado: bgremoval
  subtrai a media de 30 tracos, o que inclui o sinal. O que importa e o resultado visual.

### 2.3 Filtro depth_min

`det_depth_min_m = 0.30` (preset padrao)

Candidatos com depth_m < 0.30m sao descartados antes do CSV e do plot.
Motivacao: o AGC (v1.2.0) equalizava a airwave (reflexao direta no primeiro nanosegundo),
criando 22/50 falsos positivos com depth<=0.18m, score=15, fit_ok=False.
Com detector_input_mode=raw, a airwave nao e equalizada e raramente passa o gate de Hough.
O filtro depth_min e uma salvaguarda adicional para qualquer modo.

Resultado nos 4 DZTs PATIO:
- PATIO_001: 0 removidos
- PATIO_002: 0 removidos
- PATIO_003: 1 removido (confirmando que o filtro funciona)
- PATIO_004: 0 removidos

---

## 3. Parametros v2.0.0

### Novos parametros no preset 270mhz

| Parametro | Valor padrao | Descricao |
|-----------|-------------|-----------|
| detector_input_mode | "raw" | Matriz de entrada do detector |
| det_depth_min_m | 0.30 | Profundidade minima dos candidatos (m) |

### CLI — novo flag

```bash
python pipeline_v1.py \
  --input <pasta_dzts> \
  --output <pasta_saida> \
  --detector-input raw|raw_dewow_bandpass|sem_agc|proc_agc_atual
```

O flag `--detector-input` tem precedencia sobre o preset e sobre `--filter-config`.

---

## 4. Resultados PATIO v2.0.0

| DZT | SNR raw | SNR cient | SNR rel | n_alvos | alta | media | depth_min_rem |
|-----|---------|-----------|---------|---------|------|-------|---------------|
| PATIO_001 | 20.6 dB | 26.1 dB | -4.1 dB | 24 | 1 | 21 | 0 |
| PATIO_002 | 17.5 dB | 23.5 dB | -4.1 dB | 21 | 5 | 16 | 0 |
| PATIO_003 | 18.7 dB | 24.9 dB | -1.7 dB | 19 | 4 | 12 | 1 |
| PATIO_004 | 17.5 dB | 23.8 dB | -3.2 dB | 22 | 4 | 17 | 0 |
| **Total** | — | — | — | **86** | **14** | **66** | **1** |

CurveFit (fit_ok): PATIO_001=96%, PATIO_002=100%, PATIO_003=79%, PATIO_004=95%

---

## 5. Compatibilidade com v1.2.0

Todos os campos do index_projeto.csv da v1.2.0 estao presentes na v2.0.0.
Novos campos foram adicionados; nenhum foi removido.

| Campo v1.2.0 | Mantido em v2.0.0? | Observacao |
|-------------|-------------------|------------|
| imagem_processada | Sim | Agora aponta para _radargrama_relatorio.png (alias) |
| snr_imagem_db | Sim | Alias para snr_raw_db |
| snr_imagem_ratio | Sim | Alias para snr_raw_ratio |
| modo_processamento | Sim | — |
| array_proc_npy | Sim | processado.npy = processado_visual.npy (com AGC, compat) |
| array_sem_agc_npy | Sim | — |

Novos campos v2.0.0:
- imagem_radargrama_cientifico, imagem_radargrama_relatorio
- snr_raw_db, snr_raw_ratio (alias de snr_imagem_db/ratio)
- snr_cientifico_db, snr_cientifico_ratio
- snr_relatorio_db, snr_relatorio_ratio
- detector_input_mode
- n_removidos_depth_min
- array_cientifico_npy

---

## 6. Pendencias e Proximos Passos

### Calibracao (com Amilson)

| # | Item | Prioridade |
|---|------|-----------|
| C1 | Validar visualmente radargrama_cientifico vs. radargrama_relatorio | ALTA |
| C2 | Confirmar que candidatos RAW sao hiperboles reais (top-50 de cada PATIO) | ALTA |
| C3 | Calibrar fis_amp_metal_thr e fis_amp_nao_metal_thr com ~10 alvos conhecidos | MEDIA |
| C4 | Testar pipeline HELPER DZTs (128 arquivos) com detector_input_mode=raw | MEDIA |
| C5 | Velocity — DZTs com alvo de profundidade conhecida | MEDIA |

### Implementacao futura

| # | Item | Descricao |
|---|------|-----------|
| F1 | Modo raw_dewow_bandpass como alternativa | 75% CF, mais robusto contra ruido |
| F2 | CAR (curve_amp_ratio) como metrica adicional no CSV | Discrimina hiperbola real de artefato |
| F3 | Feedback Amilson -> ajuste automatico de depth_min e amp_threshold por projeto | Calibracao continua |
| F4 | Rodar _classificador_candidatos.py no HELPER dataset | Validacao em solo diferente |

---

## 7. Arquivos Criados nesta Versao

```
services/worker/pipeline/
  pipeline_v1.py              <- ATUALIZADO (v1.2.0 -> v2.0.0)
  _benchmark_detector.py      <- NOVO — benchmark 5 variacoes x 4 DZTs
  _classificador_candidatos.py <- NOVO — classificacao top-50 por versao
  _benchmark_output/
    RELATORIO_BENCHMARK.md    <- resultado do benchmark (arr_raw 82% CF)
    classificacao/
      RELATORIO_CLASSIFICACAO.md  <- arr_raw 54% hiperbolas, proc+AGC 8%
      <paneis por versao>

benchmark_real/
  06_docs/
    IMPLEMENTACAO_ARQUITETURA_GPR_V2.md  <- este arquivo
  04_benchmarks_detector/
    PATIO/{raw,raw_dewow_bandpass,sem_agc,proc_agc_atual}/  <- saidas por modo
    HELPER/{raw,...}/  <- saidas HELPER
```

---

*Gerado por Claude Code (Sonnet 4.6) em 2026-06-12 para ScanSOLO platform v2.0.0*
