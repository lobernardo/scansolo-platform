-- Fase B: tornar imagem científica (radargrama técnico) visível na UI
-- O pipeline já gera _radargrama_cientifico.png (dewow+bp+tpow, sem AGC/bgremoval)
-- mas o job_gpr.py não fazia upload. Esta coluna recebe a URL pública quando upada.

ALTER TABLE gpr_profiles
  ADD COLUMN IF NOT EXISTS imagem_cientifica_url text;
