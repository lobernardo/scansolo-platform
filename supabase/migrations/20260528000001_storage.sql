-- Storage buckets for Fase 1B (Supabase Storage as temporary file store)
-- gpr-uploads : raw DZT files uploaded by operador_campo
-- gpr-images  : PNG outputs from pipeline (public read)
-- gpr-tabelas : CSV outputs from pipeline

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  (
    'gpr-uploads',
    'gpr-uploads',
    false,
    104857600,  -- 100 MB per file
    null        -- any mime type (DZT files have no standard mime)
  ),
  (
    'gpr-images',
    'gpr-images',
    true,
    10485760,   -- 10 MB per image
    array['image/png', 'image/jpeg']
  ),
  (
    'gpr-tabelas',
    'gpr-tabelas',
    false,
    5242880,    -- 5 MB per CSV
    array['text/csv', 'text/plain', 'application/csv']
  )
on conflict (id) do nothing;

-- ── RLS policies ────────────────────────────────────────────────────────────

-- gpr-uploads: operador_campo and above can upload; owner project check via path
-- Path convention: gpr-uploads/{project_id}/{filename}

create policy "upload_dzt_authenticated"
  on storage.objects
  for insert
  to authenticated
  with check (
    bucket_id = 'gpr-uploads'
    and auth.role() = 'authenticated'
  );

create policy "read_own_uploads"
  on storage.objects
  for select
  to authenticated
  using (
    bucket_id = 'gpr-uploads'
    and (
      -- socio/admin see all
      (auth_user_role() in ('socio', 'admin'))
      -- others see only files in projects they own
      or exists (
        select 1 from public.projects p
        where p.id::text = (string_to_array(name, '/'))[1]
          and (
            p.created_by = auth.uid()
            or p.assigned_to = auth.uid()
          )
      )
    )
  );

create policy "delete_own_uploads"
  on storage.objects
  for delete
  to authenticated
  using (
    bucket_id = 'gpr-uploads'
    and (
      (auth_user_role() in ('socio', 'admin'))
      or exists (
        select 1 from public.projects p
        where p.id::text = (string_to_array(name, '/'))[1]
          and p.created_by = auth.uid()
      )
    )
  );

-- gpr-images: public bucket — select is open, insert/delete only service role
create policy "public_read_gpr_images"
  on storage.objects
  for select
  to public
  using (bucket_id = 'gpr-images');

-- gpr-tabelas: authenticated users with project access can read
create policy "read_own_tabelas"
  on storage.objects
  for select
  to authenticated
  using (
    bucket_id = 'gpr-tabelas'
    and (
      (auth_user_role() in ('socio', 'admin'))
      or exists (
        select 1 from public.projects p
        where p.id::text = (string_to_array(name, '/'))[1]
          and (
            p.created_by = auth.uid()
            or p.assigned_to = auth.uid()
          )
      )
    )
  );
