# Pendências Conhecidas (P1–P19)
> Objetivo: Rastreamento completo de bugs, limitações e dívidas técnicas conhecidas.
> Contexto: Atualizado em 2026-06-18. Itens com ✅ foram resolvidos e mantidos para histórico.

---

| # | Item | Impacto | Ação necessária |
|---|---|---|---|
| P1 | Dropbox é placeholder — arquivos ficam no Supabase Storage, não no Dropbox real | Marcos usa Dropbox para receber dados de campo | Integrar Dropbox API real quando Marcos validar o fluxo |
| P2 | `velocity_usada_mns` sempre = `velocity_estimada_mns` nos DZTs de teste | Calibração de profundidade imprecisa em solos heterogêneos | Sessão de calibração com Amilson usando DZTs com alvos de profundidade conhecida |
| P3 | `fkMigration` do GPRPy requer `irlib` não instalado — usa Kirchhoff numpy próprio | Qualidade da migração vs. GPRPy nativo | Avaliar com Amilson se qualidade atual é suficiente |
| P4 | IA de imagem (`gpt-image-1`) off por padrão | Melhoria potencial das imagens processadas | Avaliar custo/benefício com Amilson em projeto real |
| P5 | ~~constraint `media` rejeitada pelo schema antigo~~ | ~~Alvos média não persistiam~~ | ✅ **Resolvido** — migration 20260606000001 |
| P6 | `fis_amp_metal_thr` revisado para 0.65 e `fis_amp_nao_metal_thr` para 0.22 via Fresnel; valores aguardam validação com alvos reais | Classificação metal/não-metal ainda não validada em campo | Usar `/treinamento` ou `import_ground_truth.py` para acumular ≥20 amostras; disparar `job_recalibrar` |
| P7 | ~~GPT-4o tem viés para `galeria_concreto` sem contexto do projeto~~ | ~~Interpretações automáticas pouco diferenciadas~~ | ✅ **Resolvido** — `_build_system_prompt(project)` injeta bloco PROJECT CONTEXT (commit 91e5f9c) |
| P8 | `testar_imagem_externa.py` rodou em 13/126 imagens do dataset HELPAVPA | Validação parcial do detector em imagens RADAN | Rodar nas 113 restantes após Amilson validar |
| P9 | ~~`job_gpr.py` usa `--preset 270mhz` via subprocess — `detector_input_mode=raw` já está no preset padrão~~ | — | ✅ Resolvido — preset contém default correto |
| P10 | ~~Pileup em `det_depth_min_m=0.30m` com DZTs de alto SNR (modo MINIMO, bandpass era pulado automaticamente — documentação errada)~~ | ~~232/341 alvos em 0.30m exato em teste com 126 DZTs HELPER — falsos positivos de airwave/onda direta~~ | ✅ **Resolvido** (Fase 15, 2026-06-17/18): bandpass nunca foi pulado automaticamente — era erro de documentação. Bandpass OFF agora é decisão explícita do geofísico (toggle). Monitorar se `det_depth_min_m=0.50m` é suficiente em DZTs HELPER |
| P11 | ~~Banner "Matrizes V1.2" no log do `pipeline_v1.py` (linha ~1222)~~ | ~~Confunde auditorias — pipeline é v2.0.0~~ | ✅ **Resolvido** — banner já era `v2.0.0` na linha 1630 (verificado 2026-06-17) |
| P12 | Delete projeto remove apenas registros do DB — arquivos no Storage (DZTs, PNGs, CSVs) não são deletados | Acúmulo de arquivos órfãos no Supabase Storage | Adicionar limpeza de Storage na server action `deleteProject` quando for prioritário |
| P13 | ~~Reprocessamento individual não atualizava imagem na UI — página nunca recarregava após job concluir~~ | ~~Usuário via imagem antiga independente dos filtros aplicados~~ | ✅ **Resolvido** — `getJobStatus` + polling 5s + `router.refresh()` (commit a5c636a, 2026-06-16) |
| P14 | ~~`job_interpretada.py` ground truth: query usa `observacoes` e `revisado_por` mas colunas reais são `observacao` e `reviewed_by`~~ | ~~Campos ficam null no ground truth (silencioso — não aborta job)~~ | ✅ **Resolvido** — commit bab0ef1 |
| P15 | ~~`gpr_presets.parameters` no banco ainda não tem `bandpass_tipo` nos presets seedados~~ | ~~Presets `270mhz_void` e `270mhz_concrete` não usarão FIR triangular via UI~~ | ✅ **Resolvido** — UPDATE direto nos dois presets no banco remoto (2026-06-17) |
| P16 | ~~Bandpass não podia ser desativado antes do primeiro processamento — trava `min=30` na UI impedia `bandpass_low_mhz=0`~~ | ~~DZTs de alto SNR (ex: HELPER) tinham imagens ruins no primeiro processamento~~ | ✅ **Resolvido** (2026-06-18) — toggle Bandpass ON/OFF em Nova Entrada + modal de presets |
| P17 | ~~`velocity_mns` alterado em "Ajustar filtros" não era aplicado no reprocessamento~~ | ~~`_filtros_to_pipeline_config` não mapeava o campo; worker usava velocity do projeto original~~ | ✅ **Resolvido** (2026-06-18) — campo mapeado em `_filtros_to_pipeline_config` |
| P18 | ~~`det_depth_min_m` configurado na Nova Entrada era ignorado em modo MINIMO~~ | ~~Pipeline usava adaptativo (`calcular_depth_min_adaptativo`) sem respeitar override do usuário~~ | ✅ **Resolvido** (2026-06-18) — `_det_depth_min_m_explicit=True` setado em `_get_processing_config` e `_filtros_to_pipeline_config` quando campo presente |
| P19 | `UploadClient.tsx` caminho legado (`startProcessingWithConfig`) salva `FilterConfig.filtros_ativos.bandpass=false` em `processing_config` mas o worker não entende esse formato (`_get_processing_config` espera `bandpass_low_mhz=0`, não `filtros_ativos.bandpass`) — bandpass é aplicado mesmo quando usuário selecionou "Mínimo" | Afeta apenas projetos sem `preset_id` (pré-Fase 12 ou criados sem Nova Entrada). Projetos novos sempre têm `preset_id` via Nova Entrada | Converter `filtros_ativos.bandpass=false` → `bandpass_low_mhz=0` em `startProcessingWithConfig`, ou deprecar o caminho legado. Adiado — impacto mínimo em produção |

---

## Itens a calibrar com Amilson (antes de produção)

1. **Radargrama científico vs. relatório** — validar visualmente se `_radargrama_cientifico.png` (sem AGC) é adequado para revisão técnica
2. **Candidatos RAW** — confirmar que top-50 de cada PATIO são hipérboles reais (não artefatos)
3. **Parâmetros físicos do detector** — thresholds revisados com Fresnel (0.65/0.22); validar com ~10 alvos de tipo conhecido via `GROUND_TRUTH/`
4. **Velocity** — `VELOCITY_POR_SOLO` derivada de literatura; validar com DZT de alvos de profundidade conhecida (`GROUND_TRUTH/CALIBRACAO/`)
5. **Qualidade visual** — comparar `_radargrama_relatorio.png` do pipeline v2.0.0 vs. output RADAN para o mesmo DZT lado a lado
6. **Prompt GPT-4o** — ~~adicionar contexto do projeto~~ ✅ resolvido; validar se viés `galeria_concreto` reduziu com projetos reais
7. **Preset de filtros por tipo de solo** — limiares SNR calibrados só para PATIO. Validar com solo argiloso, úmido e pedregoso
8. **Preview RADAN 5m vs. RADAN real** — comparar `_radargrama_preview_radan_5m.png` com output RADAN para os mesmos DZTs
9. **Pileup 0.30m em DZTs HELPER** — confirmar se 232 alvos em 0.30m eram falsos positivos. Bandpass agora é decisão explícita; monitorar nova taxa de pileup nos próximos processamentos
10. **Candidato de recalibração** — após acumular ≥20 amostras em `gpr_ground_truth`, disparar `job_recalibrar` e revisar o candidato JSON antes de aplicar ao preset de produção
11. **Presets seedados** — Amilson deve revisar `det_h_max_m`, `det_depth_min_m` e `velocity_mns` de cada preset antes de usar em produção
