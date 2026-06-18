# Banco de Dados — Referência Técnica
> Objetivo: Schema completo das tabelas principais, Storage e histórico de migrations.
> Contexto: Supabase (PostgreSQL + RLS). Projeto remoto: `ayyirgjlotetrqfhpnms`.

---

## Tabela `projects`

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

---

## Tabela `gpr_presets`

| Campo | Tipo | Uso |
|---|---|---|
| `id` | uuid PK | — |
| `name` | text | Nome legível (ex: `270mhz_clay`) |
| `description` | text | Descrição de uso |
| `scientific_basis` | text | Referência bibliográfica |
| `target_scenario` | text | Cenário de aplicação |
| `antenna_freq_mhz` | int | Frequência de antena alvo (270 por padrão) |
| `is_system` | boolean | Presets do sistema são read-only |
| `is_active` | boolean | Soft delete |
| `created_by` | uuid FK | Autor (null para presets do sistema) |
| `parameters` | JSONB | Todos os parâmetros do pipeline (mesmo formato do PRESETS dict em pipeline_v1.py) |

**RLS:** leitura pública (autenticado); insert/update/delete apenas para `is_system=false` por `admin`/`socio`.

**Presets seedados (is_system=true):** `270mhz`, `270mhz_clay`, `270mhz_sandy`, `270mhz_deep`, `270mhz_void`, `270mhz_concrete`

---

## Tabela `gpr_profiles`

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
| `n_tracos` | int | Número de traços do DZT |
| `distancia_max_m` | float | Distância total da linha (m) |
| `profundidade_max_m` | float | Profundidade máxima registrada (m) |
| `filtros_customizados` | JSONB | Override de filtros no reprocessamento (null para primeiro processamento) |
| `metricas_pipeline_url` | text | URL signed (10 anos) para `{stem}_pipeline_metrics.json` em `gpr-tabelas` |

---

## Tabela `detected_targets`

Armazena todos os alvos detectados por perfil. Campos principais: `rank`, `x_m`, `depth_m`, `diam_est_m`, `confidence_score_0_100`, `confidence_label_tecnico`, `confidence_label_relatorio` (aceita `alta` / `media` / `baixa`), `tipo_material`, `status_interpretacao`.

---

## Tabela `technical_reviews`

Decisões de revisão por alvo: `vai_para_planta`, `vai_para_relatorio`, `tipo_confirmado`, `observacao`, `reviewed_by`.

---

## Tabela `processing_jobs`

| Campo | Tipo | Uso |
|---|---|---|
| `job_type` | enum | gpr / ia / ia_p2 / cartografia / relatorio / inferencias / interpretada / recalibrar / recalibrar_velocity |
| `status` | enum | aguardando / processando / concluido / erro |
| `payload` | JSONB | Parâmetros opcionais (ex: `profile_id` para reprocessamento) |
| `error_message` | text | Mensagem de erro se status=erro |

---

## Tabela `ia_training_examples`

Alvos aprovados pelo Amilson salvos para futura melhoria do modelo. Campos: `project_id`, `profile_id`, `target_data` (JSONB com geometria + tipo confirmado), `source` (aprovacao / canvas).

---

## Tabela `gpr_training_sessions` (Fase 13)

| Campo | Tipo | Uso |
|---|---|---|
| `id` | uuid PK | — |
| `project_id` | uuid FK | Projeto avaliado |
| `profile_id` | uuid FK | Perfil (DZT) avaliado |
| `created_by` | uuid | Usuário que criou a sessão |
| `descricao` | text | Descrição da sessão |
| `total_vp / total_fp / total_fn` | int | Contagens atualizadas por `finalizeTrainingSession` |
| `status` | text | rascunho / concluida |

---

## Tabela `gpr_ground_truth` — Schema expandido (Fase 11 + 13)

Tabela dupla: rows do job_interpretada.py (Fase 11, auto-feed) e rows do wizard (Fase 13, manual).

**Colunas legadas (Fase 11 — auto-feed):** `target_rank`\*, `x_m`\*, `depth_m`\*, `e_falso_positivo`, `confianca_revisao`, `e_referencia`, `profundidade_real_m`, `tipo_confirmado`, `score_detector`, `tipo_solo`, `status`, `source`

**Colunas novas (Fase 13 — wizard):** `session_id` FK, `created_by`, `detected_target_id` FK, `e_verdadeiro_positivo`†, `e_falso_negativo`, `x_real_m`, `depth_real_m`, `tipo_alvo_confirmado`, `material_alvo`, `diametro_real_mm`, `fonte_confirmacao`, `confianca_fonte`, `umidade_solo`, `tipo_superficie`, `dias_sem_chuva`, `profundidade_lencol_m`, `amplitude_relativa_max`, `depth_detector_m`

*\* tornadas nullable na Fase 13 — job_interpretada.py ainda as preenche; wizard pode omitir.*
*† backfill automático: `e_verdadeiro_positivo = NOT e_falso_positivo` para rows da Fase 11.*

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
| 20260617000001 | `recalibrar_velocity` no enum job_type | ✅ remoto |
| 20260617000002 | `gpr_presets` table + RLS + `preset_id` FK em projects | ✅ remoto |
| 20260617000003 | Seed dos 6 presets científicos do sistema em `gpr_presets` | ✅ remoto |
| 20260617000004 | `gpr_training_sessions` (CREATE) + `gpr_ground_truth` extensão (18 novas colunas + nullable legacy + backfill `e_verdadeiro_positivo`) | ✅ remoto |

**Nota:** Todas as migrations foram aplicadas ao banco remoto via MCP Supabase. Versões no remoto usam timestamps próprios — `supabase db push` pode tentar reaplicar arquivos locais; preferir MCP para novas migrations.

```bash
# Se usar supabase CLI:
supabase link --project-ref ayyirgjlotetrqfhpnms
supabase db push --password <DB_PASSWORD>
```
