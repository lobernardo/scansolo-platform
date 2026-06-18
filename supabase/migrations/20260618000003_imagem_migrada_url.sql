-- Fase 7 (Kirchhoff migration): coluna que estava referenciada em código mas
-- nunca foi criada via migration. Ausência causava erro PostgREST na query
-- getPipelineMetrics → "perfil não encontrado" no Pipeline Log.

ALTER TABLE gpr_profiles
  ADD COLUMN IF NOT EXISTS imagem_migrada_url text;
