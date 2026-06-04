-- Fase 8: Workflow da imagem interpretada
-- Adiciona: status da interpretada por perfil + tabela de exemplos de treino da IA

-- ─── Enum extensions ────────────────────────────────────────────────────────────
-- inferencias: já pode existir se foi adicionado manualmente — IF NOT EXISTS protege
alter type job_type add value if not exists 'inferencias';
alter type job_type add value if not exists 'interpretada';

alter type project_status add value if not exists 'processando_interpretada';
alter type project_status add value if not exists 'interpretada_gerada';

alter type job_status add value if not exists 'processando_interpretada';

-- Status da imagem interpretada em cada perfil GPR
alter table gpr_profiles
  add column if not exists imagem_interpretada_status text not null default 'pendente';
  -- valores: 'pendente' | 'aprovado' | 'regenerando' | 'manual'

comment on column gpr_profiles.imagem_interpretada_status is
  'Status do workflow da imagem interpretada: pendente (ainda não gerada), '
  'aprovado (Amilson aprovou — vai para relatório), '
  'regenerando (nova rodada de IA solicitada), '
  'manual (Amilson anotou manualmente).';

-- Dados da anotação manual (quando Amilson interpreta manualmente no canvas)
alter table gpr_profiles
  add column if not exists imagem_interpretada_manual_data jsonb;

comment on column gpr_profiles.imagem_interpretada_manual_data is
  'JSON com anotações manuais do Amilson: lista de marcadores desenhados no canvas. '
  'Exemplo: [{"x_pct": 0.32, "y_pct": 0.18, "tipo": "cabo_eletrico", '
  '"profundidade_m": 0.8, "diametro_m": 0.05, "observacao": ""}]';

-- Tabela de exemplos de treino da IA
-- Cada linha é um exemplo validado (revisão normal ou anotação manual)
-- que alimenta o contexto da IA nas próximas interpretações.
create table if not exists ia_training_examples (
  id              uuid primary key default uuid_generate_v4(),
  project_id      uuid not null references projects(id) on delete restrict,
  profile_id      uuid not null references gpr_profiles(id) on delete restrict,
  source          text not null,         -- 'revisao' | 'manual'
  annotation_data jsonb not null,        -- lista de alvos confirmados com tipo/prof/diâm
  imagem_url      text,                  -- URL da _processada.png usada como referência
  created_at      timestamptz not null default now(),
  created_by      uuid references profiles(id)
);

comment on table ia_training_examples is
  'Exemplos de treino para a IA de interpretação. '
  'Fonte: (a) revisão do Amilson aprovada, (b) anotação manual no canvas. '
  'Usados como few-shot examples nas chamadas ao GPT-4o do job_ia.';

-- Index para busca dos exemplos mais recentes por projeto
create index if not exists ia_training_examples_project_idx
  on ia_training_examples (project_id, created_at desc);
