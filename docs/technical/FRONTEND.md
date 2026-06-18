# Frontend — Referência Técnica
> Objetivo: Rotas, server actions, componentes e tipos do frontend Next.js 16.
> Contexto: `apps/web/` — Next.js 16 App Router + TypeScript + Tailwind, deploy no Vercel.

---

## Rotas principais

| Rota | Componente | Função |
|---|---|---|
| `/` | `page.tsx` | Redirect para dashboard |
| `/login` | `login/page.tsx` | Auth Supabase |
| `/dashboard` | `dashboard/page.tsx` | Visão geral de projetos |
| `/projetos` | `projetos/page.tsx` + `ProjetosTable.tsx` | Lista de projetos |
| `/nova-entrada` | `nova-entrada/page.tsx` | Criar projeto: selector de preset (obrigatório) + summary dos parâmetros-chave + accordion "Personalizar" com overrides → `preset_id` + `processing_config` salvos no projeto. Accordion inclui toggle **Bandpass ON/OFF** — quando OFF, salva `bandpass_low_mhz=0` em `processing_config`. |
| `/projetos/[id]` | `ProjectDetailClient.tsx` | Status + timeline + tabs de imagem (Bruta / Processada / Anotada IA / Interpretada IA / Processada 2 / Anotada P2) + botão deletar + painel "Ajustar Filtros" por perfil (polling 5s + `router.refresh()` ao concluir) + painel "Calibrar velocity do solo" + seção "Pipeline Log" colapsável por perfil |
| `/projetos/[id]/upload` | `UploadClient.tsx` | Upload adicional de DZTs. Se o projeto já tem `preset_id`, pula configuração manual e vai direto para processamento via `startProcessingDirect` (Fase 15). |
| `/projetos/[id]/revisao` | `ReviewClient.tsx` | Revisão técnica por alvo |
| `/projetos/[id]/interpretada` | `InterpretadaClient.tsx` | Aprovação/regeneração da imagem interpretada |
| `/projetos/[id]/cartografia` | `CartografiaClient.tsx` | Download DXF/KML/GeoJSON |
| `/projetos/[id]/relatorio` | `RelatorioClient.tsx` | Gerar e baixar relatório + inferências |
| `/presets` | `PresetsClient.tsx` | Cards de presets (sistema + personalizados), expand parâmetros, modal criar/editar/duplicar (admin/socio apenas). Modal inclui toggle **Bandpass ON/OFF** — quando OFF, salva `bandpass_low_mhz=0` em `parameters`. Chip BP exibe "desativado" quando `bandpass_low_mhz=0`. |
| `/treinamento` | `TreinamentoClient.tsx` | Wizard de validação manual (4 passos: idle→select→metadata→validate), stats/F1, histórico de sessões, modal recalibração com comparação atual vs. sugerido + botão "Aplicar ao preset" |
| `/admin/qualidade` | `QualidadeClient.tsx` | Dashboard de qualidade — ground truth, F1, candidatos de recalibração, botão disparar job (visível apenas para `socio`/`admin`) |
| `/api/presets` | `route.ts` (GET) | Retorna presets ativos para o selector client-side da Nova Entrada |

---

## Server actions — `apps/web/app/actions/preset-actions.ts`

`getPresets`, `getPresetById`, `createPreset`, `updatePreset`, `deletePreset` (soft delete via `is_active=false`), `duplicatePreset`. Apenas `admin`/`socio` podem criar/editar/deletar.

---

## Server actions — `apps/web/app/actions/training-actions.ts` (Fase 13)

`getProjectsForTraining` / `getProfilesForProject` / `getTargetsForProfile` — dados para o wizard.
`createTrainingSession(projectId, profileId, descricao)` → `{ ok, session_id }`.
`saveGroundTruthEntry(entry)` — copia métricas de `detected_targets` e insere em `gpr_ground_truth`.
`finalizeTrainingSession(sessionId)` — conta VP/FP/FN da sessão, atualiza `gpr_training_sessions.status='concluida'`.
`getGroundTruthStats()` — totais VP/FP/FN, F1 estimado, distribuição por tipo_solo e tipo_alvo.
`triggerRecalibracao()` — insere job `recalibrar` em `processing_jobs`.
`getTrainingSessions()` / `getRecalibracaoResults()` / `getRecalibracaoContent(signedUrl)` — histórico e candidatos.
`applyRecalibracao(thresholds)` — cria preset de usuário com thresholds do candidato.

---

## Server actions — `apps/web/app/actions/gpr-actions.ts` (Fase 14 + 15)

`getPipelineMetrics(profileId)` → `PipelineMetrics | null`

### Fluxo

1. Busca `metricas_pipeline_url` + campos de SNR/modo/traços/imagens de `gpr_profiles`
2. Busca contagens de `detected_targets` (n_alta, n_media, n_baixa, n_score_30)
3. Fetch do JSON do Storage (`pipeline_metrics.json` — URL signed de 10 anos)
4. Merge: campos do JSON + campos do perfil + contagens → objeto `PipelineMetrics` enriquecido

### Tipo `PipelineMetrics`

```typescript
export type PipelineMetrics = {
  // Do JSON
  pipeline_version?: string;
  dzt_filename?: string;
  preset_name?: string;
  modo_processamento?: string;
  modo_coleta?: string;
  n_tracos_json?: number;
  n_amostras_final?: number;
  dist_total_m?: number;
  det_depth_min_m_usado?: number;
  snr_stages_db?: Record<string, number>;   // { raw, dewow, bp, bgremoval, tpow, agc } em dB
  detector_input_mode_json?: string;
  // Do profile
  snr_raw_db?: number | null;
  snr_raw_ratio?: number | null;
  tipo_solo?: string | null;
  n_tracos?: number | null;
  distancia_max_m?: number | null;
  profundidade_max_m?: number | null;
  filtros_customizados?: Record<string, unknown> | null;
  // Bandpass efetivo — Fase 15: lido do JSON (cobre primeiro processamento e reprocessamento)
  bandpass_aplicado?: string;        // "desativado" | "80-500 MHz"
  bandpass_low_mhz_usado?: number;   // 0 se desativado
  bandpass_high_mhz_usado?: number;
  bandpass_order_usado?: number;
  bandpass_tipo_usado?: string;
  // Flags de imagens
  imagem_bruta_ok?: boolean;
  imagem_relatorio_ok?: boolean;
  imagem_anotada_ok?: boolean;
  imagem_migrada_ok?: boolean;
  imagem_preview_ok?: boolean;
  // De detected_targets
  n_alvos_alta?: number;
  n_alvos_media?: number;
  n_alvos_baixa?: number;
  n_alvos_score_30?: number;
  metricas_pipeline_url?: string | null;
}
```

---

## Componente `apps/web/components/PipelineLog.tsx` (Fase 14 + 15)

Props: `metrics: PipelineMetrics | null`, `compact?: boolean`

### compact=true

Linha horizontal com:
- Modo (badge colorido: verde=padrao, amarelo=minimo, laranja=agressivo)
- SNR ratio
- Contagem "alvos ≥30 (N alta, N média)"

### compact=false

Timeline vertical com 8 seções:
1. Leitura do DZT (filename, n_tracos, dist_total_m)
2. SNR Gate (snr_raw_db, modo, tipo_solo)
3. Filtros de Sinal (dewow, bandpass, bgremoval, tpow, AGC)
4. SNR Pós-Filtros (snr_stages_db: cientifico, relatorio)
5. Migração F-K (imagem_migrada_ok)
6. Detector (det_depth_min_m_usado, detector_input_mode)
7. Imagens Geradas (flags bruta/relatorio/anotada/migrada/preview)

Ícones ✓/⚠/✗/— por disponibilidade do dado.

**Bandpass OFF (Fase 15):** tri-source detection em Filtros de Sinal:
```typescript
const bandpassDesativado =
  m.bandpass_aplicado === "desativado" ||       // JSON — cobre primeiro processamento
  m.bandpass_low_mhz_usado === 0 ||             // JSON fallback
  filtros.bandpass === false;                    // filtros_customizados — cobre reprocessamento
```
Exibe "desativado" (✗) quando `bandpassDesativado = true`. Perfis antigos sem JSON: todos os três são undefined/null/false → mostra `—` (n/d), não "aplicado" incorretamente.

### MetricsDiff (exportado)

Componente de diff antes→depois de reprocessamento:
- Verde = melhoria de contagem de alvos
- Vermelho = regressão

### Uso em ProjectDetailClient

- Seção "Pipeline Log" colapsável (fechado por padrão) abaixo das thumbnails de cada perfil; carga lazy ao expandir
- No painel "Ajustar filtros": compact PipelineLog com label "Estado atual"; após reprocessamento → re-fetch automático → MetricsDiff exibido

### Uso em Nova Entrada

- Mini pipeline visual `Filtros → SNR Gate → Detector → Imagens` no topo do accordion "Personalizar parâmetros"
- `ParamTooltip` (CSS-only, hover:visible) em 12 parâmetros

---

## Fluxo de status do projeto

```
aguardando_arquivos
→ aguardando_processamento
→ processando_gpr
→ gpr_concluido
→ processando_ia
→ ia_concluida            (revisão manual)
→ revisao_concluida       (auto_accept_ia=true)
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
