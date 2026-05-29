-- ═══════════════════════════════════════════════════════════════════════════
-- Fase 4: Campos de detecção cartográfica em cartography_outputs
-- ═══════════════════════════════════════════════════════════════════════════

alter table cartography_outputs
  add column if not exists cartography_mode        text default 'unknown',
  add column if not exists cartography_confidence  text default 'baixa',
  add column if not exists cartography_source      text default 'inferred',
  add column if not exists cartography_notes       text,
  add column if not exists confirmed_by            uuid references profiles(id),
  add column if not exists confirmed_at            timestamptz;
