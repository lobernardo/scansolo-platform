-- Fase 8.16B: job leve de preflight DZT-first
--
-- Adiciona o job_type 'preflight' para o job leve que lê metadados do DZT
-- antes do processamento pesado GPR, sem gerar imagens.
--
-- Adiciona status de projeto para o fluxo DZT-first:
--   aguardando_preflight   : job preflight inserido, aguardando processamento pelo worker
--   aguardando_confirmacao : preflight concluído, aguardando confirmação do usuário na UI
--
-- Idempotente: IF NOT EXISTS previne erro em reaplicação.
-- Já aplicado ao banco remoto via MCP Supabase em 2026-06-22.

ALTER TYPE job_type ADD VALUE IF NOT EXISTS 'preflight';

ALTER TYPE project_status ADD VALUE IF NOT EXISTS 'aguardando_preflight';
ALTER TYPE project_status ADD VALUE IF NOT EXISTS 'aguardando_confirmacao';
