# CLAUDE.md — ScanSOLO Platform
> Última atualização: 2026-06-09 (migrations sincronizadas + teste imagens externas)

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

---

## Pipeline GPR — `services/worker/pipeline/pipeline_v1.py`

Versão: **1.2.0**

### Sequência por DZT

1. Leitura via GPRPy → `_bruta.png` + `raw.npy`
2. **SNR gate** (Hilbert per-trace, janela de ruído = 95% das amostras) → decide modo: `minimo` / `padrao` / `agressivo`
3. Filtros adaptativos: dewow → bandpass (scipy SOS Butterworth) → bgremoval → tpow → AGC — intensidade varia por modo
4. `_processada.png` + `processado_sem_agc.npy` + `processado_visual.npy`
5. **Migração F-K Kirchhoff** (numpy próprio — GPRPy `fkMigration` requer `irlib` não instalado) → `_migrada.png` + `arr_migrado`
6. **IA de imagem** gpt-image-1 (off por padrão) → `_melhorada_ia.png`
7. **Detector:** Hough → CurveFit → DeltaT + física — usa `arr_migrado` > `arr_ia` > `arr_proc` (nessa ordem de preferência)
8. **Score filter** — descarta alvos abaixo de `det_min_score_csv=30` (falsos positivos Hough-only)
9. **Estimativa de velocity** por semblance (0.06–0.16 m/ns)
10. **Análise espectral por alvo** (freq_dominante, freq_centroide, razao_alta_baixa)
11. `_anotada_completa.png` (score≥40) + `_anotada_alta_confianca.png`
12. `_alvos.csv` + `index_projeto.csv` + `tabela_campo.csv` (alta+média) + `config_used.json` + `pipeline.log`

### Matrizes numpy — finalidades separadas

| Arquivo | Conteúdo | Uso |
|---|---|---|
| `raw.npy` | Bruta pré-qualquer-filtro | Auditoria, ML futuro, evidência independente |
| `processado_sem_agc.npy` | Filtrada antes do AGC | Análise física: amplitude/fase/classificação material |
| `processado_visual.npy` | Filtrada com AGC | Detector (Hough, CurveFit), visualização |
| `processado.npy` | Alias de `processado_visual.npy` | Backward compat |

**Crítico:** o detector recebe `arr_proc` como **float32 direto do GPRPy** (não um PNG). Diferente do script `testar_imagem_externa.py`, que recebe uint8 de JPEG. Os scores e diâmetros resultantes não são diretamente comparáveis.

### Preset padrão `270mhz`

```python
{
    "dewow_window":          5,
    "bandpass_low_mhz":      80,
    "bandpass_high_mhz":     500,
    "bandpass_order":        5,
    "bgremoval_traces":      30,
    "tpow_power":            0.5,
    "agc_window":            150,
    "velocity_mns":          0.1,
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
    "fis_amp_metal_thr":     0.75,   # [CALIBRAR] com Amilson
    "fis_amp_nao_metal_thr": 0.40,   # [CALIBRAR] com Amilson
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
- `minimo` — bandpass pulado, tpow×0.6, AGC janela×2
- `padrao` — preset base (todos os 4 DZTs PATIO ficam aqui com os limiares atuais)
- `agressivo` — tpow×1.5, AGC janela÷2

Valores de referência calibrados: PATIO_001=9.25, PATIO_002=5.44, PATIO_003=6.45, PATIO_004=4.56

### Flags CLI do pipeline

```
--sem-detector       pula detecção de hipérboles
--sem-fisica         pula análises físicas (material/espectro), mantém detecção geométrica
--sem-ia-imagem      pula gpt-image-1
--sem-migracao       pula migração Kirchhoff
--filter-config <json>  override de parâmetros do preset em JSON
--solo {standard,arenoso,argiloso,umido,pedregoso}
--preset {270mhz,default}
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
| `cartografia` | `job_cartografia.handle_cartografia_job` | DXF + KML + GeoJSON + CSV |
| `relatorio` | `job_relatorio.handle_relatorio_job` | DOCX + PDF via LibreOffice |
| `inferencias` | `job_gpr.handle_inferencias_job` | Relatório `.txt` sob demanda (não altera status) |
| `interpretada` | `job_interpretada.handle_interpretada_job` | Imagem interpretada com alvos aprovados |

### job_gpr.py

Dois fluxos:
1. **Job completo** (sem `payload.profile_id`): baixa todos DZTs do projeto → roda pipeline → persiste perfis + alvos + imagens
2. **Reprocessamento individual** (com `payload.profile_id`): reprocessa um único DZT com filtros customizados → não altera status do projeto, não cria job IA

### job_ia.py

1. Interpreta cada alvo via GPT-4o (prompt em inglês, resposta JSON com 10 campos)
2. Gera `_interpretada_ia.png` com labels `[tipo] [conf]%` sobrepostos
3. Salva URL em `gpr_profiles.imagem_interpretada_url`
4. Se `project.auto_accept_ia = true`: insere `technical_reviews` automaticamente (alta→planta+rel, média→só planta, baixa→descartado) → avança para `revisao_concluida`
5. Senão: avança para `ia_concluida` → aguarda revisão manual

**Categorias de tipo IA (prompt):** tubulacao_agua, tubulacao_gas, tubulacao_esgoto, cabo_eletrico, cabo_telecom, galeria_concreto, vazio_ar, rocha, inconclusivo

**Observação de calibração (2026-06-09):** testes com 13 imagens RADAN do Amilson (HELPAVPA) mostraram forte viés do GPT-4o para `galeria_concreto` (~80% dos alvos). Provável causa: sem contexto do projeto (solo, cliente, tipo de obra), o modelo escolhe a categoria de maior diâmetro como "segura". Mitigação futura: incluir contexto do projeto no prompt (tipo de obra, cliente, histórico de alvos do mesmo projeto).

### job_cartografia.py

Gera: DXF (camadas por tipo), KML (placemarks georreferenciados), GeoJSON, CSV de campo  
Upload para `gpr-tabelas/{project_id}/`

### job_relatorio.py

Gera DOCX via python-docx + converte para PDF via LibreOffice (instalado no Dockerfile do Railway)  
Upload para `gpr-tabelas/{project_id}/`

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
| `/nova-entrada` | `nova-entrada/page.tsx` | Criar projeto + upload DZT (UI 2-step) |
| `/projetos/[id]` | `ProjectDetailClient.tsx` | Status + timeline do projeto |
| `/projetos/[id]/upload` | `UploadClient.tsx` | Upload adicional de DZTs |
| `/projetos/[id]/revisao` | `ReviewClient.tsx` | Revisão técnica por alvo |
| `/projetos/[id]/interpretada` | `InterpretadaClient.tsx` | Aprovação/regeneração da imagem interpretada |
| `/projetos/[id]/cartografia` | `CartografiaClient.tsx` | Download DXF/KML/GeoJSON |
| `/projetos/[id]/relatorio` | `RelatorioClient.tsx` | Gerar e baixar relatório + inferências |

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
| `processing_config` | JSONB | Filtros GPR configurados na UI (override do preset) |
| `auto_accept_ia` | boolean | Auto-aprovação sem revisão manual |
| `codigo_projeto` | text | Ex: PT-GPR-SOL-036 |
| `contato_nome` | text | A/C do cliente |
| `area_m2` | float | Área levantada |
| `antena_freq_mhz` | int | 270 (hardcoded por ora) |
| `tem_pipe_locator` | boolean | — |

### `gpr_profiles`

| Campo | Tipo | Uso |
|---|---|---|
| `run_id` | uuid | Versão do processamento (nunca sobrescreve) |
| `imagem_bruta_url` | text | URL pública `gpr-images` |
| `imagem_processada_url` | text | URL pública `gpr-images` |
| `imagem_anotada_url` | text | URL pública `gpr-images` |
| `imagem_migrada_url` | text | URL pública `gpr-images` |
| `imagem_interpretada_url` | text | URL pública — `_interpretada_ia.png` (job_ia) |
| `imagem_interpretada_status` | enum | pendente / aprovado / regenerando / manual |
| `imagem_interpretada_manual_data` | JSONB | Anotações do canvas manual |
| `csv_alvos_url` | text | URL signed `gpr-tabelas` |
| `snr_imagem_db` | float | SNR em dB (Hilbert per-trace) |
| `snr_imagem_ratio` | float | S/sigma ratio |
| `modo_processamento` | text | minimo / padrao / agressivo |
| `tipo_solo` | text | solo usado no SNR gate |
| `filtros_customizados` | JSONB | Override de filtros no reprocessamento |

### `detected_targets`

Armazena todos os alvos detectados por perfil. Campos principais: `rank`, `x_m`, `depth_m`, `diam_est_m`, `confidence_score_0_100`, `confidence_label_tecnico`, `confidence_label_relatorio` (aceita `alta` / `media` / `baixa`), `tipo_material`, `status_interpretacao`.

### `technical_reviews`

Decisões de revisão por alvo: `vai_para_planta`, `vai_para_relatorio`, `tipo_confirmado`, `observacoes`, `revisado_por`.

### `processing_jobs`

| Campo | Tipo | Uso |
|---|---|---|
| `job_type` | enum | gpr / ia / cartografia / relatorio / inferencias / interpretada |
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
| `gpr-images` | PNGs (bruta / processada / anotada / interpretada / migrada) | Público |
| `gpr-tabelas` | CSVs, DXF, KML, GeoJSON, DOCX, PDF, inferencias.txt | Privado |

---

## Migrations aplicadas (remoto sincronizado em 2026-06-09)

| Arquivo | Conteúdo |
|---|---|
| 20260527000001 | Schema inicial (11 tabelas + enums + índices) |
| 20260527000002 | RLS completo por perfil |
| 20260528000001 | Storage buckets |
| 20260529000001 | Campos de detecção (cartography) |
| 20260529000002 | MIME types gpr-tabelas (fase 4+5) |
| 20260530000001 | report_project_fields (docx_storage_url, approved_at, codigo_projeto etc.) |
| 20260602000001 | processing_config JSONB em projects |
| 20260602000002 | auto_accept_ia BOOLEAN + imagem_interpretada_url em gpr_profiles |
| 20260603000001 | imagem_interpretada_status + imagem_interpretada_manual_data + ia_training_examples; enum extensions |
| 20260606000001 | fix constraint confidence_label_relatorio — adiciona 'media' aos valores aceitos |
| 20260608000001 | SNR gate: snr_imagem_db, snr_imagem_ratio, modo_processamento, tipo_solo em gpr_profiles |

Banco remoto sincronizado: `supabase migration list` confirma Local = Remote para todas as 11 migrations.

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
| P5 | ~~constraint `media` rejeitada pelo schema antigo~~ | ~~Alvos média não persistiam~~ | ✅ **Resolvido** — migration 20260606000001 aplicada no remoto em 2026-06-09 |
| P6 | `fis_amp_metal_thr=0.75` e `fis_amp_nao_metal_thr=0.40` não calibrados com dados reais | Classificação metal/não-metal imprecisa | Calibrar com ~10 alvos de tipo conhecido (Amilson) |
| P7 | GPT-4o tem viés para `galeria_concreto` sem contexto do projeto | Interpretações automáticas pouco diferenciadas | Adicionar contexto do projeto no prompt: tipo de obra, cliente, histórico de alvos |
| P8 | `testar_imagem_externa.py` rodou em 13/126 imagens do dataset HELPAVPA | Validação parcial do detector em imagens RADAN | Rodar nas 113 restantes após Amilson validar qualidade dos primeiros 13 |

---

## Itens a calibrar com Amilson (antes de produção)

1. **Parâmetros físicos do detector** (`fis_amp_metal_thr`, `fis_amp_nao_metal_thr`) — usar ~10 alvos de tipo conhecido
2. **Velocity** — DZT com alvos de profundidade conhecida para validar `velocity_estimada_mns`
3. **Qualidade visual da imagem processada** — comparar `_processada.png` do pipeline vs. output RADAN para o mesmo DZT lado a lado
4. **Prompt GPT-4o** — adicionar contexto do projeto para reduzir viés `galeria_concreto`
5. **Preset de filtros por tipo de solo** — os limiares SNR atuais foram calibrados só para PATIO (solo padrão). Validar com projetos em solo argiloso, úmido e pedregoso.
