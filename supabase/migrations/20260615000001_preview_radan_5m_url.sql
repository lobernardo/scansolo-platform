-- Pipeline v2.0.0: campo preview RADAN 5m em gpr_profiles
ALTER TABLE gpr_profiles
  ADD COLUMN IF NOT EXISTS imagem_preview_radan_5m_url text;
