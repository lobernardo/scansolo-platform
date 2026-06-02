-- Fase 7: Funcionalidades de IA
-- 1. auto_accept_ia: aprovação automática de alvos sem revisão manual
-- 2. imagem_interpretada_url: imagem anotada com labels da interpretação IA

alter table projects
  add column if not exists auto_accept_ia boolean not null default false;

alter table gpr_profiles
  add column if not exists imagem_interpretada_url text;

comment on column projects.auto_accept_ia is
  'Se true, alvos alta/media são auto-aprovados após IA e projeto avança '
  'para cartografia sem parar em revisão manual.';

comment on column gpr_profiles.imagem_interpretada_url is
  'URL da imagem processada com labels da interpretação IA sobrepostos '
  '(tipo + confiança por alvo). Gerada por job_ia após todas as interpretações.';
