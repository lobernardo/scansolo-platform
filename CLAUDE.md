# CLAUDE.md — ScanSOLO Platform
> Última atualização: 2026-06-04 (fase 9 — imagem interpretada)

## Stack

| Camada | Tecnologia | Destino |
|---|---|---|
| Frontend | Next.js 16 App Router + TypeScript + Tailwind | Vercel |
| Auth / DB / Storage | Supabase (PostgreSQL + RLS + Storage) | Supabase Cloud |
| Worker Python | services/worker/ — polling loop | Railway (Dockerfile + railway.toml) |
| IA | OpenAI GPT-4o (texto) + gpt-image-1 (imagem, off por padrão) | — |
| Storage brutos | Supabase Storage (gpr-uploads, gpr-images, gpr-tabelas) | — |

## Regras absolutas (nunca violar)

- `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DROPBOX_REFRESH_TOKEN`: só em env vars server-side / worker — NUNCA no frontend
- Variáveis sensíveis NUNCA com prefixo `NEXT_PUBLIC_`
- RLS obrigatório em todas as tabelas com dados de projeto
- Arquivos brutos `.DZT` nunca apagados — só versionados
- Reprocessamento gera novo `run_id` — nunca sobrescreve

## Personas

| Role | Acesso |
|---|---|
| `operador_campo` | Nova Entrada + upload + ver status próprio |
| `tecnico` | Projetos assigned_to = seu uid |
| `socio` / `admin` | Tudo |

---

## Estado atual do pipeline (2026-06-04)

### Fases implementadas

| Fase | Descrição | Status |
|---|---|---|
| 0 | Fundação monorepo (Next.js + Supabase + worker base) | ✅ |
| 1 | Upload DZT + pipeline GPR (readgssi/GPRPy) + imagens processadas | ✅ |
| 2 | IA GPT-4o por alvo + `_interpretada_ia.png` | ✅ |
| 3 | Revisão técnica — tela interativa por alvo | ✅ |
| 4 | Cartografia — DXF + KML + GeoJSON + CSV | ✅ |
| 5 | Relatório DOCX (python-docx) + PDF via LibreOffice | ✅ |
| 6 | Nova entrada: filtros configuráveis + UI 2-step + `processing_config` | ✅ |
| 7 | `_migrada.png` (Kirchhoff numpy) + velocity estimada + espectro por alvo | ✅ |
| 8 | Relatório de inferências sob demanda (job `inferencias` → `.txt` para Amilson) | ✅ |
| 9 | Workflow da imagem interpretada (Amilson aprova/regenera/anota manualmente) | ✅ |

### Pipeline GPR — `services/worker/pipeline/pipeline_v1.py`

Versão: **1.1.0**

Sequência por DZT:
1. Leitura via GPRPy → `_bruta.png` + `raw.npy`
2. Filtros configuráveis (dewow / bandpass / bgremoval / tpow / AGC)
3. `_processada.png` + `processado_sem_agc.npy` + `processado_visual.npy`
4. **Migração F-K Kirchhoff** (numpy) → `_migrada.png` + `arr_migrado`
5. **IA de imagem** gpt-image-1 (off por padrão) → `_melhorada_ia.png`
6. Detector: Hough → CurveFit → DeltaT + física (usa arr_migrado > arr_ia > arr_proc)
7. **Estimativa de velocity** por semblance (0.06–0.16 m/ns)
8. **Análise espectral por alvo** (freq_dominante, freq_centroide, razao_alta_baixa)
9. `_anotada_completa.png` + `_anotada_alta_confianca.png`
10. `_alvos.csv` + `index_projeto.csv` + `tabela_campo.csv` (alta+média)

**Preset padrão `270mhz`:** bgremoval=30, tpow=0.5, contrast=2.5, migracao_ativa=True

**Flags CLI:** `--sem-detector`, `--sem-fisica`, `--sem-ia-imagem`, `--sem-migracao`, `--filter-config <json>`

### Colunas CSV de alvos (por alvo)

Geométricas: rank, x_m, depth_m, depth_hough_m, fit_ok, diam_est_m, diam_confianca, score  
Novas: prof_topo_m, largura_hiperbole_m, altura_hiperbole_m, tipo_tamanho  
Velocity: velocity_usada_mns, velocity_estimada_mns, velocity_fonte  
Física: tipo_material, confianca_tipo, amplitude_relativa_*, fase_consistente, evidencia_raw/sem_agc, snr_local  
Espectral: freq_dominante_mhz, freq_centroide_mhz, razao_alta_baixa  
Score: confidence_score_0_100, confidence_label_tecnico, confidence_label_relatorio, status_interpretacao, motivo_confianca  

### Tabela `projects` — campos relevantes

| Campo | Tipo | Uso |
|---|---|---|
| `status` | enum | Fluxo do pipeline |
| `processing_config` | JSONB | Filtros GPR configurados na UI |
| `auto_accept_ia` | boolean | Auto-aprovação sem revisão manual |
| `codigo_projeto` | text | Ex: PT-GPR-SOL-036 |
| `contato_nome` | text | A/C do cliente |
| `area_m2` | float | Área levantada |
| `antena_freq_mhz` | int | 270 (hardcoded) |
| `tem_pipe_locator` | boolean | — |

### Fluxo de status do projeto

```
aguardando_arquivos → aguardando_processamento → processando_gpr → gpr_concluido
→ processando_ia → ia_concluida (ou revisao_concluida se auto_accept_ia=true)
→ revisao_em_andamento → revisao_concluida
→ processando_interpretada → interpretada_gerada   ← NOVO (Fase 9)
→ aguardando_cartografia → cartografia_concluida (ou cartografia_pendente_dados)
→ aguardando_relatorio → relatorio_em_andamento → relatorio_gerado → finalizado
```

### job_ia.py — comportamento atual

1. Interpreta cada alvo via GPT-4o (prompt em inglês, resposta em JSON com 10 campos)
2. Gera `_interpretada_ia.png` com labels `[tipo] [conf]%` sobrepostos
3. Salva URL em `gpr_profiles.imagem_interpretada_url`
4. Se `project.auto_accept_ia = true`:
   - Insere `technical_reviews` automaticamente (alta→planta+rel, média→só planta, baixa→descartado)
   - Avança para `revisao_concluida` → pula revisão manual
5. Senão: avança para `ia_concluida` → aguarda revisão

### job_gpr.py — relatório de inferências (sob demanda)

Função: `gerar_relatorio_inferencias(df_campo, projeto, preset) -> str`
- Filtra `confidence_label_tecnico in ("alta", "media")`
- Colunas: Linha | # | Dist.(m) | P.Topo(m) | P.Eixo(m) | Diâm.(m) | Larg.(m) | Tam. | Material | Conf.
- `prof_topo_m` estimado como `depth_m − diam_est_m / 2` quando não disponível no CSV
- Inclui legenda técnica e avisos de calibração de velocity no rodapé

Handler: `handle_inferencias_job(supa, job)`
- Registrado no `worker_main.py` como `job_type = "inferencias"`
- Baixa os CSVs por perfil de `gpr-tabelas` (campo `gpr_profiles.csv_alvos_url`)
- Fallback: lê `detected_targets` do DB se CSVs indisponíveis
- Upload para `gpr-tabelas/{project_id}/inferencias.txt` (upsert)
- **Não altera `project.status`** — job independente, não bloqueia o fluxo principal

UI (`page.tsx`): card aparece assim que `gpr_profiles` existem para o projeto
- **"Gerar relatório de inferências"** → insere job via `generateInferenceReport()` (server action em `relatorio/actions.ts`)
- **"Gerando…"** → job em `aguardando` ou `processando`
- **"↓ Baixar inferências"** → signed URL de `gpr-tabelas/{project_id}/inferencias.txt` (expira em 1h)
- Job aparece na timeline de chips como **"Inferências"**

### job_interpretada.py — workflow da imagem interpretada (Fase 9)

Disparado por `finalizeReview` (inserção de job `interpretada` em `processing_jobs`).

1. Busca perfis do projeto (run mais recente via `run_id`)
2. Para cada perfil: pega alvos aprovados (`technical_reviews.vai_para_relatorio=true`)
3. Baixa `_processada.png` do Storage (`gpr-images`) via `_download_from_storage_url()`
4. Desenha marcadores coloridos por tipo em PT (círculo + label tipo/profundidade/diâmetro) → `_interpretada.png`
5. Upload para `gpr-images/{project_id}/{run_id}/{stem}_interpretada.png`
6. Atualiza `gpr_profiles.imagem_interpretada_url` + `imagem_interpretada_status = "pendente"`
7. Salva `ia_training_examples` com os alvos aprovados (loop de aprendizado)

**Status do perfil** (`gpr_profiles.imagem_interpretada_status`):
- `pendente` — gerada, aguarda aprovação de Amilson
- `aprovado` — Amilson aprovou; será usada no relatório
- `regenerando` — nova rodada de IA solicitada (novo job `interpretada`)
- `manual` — Amilson anotou diretamente no canvas

**Rota UI:** `/projetos/[id]/interpretada`
- Visualiza a imagem interpretada por perfil
- 3 ações: **Aprovar** (marca aprovado + exemplo de treino) | **Regenerar** (novo job) | **Interpretar manualmente** (canvas interativo)
- Canvas: clique na imagem para marcar alvo, seleciona tipo em PT, edita profundidade/diâmetro, confirma → salva em `ia_training_examples` e re-dispara job

**Enums de projeto:** `processando_interpretada` e `interpretada_gerada` (adicionados em 20260603000001)  
**job_type:** `interpretada` (adicionado em 20260603000001 com IF NOT EXISTS)

### Supabase Storage — buckets

| Bucket | Conteúdo | Visibilidade |
|---|---|---|
| `gpr-uploads` | DZTs brutos enviados pelo usuário | Privado |
| `gpr-images` | PNGs (bruta/processada/anotada/interpretada/migrada) | Público |
| `gpr-tabelas` | CSVs, DXF, KML, GeoJSON, DOCX, PDF | Privado (MIME: csv/plain/octet-stream/docx/pdf) |

### Migrations aplicadas

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
| 20260603000001 | imagem_interpretada_status + imagem_interpretada_manual_data em gpr_profiles; tabela ia_training_examples; enum extensions (job_type + project_status + job_status) |

---

## Deploy

**Frontend (Vercel):** conectar repo + env vars de `apps/web/.env.local`

**Worker (Railway):**
- Root: `services/worker/`  
- Usa `railway.toml` (builder=dockerfile, startCommand=`python worker_main.py`)
- Dockerfile inclui LibreOffice para conversão DOCX→PDF
- Env vars necessárias: `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`

---

## Pendências conhecidas

| # | Item | Impacto |
|---|---|---|
| P1 | Dropbox ainda é placeholder — arquivos ficam no Supabase Storage, não no Dropbox real | Operacional (Marcos usa Dropbox) |
| P2 | `velocity_usada_mns` sempre = `velocity_estimada_mns` nos DZTs de teste (solo homogêneo) | Calibrar com Amilson |
| P3 | `fkMigration` do GPRPy requer `irlib` não instalado — usa Kirchhoff numpy próprio | Qualidade da migração |
| P4 | IA de imagem (`gpt-image-1`) off por padrão — avaliar custo/benefício com Amilson | — |
| P5 | `confidence_label_relatorio = "media"` não é persistido no DB (bug pré-existente em `_clamp_label_relatorio`) | Alvos de média confiança não aparecem no banco |
