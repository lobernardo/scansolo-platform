-- Fix: adiciona 'media' ao check constraint de confidence_label_relatorio
-- O constraint original só aceitava ('alta', 'baixa'), excluindo 'media'.
-- O pipeline gera 'media' como valor válido para alvos de confiança intermediária.

alter table detected_targets
  drop constraint if exists detected_targets_confidence_label_relatorio_check;

alter table detected_targets
  add constraint detected_targets_confidence_label_relatorio_check
  check (confidence_label_relatorio in ('alta', 'media', 'baixa'));
