-- Fase 6: Configuração de filtros por projeto
-- Permite que a UI salve os parâmetros de processamento GPR escolhidos pelo usuário.

alter table projects
  add column if not exists processing_config jsonb;

comment on column projects.processing_config is
  'Configuração de filtros do pipeline GPR escolhida na UI de upload. '
  'Exemplo: {"filtros_ativos": {"dewow": true, "agc": true, "ia_imagem": false}, '
  '"bgremoval_traces": 30, "tpow_power": 0.5, "contrast": 2.5, "agc_window": 150}';
