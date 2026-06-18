# Histórico de Fases — 15+
> Objetivo: Registro das fases a partir da Fase 15, com detalhes de implementação e contexto de decisões.
> Contexto: Fase 15 implementada em 2026-06-17/18. Fases futuras a documentar aqui.

---

## Fase 15 — Controle explícito de bandpass (2026-06-17/18)

**Problema raiz:** antes da Fase 15, não era possível desativar o bandpass antes do primeiro processamento — a UI tinha `min=30` no campo `bandpass_low_mhz`. DZTs de alto SNR (ex: HELPER, 126 DZTs) precisavam de bandpass desativado, mas só era corrigível via "Ajustar filtros" pós-fato (P16). Além disso, P10 havia documentado pileup de alvos em 0.30m em modo MINIMO, que estava incorretamente atribuído ao bandpass ser "pulado automaticamente" — na verdade o bandpass nunca foi pulado pelo código; a confusão era de documentação.

### O que foi implementado

**UI — Nova Entrada:**
- Toggle **Bandpass ON/OFF** no accordion "Personalizar parâmetros"
- Quando OFF: salva `bandpass_low_mhz=0` em `processing_config` → pipeline desativa bandpass
- Convenção `bandpass_low_mhz=0` já existia no pipeline (linha 1220 de `pipeline_v1.py`)

**UI — Modal de presets (`/presets`):**
- Toggle **Bandpass ON/OFF** no modal criar/editar/duplicar
- Quando OFF: salva `bandpass_low_mhz=0` em `parameters`
- Chip BP na listagem de parâmetros exibe "desativado" quando `bandpass_low_mhz=0`

**Worker — `_filtros_to_pipeline_config` (job_gpr.py):**
- `velocity_mns` em `filtros_customizados` → `cfg["velocity_mns"]` (fix P17: campo não era mapeado)
- `det_depth_min_m` em `filtros_customizados` → seta `cfg["_det_depth_min_m_explicit"] = True` (fix P18: override era ignorado em modo MINIMO)
- `bandpass_low_mhz=0` continua sendo a convenção para bandpass OFF

**Worker — `_get_processing_config` (job_gpr.py):**
- Se `det_depth_min_m` estiver em `project_config`, seta `merged["_det_depth_min_m_explicit"] = True` (fix P18 via Nova Entrada accordion)

**Pipeline — `pipeline_v1.py`:**
- 6 novos campos em `_metrics` dict para `pipeline_metrics.json`:
  - `bandpass_aplicado`: `"desativado"` | `"80-500 MHz"` (ou outro range)
  - `bandpass_low_mhz_usado`, `bandpass_high_mhz_usado`, `bandpass_order_usado`, `bandpass_tipo_usado`
  - `detector_input_mode` (já existia no return dict mas não estava sendo salvo no JSON)

**Server action — `gpr-actions.ts`:**
- 5 novos campos em `PipelineMetrics` type: `bandpass_aplicado`, `bandpass_low_mhz_usado`, `bandpass_high_mhz_usado`, `bandpass_order_usado`, `bandpass_tipo_usado`
- Mapeados do JSON na função `getPipelineMetrics`

**Componente — `PipelineLog.tsx`:**
- Bandpass detection mudou de single-source para tri-source:
  ```typescript
  const bandpassDesativado =
    m.bandpass_aplicado === "desativado" ||   // JSON — cobre primeiro processamento
    m.bandpass_low_mhz_usado === 0 ||         // JSON fallback
    filtros.bandpass === false;                // filtros_customizados — cobre reprocessamento
  ```
- Antes: só checava `filtros.bandpass === false` → não detectava bandpass OFF no primeiro processamento
- Perfis antigos sem JSON: todos os três undefined/null/false → mostra `—` (n/d), não "aplicado" incorretamente

**CLAUDE.md — 8 correções de documentação:**
- Regras absolutas: substituída regra sobre bandpass pelo wording correto
- Sequência step 3: "bandpass sempre aplicado" → condicional correto
- Modo MINIMO: "tpow×0.6" → "tpow fixo em 0.3" (código real)
- Modo MINIMO: "bandpass sempre aplicado" → removido (era falso)
- Modo AGRESSIVO: "tpow×1.5" → "tpow×1.5 (cap 1.2)" (código real)
- PipelineMetrics fields: adicionados 5 campos de bandpass
- PipelineLog description: atualizado para tri-source
- P10: atualizado para refletir a realidade (nunca foi pulado automaticamente)
- P9 calibração: removida frase sobre "bandpass nunca é pulado"

### Pendências registradas nesta fase

- **P16** ✅ (resolvido nesta fase): toggle ON/OFF em Nova Entrada + presets
- **P17** ✅ (resolvido nesta fase): velocity_mns em _filtros_to_pipeline_config
- **P18** ✅ (resolvido nesta fase): det_depth_min_m explicit flag
- **P19** (registrada, adiada): caminho legado em UploadClient.tsx — ver [known_issues.md](../known_issues.md)

### Pendências abertas para Fase A (visual/depth_preview_m)

- **Bug `depth_preview_m`** (pipeline_v1.py linha ~514): `salvar_imagem_preview_radan_5m` recebe `depth_preview_m` como parâmetro mas o sobrescreve imediatamente com `twtt_max_ns × velocity / 2` → Processada 2 mostra ~1.5m em vez de 5m. Fix: não sobrescrever; calcular na chamada e passar como constante. **Adiado para Fase A.**

---

## Fase A — Arquitetura visual RADAN-like (planejada)

Tema: ferramentas de visualização configuráveis para o geofísico.
Detalhe: a ser documentado quando implementado.
