-- B1 — Módulo de treinamento ground truth
-- NOTA: gpr_ground_truth já existe (Fase 11 via job_interpretada.py).
--       Esta migration CRIA gpr_training_sessions e ESTENDE gpr_ground_truth
--       com as colunas necessárias para o wizard de validação manual.
-- Aplicado ao remoto via MCP como:
--   ground_truth_wizard            (20260617210714)
--   ground_truth_nullable_legacy_cols (20260617210759)

-- 1. Tabela de sessões de treinamento (agrupador de entradas do wizard)
CREATE TABLE IF NOT EXISTS gpr_training_sessions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid REFERENCES projects(id),
  profile_id    uuid REFERENCES gpr_profiles(id),
  created_by    uuid,
  descricao     text,
  total_vp      int DEFAULT 0,
  total_fp      int DEFAULT 0,
  total_fn      int DEFAULT 0,
  status        text DEFAULT 'rascunho',
  created_at    timestamptz DEFAULT now()
);
ALTER TABLE gpr_training_sessions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='gpr_training_sessions' AND policyname='ts_all') THEN
    CREATE POLICY "ts_all" ON gpr_training_sessions FOR ALL USING (true) WITH CHECK (true);
  END IF;
END $$;

-- 2. Novos campos no gpr_ground_truth para o wizard de validação manual
ALTER TABLE gpr_ground_truth
  ADD COLUMN IF NOT EXISTS session_id              uuid REFERENCES gpr_training_sessions(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS created_by              uuid,
  ADD COLUMN IF NOT EXISTS detected_target_id      uuid REFERENCES detected_targets(id),
  ADD COLUMN IF NOT EXISTS e_verdadeiro_positivo   boolean,
  ADD COLUMN IF NOT EXISTS e_falso_negativo         boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS x_real_m               float,
  ADD COLUMN IF NOT EXISTS depth_real_m            float,
  ADD COLUMN IF NOT EXISTS tipo_alvo_confirmado    text,
  ADD COLUMN IF NOT EXISTS material_alvo           text,
  ADD COLUMN IF NOT EXISTS diametro_real_mm        float,
  ADD COLUMN IF NOT EXISTS fonte_confirmacao       text DEFAULT 'avaliacao_especialista',
  ADD COLUMN IF NOT EXISTS confianca_fonte         int,
  ADD COLUMN IF NOT EXISTS umidade_solo            text,
  ADD COLUMN IF NOT EXISTS tipo_superficie         text,
  ADD COLUMN IF NOT EXISTS dias_sem_chuva          int,
  ADD COLUMN IF NOT EXISTS profundidade_lencol_m   float,
  ADD COLUMN IF NOT EXISTS amplitude_relativa_max  float,
  ADD COLUMN IF NOT EXISTS depth_detector_m        float;

-- 3. Backfill e_verdadeiro_positivo a partir de e_falso_positivo (rows existentes)
UPDATE gpr_ground_truth
SET e_verdadeiro_positivo = NOT e_falso_positivo
WHERE e_verdadeiro_positivo IS NULL AND e_falso_positivo IS NOT NULL;

-- 4. Tornar nullable colunas legadas NOT NULL (permitem inserts do wizard sem match no detector)
ALTER TABLE gpr_ground_truth
  ALTER COLUMN target_rank DROP NOT NULL,
  ALTER COLUMN x_m         DROP NOT NULL,
  ALTER COLUMN depth_m     DROP NOT NULL;
