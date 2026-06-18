# Worker Jobs — Referência Técnica
> Objetivo: Documentação de todos os job handlers do worker Python e do polling loop.
> Contexto: `services/worker/` — roda em Railway via `python worker_main.py`. Leia junto com [GPR_PIPELINE.md](GPR_PIPELINE.md).

---

## worker_main.py — polling loop

- Polling a cada `WORKER_POLL_INTERVAL_SECONDS` (default: 10s)
- Busca 1 job por vez em `processing_jobs` (status=`aguardando`, ordenado por `created_at`)
- Despacha por `job_type`:

| job_type | Handler | Descrição |
|---|---|---|
| `gpr` | `job_gpr.handle_gpr_job` | Roda pipeline_v1.py via subprocess |
| `ia` | `job_ia.handle_ia_job` | GPT-4o por alvo + `_interpretada_ia.png` |
| `ia_p2` | `job_ia.handle_ia_p2_job` | Anotações do detector sobre `imagem_preview_radan_5m` (sem nova chamada GPT-4o) |
| `cartografia` | `job_cartografia.handle_cartografia_job` | DXF + KML + GeoJSON + CSV |
| `relatorio` | `job_relatorio.handle_relatorio_job` | DOCX + PDF via LibreOffice |
| `inferencias` | `job_gpr.handle_inferencias_job` | Relatório `.txt` sob demanda (não altera status) |
| `interpretada` | `job_interpretada.handle_interpretada_job` | Imagem interpretada com alvos aprovados |
| `recalibrar` | `job_recalibrar.handle_recalibrar_job` | Otimiza thresholds via `gpr_ground_truth` (min 20 amostras) |
| `recalibrar_velocity` | `job_recalibrar_velocity.handle_recalibrar_velocity_job` | Recalcula profundidades com nova velocity |

---

## job_gpr.py

### Dois fluxos

1. **Job completo** (sem `payload.profile_id`): baixa todos DZTs do projeto → roda pipeline → persiste perfis + alvos + imagens (inclusive `imagem_preview_radan_5m_url`)
2. **Reprocessamento individual** (com `payload.profile_id`): reprocessa um único DZT com filtros customizados → não altera status do projeto, não cria job IA

### Flags e comportamento

**`skip_ia` flag:** `processing_config.skip_ia = true` → worker não cria job `ia` após o GPR concluir. Disponível na UI de Nova Entrada como checkbox.

**`--sem-ia-imagem` sempre ativo:** flag passada em toda execução do worker (job completo e reprocessamento) — `gpt-image-1` nunca roda via worker.

### Integração de presets (Fase 12)

`_get_processing_config` busca `projects.preset_id` → carrega `gpr_presets.parameters` → merge com `projects.processing_config` (projeto override ganha). O `--preset 270mhz` é passado como base ao subprocess; o merged dict é passado via `--filter-config` sobrescrevendo todos os campos do preset carregado do banco.

**Fase 15 — fix `_get_processing_config`:**
- Se `det_depth_min_m` estiver em `project_config` (configurado via Nova Entrada accordion), seta `merged["_det_depth_min_m_explicit"] = True` automaticamente

### `_filtros_to_pipeline_config` (Fase 15 — fixes)

Traduz `FilterState` do frontend para dict de parâmetros do pipeline:
- `velocity_mns` em `filtros_customizados` → `cfg["velocity_mns"]` (tem precedência sobre config do projeto)
- `det_depth_min_m` em `filtros_customizados` → seta `cfg["_det_depth_min_m_explicit"] = True` (impede pipeline de usar adaptativo do SNR gate)
- `filtros.bandpass = false` → `bandpass_low_mhz=0` (convenção para desativar no pipeline)

### pipeline metrics upload (Fase 11)

Após processamento de cada DZT, faz upload de `{stem}_pipeline_metrics.json` para `gpr-tabelas/{project_id}/{run_id}/{profile_id[:8]}/`:
- URL signed (10 anos) salva em `gpr_profiles.metricas_pipeline_url`
- `dzt_sha256` logado (não salvo em coluna separada ainda)
- Bloco em try/except — nunca aborta o job

### Relatório de inferências (sob demanda)

`gerar_relatorio_inferencias(df_campo, projeto, preset) -> str`
- Filtra `confidence_label_tecnico in ("alta", "media")`
- Colunas: Linha | # | Dist.(m) | P.Topo(m) | P.Eixo(m) | Diâm.(m) | Larg.(m) | Tam. | Material | Conf.
- `prof_topo_m` estimado como `depth_m − diam_est_m / 2` quando ausente no CSV
- Inclui legenda técnica e avisos de calibração de velocity no rodapé
- Upload para `gpr-tabelas/{project_id}/inferencias.txt` (upsert)
- **Não altera `project.status`** — job independente

---

## job_ia.py — handle_ia_job

1. Interpreta cada alvo via GPT-4o (prompt em inglês, resposta JSON com 10 campos)
2. Gera `_interpretada_ia.png` com labels `[tipo] [conf]%` sobrepostos
3. Salva URL em `gpr_profiles.imagem_interpretada_url`
4. Se `project.auto_accept_ia = true`: insere `technical_reviews` automaticamente (alta→planta+rel, média→só planta, baixa→descartado) → avança para `revisao_concluida`
5. Senão: avança para `ia_concluida` → aguarda revisão manual

**Categorias de tipo IA (prompt):** tubulacao_agua, tubulacao_gas, tubulacao_esgoto, cabo_eletrico, cabo_telecom, galeria_concreto, vazio_ar, rocha, inconclusivo

### GPT-4o com contexto do projeto (Fase 11)

`_build_system_prompt(project: dict)` injeta bloco PROJECT CONTEXT:
- `codigo_projeto`, `tipo_obra` (mapeado via `TIPO_OBRA_EN` para inglês), `area_m2`, `antena_freq_mhz`, `contato_nome`
- Reduz viés `galeria_concreto` ao dar contexto de tipo de obra ao modelo

**Observação de calibração (2026-06-09):** 13 imagens RADAN do Amilson (HELPAVPA) mostraram forte viés para `galeria_concreto` (~80% dos alvos). Provável causa: sem contexto do projeto, o modelo escolhe a categoria de maior diâmetro. Mitigação aplicada. Validar em produção.

---

## job_ia.py — handle_ia_p2_job (Fase 10)

Disparado por `requestIaP2(profileId)` via server action → job `ia_p2` em `processing_jobs`

1. Reusa resultados do job `ia` já existentes no perfil (sem nova chamada GPT-4o)
2. Baixa `imagem_preview_radan_5m_url` do Storage (`gpr-images`)
3. Usa `depth_preview_m` de `filtros_customizados` (ou 5.0 por padrão) como escala de profundidade
4. Desenha anotações do detector (rank / profundidade / diâmetro) no mesmo estilo de `plotar_deteccoes` — alvos fora da janela visível são silenciados
5. Upload → `gpr-images/{project_id}/{run_id}/{stem}_anotada_p2.png`
6. Salva URL em `gpr_profiles.imagem_interpretada_ia_p2_url`

**Frontend:** aba "IA Proc.2" visível quando Processada 2 + IA existem; botões "Interpretar Proc.2" / "Regenerar IA P2"

---

## job_interpretada.py (Fase 9)

Disparado por `finalizeReview` → job `interpretada` em `processing_jobs`

1. Busca perfis do projeto (run mais recente via `run_id`)
2. Para cada perfil: pega alvos aprovados (`technical_reviews.vai_para_relatorio=true`)
3. Baixa `_processada.png` do Storage (`gpr-images`)
4. Desenha marcadores coloridos por tipo em PT (círculo + label tipo/profundidade/diâmetro) → `_interpretada.png`
5. Upload para `gpr-images/{project_id}/{run_id}/{stem}_interpretada.png`
6. Atualiza `gpr_profiles.imagem_interpretada_url` + `imagem_interpretada_status = "pendente"`
7. Salva `ia_training_examples` com alvos aprovados

**Status do perfil** (`gpr_profiles.imagem_interpretada_status`):
- `pendente` — gerada, aguarda aprovação de Amilson
- `aprovado` — Amilson aprovou; será usada no relatório
- `regenerando` — nova rodada solicitada (novo job `interpretada`)
- `manual` — Amilson anotou diretamente no canvas

### Ground truth feeding (Fase 11)

Após `ia_training_examples`, faz upsert de cada alvo revisado em `gpr_ground_truth`:
- `e_falso_positivo = not vai_para_relatorio`
- `confianca_revisao` normalizada: `alta/media/baixa → certa/provavel/duvidosa`
- Upsert em `(profile_id, target_rank)` — idempotente
- Bloco em try/except — nunca aborta o job

---

## job_cartografia.py

Gera: DXF (camadas por tipo), KML (placemarks georreferenciados), GeoJSON, CSV de campo
Upload para `gpr-tabelas/{project_id}/`

---

## job_relatorio.py

Gera DOCX via python-docx + converte para PDF via LibreOffice (instalado no Dockerfile do Railway)
Upload para `gpr-tabelas/{project_id}/`

---

## job_recalibrar.py (Fase 11 + 13)

Disparado manualmente via botão em `/admin/qualidade` ou `/treinamento`.

1. Busca todos os rows de `gpr_ground_truth` (mínimo 20 amostras)
2. Usa `e_verdadeiro_positivo` diretamente; rows antigos têm backfill automático de `NOT e_falso_positivo`
3. **Score threshold (F1):** varre 10–90 (step=5), maximiza F1 = 2TP/(2TP+FP+FN)
4. **det_amp_threshold:** mediana(`amplitude_relativa_max` dos VP) − 0.1×IQR; requer ≥5 amostras
5. **det_depth_min_m:** se >5 FP com `depth_detector_m < 0.5m` → mediana + 0.05m; senão mantém 0.30
6. Salva candidato JSON em `gpr-tabelas/recalibracao/candidato_<ts>.json` com `aprovado: false`
7. **NÃO aplica thresholds automaticamente** — requer revisão manual (modal em `/treinamento`)

---

## job_recalibrar_velocity.py (Fase 12)

Disparado via painel "Calibrar velocity do solo" em `/projetos/[id]`.

1. Valida payload (`project_id`, `velocity_mns` obrigatórios; range 0.04–0.35)
2. Busca run mais recente do projeto; itera sobre perfis do run
3. Para cada perfil: reconstrói `twtt_max_ns = prof_antiga × 2 / velocity_antiga`; calcula `nova_profundidade = twtt_max_ns × nova_velocity / 2`; atualiza `gpr_profiles`
4. Atualiza `projects.processing_config` com nova velocity
5. Erros por perfil são logados e pulados — não aborta o job

---

## supabase_client.py — retry com backoff exponencial

`download_file(bucket, path)` e `upload_file(bucket, path, data, content_type)` fazem até 3 tentativas com backoff exponencial (1s, 2s, 4s). Loga cada retry via structlog (`download_file_retry` / `upload_file_retry`). Levanta a última exceção se todas as tentativas falharem.

---

## import_ground_truth.py (Fase 11)

`services/worker/scripts/import_ground_truth.py` — importação batch de CSV para `gpr_ground_truth`.

- Lê CSV com colunas: `profile_id`, `target_rank`, `e_falso_positivo`, `depth_m`, `amplitude_relativa_max`, `confianca_revisao`, `notas`
- `confianca_revisao` aceita `certa/provavel/duvidosa` ou `alta/media/baixa` (normalizado automaticamente)
- Upsert em `(profile_id, target_rank)` — idempotente
- Uso: `python scripts/import_ground_truth.py --csv <arquivo.csv> --project <project_id>`
- Template em `KB_ScansoloPlataform/GROUND_TRUTH/template_validacao.csv`

---

## parse_dzx.py (Fase 11)

`services/worker/pipeline/parse_dzx.py` — parser stdlib-only para arquivos `.DZX` (GSSI).

- `parse_dzx(path) -> dict` — nunca levanta exceção
- Suporta variantes de tag SIR-4000/SIR-30 (ex: `Latitude|LAT|lat|Y`)
- Containers suportados: `<Marks>`, `<GPS>`, `<GpsData>`, raiz
- Deduplicação por `TraceNumber`
- `haversine_m()` para distância entre primeiro e último mark GPS
- Campos escalares → `index_projeto.csv`; `dzx_marks` lista completa → `pipeline_metrics.json` apenas
