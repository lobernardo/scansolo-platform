-- ═══════════════════════════════════════════════════════════════════════════
-- Fase 5: Campos necessários para geração do relatório
-- ═══════════════════════════════════════════════════════════════════════════

-- Campos de projeto usados no relatório
alter table projects
  add column if not exists codigo_projeto  text,        -- ex: PT-GPR-SOL-036
  add column if not exists contato_nome    text,        -- A/C do cliente
  add column if not exists area_m2         float;       -- área levantada em m²

-- Storage path do DOCX gerado (PDF fica como TODO)
alter table report_outputs
  add column if not exists docx_storage_url text,
  add column if not exists approved_at      timestamptz;
