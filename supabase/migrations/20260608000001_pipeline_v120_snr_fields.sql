-- Pipeline v1.2.0: campos SNR gate em gpr_profiles
-- snr_imagem_db, snr_imagem_ratio, modo_processamento, tipo_solo

ALTER TABLE gpr_profiles
  ADD COLUMN IF NOT EXISTS snr_imagem_db     FLOAT,
  ADD COLUMN IF NOT EXISTS snr_imagem_ratio  FLOAT,
  ADD COLUMN IF NOT EXISTS modo_processamento TEXT DEFAULT 'padrao',
  ADD COLUMN IF NOT EXISTS tipo_solo          TEXT DEFAULT 'standard';
