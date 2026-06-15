# Correções P1-P4 — Preview RADAN 5m + Skip IA
> Data: 2026-06-15
> Base: Auditoria AUDITORIA_UI_PREVIEW_RADAN_5M_LOCAL.md (Teste 15-6, 126 DZTs HELPER)

---

## P1 — Upload da preview no worker

**Arquivo:** `services/worker/job_gpr.py`

**Mudança:** `_radargrama_preview_radan_5m.png` adicionado ao loop de upload de imagens.

```python
# Antes (4 imagens):
for filename, col in [
    (f"{stem}_bruta.png", "imagem_bruta_url"),
    (f"{stem}_processada.png", "imagem_processada_url"),
    (f"{stem}_anotada_completa.png", "imagem_anotada_url"),
    (f"{stem}_anotada_alta_confianca.png", "imagem_alta_conf_url"),
]:

# Depois (5 imagens):
for filename, col in [
    (f"{stem}_bruta.png", "imagem_bruta_url"),
    (f"{stem}_processada.png", "imagem_processada_url"),
    (f"{stem}_anotada_completa.png", "imagem_anotada_url"),
    (f"{stem}_anotada_alta_confianca.png", "imagem_alta_conf_url"),
    (f"{stem}_radargrama_preview_radan_5m.png", "imagem_preview_radan_5m_url"),
]:
```

`_upload_image` retorna `None` se o arquivo não existe — sem risco de quebrar job caso a preview não seja gerada.

---

## P2 — Persistência no banco de dados

### Migration

**Arquivo criado:** `supabase/migrations/20260615000001_preview_radan_5m_url.sql`

```sql
ALTER TABLE gpr_profiles
  ADD COLUMN IF NOT EXISTS imagem_preview_radan_5m_url text;
```

### Tipos TypeScript

**Arquivo:** `apps/web/lib/types/database.ts`

Campos adicionados ao `gpr_profiles` Row / Insert / Update:

| Campo | Tipo | Seção |
|---|---|---|
| `imagem_preview_radan_5m_url` | `string \| null` | Row (required), Insert/Update (optional) |
| `snr_imagem_db` | `number \| null` | Row/Insert/Update — estava faltando desde migration 20260608000001 |
| `snr_imagem_ratio` | `number \| null` | idem |
| `modo_processamento` | `string \| null` | idem |
| `tipo_solo` | `string \| null` | idem |

Os 4 campos SNR já existiam no banco (migration 20260608000001) mas estavam ausentes nos tipos TypeScript. Corrigidos na mesma oportunidade.

---

## P3 — Frontend: 4ª aba de imagem

**Arquivo:** `apps/web/app/(dashboard)/projetos/[id]/ProjectDetailClient.tsx`

**Mudança em `openLightbox` (lightbox modal):**
```typescript
// Adicionado como 4ª entrada:
{ url: profile.imagem_preview_radan_5m_url ?? "", label: "Preview RADAN 5m" },
```

**Mudança nos cards de perfil (thumbnails):**
```typescript
// Adicionado como 4ª entrada:
{ url: profile.imagem_preview_radan_5m_url, label: "Preview RADAN 5m" },
```

Em ambos os casos o `.filter(i => !!i.url)` garante que a entrada só aparece quando a URL existe. Projetos processados antes desta migration continuam exibindo 3 imagens.

---

## P4 — Skip IA na nova entrada

### UI

**Arquivo:** `apps/web/app/(dashboard)/nova-entrada/page.tsx`

- Novo checkbox `skip_ia` adicionado após o bloco `auto_accept_ia`
- Label do `auto_accept_ia` atualizado de "Aprovação automática pela IA" para "Aprovação automática da interpretação IA (GPT-4o por alvo)" — diferencia do gpt-image-1 visual

### Action

**Arquivo:** `apps/web/app/(dashboard)/nova-entrada/actions.ts`

```typescript
const skip_ia = formData.get("skip_ia") === "true";
// Gravado em processing_config:
processing_config: skip_ia ? { skip_ia: true } : null,
```

### Worker

**Arquivo:** `services/worker/job_gpr.py`

```python
# Após gpr_concluido, antes de criar job IA:
skip_ia = (raw_config or {}).get("skip_ia", False)
if skip_ia:
    log.info("gpr_skip_ia", project_id=project_id)
else:
    supa.create_job(project_id, "ia")
```

`raw_config` já estava disponível na linha 94 do arquivo. Sem alteração de interface.

### Banner de versão

**Arquivo:** `services/worker/pipeline/pipeline_v1.py`

`"V1.2 outputs"` → `"v2.0 outputs"` + adicionado `*_radargrama_preview_radan_5m.png` na listagem de saídas.

---

## P5 — Pileup em 0.30m (DIFERIDO)

232/341 alvos em exatamente `det_depth_min_m=0.30m` nos DZTs HELPER (modo MINIMO, sem bandpass).

Causa provável: MINIMO mode pula bandpass → direct wave não filtrada → falsos positivos rasos empilhados no cutoff.

**Não corrigido neste round.** Aguarda avaliação com Amilson nos candidatos brutos via `_classificador_candidatos.py`.

---

## Validação TypeScript

```
npx tsc --noEmit → 0 erros
```

---

## Arquivos modificados

| Arquivo | Tipo | Descrição |
|---|---|---|
| `supabase/migrations/20260615000001_preview_radan_5m_url.sql` | NOVO | Coluna `imagem_preview_radan_5m_url` em `gpr_profiles` |
| `apps/web/lib/types/database.ts` | MOD | +5 campos em gpr_profiles Row/Insert/Update |
| `services/worker/job_gpr.py` | MOD | Upload preview + skip_ia guard |
| `apps/web/app/(dashboard)/projetos/[id]/ProjectDetailClient.tsx` | MOD | 4ª imagem no lightbox e cards |
| `apps/web/app/(dashboard)/nova-entrada/page.tsx` | MOD | Checkbox skip_ia + label atualizado |
| `apps/web/app/(dashboard)/nova-entrada/actions.ts` | MOD | skip_ia → processing_config |
| `services/worker/pipeline/pipeline_v1.py` | MOD | Banner v2.0 |

---

## Próximo passo

1. Aplicar migration no banco remoto: `supabase db push --password <DB_PASSWORD>`
2. Criar novo projeto com "Pular interpretação IA" marcado e confirmar que job IA não é criado
3. Confirmar que preview aparece como 4ª thumbnail após reprocessamento com DZT HELPER
