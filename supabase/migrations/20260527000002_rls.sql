-- ═══════════════════════════════════════════════════════════════════════════
-- ScanSOLO Platform — Row Level Security (Phase 0)
-- Migration: 20260527000002_rls
-- ═══════════════════════════════════════════════════════════════════════════

-- Helper: get current user's role from profiles
create or replace function auth_user_role()
returns user_role
language sql
stable
security definer
set search_path = public
as $$
  select role from profiles where id = auth.uid()
$$;

-- ─── profiles ─────────────────────────────────────────────────────────────────
alter table profiles enable row level security;

-- Users can read their own profile; admin/socio can read all
create policy "profiles_select_own"
  on profiles for select
  using (
    id = auth.uid()
    or auth_user_role() in ('socio', 'admin')
  );

-- Users can update their own profile (name only — role managed by admin)
create policy "profiles_update_own"
  on profiles for update
  using (id = auth.uid());

-- Only admin inserts profiles (via service role on signup trigger)
create policy "profiles_insert_admin"
  on profiles for insert
  with check (auth_user_role() = 'admin' or auth.uid() = id);

-- ─── projects ─────────────────────────────────────────────────────────────────
alter table projects enable row level security;

-- operador_campo: only their own projects
-- tecnico: projects assigned to them
-- socio/admin: all projects
create policy "projects_select"
  on projects for select
  using (
    auth_user_role() in ('socio', 'admin')
    or (auth_user_role() = 'tecnico' and assigned_to = auth.uid())
    or (auth_user_role() = 'operador_campo' and created_by = auth.uid())
  );

create policy "projects_insert"
  on projects for insert
  with check (
    auth_user_role() in ('socio', 'admin', 'operador_campo')
    and created_by = auth.uid()
  );

-- operador_campo cannot update projects (only socio/admin/tecnico on assigned)
create policy "projects_update"
  on projects for update
  using (
    auth_user_role() in ('socio', 'admin')
    or (auth_user_role() = 'tecnico' and assigned_to = auth.uid())
  );

-- Only admin can delete projects (and only soft-delete in practice)
create policy "projects_delete"
  on projects for delete
  using (auth_user_role() = 'admin');

-- ─── project_files ────────────────────────────────────────────────────────────
alter table project_files enable row level security;

-- Inherit project access: if you can see the project, you can see its files
create policy "project_files_select"
  on project_files for select
  using (
    exists (
      select 1 from projects p
      where p.id = project_id
      and (
        auth_user_role() in ('socio', 'admin')
        or (auth_user_role() = 'tecnico' and p.assigned_to = auth.uid())
        or (auth_user_role() = 'operador_campo' and p.created_by = auth.uid())
      )
    )
  );

-- operador_campo can insert files for projects they created
create policy "project_files_insert"
  on project_files for insert
  with check (
    exists (
      select 1 from projects p
      where p.id = project_id
      and (
        auth_user_role() in ('socio', 'admin')
        or (auth_user_role() = 'operador_campo' and p.created_by = auth.uid())
      )
    )
  );

-- Only socio/admin update file records (e.g., confirming upload)
create policy "project_files_update"
  on project_files for update
  using (auth_user_role() in ('socio', 'admin'));

-- ─── processing_jobs ──────────────────────────────────────────────────────────
alter table processing_jobs enable row level security;

-- Frontend reads job status; worker uses service role (bypasses RLS)
create policy "processing_jobs_select"
  on processing_jobs for select
  using (
    auth_user_role() in ('socio', 'admin')
    or (
      auth_user_role() = 'tecnico'
      and exists (
        select 1 from projects p
        where p.id = project_id and p.assigned_to = auth.uid()
      )
    )
  );

-- Only socio/admin can create jobs from frontend (worker uses service role)
create policy "processing_jobs_insert"
  on processing_jobs for insert
  with check (auth_user_role() in ('socio', 'admin'));

-- ─── gpr_profiles ─────────────────────────────────────────────────────────────
alter table gpr_profiles enable row level security;

create policy "gpr_profiles_select"
  on gpr_profiles for select
  using (
    auth_user_role() in ('socio', 'admin')
    or (
      auth_user_role() = 'tecnico'
      and exists (
        select 1 from projects p
        where p.id = project_id and p.assigned_to = auth.uid()
      )
    )
  );

-- Only worker (service role) inserts gpr_profiles
-- No frontend insert policy needed

-- ─── detected_targets ─────────────────────────────────────────────────────────
alter table detected_targets enable row level security;

create policy "detected_targets_select"
  on detected_targets for select
  using (
    auth_user_role() in ('socio', 'admin')
    or (
      auth_user_role() = 'tecnico'
      and exists (
        select 1 from projects p
        where p.id = project_id and p.assigned_to = auth.uid()
      )
    )
  );

-- operador_campo cannot see detected_targets (ADR-017)
-- Worker inserts via service role

-- ─── ai_interpretations ───────────────────────────────────────────────────────
alter table ai_interpretations enable row level security;

create policy "ai_interpretations_select"
  on ai_interpretations for select
  using (
    auth_user_role() in ('socio', 'admin', 'tecnico')
    and exists (
      select 1 from detected_targets dt
      join projects p on p.id = dt.project_id
      where dt.id = target_id
      and (
        auth_user_role() in ('socio', 'admin')
        or (auth_user_role() = 'tecnico' and p.assigned_to = auth.uid())
      )
    )
  );

-- Worker inserts via service role

-- ─── technical_reviews ────────────────────────────────────────────────────────
alter table technical_reviews enable row level security;

create policy "technical_reviews_select"
  on technical_reviews for select
  using (
    auth_user_role() in ('socio', 'admin', 'tecnico')
  );

create policy "technical_reviews_insert"
  on technical_reviews for insert
  with check (auth_user_role() in ('socio', 'admin', 'tecnico'));

create policy "technical_reviews_update"
  on technical_reviews for update
  using (auth_user_role() in ('socio', 'admin', 'tecnico'));

-- ─── cartography_outputs ──────────────────────────────────────────────────────
alter table cartography_outputs enable row level security;

create policy "cartography_outputs_select"
  on cartography_outputs for select
  using (auth_user_role() in ('socio', 'admin', 'tecnico'));

create policy "cartography_outputs_insert"
  on cartography_outputs for insert
  with check (auth_user_role() in ('socio', 'admin'));

-- ─── report_outputs ───────────────────────────────────────────────────────────
alter table report_outputs enable row level security;

create policy "report_outputs_select"
  on report_outputs for select
  using (auth_user_role() in ('socio', 'admin'));

create policy "report_outputs_insert"
  on report_outputs for insert
  with check (auth_user_role() in ('socio', 'admin'));

-- ─── audit_logs ───────────────────────────────────────────────────────────────
alter table audit_logs enable row level security;

-- Any authenticated user can insert audit events (action tracing)
create policy "audit_logs_insert"
  on audit_logs for insert
  with check (auth.uid() is not null);

-- Only socio/admin can read audit logs
create policy "audit_logs_select"
  on audit_logs for select
  using (auth_user_role() in ('socio', 'admin'));

-- No UPDATE or DELETE ever (append-only table)

-- ─── Supabase Auth trigger: create profile on signup ─────────────────────────
create or replace function handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into profiles (id, name, email, role)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', split_part(new.email, '@', 1)),
    new.email,
    coalesce((new.raw_user_meta_data->>'role')::user_role, 'operador_campo')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();
