-- ── gpr_presets: presets técnicos de processamento GPR ───────────────────────

CREATE TABLE IF NOT EXISTS gpr_presets (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name             text NOT NULL,
  description      text,
  scientific_basis text,
  target_scenario  text,
  antenna_freq_mhz int,
  is_system        boolean DEFAULT false,
  is_active        boolean DEFAULT true,
  created_by       uuid REFERENCES auth.users(id),
  parameters       jsonb NOT NULL,
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now()
);

ALTER TABLE gpr_presets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "presets_select" ON gpr_presets
  FOR SELECT USING (true);

CREATE POLICY "presets_insert" ON gpr_presets
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'socio')
    )
  );

CREATE POLICY "presets_update" ON gpr_presets
  FOR UPDATE USING (
    NOT is_system AND
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'socio')
    )
  );

CREATE POLICY "presets_delete" ON gpr_presets
  FOR DELETE USING (
    NOT is_system AND
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('admin', 'socio')
    )
  );

-- Referência ao preset usado no projeto
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS preset_id uuid REFERENCES gpr_presets(id);
