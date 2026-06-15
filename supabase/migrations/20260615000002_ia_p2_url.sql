-- IA P2: anotação dos resultados de IA sobre a imagem Processada 2
alter type job_type add value if not exists 'ia_p2';

alter table gpr_profiles
  add column if not exists imagem_interpretada_ia_p2_url text;
