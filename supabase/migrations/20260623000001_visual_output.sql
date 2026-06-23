-- Visual output: imagem_visual_url + visual_config per profile + job_type 'visual'
--
-- imagem_visual_url : URL pública da imagem gerada pelo job visual
-- visual_config     : parâmetros efetivamente usados na última geração (JSONB)
-- job_type 'visual' : novo tipo de job para geração visual customizada

ALTER TABLE gpr_profiles
  ADD COLUMN IF NOT EXISTS imagem_visual_url text,
  ADD COLUMN IF NOT EXISTS visual_config     jsonb;

ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'visual';
