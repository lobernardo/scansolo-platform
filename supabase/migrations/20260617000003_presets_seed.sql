-- ── Seed: 6 presets do sistema com base científica ───────────────────────────
-- is_system=true → somente leitura via RLS (não editáveis nem deletáveis)

INSERT INTO gpr_presets
  (name, description, scientific_basis, target_scenario, antenna_freq_mhz,
   is_system, is_active, created_by, parameters)
VALUES

-- 1. Padrão — Solo Misto
(
  'Utilidades Urbanas — Solo Misto 270MHz',
  'Preset padrão ScanSOLO para mapeamento de utilidades em solo urbano misto.',
  'Daniels (2004) Ground Penetrating Radar, cap.4; GSSI SIR-30 Application Note — Utility Detection; Topp et al. (1980) ε_r=9 para solo misto úmido (loam)',
  'Detecção de utilidades (água, gás, telecom, elétrico) em solo urbano misto. Profundidade típica 0–3m.',
  270,
  true, true, NULL,
  '{
    "dewow_window": 5,
    "bandpass_low_mhz": 80, "bandpass_high_mhz": 500, "bandpass_order": 5,
    "bgremoval_traces": 30, "tpow_power": 0.5, "agc_window": 150,
    "velocity_mns": 0.10, "contrast": 2.5, "colormap": "gray", "dpi": 150,
    "det_amp_threshold": 0.50, "det_h_min_m": 0.10, "det_h_max_m": 3.00,
    "det_top_n": 25, "det_min_score_csv": 30, "det_depth_min_m": 0.30,
    "detector_input_mode": "raw", "tipo_solo": "standard",
    "fis_ativo": true, "fis_amp_metal_thr": 0.75, "fis_amp_nao_metal_thr": 0.40
  }'::jsonb
),

-- 2. Solo Argiloso
(
  'Utilidades Urbanas — Solo Argiloso 270MHz',
  'Otimizado para solos argilosos com alta atenuação eletromagnética. Bandpass estreito, ganho alto.',
  'Cassidy (2009) in Jol (ed.) GPR Theory and Applications, cap.2 — Electromagnetic Properties of Soils; Daniels (2004) cap.4; ε_r≈18 para argila saturada (Cassidy 2009, Tabela 2.3)',
  'Detecção de utilidades em solo argiloso ou úmido. Penetração reduzida (~2.5m máx).',
  270,
  true, true, NULL,
  '{
    "dewow_window": 5,
    "bandpass_low_mhz": 60, "bandpass_high_mhz": 400, "bandpass_order": 5,
    "bgremoval_traces": 20, "tpow_power": 0.7, "agc_window": 100,
    "velocity_mns": 0.07, "contrast": 3.0, "colormap": "gray", "dpi": 150,
    "det_amp_threshold": 0.40, "det_h_min_m": 0.10, "det_h_max_m": 2.50,
    "det_top_n": 20, "det_min_score_csv": 25, "det_depth_min_m": 0.30,
    "detector_input_mode": "raw", "tipo_solo": "argiloso",
    "fis_ativo": true, "fis_amp_metal_thr": 0.65, "fis_amp_nao_metal_thr": 0.35
  }'::jsonb
),

-- 3. Areia Seca / Entulho Urbano
(
  'Utilidades Urbanas — Areia Seca / Entulho 270MHz',
  'Para solos secos com baixa atenuação: areia, cascalho ou entulho de demolição. Alta penetração.',
  'Annan (2003) GPR Principles, Procedures & Applications, sec.4.3; Daniels (2004) Tabela 4.1 — ε_r≈2.25 para areia seca (v=0.20 m/ns)',
  'Detecção de utilidades em areia seca, cascalho ou entulho urbano de demolição. Profundidade até 5m.',
  270,
  true, true, NULL,
  '{
    "dewow_window": 5,
    "bandpass_low_mhz": 100, "bandpass_high_mhz": 500, "bandpass_order": 5,
    "bgremoval_traces": 35, "tpow_power": 0.4, "agc_window": 180,
    "velocity_mns": 0.20, "contrast": 2.0, "colormap": "gray", "dpi": 150,
    "det_amp_threshold": 0.55, "det_h_min_m": 0.10, "det_h_max_m": 5.00,
    "det_top_n": 30, "det_min_score_csv": 30, "det_depth_min_m": 0.40,
    "detector_input_mode": "raw", "tipo_solo": "arenoso",
    "fis_ativo": true, "fis_amp_metal_thr": 0.80, "fis_amp_nao_metal_thr": 0.45
  }'::jsonb
),

-- 4. Pavimento e Concreto
(
  'Pavimento e Concreto 270MHz',
  'Otimizado para inspeção de pavimento asfáltico e estruturas de concreto. Foco em alvos rasos e metálicos.',
  'Huston et al. (2004) Concrete Inspection with GPR, ASTM C1383; Bungey (2004) Testing of Concrete Structures, cap.9; ε_r≈6.25 para concreto curado (v=0.12 m/ns)',
  'Inspeção de pavimento, laje, piso de concreto. Localização de armação, dutos embutidos. Máx 1.5m.',
  270,
  true, true, NULL,
  '{
    "dewow_window": 3,
    "bandpass_low_mhz": 100, "bandpass_high_mhz": 500, "bandpass_order": 4,
    "bgremoval_traces": 25, "tpow_power": 0.4, "agc_window": 120,
    "velocity_mns": 0.12, "contrast": 2.5, "colormap": "gray", "dpi": 150,
    "det_amp_threshold": 0.60, "det_h_min_m": 0.05, "det_h_max_m": 1.50,
    "det_top_n": 20, "det_min_score_csv": 35, "det_depth_min_m": 0.10,
    "detector_input_mode": "raw", "tipo_solo": "standard",
    "fis_ativo": true, "fis_amp_metal_thr": 0.85, "fis_amp_nao_metal_thr": 0.50
  }'::jsonb
),

-- 5. Solo Úmido / Alagado
(
  'Solo Úmido / Alagado 270MHz',
  'Para solos saturados com alta condutividade e atenuação severa. Compensação máxima de ganho.',
  'Topp et al. (1980) Electromagnetic determination of soil water content — ε_r≈25 (v=0.06 m/ns); Knight (2001) GPR for Environmental Applications',
  'Solo saturado, várzea, área alagada ou próxima a lençol freático superficial. Penetração 1–2m.',
  270,
  true, true, NULL,
  '{
    "dewow_window": 7,
    "bandpass_low_mhz": 60, "bandpass_high_mhz": 350, "bandpass_order": 5,
    "bgremoval_traces": 15, "tpow_power": 0.8, "agc_window": 80,
    "velocity_mns": 0.06, "contrast": 3.5, "colormap": "gray", "dpi": 150,
    "det_amp_threshold": 0.35, "det_h_min_m": 0.10, "det_h_max_m": 2.00,
    "det_top_n": 15, "det_min_score_csv": 20, "det_depth_min_m": 0.30,
    "detector_input_mode": "raw", "tipo_solo": "umido",
    "fis_ativo": true, "fis_amp_metal_thr": 0.60, "fis_amp_nao_metal_thr": 0.30
  }'::jsonb
),

-- 6. Detecção de Vazios e Cavidades
(
  'Detecção de Vazios e Cavidades 270MHz',
  'Configuração para detectar espaços vazios, galerias e cavidades subterrâneas. Sem análise de material.',
  'Papadopoulos et al. (2008) GPR Subsurface Survey, Near Surface Geophysics; Annan (2003) sec.7.2 — Void Detection; sem_agc preserva amplitude real da reflexão',
  'Vazios, cavernas, galerias de drenagem, colapsos de solo. Profundidade até 4m.',
  270,
  true, true, NULL,
  '{
    "dewow_window": 5,
    "bandpass_low_mhz": 60, "bandpass_high_mhz": 400, "bandpass_order": 5,
    "bgremoval_traces": 40, "tpow_power": 0.5, "agc_window": 200,
    "velocity_mns": 0.10, "contrast": 2.0, "colormap": "gray", "dpi": 150,
    "det_amp_threshold": 0.45, "det_h_min_m": 0.20, "det_h_max_m": 4.00,
    "det_top_n": 15, "det_min_score_csv": 25, "det_depth_min_m": 0.40,
    "detector_input_mode": "sem_agc", "tipo_solo": "standard",
    "fis_ativo": false
  }'::jsonb
);
