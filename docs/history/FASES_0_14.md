# Histórico de Fases — 0 a 14
> Objetivo: Registro das fases implementadas até Fase 14 (inclusive), com contexto de decisões.
> Contexto: Cada fase corresponde a uma entrega funcional incremental da plataforma ScanSOLO.

---

## Fase 0 — Fundação monorepo (2026-05-27)

Monorepo com Next.js 16 App Router + Supabase + worker Python base.
Decisão de arquitetura: Next.js 16 usa proxy automático para Supabase — sem CORS issues.
Schema inicial: 11 tabelas + enums + índices + RLS completo. Storage buckets configurados.

## Fase 1 — Upload DZT + pipeline GPR

Upload de arquivos `.DZT` para `gpr-uploads`. Worker roda `pipeline_v1.py` via subprocess.
Saídas: `_bruta.png`, `_processada.png`, `_anotada_completa.png`.

## Fase 2 — IA GPT-4o por alvo

Job `ia` interpreta cada alvo detectado via GPT-4o (prompt em inglês, resposta JSON com 10 campos).
Gera `_interpretada_ia.png` com labels `[tipo] [conf]%` sobrepostos.

## Fase 3 — Revisão técnica

Tela `/projetos/[id]/revisao` com interface interativa por alvo.
Amilson valida/descarta cada alvo, confirma tipo e adiciona observações.

## Fase 4 — Cartografia

Job `cartografia` gera DXF (camadas por tipo), KML (placemarks), GeoJSON, CSV de campo.
Upload para `gpr-tabelas/{project_id}/`.

## Fase 5 — Relatório DOCX + PDF

Job `relatorio` gera DOCX via python-docx + converte para PDF via LibreOffice no Railway.

## Fase 6 — Nova entrada com filtros configuráveis

UI 2-step para criar projeto: metadados + configuração de filtros.
`processing_config` JSONB em `projects` para armazenar overrides do geofísico.

## Fase 7 — Migração F-K Kirchhoff + velocity + espectro

`_migrada.png` via Kirchhoff numpy próprio (GPRPy nativo requer `irlib` não instalado).
Velocity estimada por semblance. Espectro por alvo.

## Fase 8 — Relatório de inferências sob demanda

Job `inferencias` gera `.txt` para Amilson com tabela de alvos (alta/média confiança).
Não altera `project.status` — job independente.

## Fase 9 — Workflow da imagem interpretada

Amilson pode aprovar/regenerar/anotar manualmente a imagem interpretada.
`imagem_interpretada_status`: pendente / aprovado / regenerando / manual.

## Fase 10 — Preview RADAN 5m + IA P2 + delete projeto + skip_ia

`_radargrama_preview_radan_5m.png`: arr_dewow_bp → AGC(80) → PNG com footer laranja de aviso.
Job `ia_p2`: anotações do detector sobre o preview RADAN (sem nova chamada GPT-4o).
Flag `skip_ia`: pula job de IA após GPR concluir (útil para testes sem custo).
Delete projeto: remove registros do DB (Storage orphans — ver P12 em known_issues.md).

## Fase 11 — Loop de aprendizado

`pipeline_metrics.json` por DZT → URL signed em `gpr_profiles.metricas_pipeline_url`.
`gpr_ground_truth`: tabela para validação manual de alvos.
`job_recalibrar`: otimiza thresholds via F1 (mínimo 20 amostras, NÃO aplica automaticamente).
Dashboard `/admin/qualidade`.
`parse_dzx.py`: parser stdlib-only para `.DZX` (GSSI).
GPT-4o com contexto do projeto: `_build_system_prompt(project)` injeta tipo_obra, area_m2, etc.

## Fase 12 — Sistema de presets

`gpr_presets` table + 6 presets científicos seedados + UI `/presets`.
Nova Entrada: selector de preset (obrigatório).
Worker: `_get_processing_config` faz merge preset + project override.
`job_recalibrar_velocity`: recalcula profundidades com nova velocity sem reprocessar.

## Fase 13 — Módulo de treinamento ground truth

`gpr_training_sessions` table. Extensão de `gpr_ground_truth` com 18 novas colunas.
Wizard `/treinamento` (4 passos: idle→select→metadata→validate).
`training-actions.ts`: server actions para o wizard.
Modal de recalibração com comparação atual vs. sugerido + "Aplicar ao preset".

## Fase 14 — Logs visuais do pipeline

`getPipelineMetrics` server action em `gpr-actions.ts`.
`PipelineLog.tsx`: timeline vertical (8 seções) + compact + MetricsDiff.
Pipeline Log colapsável por perfil em `/projetos/[id]`.
Diff antes→depois de reprocessamento no painel "Ajustar filtros".
Mini pipeline visual + `ParamTooltip` em Nova Entrada.
