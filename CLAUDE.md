# CLAUDE.md — ScanSOLO Platform
> Última atualização: 2026-06-17 (sistema de presets + gpr_presets table + Nova Entrada refatorada + job_recalibrar_velocity + tab Interpretada IA + velocity Processada 2 corrigida + download_file retry + bandpass sempre ativo)

---

## Stack

| Camada | Tecnologia | Destino |
|---|---|---|
| Frontend | Next.js 16 App Router + TypeScript + Tailwind | Vercel |
| Auth / DB / Storage | Supabase (PostgreSQL + RLS + Storage) | Supabase Cloud |
| Worker Python | services/worker/ — polling loop | Railway (Dockerfile + railway.toml) |
| IA | OpenAI GPT-4o (texto) + gpt-image-1 (imagem, off por padrão) | — |
| Storage brutos | Supabase Storage (gpr-uploads, gpr-images, gpr-tabelas) | — |

---

## Regras absolutas (nunca violar)

- `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DROPBOX_REFRESH_TOKEN`: só em env vars server-side / worker — NUNCA no frontend
- Variáveis sensíveis NUNCA com prefixo `NEXT_PUBLIC_`
- RLS obrigatório em todas as tabelas com dados de projeto
- Arquivos brutos `.DZT` nunca apagados — só versionados
- Reprocessamento gera novo `run_id` — nunca sobrescreve
- `Bandpass nunca pulado` — modo minimo ajusta tpow e AGC mas NÃO pula o bandpass; DZTs com SNR alto (onda direta forte) precisam mais do filtro, não menos

---

## Personas

| Role | Acesso |
|---|---|
| `operador_campo` | Nova Entrada + upload + ver status próprio |
| `tecnico` | Projetos assigned_to = seu uid |
| `socio` / `admin` | Tudo |

---

## Fases implementadas

| Fase | Descrição | Status |
|---|---|---|
| 0 | Fundação monorepo (Next.js + Supabase + worker base) | ✅ |
| 1 | Upload DZT + pipeline GPR (GPRPy) + imagens processadas | ✅ |
| 2 | IA GPT-4o por alvo + `_interpretada_ia.png` | ✅ |
| 3 | Revisão técnica — tela interativa por alvo | ✅ |
| 4 | Cartografia — DXF + KML + GeoJSON + CSV | ✅ |
| 5 | Relatório DOCX (python-docx) + PDF via LibreOffice | ✅ |
| 6 | Nova entrada: filtros configuráveis + UI 2-step + `processing_config` | ✅ |
| 7 | `_migrada.png` (Kirchhoff numpy) + velocity estimada + espectro por alvo | ✅ |
| 8 | Relatório de inferências sob demanda (job `inferencias` → `.txt` para Amilson) | ✅ |
| 9 | Workflow da imagem interpretada (Amilson aprova/regenera/anota manualmente) | ✅ |
| 10 | Preview RADAN 5m (`_radargrama_preview_radan_5m.png`) + job `ia_p2` (anotações sobre P2) + delete projeto + `skip_ia` flag | ✅ |
| 11 | Loop de aprendizado: `pipeline_metrics.json` + `gpr_ground_truth` + `job_recalibrar` + dashboard qualidade + `parse_dzx.py` + GPT-4o contexto do projeto + campos revisão (`confianca_revisao`, `e_referencia`, `profundidade_real_m`) | ✅ |
| 12 | Sistema de presets: `gpr_presets` table + 6 presets científicos seedados + `/presets` UI + Nova Entrada com selector + `job_gpr` fetch+merge preset → project config | ✅ |

---

## Pipeline GPR — `services/worker/pipeline/pipeline_v1.py`

Versão: **2.0.0** (atualizado 2026-06-12)

### Arquitetura v2.0.0 — Três Fluxos Separados

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

### Sequência por DZT

1. Leitura via GPRPy → `_bruta.png` + `raw.npy`
2. **SNR gate raw** → decide modo: `minimo` / `padrao` / `agressivo`
3. **Dewow + Bandpass** → `arr_dewow_bp` (bifurcação dos fluxos) — bandpass sempre aplicado independente do modo
4. **Fluxo Científico:** `arr_dewow_bp` → tpow manual → `arr_cientifico` → `_radargrama_cientifico.png` + SNR cientifico
5. **Fluxo Relatório:** `arr_dewow_bp` → bgremoval → tpow → `arr_sem_agc` → SNR relatorio → AGC → `_radargrama_relatorio.png` + `_processada.png` (alias)
6. **Seleção detector** via `detector_input_mode` → `arr_detector`
7. **Migração F-K Kirchhoff** (numpy próprio) → `_migrada.png`
8. **IA de imagem** gpt-image-1 (off por padrão)
9. **Detector:** Hough → CurveFit → DeltaT + física — entrada = `arr_detector`; filtro `det_depth_min_m=0.30m`
10. **Score filter** ≥30; anotações desenhadas sobre `arr_cientifico` (não sobre arr_proc)
11. **Velocity** por semblance; **Espectro** por alvo
12. **Preview RADAN 5m**: `arr_dewow_bp` (cópia independente) → AGC(window=80) → PNG com footer laranja de aviso; velocity = `preset["velocity_mns"]` (direto do preset, não mais calculado de forma invertida); profundidade derivada de `twtt_max_ns × velocity / 2`; campos `preview_depth_m` + `preview_velocity_mns` adicionados ao `index_projeto.csv`
13. `_anotada_completa.png` + `_anotada_alta_confianca.png` + `_radargrama_preview_radan_5m.png` + `_alvos.csv` + `index_projeto.csv` + `config_used.json`

### Matrizes numpy — finalidades separadas

| Arquivo | Conteúdo | Uso |
|---|---|---|
| `raw.npy` | Bruta pré-qualquer-filtro | Auditoria, ML futuro, evidência independente |
| `radargrama_cientifico.npy` | dewow+bp+tpow, sem AGC/bgremoval | Base das imagens anotadas; revisão Amilson |
| `processado_sem_agc.npy` | bgremoval+tpow, sem AGC | Análise física: amplitude/fase/classificação material |
| `processado_visual.npy` | Com AGC completo | Backward compat |
| `processado.npy` | Alias de `processado_visual.npy` | Backward compat |

### VELOCITY_POR_SOLO (v2.0.0 — derivado de v = c/√εr)

| Tipo de solo | velocity_mns | εr ref | Fonte |
|---|---|---|---|
| `standard` | 0.100 | 7–10 | USACE 1995, GuidelineGEO |
| `arenoso` | 0.130 | 4–6 | Daniels 2004, CLU-IN |
| `argiloso` | 0.070 | 14–22 | Reynolds 1997 |
| `umido` | 0.060 | 22–35 | USACE |
| `pedregoso` | 0.115 | 5–8 | EOAS UBC |

A1 em `main()`: aplica `VELOCITY_POR_SOLO[tipo_solo]` antes dos filtros_customizados. Se `velocity_mns` estiver explicitamente em `filtros_customizados`, prevalece.

### Presets disponíveis (`--preset`)

| Nome | Diferenças do base | Uso típico |
|---|---|---|
| `270mhz` | — (base) | PATIO padrão, solo misto |
| `270mhz_clay` | v=0.07, bgremoval=20, tpow=0.70 | Solo argiloso/úmido |
| `270mhz_sandy` | v=0.13, agc_window=200 | Solo arenoso/seco |
| `270mhz_deep` | tpow=0.80, agc=100, det_h_max=5.0 | Alvos 3–5 m |
| `270mhz_void` | fis_amp_metal=0.30, fis_amp_nao_metal=0.45 | Vazios e galerias |
| `270mhz_concrete` | v=0.107, det_h_max=0.50, dewow=3 | Laje/piso de concreto |
| `default` | preset genérico (standalone, não herdado) | Fallback |

Os 5 derivados são criados via `{**PRESETS["270mhz"], **overrides}` em nível de módulo. Os mesmos 6 presets estão seedados em `gpr_presets` (banco) para uso pela UI.

### Bandpass — dois modos disponíveis

`aplicar_bandpass(prof, low_mhz, high_mhz, order, bandpass_tipo="butterworth")`

| `bandpass_tipo` | Implementação | Quando usar |
|---|---|---|
| `"butterworth"` | Butterworth SOS via `scipy.signal.butter` + `sosfiltfilt` (loop por traço) | Default — boa atenuação fora da banda |
| `"triangular"` | FIR `firwin2` com resposta triangular `fl→fc→fh` + `filtfilt` em bloco | Vazios, galerias, concreto armado — menos ringing em reflexões largas/múltiplas |

`numtaps` do FIR: `max(101, ceil(fs/fl) × 3) | 1` — garante ímpar e resolução em baixas frequências.

Presets com `"triangular"` por default: `270mhz_void`, `270mhz_concrete`.

### Preset base `270mhz`

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

### SNR gate — limiares por tipo de solo

`SNR_LIMIARES` — razão S/sigma Hilbert per-trace (janela ruído = 95% das amostras):

| Solo | limiar_minimo (→MINIMO) | limiar_padrao (→PADRAO) |
|---|---|---|
| standard / arenoso | 30.0 | 4.0 |
| argiloso | 20.0 | 3.5 |
| umido | 15.0 | 3.0 |
| pedregoso | 35.0 | 6.0 |

Comportamento por modo:
- `minimo` — tpow×0.6, AGC janela×2 (bandpass sempre aplicado — DZTs com SNR alto têm onda direta forte, precisam do filtro)
- `padrao` — preset base (todos os 4 DZTs PATIO ficam aqui com os limiares atuais)
- `agressivo` — tpow×1.5, AGC janela÷2

Valores SNR raw (Hilbert per-trace) calibrados: PATIO_001=20.6dB, PATIO_002=17.5dB, PATIO_003=18.7dB, PATIO_004=17.5dB — todos em modo PADRAO.

### SNR medido em 3 pontos (v2.0.0)

| Campo index_projeto.csv | Estágio | Observação |
|---|---|---|
| `snr_raw_db` | Dado bruto | Governa modo (minimo/padrao/agressivo) |
| `snr_cientifico_db` | Após dewow+bp+tpow | Sempre > snr_raw (+5-6 dB em PATIO) |
| `snr_relatorio_db` | Após bgremoval+tpow (pré-AGC) | Sempre << snr_raw — bgremoval remove fundo+sinal |

### Flags CLI do pipeline

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

### Colunas CSV de alvos (por alvo)

**Geométricas:** rank, x_m, depth_m, depth_hough_m, fit_ok, diam_est_m, diam_confianca, score  
**Morfológicas:** prof_topo_m, largura_hiperbole_m, altura_hiperbole_m, tipo_tamanho  
**Velocity:** velocity_usada_mns, velocity_estimada_mns, velocity_fonte  
**Física:** tipo_material, confianca_tipo, amplitude_relativa_*, fase_consistente, evidencia_raw/sem_agc, snr_local  
**Espectral:** freq_dominante_mhz, freq_centroide_mhz, razao_alta_baixa  
**Score:** confidence_score_0_100, confidence_label_tecnico, confidence_label_relatorio, status_interpretacao, motivo_confianca  

---

## Worker — `services/worker/`

### worker_main.py — polling loop

- Polling a cada `WORKER_POLL_INTERVAL_SECONDS` (default: 10s)
- Busca 1 job por vez em `processing_jobs` (status=`aguardando`, ordenado por `created_at`)
- Despacha por `job_type`:

| job_type | Handler | Descrição |
|---|---|---|
| `gpr` | `job_gpr.handle_gpr_job` | Roda pipeline_v1.py via subprocess |
| `ia` | `job_ia.handle_ia_job` | GPT-4o por alvo + `_interpretada_ia.png` |
| `ia_p2` | `job_ia.handle_ia_p2_job` | Anotações do detector sobre `imagem_preview_radan_5m` (sem nova chamada GPT-4o) |
| `cartografia` | `job_cartografia.handle_cartografia_job` | DXF + KML + GeoJSON + CSV |
| `relatorio` | `job_relatorio.handle_relatorio_job` | DOCX + PDF via LibreOffice |
| `inferencias` | `job_gpr.handle_inferencias_job` | Relatório `.txt` sob demanda (não altera status) |
| `interpretada` | `job_interpretada.handle_interpretada_job` | Imagem interpretada com alvos aprovados |
| `recalibrar` | `job_recalibrar.handle_recalibrar_job` | Otimiza thresholds via `gpr_ground_truth` (min 20 amostras) → salva candidato JSON em `gpr-tabelas/recalibracao/` |
| `recalibrar_velocity` | `job_recalibrar_velocity.handle_recalibrar_velocity_job` | Recalcula profundidades de perfis com nova velocity; atualiza `gpr_profiles` + `projects.processing_config` |

### job_gpr.py

Dois fluxos:
1. **Job completo** (sem `payload.profile_id`): baixa todos DZTs do projeto → roda pipeline → persiste perfis + alvos + imagens (inclusive `imagem_preview_radan_5m_url`)
2. **Reprocessamento individual** (com `payload.profile_id`): reprocessa um único DZT com filtros customizados → não altera status do projeto, não cria job IA

**`skip_ia` flag:** `processing_config.skip_ia = true` → worker não cria job `ia` após o GPR concluir. Disponível na UI de Nova Entrada como checkbox. Útil para testes e validação local sem custo de GPT-4o.

**`--sem-ia-imagem` sempre ativo:** flag passada em toda execução do worker (job completo e reprocessamento) — `gpt-image-1` nunca roda via worker, independente de `processing_config`.

**Integração de presets (Fase 12):** `_get_processing_config` busca `projects.preset_id` → carrega `gpr_presets.parameters` → merge com `projects.processing_config` (projeto override ganha). O `--preset 270mhz` é passado como base ao subprocess; o merged dict é passado via `--filter-config` sobrescrevendo todos os campos do preset carregado do banco.

### supabase_client.py — download_file retry

`download_file(bucket, path)` faz até 3 tentativas com backoff exponencial (1s, 2s, 4s). Loga cada retry via structlog (`download_file_retry`). Levanta a última exceção se todas as tentativas falharem.

### job_ia.py

1. Interpreta cada alvo via GPT-4o (prompt em inglês, resposta JSON com 10 campos)
2. Gera `_interpretada_ia.png` com labels `[tipo] [conf]%` sobrepostos
3. Salva URL em `gpr_profiles.imagem_interpretada_url`
4. Se `project.auto_accept_ia = true`: insere `technical_reviews` automaticamente (alta→planta+rel, média→só planta, baixa→descartado) → avança para `revisao_concluida`
5. Senão: avança para `ia_concluida` → aguarda revisão manual

**Categorias de tipo IA (prompt):** tubulacao_agua, tubulacao_gas, tubulacao_esgoto, cabo_eletrico, cabo_telecom, galeria_concreto, vazio_ar, rocha, inconclusivo

**Observação de calibração (2026-06-09):** testes com 13 imagens RADAN do Amilson (HELPAVPA) mostraram forte viés do GPT-4o para `galeria_concreto` (~80% dos alvos). Provável causa: sem contexto do projeto (solo, cliente, tipo de obra), o modelo escolhe a categoria de maior diâmetro como "segura". Mitigação: `_build_system_prompt(project)` injeta bloco PROJECT CONTEXT (tipo_obra, area_m2, antena_freq_mhz). Validar em produção se viés reduziu.

### job_cartografia.py

Gera: DXF (camadas por tipo), KML (placemarks georreferenciados), GeoJSON, CSV de campo  
Upload para `gpr-tabelas/{project_id}/`

### job_relatorio.py

Gera DOCX via python-docx + converte para PDF via LibreOffice (instalado no Dockerfile do Railway)  
Upload para `gpr-tabelas/{project_id}/`

### job_ia.py — handle_ia_p2_job (Fase 10)

Disparado por `requestIaP2(profileId)` via server action → job `ia_p2` em `processing_jobs`

1. Reusa resultados do job `ia` já existentes no perfil (sem nova chamada GPT-4o)
2. Baixa `imagem_preview_radan_5m_url` do Storage (`gpr-images`)
3. Usa `depth_preview_m` de `filtros_customizados` (ou 5.0 por padrão) como escala de profundidade
4. Desenha anotações do detector (rank / profundidade / diâmetro) no mesmo estilo de `plotar_deteccoes` (Anotada IA) — alvos fora da janela visível são silenciados
5. Upload → `gpr-images/{project_id}/{run_id}/{stem}_anotada_p2.png`
6. Salva URL em `gpr_profiles.imagem_interpretada_ia_p2_url`

**Frontend:** aba "IA Proc.2" visível quando Processada 2 + IA existem; botões "Interpretar Proc.2" / "Regenerar IA P2"

### job_interpretada.py (Fase 9)

Disparado por `finalizeReview` → job `interpretada` em `processing_jobs`

1. Busca perfis do projeto (run mais recente via `run_id`)
2. Para cada perfil: pega alvos aprovados (`technical_reviews.vai_para_relatorio=true`)
3. Baixa `_processada.png` do Storage (`gpr-images`)
4. Desenha marcadores coloridos por tipo em PT (círculo + label tipo/profundidade/diâmetro) → `_interpretada.png`
5. Upload para `gpr-images/{project_id}/{run_id}/{stem}_interpretada.png`
6. Atualiza `gpr_profiles.imagem_interpretada_url` + `imagem_interpretada_status = "pendente"`
7. Salva `ia_training_examples` com alvos aprovados (loop de aprendizado futuro)

**Status do perfil** (`gpr_profiles.imagem_interpretada_status`):
- `pendente` — gerada, aguarda aprovação de Amilson
- `aprovado` — Amilson aprovou; será usada no relatório
- `regenerando` — nova rodada de IA solicitada (novo job `interpretada`)
- `manual` — Amilson anotou diretamente no canvas

### job_gpr.py — relatório de inferências (sob demanda)

`gerar_relatorio_inferencias(df_campo, projeto, preset) -> str`
- Filtra `confidence_label_tecnico in ("alta", "media")`
- Colunas: Linha | # | Dist.(m) | P.Topo(m) | P.Eixo(m) | Diâm.(m) | Larg.(m) | Tam. | Material | Conf.
- `prof_topo_m` estimado como `depth_m − diam_est_m / 2` quando ausente no CSV
- Inclui legenda técnica e avisos de calibração de velocity no rodapé
- Upload para `gpr-tabelas/{project_id}/inferencias.txt` (upsert)
- **Não altera `project.status`** — job independente

### job_recalibrar.py (Fase 11)

Disparado manualmente via INSERT em `processing_jobs` (`job_type='recalibrar'`) ou pelo botão no dashboard de qualidade.

1. Busca todos os rows de `gpr_ground_truth` (mínimo 20 amostras)
2. Inverte `e_falso_positivo` → `e_verdadeiro_positivo` para cálculos
3. **Score threshold (F1):** varre 10–90 (step=5), maximiza F1 = 2TP/(2TP+FP+FN)
4. **det_amp_threshold:** mediana(`amplitude_relativa_max` dos VP) − 0.1×IQR; requer ≥5 amostras com esse campo
5. **det_depth_min_m:** se >5 FP com `depth_m < 0.5m` → mediana + 0.05m; senão mantém 0.30
6. Salva candidato JSON em `gpr-tabelas/recalibracao/candidato_<ts>.json` com `aprovado: false`
7. **NÃO aplica thresholds automaticamente** — requer revisão manual

### job_recalibrar_velocity.py (Fase 12)

Disparado via painel "Calibrar velocity do solo" em `/projetos/[id]`.

1. Valida payload (`project_id`, `velocity_mns` obrigatórios; range 0.04–0.35)
2. Busca run mais recente do projeto; itera sobre perfis do run
3. Para cada perfil: reconstrói `twtt_max_ns = prof_antiga × 2 / velocity_antiga`; calcula `nova_profundidade = twtt_max_ns × nova_velocity / 2`; atualiza `gpr_profiles`
4. Atualiza `projects.processing_config` com nova velocity
5. Erros por perfil são logados e pulados — não aborta o job

### job_interpretada.py — ground truth feeding (Fase 11)

Após `ia_training_examples`, faz upsert de cada alvo revisado em `gpr_ground_truth`:
- `e_falso_positivo = not vai_para_relatorio`
- `confianca_revisao` normalizada: `alta/media/baixa → certa/provavel/duvidosa` (constraint do banco)
- Upsert em `(profile_id, target_rank)` — idempotente
- Bloco em try/except — nunca aborta o job se a tabela não existir

### job_gpr.py — pipeline metrics upload (Fase 11)

Após processamento de cada DZT, faz upload de `{stem}_pipeline_metrics.json` para `gpr-tabelas/{project_id}/{run_id}/{profile_id[:8]}/`:
- URL signed (10 anos) salva em `gpr_profiles.metricas_pipeline_url`
- `dzt_sha256` logado (não salvo em coluna separada ainda)
- Bloco em try/except — nunca aborta o job

### job_ia.py — GPT-4o com contexto do projeto (Fase 11)

`_build_system_prompt(project: dict)` injeta bloco PROJECT CONTEXT entre a explicação do radargrama e a lista de categorias:
- `codigo_projeto`, `tipo_obra` (mapeado via `TIPO_OBRA_EN` para inglês), `area_m2`, `antena_freq_mhz`, `contato_nome`
- Reduz viés `galeria_concreto` ao dar contexto de tipo de obra ao modelo

### import_ground_truth.py (Fase 11)

`services/worker/scripts/import_ground_truth.py` — importação batch de CSV para `gpr_ground_truth`.

- Lê CSV com colunas: `profile_id`, `target_rank`, `e_falso_positivo`, `depth_m`, `amplitude_relativa_max`, `confianca_revisao`, `notas`
- `confianca_revisao` aceita `certa/provavel/duvidosa` ou `alta/media/baixa` (normalizado automaticamente)
- Upsert em `(profile_id, target_rank)` — idempotente
- Uso: `python scripts/import_ground_truth.py --csv <arquivo.csv> --project <project_id>`
- Template em `KB_ScansoloPlataform/GROUND_TRUTH/template_validacao.csv`

### parse_dzx.py (Fase 11)

`services/worker/pipeline/parse_dzx.py` — parser stdlib-only para arquivos `.DZX` (GSSI).

- `parse_dzx(path) -> dict` — nunca levanta exceção
- Suporta variantes de tag SIR-4000/SIR-30 (ex: `Latitude|LAT|lat|Y`)
- Containers suportados: `<Marks>`, `<GPS>`, `<GpsData>`, raiz
- Deduplicação por `TraceNumber`
- `haversine_m()` para distância entre primeiro e último mark GPS
- Campos escalares → `index_projeto.csv`; `dzx_marks` lista completa → `pipeline_metrics.json` apenas

---

## KB_ScansoloPlataform — Base de conhecimento GPR

Diretório raiz: `KB_ScansoloPlataform/` (commitado; benchmark_real/ e PDFs excluídos via `.gitignore`)

| Arquivo/Pasta | Conteúdo |
|---|---|
| `KB_MASTER.md` | Referência consolidada: literatura GPR, εr por material, coeficientes Fresnel, velocity vs. solo |
| `GROUND_TRUTH/README_AMILSON.md` | Instruções para Amilson preencher validações manuais |
| `GROUND_TRUTH/template_validacao.csv` | Template CSV para importação via `import_ground_truth.py` |
| `GROUND_TRUTH/PATIO/` | Validações do dataset PATIO (vazio — aguarda preenchimento) |
| `GROUND_TRUTH/HELPER/` | Validações do dataset HELPER (vazio — aguarda preenchimento) |
| `GROUND_TRUTH/CALIBRACAO/` | Alvos de profundidade conhecida para calibrar velocity (vazio) |

---

## Detector de hipérboles — `pipeline/detector_hiperboles.py`

Versão: **1.1**

**Fluxo:** Hough adaptado → CurveFit (mínimos quadrados) → DeltaT (reflexão topo+fundo) → enriquecimento físico → score composto 0-100

**Parâmetros DEFAULT_PARAMS** (calibrados para PATIO 270 MHz):

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

**Entrada:** `arr_proc` = float32 numpy array (com AGC) — **não** um PNG carregado do disco  
**Física:** usa `arr_sem_agc` para amplitude/fase (sem distorção do AGC) e `arr_raw` como evidência independente

---

## Script de validação — `pipeline/testar_imagem_externa.py`

Ferramenta standalone para testar o detector em imagens JPG já processadas pelo RADAN (output do Amilson). **Não é equivalente ao pipeline completo.**

**O que faz:**
1. Recebe JPG/PNG processado pelo RADAN
2. Aplica crop de eixos matplotlib (opcional, `--crop`)
3. Aplica bgremoval simplificado (média horizontal por linha)
4. Roda `detectar_hiperboles` + `enriquecer_deteccoes_fisica`
5. Gera `_anotada.png` + chama GPT-4o por alvo → `_interpretada.txt`

**O que NÃO faz (diferenças do pipeline real):**
- Não lê DZT bruto — recebe JPG já processado
- Não roda dewow / bandpass / tpow / AGC / migração
- O detector recebe imagem uint8 convertida de JPEG — não o float32 do GPRPy
- Aplica bgremoval extra em cima do que o RADAN já processou
- Parâmetros de escala (depth_max, dist_max) são manuais via CLI, não vêm dos metadados do DZT

**Uso:**
```bash
python pipeline/testar_imagem_externa.py <imagem.jpg> \
  --depth-max 5.0 --dist-max 8.82 --min-score 40
```

**Flags:** `--depth-max`, `--dist-max`, `--min-score`, `--sem-ia`, `--crop`

**Outputs:** salvos na mesma pasta da imagem de entrada:
- `<stem>_anotada.png` — detector plotado sobre a imagem
- `<stem>_interpretada.txt` — GPT-4o por alvo (tipo, confiança, justificativa técnica, custo)

**Dataset testado (2026-06-09):** 13 imagens das 126 disponíveis em `HELPAVPA_imagens georada rproc joeg/` (pasta ScanSOLO raiz, fora do repo). Imagens 0001–0013 processadas. 0014–0126 pendentes.

---

## Frontend — `apps/web/`

### Rotas principais

| Rota | Componente | Função |
|---|---|---|
| `/` | `page.tsx` | Redirect para dashboard |
| `/login` | `login/page.tsx` | Auth Supabase |
| `/dashboard` | `dashboard/page.tsx` | Visão geral de projetos |
| `/projetos` | `projetos/page.tsx` + `ProjetosTable.tsx` | Lista de projetos |
| `/nova-entrada` | `nova-entrada/page.tsx` | Criar projeto: selector de preset (obrigatório) + summary dos parâmetros-chave + accordion "Personalizar" com overrides → `preset_id` + `processing_config` salvos no projeto |
| `/projetos/[id]` | `ProjectDetailClient.tsx` | Status + timeline + tabs de imagem (Bruta / Processada / Anotada IA / **Interpretada IA** / Processada 2 / Anotada P2) + botão deletar + painel "Ajustar Filtros" por perfil (reprocessamento individual com polling automático 5s + `router.refresh()` ao concluir) + painel "Calibrar velocity do solo" |
| `/projetos/[id]/upload` | `UploadClient.tsx` | Upload adicional de DZTs |
| `/projetos/[id]/revisao` | `ReviewClient.tsx` | Revisão técnica por alvo |
| `/projetos/[id]/interpretada` | `InterpretadaClient.tsx` | Aprovação/regeneração da imagem interpretada |
| `/projetos/[id]/cartografia` | `CartografiaClient.tsx` | Download DXF/KML/GeoJSON |
| `/projetos/[id]/relatorio` | `RelatorioClient.tsx` | Gerar e baixar relatório + inferências |
| `/presets` | `PresetsClient.tsx` | Cards de presets (sistema + personalizados), expand parâmetros, modal criar/editar/duplicar (admin/socio apenas) |
| `/admin/qualidade` | `QualidadeClient.tsx` | Dashboard de qualidade — ground truth, F1, candidatos de recalibração, botão disparar job (visível apenas para `socio`/`admin`) |
| `/api/presets` | `route.ts` (GET) | Retorna presets ativos para o selector client-side da Nova Entrada |

### Server actions — `apps/web/app/actions/preset-actions.ts`

`getPresets`, `getPresetById`, `createPreset`, `updatePreset`, `deletePreset` (soft delete via `is_active=false`), `duplicatePreset`. Apenas `admin`/`socio` podem criar/editar/deletar.

### Fluxo de status do projeto

```
aguardando_arquivos
→ aguardando_processamento
→ processando_gpr
→ gpr_concluido
→ processando_ia
→ ia_concluida            (revisão manual) | revisao_concluida (auto_accept_ia=true)
→ revisao_em_andamento
→ revisao_concluida
→ processando_interpretada
→ interpretada_gerada
→ aguardando_cartografia
→ cartografia_concluida   | cartografia_pendente_dados
→ aguardando_relatorio
→ relatorio_em_andamento
→ relatorio_gerado
→ finalizado
```

---

## Banco de dados — tabelas principais

### `projects`

| Campo | Tipo | Uso |
|---|---|---|
| `status` | enum | Fluxo do pipeline |
| `preset_id` | uuid FK | Preset selecionado na Nova Entrada (referência a `gpr_presets.id`) |
| `processing_config` | JSONB | Overrides sobre o preset (campos específicos do projeto) |
| `auto_accept_ia` | boolean | Auto-aprovação sem revisão manual |
| `codigo_projeto` | text | Ex: PT-GPR-SOL-036 |
| `contato_nome` | text | A/C do cliente |
| `area_m2` | float | Área levantada |
| `antena_freq_mhz` | int | 270 (hardcoded por ora) |
| `tem_pipe_locator` | boolean | — |

### `gpr_presets`

| Campo | Tipo | Uso |
|---|---|---|
| `id` | uuid PK | — |
| `name` | text | Nome legível (ex: `270mhz_clay`) |
| `description` | text | Descrição de uso |
| `scientific_basis` | text | Referência bibliográfica |
| `target_scenario` | text | Cenário de aplicação |
| `antenna_freq_mhz` | int | Frequência de antena alvo (270 por padrão) |
| `is_system` | boolean | Presets do sistema são read-only — sem editar/deletar pela UI |
| `is_active` | boolean | Soft delete |
| `created_by` | uuid FK | Autor (null para presets do sistema) |
| `parameters` | JSONB | Todos os parâmetros do pipeline (mesmo formato do PRESETS dict em pipeline_v1.py) |

**RLS:** leitura pública (autenticado); insert/update/delete apenas para `is_system=false` por `admin`/`socio`.

**Presets seedados (is_system=true):** `270mhz`, `270mhz_clay`, `270mhz_sandy`, `270mhz_deep`, `270mhz_void`, `270mhz_concrete`

### `gpr_profiles`

| Campo | Tipo | Uso |
|---|---|---|
| `run_id` | uuid | Versão do processamento (nunca sobrescreve) |
| `imagem_bruta_url` | text | URL pública `gpr-images` — `_bruta.png` |
| `imagem_processada_url` | text | URL pública `gpr-images` — `_processada.png` (alias de `_radargrama_relatorio.png`) |
| `imagem_anotada_url` | text | URL pública `gpr-images` — `_anotada_completa.png` (sobre radargrama científico) |
| `imagem_migrada_url` | text | URL pública `gpr-images` |
| `imagem_preview_radan_5m_url` | text | URL pública `gpr-images` — `_radargrama_preview_radan_5m.png` (5m preview) |
| `imagem_interpretada_url` | text | URL pública — `_interpretada_ia.png` (job_ia) |
| `imagem_interpretada_ia_p2_url` | text | URL pública — `_anotada_p2.png` (job_ia_p2, sobre preview RADAN 5m) |
| `imagem_interpretada_status` | enum | pendente / aprovado / regenerando / manual |
| `imagem_interpretada_manual_data` | JSONB | Anotações do canvas manual |
| `csv_alvos_url` | text | URL signed `gpr-tabelas` |
| `snr_imagem_db` | float | SNR em dB (Hilbert per-trace) |
| `snr_imagem_ratio` | float | S/sigma ratio |
| `modo_processamento` | text | minimo / padrao / agressivo |
| `tipo_solo` | text | solo usado no SNR gate |
| `filtros_customizados` | JSONB | Override de filtros no reprocessamento |
| `metricas_pipeline_url` | text | URL signed (10 anos) para `{stem}_pipeline_metrics.json` em `gpr-tabelas` |

### `detected_targets`

Armazena todos os alvos detectados por perfil. Campos principais: `rank`, `x_m`, `depth_m`, `diam_est_m`, `confidence_score_0_100`, `confidence_label_tecnico`, `confidence_label_relatorio` (aceita `alta` / `media` / `baixa`), `tipo_material`, `status_interpretacao`.

### `technical_reviews`

Decisões de revisão por alvo: `vai_para_planta`, `vai_para_relatorio`, `tipo_confirmado`, `observacoes`, `revisado_por`.

### `processing_jobs`

| Campo | Tipo | Uso |
|---|---|---|
| `job_type` | enum | gpr / ia / ia_p2 / cartografia / relatorio / inferencias / interpretada / recalibrar / recalibrar_velocity |
| `status` | enum | aguardando / processando / concluido / erro |
| `payload` | JSONB | Parâmetros opcionais (ex: `profile_id` para reprocessamento) |
| `error_message` | text | Mensagem de erro se status=erro |

### `ia_training_examples`

Alvos aprovados pelo Amilson salvos para futura melhoria do modelo. Campos: `project_id`, `profile_id`, `target_data` (JSONB com geometria + tipo confirmado), `source` (aprovacao / canvas).

---

## Supabase Storage — buckets

| Bucket | Conteúdo | Visibilidade |
|---|---|---|
| `gpr-uploads` | DZTs brutos | Privado |
| `gpr-images` | PNGs (bruta / processada / anotada / interpretada / migrada / preview_radan_5m / anotada_p2) | Público |
| `gpr-tabelas` | CSVs, DXF, KML, GeoJSON, DOCX, PDF, inferencias.txt, pipeline_metrics.json, candidatos de recalibração | Privado |

---

## Migrations aplicadas

| Arquivo | Conteúdo | Status remoto |
|---|---|---|
| 20260527000001 | Schema inicial (11 tabelas + enums + índices) | ✅ |
| 20260527000002 | RLS completo por perfil | ✅ |
| 20260528000001 | Storage buckets | ✅ |
| 20260529000001 | Campos de detecção (cartography) | ✅ |
| 20260529000002 | MIME types gpr-tabelas (fase 4+5) | ✅ |
| 20260530000001 | report_project_fields (docx_storage_url, approved_at, codigo_projeto etc.) | ✅ |
| 20260602000001 | processing_config JSONB em projects | ✅ |
| 20260602000002 | auto_accept_ia BOOLEAN + imagem_interpretada_url em gpr_profiles | ✅ |
| 20260603000001 | imagem_interpretada_status + imagem_interpretada_manual_data + ia_training_examples; enum extensions | ✅ |
| 20260606000001 | fix constraint confidence_label_relatorio — adiciona 'media' aos valores aceitos | ✅ |
| 20260608000001 | SNR gate: snr_imagem_db, snr_imagem_ratio, modo_processamento, tipo_solo em gpr_profiles | ✅ |
| 20260615000001 | `imagem_preview_radan_5m_url` em gpr_profiles (Preview RADAN 5m) | ✅ |
| 20260615000002 | `ia_p2` no enum job_type + `imagem_interpretada_ia_p2_url` em gpr_profiles | ✅ |
| 20260617000001 | `recalibrar_velocity` no enum job_type | pendente push |
| 20260617000002 | `gpr_presets` table + RLS + `preset_id` FK em projects | pendente push |
| 20260617000003 | Seed dos 6 presets científicos do sistema em `gpr_presets` | pendente push |

As 3 migrations 20260617 foram aplicadas ao banco remoto via MCP Supabase na sessão de 2026-06-17. Confirmar com `supabase migration list`.

---

## Deploy

**Frontend (Vercel):** conectar repo + env vars de `apps/web/.env.local`

**Worker (Railway):**
- Root: `services/worker/`
- Usa `railway.toml` (builder=dockerfile, startCommand=`python worker_main.py`)
- Dockerfile inclui LibreOffice para conversão DOCX→PDF
- Env vars necessárias: `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`

**Migrations:**
```bash
supabase link --project-ref ayyirgjlotetrqfhpnms
supabase db push --password <DB_PASSWORD>
```

---

## Pendências conhecidas

| # | Item | Impacto | Ação necessária |
|---|---|---|---|
| P1 | Dropbox é placeholder — arquivos ficam no Supabase Storage, não no Dropbox real | Marcos usa Dropbox para receber dados de campo | Integrar Dropbox API real quando Marcos validar o fluxo |
| P2 | `velocity_usada_mns` sempre = `velocity_estimada_mns` nos DZTs de teste | Calibração de profundidade imprecisa em solos heterogêneos | Sessão de calibração com Amilson usando DZTs com alvos de profundidade conhecida |
| P3 | `fkMigration` do GPRPy requer `irlib` não instalado — usa Kirchhoff numpy próprio | Qualidade da migração vs. GPRPy nativo | Avaliar com Amilson se qualidade atual é suficiente |
| P4 | IA de imagem (`gpt-image-1`) off por padrão | Melhoria potencial das imagens processadas | Avaliar custo/benefício com Amilson em projeto real |
| P5 | ~~constraint `media` rejeitada pelo schema antigo~~ | ~~Alvos média não persistiam~~ | ✅ **Resolvido** — migration 20260606000001 |
| P6 | `fis_amp_metal_thr` revisado para 0.65 e `fis_amp_nao_metal_thr` para 0.22 via Fresnel; valores aguardam validação com alvos reais | Classificação metal/não-metal ainda não validada em campo | Usar `KB_ScansoloPlataform/GROUND_TRUTH/` + `import_ground_truth.py` para acumular ≥20 amostras e disparar `job_recalibrar` |
| P7 | ~~GPT-4o tem viés para `galeria_concreto` sem contexto do projeto~~ | ~~Interpretações automáticas pouco diferenciadas~~ | ✅ **Resolvido** — `_build_system_prompt(project)` injeta bloco PROJECT CONTEXT (commit 91e5f9c) |
| P8 | `testar_imagem_externa.py` rodou em 13/126 imagens do dataset HELPAVPA | Validação parcial do detector em imagens RADAN | Rodar nas 113 restantes após Amilson validar |
| P9 | ~~`job_gpr.py` usa `--preset 270mhz` via subprocess — `detector_input_mode=raw` já está no preset padrão~~ | — | ✅ Resolvido — preset contém default correto |
| P10 | ~~Pileup em `det_depth_min_m=0.30m` com DZTs de alto SNR (modo MINIMO, bandpass pulado)~~ | ~~232/341 alvos em 0.30m exato em teste com 126 DZTs HELPER — falsos positivos de airwave/onda direta~~ | ✅ **Resolvido** — bandpass nunca mais pulado em modo MINIMO (2026-06-17); monitorar se `det_depth_min_m=0.50m` é suficiente em DZTs HELPER futuros |
| P11 | ~~Banner "Matrizes V1.2" no log do `pipeline_v1.py` (linha ~1222)~~ | ~~Confunde auditorias — pipeline é v2.0.0~~ | ✅ **Resolvido** — banner já era `v2.0.0` na linha 1630 (verificado 2026-06-17) |
| P12 | Delete projeto remove apenas registros do DB — arquivos no Storage (DZTs, PNGs, CSVs) não são deletados | Acúmulo de arquivos órfãos no Supabase Storage | Adicionar limpeza de Storage na server action `deleteProject` quando for prioritário |
| P13 | ~~Reprocessamento individual não atualizava imagem na UI — página nunca recarregava após job concluir~~ | ~~Usuário via imagem antiga independente dos filtros aplicados~~ | ✅ **Resolvido** — `getJobStatus` + polling 5s + `router.refresh()` (commit a5c636a, 2026-06-16) |
| P14 | ~~`job_interpretada.py` ground truth: query usa `observacoes` e `revisado_por` mas colunas reais são `observacao` e `reviewed_by`~~ | ~~Campos ficam null no ground truth (silencioso — não aborta job)~~ | ✅ **Resolvido** — commit bab0ef1 |
| P15 | `gpr_presets.parameters` no banco ainda não tem `bandpass_tipo` nos presets seedados | Presets `270mhz_void` e `270mhz_concrete` não usarão FIR triangular via UI | Adicionar `"bandpass_tipo": "triangular"` no JSON dos dois presets afetados via migration ou UPDATE direto |

---

## Itens a calibrar com Amilson (antes de produção)

1. **Radargrama científico vs. relatório** — validar visualmente se `_radargrama_cientifico.png` (sem AGC) é adequado para revisão técnica
2. **Candidatos RAW** — confirmar que top-50 de cada PATIO são hipérboles reais (não artefatos) via `_classificador_candidatos.py`
3. **Parâmetros físicos do detector** — thresholds revisados com Fresnel (0.65/0.22); validar com ~10 alvos de tipo conhecido via `GROUND_TRUTH/` + `import_ground_truth.py`
4. **Velocity** — `VELOCITY_POR_SOLO` derivada de literatura; validar com DZT de alvos de profundidade conhecida (`GROUND_TRUTH/CALIBRACAO/`)
5. **Qualidade visual** — comparar `_radargrama_relatorio.png` do pipeline v2.0.0 vs. output RADAN para o mesmo DZT lado a lado
6. **Prompt GPT-4o** — ~~adicionar contexto do projeto~~ ✅ resolvido (commit 91e5f9c); validar se viés `galeria_concreto` reduziu com projetos reais
7. **Preset de filtros por tipo de solo** — limiares SNR calibrados só para PATIO. Validar com solo argiloso, úmido e pedregoso usando os novos presets `270mhz_clay`, `270mhz_sandy` etc.
8. **Preview RADAN 5m vs. RADAN real** — comparar `_radargrama_preview_radan_5m.png` com o output visual do RADAN para os mesmos DZTs. Confirmar se a profundidade derivada da velocity do preset é adequada.
9. **Pileup 0.30m em DZTs HELPER** — confirmar se 232 alvos em 0.30m eram falsos positivos (onda direta). Agora que o bandpass nunca é pulado, monitorar nova taxa de pileup nos próximos processamentos.
10. **Candidato de recalibração** — após acumular ≥20 amostras validadas no `gpr_ground_truth`, usar dashboard `/admin/qualidade` para disparar `job_recalibrar` e revisar o candidato JSON antes de aplicar ao preset de produção.
11. **Presets seedados** — validar que os 6 presets do sistema têm parâmetros adequados para cada tipo de projeto antes de usar em produção. Amilson deve revisar `det_h_max_m`, `det_depth_min_m` e `velocity_mns` de cada preset.
