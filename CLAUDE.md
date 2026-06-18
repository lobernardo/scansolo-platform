# CLAUDE.md — ScanSOLO Platform
> Última atualização: 2026-06-18 (Estabilização F: fix campos n/d Pipeline Log + criar preset redesign Nova Entrada)
> Este arquivo é o índice operacional. Detalhes técnicos estão nos docs/ linkados abaixo.

---

## Documentação técnica

| Doc | Conteúdo |
|---|---|
| [docs/MANUAL_USO_SISTEMA.md](docs/MANUAL_USO_SISTEMA.md) | Manual operacional: 5 imagens, presets, velocity/prof, filtros, detector, IA, FAQ |
| [docs/technical/GPR_PIPELINE.md](docs/technical/GPR_PIPELINE.md) | Pipeline v2.0.0 — sequência 13 passos, matrizes numpy, VELOCITY_POR_SOLO, presets, bandpass, SNR gate, flags CLI, CSV alvos |
| [docs/technical/WORKER_JOBS.md](docs/technical/WORKER_JOBS.md) | Todos os job handlers: job_gpr (2 fluxos + Fase 15 fixes), job_ia, job_ia_p2, job_interpretada, job_recalibrar, job_recalibrar_velocity, supabase retry, metrics upload |
| [docs/technical/FRONTEND.md](docs/technical/FRONTEND.md) | Rotas, server actions (preset-actions, training-actions, gpr-actions), PipelineLog component, PipelineMetrics type, fluxo de status |
| [docs/technical/DETECTOR.md](docs/technical/DETECTOR.md) | Detector de hipérboles (DEFAULT_PARAMS, fluxo Hough→CurveFit→DeltaT) + testar_imagem_externa.py |
| [docs/technical/DATABASE.md](docs/technical/DATABASE.md) | Schema completo: todas as tabelas, Storage buckets, migrations (até 20260618000003) |
| [docs/history/FASES_0_14.md](docs/history/FASES_0_14.md) | Histórico e contexto das Fases 0–14 |
| [docs/history/FASES_15_PLUS.md](docs/history/FASES_15_PLUS.md) | Fase 15 detalhada + pendências para Fase A |
| [docs/known_issues.md](docs/known_issues.md) | Pendências P1–P19 completas (Item + Impacto + Ação) + itens a calibrar com Amilson |

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
- `Bandpass é decisão explícita do geofísico` — não existe regra automática "solo X = bandpass OFF". O controle está em Nova Entrada (toggle), modal de presets, e "Ajustar filtros". `bandpass_low_mhz=0` é a convenção para desativar no pipeline (linha 1220 pipeline_v1.py). Nenhum modo automático (MINIMO/PADRAO/AGRESSIVO) toca o bandpass.
- `Bandpass OFF não é padrão` — use apenas quando SNR muito alto distorce hipérboles. DZTs ruidosos precisam do filtro.

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
| 10 | Preview RADAN 5m + job `ia_p2` + delete projeto + `skip_ia` flag | ✅ |
| 11 | Loop de aprendizado: `pipeline_metrics.json` + `gpr_ground_truth` + `job_recalibrar` + dashboard qualidade + `parse_dzx.py` + GPT-4o contexto do projeto | ✅ |
| 12 | Sistema de presets: `gpr_presets` table + 6 presets científicos seedados + `/presets` UI + Nova Entrada com selector | ✅ |
| 13 | Módulo de treinamento ground truth: `gpr_training_sessions` + wizard `/treinamento` (4 passos) + modal recalibração | ✅ |
| 14 | Logs visuais do pipeline: `getPipelineMetrics` + `PipelineLog.tsx` (timeline + compact + MetricsDiff) | ✅ |
| 15 | Controle explícito de bandpass: toggle ON/OFF em Nova Entrada + presets + fixes velocity_mns / det_depth_min_m + rastreabilidade bandpass no `pipeline_metrics.json` | ✅ |
| B | Aba "Técnica" (`_radargrama_cientifico.png`) + renomear Processada→Relatório + Processada 2→Visual | ✅ |
| C | Campos `depth_preview_m` / `agc_window_preview` em Nova Entrada + rastreio `velocity_fonte` no pipeline e PipelineLog | ✅ |
| D | Preset versionamento: 8 colunas em `gpr_presets` + "Salvar como preset" em Ajustar Filtros + badge validado | ✅ |
| E | Fix Pipeline Log (`imagem_migrada_url` migration) + PipelineLog preview fields + velocity UX + criar preset inline em Nova Entrada + manual | ✅ |
| F | Fix campos n/d Pipeline Log (dewow/bgremoval/tpow/agc mapeados do pipeline_metrics.json) + Nova Entrada criar preset redesign (opção `__new__` no dropdown + modal unificado scratch/selection + botão no accordion + campos notas/dataset) | ✅ |

---

## Pipeline GPR — Arquitetura v2.0.0

→ Detalhes completos em [docs/technical/GPR_PIPELINE.md](docs/technical/GPR_PIPELINE.md)

```
DZT → raw → dewow+bp → [bifurcação]
                         |
              [tpow manual]   [bgremoval → tpow → AGC]
                   |                   |
           arr_cientifico        arr_relatorio
        (para Amilson/detector)   (para cliente/PDF)
```

| Fluxo | Saída | Finalidade |
|---|---|---|
| Científico (dewow+bp+tpow) | `_radargrama_cientifico.png` | Revisão técnica (Amilson) |
| Relatório (dewow+bp+bgremoval+tpow+AGC) | `_radargrama_relatorio.png` / `_processada.png` | Cliente/PDF |
| Detector (input: `arr_raw` por padrão — v2.0.0) | `_anotada_completa.png` | Hough+CurveFit+DeltaT |
| Preview RADAN (arr_dewow_bp → AGC(80)) | `_radargrama_preview_radan_5m.png` | Comparação RADAN |

---

## Worker — job_type table

→ Detalhes completos em [docs/technical/WORKER_JOBS.md](docs/technical/WORKER_JOBS.md)

| job_type | Handler | Descrição |
|---|---|---|
| `gpr` | `job_gpr.handle_gpr_job` | Roda pipeline_v1.py via subprocess |
| `ia` | `job_ia.handle_ia_job` | GPT-4o por alvo + `_interpretada_ia.png` |
| `ia_p2` | `job_ia.handle_ia_p2_job` | Anotações sobre preview RADAN (sem nova chamada GPT-4o) |
| `cartografia` | `job_cartografia.handle_cartografia_job` | DXF + KML + GeoJSON + CSV |
| `relatorio` | `job_relatorio.handle_relatorio_job` | DOCX + PDF via LibreOffice |
| `inferencias` | `job_gpr.handle_inferencias_job` | Relatório `.txt` sob demanda |
| `interpretada` | `job_interpretada.handle_interpretada_job` | Imagem interpretada com alvos aprovados |
| `recalibrar` | `job_recalibrar.handle_recalibrar_job` | Otimiza thresholds via gpr_ground_truth |
| `recalibrar_velocity` | `job_recalibrar_velocity.handle_recalibrar_velocity_job` | Recalcula profundidades com nova velocity |

---

## Frontend — rotas-chave

→ Detalhes completos em [docs/technical/FRONTEND.md](docs/technical/FRONTEND.md)

| Rota | Componente | Função |
|---|---|---|
| `/nova-entrada` | `nova-entrada/page.tsx` | Criar projeto com preset + toggle Bandpass + "＋ Criar novo preset..." no dropdown + "Salvar configuração como preset" no accordion |
| `/projetos/[id]` | `ProjectDetailClient.tsx` | Status + imagens + Ajustar Filtros + Pipeline Log |
| `/projetos/[id]/upload` | `UploadClient.tsx` | Upload adicional; com `preset_id` usa `startProcessingDirect` |
| `/presets` | `PresetsClient.tsx` | Cards + modal criar/editar (com toggle Bandpass ON/OFF) |
| `/treinamento` | `TreinamentoClient.tsx` | Wizard validação manual (4 passos) + modal recalibração |
| `/admin/qualidade` | `QualidadeClient.tsx` | Dashboard qualidade (socio/admin) |

---

## Banco de dados — tabelas principais

→ Schema completo em [docs/technical/DATABASE.md](docs/technical/DATABASE.md)

| Tabela | Campos-chave |
|---|---|
| `projects` | `status`, `preset_id`, `processing_config` JSONB, `auto_accept_ia` |
| `gpr_presets` | `name`, `parameters` JSONB, `is_system`, `is_active` |
| `gpr_profiles` | `run_id`, imagens URLs (incl. `imagem_cientifica_url`, `imagem_migrada_url`), `filtros_customizados` JSONB, `metricas_pipeline_url` |
| `detected_targets` | `rank`, `depth_m`, `confidence_score_0_100`, `confidence_label_relatorio` |
| `processing_jobs` | `job_type`, `status`, `payload` JSONB, `error_message` |
| `gpr_ground_truth` | 12 cols legadas (Fase 11) + 18 cols wizard (Fase 13) |
| `gpr_training_sessions` | `project_id`, `profile_id`, `total_vp/fp/fn`, `status` |

**Storage:** `gpr-uploads` (privado) | `gpr-images` (público) | `gpr-tabelas` (privado)

---

## Pendências ativas (resumo)

→ Lista completa em [docs/known_issues.md](docs/known_issues.md)

| # | Item (resumo) | Status |
|---|---|---|
| P1 | Dropbox é placeholder | Aberto |
| P2 | velocity_usada_mns não calibrada em campo | Aberto |
| P3 | fkMigration usa Kirchhoff numpy (não GPRPy nativo) | Aberto |
| P4 | gpt-image-1 off por padrão | Aberto |
| P6 | fis_amp thresholds aguardam validação com alvos reais | Aberto |
| P8 | testar_imagem_externa.py rodou em 13/126 imagens HELPAVPA | Aberto |
| P12 | Delete projeto não limpa Storage | Aberto |
| P19 | UploadClient.tsx caminho legado não mapeia bandpass OFF | Aberto |
| P20 | `imagem_migrada_url` nunca populada pelo worker (Fase 7 incompleta) — migration adicionada, job_gpr precisa salvar a URL | Aberto |

---

## Deploy

**Frontend (Vercel):** conectar repo + env vars de `apps/web/.env.local`

**Worker (Railway):**
- Root: `services/worker/`
- Usa `railway.toml` (builder=dockerfile, startCommand=`python worker_main.py`)
- Dockerfile inclui LibreOffice para conversão DOCX→PDF
- Env vars: `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `OPENAI_API_KEY`

**Migrations:** preferir MCP Supabase para novas migrations (não `supabase db push` — pode reaplicar locais).
