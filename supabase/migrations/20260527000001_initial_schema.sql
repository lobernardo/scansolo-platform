-- ═══════════════════════════════════════════════════════════════════════════
-- ScanSOLO Platform — Initial Schema (Phase 0)
-- Migration: 20260527000001_initial_schema
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── Extensions ──────────────────────────────────────────────────────────────
create extension if not exists "uuid-ossp";

-- ─── Enums ───────────────────────────────────────────────────────────────────

create type user_role as enum (
  'operador_campo',
  'tecnico',
  'socio',
  'admin'
);

create type project_status as enum (
  'criado',
  'aguardando_arquivos',
  'aguardando_confirmacao_operador',
  'backup_em_andamento',
  'backup_confirmado',
  'aguardando_processamento',
  'processando_gpr',
  'gpr_concluido',
  'processando_ia',
  'ia_concluida',
  'ia_pendente_erro',
  'aguardando_decisao_revisao',
  'revisao_opcional',
  'revisao_em_andamento',
  'revisao_concluida',
  'aguardando_cartografia',
  'cartografia_concluida',
  'cartografia_pendente_dados',
  'aguardando_relatorio',
  'relatorio_em_andamento',
  'relatorio_gerado',
  'aguardando_aprovacao',
  'finalizado',
  'erro',
  'pendente_dados'
);

create type job_type as enum (
  'gpr',
  'ia',
  'cartografia',
  'relatorio'
);

create type job_status as enum (
  'aguardando',
  'processando_gpr',
  'processando_ia',
  'processando',
  'concluido',
  'erro'
);

create type file_status as enum (
  'pendente',
  'confirmado',
  'erro'
);

create type output_type as enum (
  'dxf',
  'kml',
  'geojson',
  'csv'
);

create type review_status as enum (
  'pendente',
  'aprovado',
  'descartado',
  'ajustado'
);

create type saida_desejada as enum (
  'autocad',
  'google_earth',
  'ambos',
  'decidir_depois'
);

-- ─── profiles (extends auth.users) ───────────────────────────────────────────
create table profiles (
  id         uuid primary key references auth.users on delete cascade,
  name       text not null,
  email      text not null,
  role       user_role not null default 'operador_campo',
  active     boolean not null default true,
  created_at timestamptz not null default now()
);

comment on table profiles is 'User profiles extending Supabase Auth users. Role enforces access control.';

-- ─── projects ─────────────────────────────────────────────────────────────────
create table projects (
  id                   uuid primary key default uuid_generate_v4(),
  nome                 text not null unique,
  cliente              text not null,
  local                text,
  estado               char(2) not null,
  endereco             text,
  data_levantamento    date not null,
  codigo_interno       text,

  -- Service metadata
  tipo_servico         text,
  equipamento_gpr      text,
  antena_freq_mhz      int,
  tem_pipe_locator     boolean,
  tem_dzg              boolean,
  tem_kml              boolean,
  tem_dwg              boolean,
  saida_desejada       saida_desejada,

  -- Field notes
  observacoes          text,
  prioridade           text check (prioridade in ('normal', 'urgente', 'baixa')),
  prazo_desejado       date,

  -- Status and paths
  status               project_status not null default 'criado',
  dropbox_project_path text,

  -- Ownership
  created_by           uuid references profiles(id),
  assigned_to          uuid references profiles(id),

  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now()
);

comment on table projects is 'Core project record. status drives the workflow state machine.';

create index projects_status_idx on projects(status);
create index projects_created_by_idx on projects(created_by);
create index projects_assigned_to_idx on projects(assigned_to);

-- auto-update updated_at
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger projects_updated_at
  before update on projects
  for each row execute function set_updated_at();

-- ─── project_files ────────────────────────────────────────────────────────────
create table project_files (
  id                    uuid primary key default uuid_generate_v4(),
  project_id            uuid not null references projects(id) on delete restrict,
  file_name             text not null,
  file_type             text,
  extension             text,
  dropbox_path          text,
  supabase_storage_path text,
  hash_sha256           text,
  size_bytes            bigint,
  version               int not null default 1,
  uploaded_by           uuid references profiles(id),
  status                file_status not null default 'pendente',
  created_at            timestamptz not null default now()
);

comment on table project_files is 'Every file associated with a project. Raw files: Dropbox only. Light outputs: also Supabase Storage. Never delete raw files.';

create index project_files_project_id_idx on project_files(project_id);
create index project_files_extension_idx on project_files(extension);

-- ─── processing_jobs ──────────────────────────────────────────────────────────
create table processing_jobs (
  id             uuid primary key default uuid_generate_v4(),
  project_id     uuid not null references projects(id) on delete restrict,
  job_type       job_type not null,
  status         job_status not null default 'aguardando',
  tentativas     int not null default 0,
  started_at     timestamptz,
  finished_at    timestamptz,
  error_message  text,
  logs_path      text,
  worker_version text,
  created_at     timestamptz not null default now()
);

comment on table processing_jobs is 'Job queue polled by the worker. Worker updates status; never expose to frontend directly.';

create index processing_jobs_status_idx on processing_jobs(status, created_at);
create index processing_jobs_project_id_idx on processing_jobs(project_id);

-- ─── gpr_profiles ─────────────────────────────────────────────────────────────
create table gpr_profiles (
  id                    uuid primary key default uuid_generate_v4(),
  project_id            uuid not null references projects(id) on delete restrict,
  run_id                text not null,
  arquivo_dzt           text not null,
  n_tracos              int,
  n_amostras            int,
  profundidade_max_m    float,
  distancia_max_m       float,
  velocity_mns          float,
  velocity_calibrada    boolean default false,
  config_hash           text,
  dropbox_output_path   text,
  imagem_bruta_url      text,
  imagem_processada_url text,
  imagem_anotada_url    text,
  imagem_alta_conf_url  text,
  csv_alvos_url         text,
  status                text not null default 'processando',
  created_at            timestamptz not null default now()
);

create index gpr_profiles_project_id_idx on gpr_profiles(project_id);
create index gpr_profiles_run_id_idx on gpr_profiles(run_id);

-- ─── detected_targets ─────────────────────────────────────────────────────────
create table detected_targets (
  id                          uuid primary key default uuid_generate_v4(),
  project_id                  uuid not null references projects(id) on delete restrict,
  profile_id                  uuid not null references gpr_profiles(id) on delete restrict,
  arquivo_dzt                 text not null,
  run_id                      text not null,
  rank                        int,
  x_m                         float,
  depth_m                     float,
  diam_est_m                  float,
  diam_confianca              text,
  fit_ok                      boolean,
  tipo_material               text,
  confianca_tipo              text,
  evidencia_raw               boolean,
  evidencia_sem_agc           boolean,
  snr_local                   float,
  confidence_score            int,
  confidence_label_tecnico    text check (confidence_label_tecnico in ('alta', 'media', 'baixa')),
  confidence_label_relatorio  text check (confidence_label_relatorio in ('alta', 'baixa')),
  motivo_confianca            text,
  crop_url                    text,
  json_tecnico                jsonb,
  created_at                  timestamptz not null default now()
);

create index detected_targets_project_id_idx on detected_targets(project_id);
create index detected_targets_profile_id_idx on detected_targets(profile_id);
create index detected_targets_confidence_relatorio_idx on detected_targets(confidence_label_relatorio);

-- ─── ai_interpretations ───────────────────────────────────────────────────────
create table ai_interpretations (
  id                          uuid primary key default uuid_generate_v4(),
  target_id                   uuid not null references detected_targets(id) on delete restrict,
  ia_tipo_sugerido            text,
  ia_descricao                text,
  ia_justificativa_visual     text,
  ia_justificativa_tecnica    text,
  ia_confianca                text,
  ia_recomendacao             text,
  vai_para_planta_sugerido    boolean,
  vai_para_relatorio_sugerido boolean,
  observacoes                 text,
  raw_response_json           jsonb,
  model_usado                 text,
  tokens_usados               int,
  custo_usd                   float,
  created_at                  timestamptz not null default now()
);

create index ai_interpretations_target_id_idx on ai_interpretations(target_id);

-- ─── technical_reviews ────────────────────────────────────────────────────────
create table technical_reviews (
  id                    uuid primary key default uuid_generate_v4(),
  target_id             uuid not null references detected_targets(id) on delete restrict,
  status_review         review_status not null default 'pendente',
  tipo_final            text,
  profundidade_ajustada float,
  diametro_ajustado     float,
  vai_para_planta       boolean,
  vai_para_relatorio    boolean,
  observacao            text,
  reviewed_by           uuid references profiles(id),
  reviewed_at           timestamptz
);

create index technical_reviews_target_id_idx on technical_reviews(target_id);

-- ─── cartography_outputs ──────────────────────────────────────────────────────
create table cartography_outputs (
  id                uuid primary key default uuid_generate_v4(),
  project_id        uuid not null references projects(id) on delete restrict,
  output_type       output_type,
  dxf_dropbox_path  text,
  kml_dropbox_path  text,
  geojson_path      text,
  csv_path          text,
  dxf_storage_url   text,
  kml_storage_url   text,
  status            text not null default 'pendente',
  created_at        timestamptz not null default now()
);

create index cartography_outputs_project_id_idx on cartography_outputs(project_id);

-- ─── report_outputs ───────────────────────────────────────────────────────────
create table report_outputs (
  id                   uuid primary key default uuid_generate_v4(),
  project_id           uuid not null references projects(id) on delete restrict,
  version              int not null default 1,
  docx_dropbox_path    text,
  pdf_dropbox_path     text,
  pdf_storage_url      text,
  dados_usados_json    jsonb,
  status               text not null default 'gerando',
  generated_by         uuid references profiles(id),
  approved_by          uuid references profiles(id),
  created_at           timestamptz not null default now()
);

create index report_outputs_project_id_idx on report_outputs(project_id);

-- ─── audit_logs (append-only) ─────────────────────────────────────────────────
create table audit_logs (
  id            uuid primary key default uuid_generate_v4(),
  project_id    uuid references projects(id),
  user_id       uuid references profiles(id),
  action        text not null,
  entity_type   text,
  entity_id     uuid,
  metadata_json jsonb,
  ip_address    text,
  created_at    timestamptz not null default now()
);

comment on table audit_logs is 'Immutable audit trail. INSERT via service role only. No UPDATE or DELETE ever.';

create index audit_logs_project_id_idx on audit_logs(project_id);
create index audit_logs_user_id_idx on audit_logs(user_id);
create index audit_logs_created_at_idx on audit_logs(created_at desc);
