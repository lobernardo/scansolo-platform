-- Fase D: campos de versionamento e validação para presets do cliente
-- Presets do sistema (is_system=true) não são afetados funcionalmente.
-- parent_id, version, validated_by/at são úteis apenas para presets criados por usuários.

ALTER TABLE gpr_presets
  ADD COLUMN IF NOT EXISTS version       integer NOT NULL DEFAULT 1,
  ADD COLUMN IF NOT EXISTS parent_id     uuid REFERENCES gpr_presets(id),
  ADD COLUMN IF NOT EXISTS validated_by  uuid REFERENCES auth.users(id),
  ADD COLUMN IF NOT EXISTS validated_at  timestamptz,
  ADD COLUMN IF NOT EXISTS notes         text,
  ADD COLUMN IF NOT EXISTS dataset_validation text,
  ADD COLUMN IF NOT EXISTS priority_order     integer,
  ADD COLUMN IF NOT EXISTS is_hidden_for_client boolean NOT NULL DEFAULT false;
