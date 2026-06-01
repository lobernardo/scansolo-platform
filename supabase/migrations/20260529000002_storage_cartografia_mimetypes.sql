-- ═══════════════════════════════════════════════════════════════════════════
-- Fase 4+5: Ampliar allowed_mime_types do bucket gpr-tabelas
-- Fase 4: application/octet-stream (DXF), text/plain (GeoJSON/KML)
-- Fase 5: DOCX (relatório Word) + PDF (conversão LibreOffice)
-- ═══════════════════════════════════════════════════════════════════════════

update storage.buckets
set
  allowed_mime_types = array[
    'text/csv',
    'text/plain',
    'application/csv',
    'application/octet-stream',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/pdf'
  ],
  file_size_limit = 52428800  -- 50 MB
where id = 'gpr-tabelas';
