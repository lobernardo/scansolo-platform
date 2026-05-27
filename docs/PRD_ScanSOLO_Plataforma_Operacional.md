# PRD — Plataforma Operacional ScanSOLO
**Versão:** 1.0  
**Data:** 2026-05-27  
**Status:** Aprovado para implementação — Fase 0  

---

## 1. VISÃO DO PRODUTO

Uma plataforma web operacional que automatiza o fluxo completo de trabalho da ScanSOLO: desde o recebimento dos dados de campo até a entrega do relatório técnico ao cliente.

O operador de campo envia os dados. O sistema processa, interpreta com IA, organiza e prepara os entregáveis. Os sócios revisam quando quiserem e aprovam a entrega. Amilson foca em interpretação técnica de casos complexos, não em trabalho operacional repetitivo.

**Princípio central:** O dado bruto nunca se perde. O processamento é automático. A IA gera a interpretação operacional padrão. Revisão humana é disponível para controle, exceções, ajustes e aprovação final — não é obrigatória, não é gargalo.

---

## 2. PROBLEMA OPERACIONAL

### Situação atual
- Processamento GPR 100% manual via Radan (~1 min por imagem, centralizado em Amilson)
- Interpretação manual de radargramas (detecção de hipérboles, profundidade, diâmetro, tipo)
- Geração de relatório manual (template preenchido a mão por Marcos)
- Risco recorrente de perda de dados em campo (memória cheia, esquecimento)
- Processo não escala: tudo depende de uma pessoa (Amilson) e uma máquina (com Radan instalado)

### Meta declarada por Marcos
> "Deixar 90% do processamento encaminhado, não eliminar 100% do processo humano."

### O que esta plataforma resolve
- Processa qualquer volume de .DZT automaticamente, sem Radan, sem Amilson manual
- Garante que nenhum arquivo bruto se perde (Dropbox como cofre)
- IA gera a interpretação operacional padrão de cada alvo com contexto técnico completo antes do relatório
- Sócios controlam revisão e aprovação sem depender de Amilson para tudo
- Entregáveis (DXF, KML, relatório) gerados automaticamente quando os dados forem suficientes

---

## 3. OBJETIVOS

| # | Objetivo | Métrica de sucesso |
|---|---|---|
| O1 | Eliminar processamento manual de .DZT via Radan | 100% dos projetos processados pelo pipeline Python |
| O2 | Garantir backup confiável de todos os arquivos brutos | Hash confirmado para 100% dos .DZT recebidos |
| O3 | IA gera interpretação operacional padrão de todos os alvos antes do relatório | IA roda automaticamente em 100% dos projetos com .DZT |
| O4 | Reduzir tempo de entrega do relatório | De dias para horas (após calibração e aprovação dos sócios) |
| O5 | Escalar processamento sem aumentar headcount técnico | Amilson valida apenas casos complexos |
| O6 | Rastreabilidade completa | Todo estado de todo projeto auditável no sistema |

---

## 4. PERSONAS E PERMISSÕES

### Operador de Campo
**Quem é:** Técnico de campo. Coleta dados com GPR e Pipe Locator. Nem sempre tem acesso a computador bom ou conexão estável.

**Pode:**
- Acessar tela "Nova Entrada"
- Preencher formulário inicial do projeto
- Fazer upload de arquivos (.DZT, .DZG, .KML, fotos, etc.)
- Ver resumo do que foi recebido
- Confirmar arquivos recebidos
- Ver status básico: "backup confirmado" ou "backup pendente"

**Não pode ver:**
- Dashboard geral de projetos
- Resultados técnicos de nenhum projeto
- Interpretações da IA
- Tela de revisão técnica
- Geração de relatório
- Projetos de outros operadores
- Qualquer configuração do sistema

### Sócio / Admin
**Quem é:** Marcos e outros sócios. Gestão geral, aprovação de entregas.

**Pode:** tudo.

### Técnico / Intérprete (perfil opcional, se existir)
**Quem é:** Amilson ou técnico designado para revisão técnica.

**Pode:**
- Ver projetos atribuídos a ele
- Ver imagens e candidatos detectados
- Ver interpretação da IA
- Validar, descartar ou ajustar alvos (tipo, profundidade, diâmetro)
- Marcar vai_para_planta e vai_para_relatorio
- Adicionar observações técnicas
- Marcar revisão concluída

**Não pode:** aprovar entrega final, gerar relatório, gerenciar usuários.

---

## 5. FLUXO COMPLETO PONTA A PONTA

```
[Campo] → Nova Entrada / Dropbox direto
    ↓
[Sistema] → Confirma arquivos + checksum + manifest
    ↓
[Sistema] → Cria pasta Dropbox + registra no Supabase
    ↓
[Worker] → Processamento GPR (pipeline_v1.py)
    ↓
[Worker] → IA automática (OpenAI GPT-4o)
    ↓
[Sócio] → Vê resultados → decide revisar ou aceitar IA
    ↓
[Worker] → Cartografia (DXF / KML / GeoJSON)
    ↓
[Sócio] → Configura e gera relatório
    ↓
[Sócio] → Aprova e entrega ao cliente
```

---

## 6. FLUXO NOVA ENTRADA

1. Sócio ou operador clica "Nova Entrada"
2. Preenche formulário:
   - Cliente, local, estado, data do levantamento
   - Responsável de campo, responsável técnico (opcional)
   - Tipo de serviço, equipamento GPR, antena/frequência
   - Pipe Locator usado? (sim / não / não sei)
   - Tem .DZG? .KML/.KMZ? .DWG/.DXF?
   - Saída desejada: AutoCAD / Google Earth / Ambos / Decidir depois
   - Observações de campo
   - Prioridade, prazo desejado
   - Código interno (opcional — ex.: PT-GPR-SOL-036)
3. Sistema gera nome do projeto: `projeto_{nomecliente}_{estado}_{data}`
   - Exemplo: `projeto_ternium_rj_2026-05-20`
   - Código interno vai como campo adicional, não muda o padrão de nome
4. Sistema cria:
   - Registro em Supabase (status: `criado`)
   - Pasta no Dropbox com estrutura padrão
   - `project_manifest.json` inicial
5. Operador prossegue para upload (ou sócio finaliza e aguarda Fluxo B)

**Importante:** Todos os campos do formulário são editáveis depois pelos sócios. O formulário inicial captura o essencial — o resto pode ser preenchido ao longo do processo.

---

## 7. FLUXO A — UPLOAD PELO SISTEMA

1. Após Nova Entrada, operador vê tela de upload
2. Pode arrastar e soltar ou selecionar arquivos
3. Sistema aceita: `.DZT`, `.DZG`, `.KML`, `.KMZ`, `.DWG`, `.DXF`, `.jpg`, `.jpeg`, `.png`, `.pdf`, `.xlsx`, `.csv`, qualquer outro
4. Para cada arquivo:
   - Calcula SHA-256
   - Registra metadados em `project_files` (nome, tipo, extensão, tamanho, hash, usuário)
   - Envia para Dropbox em `00_Entrada/{tipo}/`
   - Marca status: `confirmado`
5. Sistema mostra progresso de cada arquivo
6. Operador pode adicionar mais arquivos ou prosseguir
7. Operador clica "Confirmar — estes são todos os arquivos"
8. Status do projeto → `aguardando_confirmacao_operador` → `backup_confirmado`
9. Operador vê tela final: "✓ X arquivos recebidos e protegidos no backup"

---

## 8. FLUXO B — OPERADOR JÁ JOGOU DIRETO NO DROPBOX

**Cenário:** Operador de campo já usa Dropbox hoje. Joga os arquivos direto na pasta, como sempre fez. A plataforma deve ser capaz de assimilar isso.

**Duas sub-opções:**

### B1 — Acionamento manual pelo sócio (padrão inicial)
1. Sócio acessa o projeto no sistema (já criado via Nova Entrada ou criado retroativamente)
2. Clica em "Sincronizar com Dropbox"
3. Sistema lê a pasta `00_Entrada/` do Dropbox para esse projeto
4. Para cada arquivo encontrado que ainda não está registrado:
   - Calcula SHA-256
   - Registra em `project_files`
   - Marca como `confirmado`
5. Sistema exibe resumo do que foi encontrado
6. Sócio confirma ou ajusta
7. Status avança para `backup_confirmado` após confirmação

### B2 — Webhook Dropbox (fase futura)
- Dropbox notifica o sistema quando há alterações na pasta do projeto
- Worker processa automaticamente sem intervenção manual
- Implementar após B1 estar estável

**Decisão pendente P4:** Confirmar se começamos com B1 (acionamento manual) ou preparamos B2 (webhook) desde o início.

---

## 9. FLUXO BACKUP / MANIFESTO / CHECKSUM

1. Ao receber qualquer arquivo (Fluxo A ou B):
   - Calcular SHA-256
   - Verificar se hash já existe para esse projeto (detecta duplicata)
   - Registrar em `project_files`: nome, tipo, extensão, tamanho, hash, dropbox_path, versão, usuário, data
2. Gerar/atualizar `project_manifest.json` na raiz do projeto no Dropbox:
   ```json
   {
     "projeto": "projeto_ternium_rj_2026-05-20",
     "arquivos": [
       {"nome": "linha_001.DZT", "hash": "abc123...", "tamanho": 2458600, "recebido_em": "2026-05-20T14:30:00Z"}
     ],
     "status_backup": "confirmado",
     "confirmado_por": "operador@scansolo.com.br",
     "confirmado_em": "2026-05-20T14:35:00Z"
   }
   ```
3. Regras absolutas:
   - NUNCA apagar arquivo bruto — apenas versionar
   - Novo upload do mesmo nome → incrementa versão, preserva anterior
   - Se hash divergir → alerta no sistema

---

## 10. FLUXO PROCESSAMENTO GPR

**Trigger:** status do projeto muda para `backup_confirmado` e há pelo menos 1 arquivo `.DZT`

1. Sistema cria `processing_jobs` com `job_type='gpr'`, `status='aguardando'`
2. Worker detecta o job (polling a cada 10s)
3. Worker atualiza status → `processando_gpr`
4. Worker baixa todos os `.DZT` do Dropbox para `/tmp/projeto_X/DZT/`
5. Worker executa: `python pipeline_v1.py --input /tmp/.../DZT --output /tmp/.../saida --preset 270mhz`
6. Pipeline gera outputs em `/tmp/saida/`:
   - 4 imagens por .DZT (bruta, processada, anotada_completa, anotada_alta_confianca)
   - 4 matrizes .npy por .DZT (raw, sem_agc, visual, processado)
   - CSV de alvos (23 colunas) por .DZT
   - `index_projeto.csv` (42 colunas)
   - `config_used.json`
7. Worker lê resultados e grava no Supabase:
   - Um `gpr_profiles` por .DZT
   - Um `detected_targets` por alvo detectado
8. Worker faz upload dos outputs para:
   - Supabase Storage: imagens, CSV (para visualização rápida no front-end)
   - Dropbox `01_Processamento_GPR/run_001_{data}_{hash}/`: saída completa
9. Worker atualiza status → `gpr_concluido`
10. Worker cria novo job: `job_type='ia'`
11. Worker limpa `/tmp/projeto_X/`

**Versionamento:** Cada execução gera `run_001`, `run_002`, etc. Reprocessamento não sobrescreve run anterior.

---

## 11. FLUXO IA AUTOMÁTICA

**Trigger:** job `job_type='ia'` criado após GPR concluído. IA **sempre** roda — não é opcional.

1. Worker atualiza status → `processando_ia`
2. Para cada alvo em `detected_targets`:
   a. Gera crop da imagem centrado no alvo (±1.5m em torno de x_m, ±0.8m de profundidade)
   b. Monta contexto técnico JSON por alvo (todos os campos do CSV + dados do projeto)
   c. Baixa imagem processada do alvo do Supabase Storage
3. Chama OpenAI GPT-4o com:
   - System prompt: contexto da empresa, padrões técnicos da ScanSOLO
   - User content: contexto JSON do alvo + crop + trecho do radargrama
4. Recebe resposta estruturada:
   - `ia_tipo_sugerido`, `ia_descricao`, `ia_justificativa_visual`, `ia_justificativa_tecnica`
   - `ia_confianca`, `ia_recomendacao`
   - `vai_para_planta_sugerido`, `vai_para_relatorio_sugerido`
   - `observacoes`, `raw_response_json`
5. Grava `ai_interpretations` no Supabase
6. Faz upload dos crops para Supabase Storage
7. Faz upload de `02_IA_Interpretacao/` para Dropbox
8. Atualiza status → `ia_concluida`

**Tratamento de falha:**
- Se OpenAI falhar para um alvo → tenta 3x com backoff
- Se falhar para todos → status `ia_pendente_erro`, sócio pode reprocessar IA
- Nunca bloqueia resultados GPR já gravados

**Modelo inicial:** `gpt-4o` para máxima qualidade. Custo estimado: R$0,15–0,45 por projeto (10–30 alvos). Migrar para `gpt-4o-mini` se custo for relevante.

---

## 12. FLUXO REVISÃO OPCIONAL

Após IA concluída, sócio escolhe uma das opções:

| Opção | Descrição |
|---|---|
| Aceitar IA | Aceita todas as sugestões sem revisão manual |
| Revisar alta confiança | Revisão apenas dos alvos com `confidence_label_relatorio = alta` |
| Revisar todos | Revisão de todos os candidatos |

**Interface de revisão (por alvo):**
- Ver: imagem do radargrama, crop do alvo, dados técnicos, sugestão da IA
- Editar: tipo_final, profundidade_ajustada, diâmetro_ajustado, observação
- Marcar: vai_para_planta (sim/não), vai_para_relatorio (sim/não), validado/descartado
- Resultado gravado em `technical_reviews`

**Relatório final pode ser gerado:**
- Com revisão concluída (usa `technical_reviews`)
- Sem revisão manual (usa interpretação operacional padrão da IA diretamente, com marcação "não revisado manualmente")
- O sócio escolhe — não há bloqueio automático

---

## 13. FLUXO CARTOGRAFIA

**Regra de decisão (em ordem):**

1. Campo `saida_desejada` no cadastro do projeto (prioridade máxima)
2. Fallback automático:
   - Recebeu `.DWG` ou `.DXF` → sugerir AutoCAD
   - Recebeu `.KML`/`.KMZ` ou `.DZG` → sugerir Google Earth
   - Recebeu ambos → sugerir Ambos
   - Não recebeu nenhum → pedir escolha do sócio e/ou `mapa_linhas.csv`
3. Sócio confirma ou altera antes de gerar

**O objetivo final é substituição completa do trabalho manual de montagem de planta/croqui**, não apenas alimentar o fluxo atual. A integração com o fluxo atual do Amilson é apenas etapa de compatibilidade e validação — não é o destino final. O sistema deve gerar:

- **DXF final:** layers por tipo de material (metálico/não-metálico/galeria), cores padrão ScanSOLO, textos com profundidade e diâmetro, símbolos, legenda. Compatível com AutoCAD.
- **KML/KMZ final:** pontos e linhas com descrições, estilos de cores por tipo, para Google Earth
- **GeoJSON:** formato aberto para reuso
- **CSV cartográfico:** tabela de alvos com coordenadas para importação

**Fase de mapeamento (antes da implementação da Fase 4):**
Antes de implementar a geração automática, mapear com Amilson:
- Exemplo de DXF/DWG final atual → padrão de layers, cores, símbolos
- Exemplo de KML/KMZ atual → padrão de estilos
- Como profundidade e diâmetro aparecem nos textos e etiquetas
- Como a planta/croqui é anexada ao relatório

A integração com o programa atual do Amilson é **validação de compatibilidade**, não objetivo final.

**Outputs gravados em:**
- Supabase: `cartography_outputs`
- Dropbox: `04_Cartografia/`
- Supabase Storage: KML e CSV (para download rápido)

---

## 14. FLUXO RELATÓRIO

**Trigger:** Sócio clica "Gerar Relatório" (após cartografia concluída ou com pendência registrada)

**Antes de gerar, sócio pode:**
- Editar dados iniciais do projeto (cliente, endereço, data, escopo)
- Inserir informações extras (condições de campo, metodologia específica, recomendações)
- Selecionar imagens para incluir no relatório
- Selecionar fotos de campo
- Escolher/confirmar saída cartográfica (AutoCAD ou Google Earth)
- Editar texto de conclusão
- Escolher usar IA sem revisão manual ou exigir revisão

**O relatório é gerado com:**
- Template padronizado (baseado no modelo Ternium SOL-0036)
- Dados do projeto (fixos e editáveis)
- Alvos aceitos/revisados com profundidade, diâmetro, tipo
- Imagens dos radargramas selecionadas
- Planta/croqui cartográfico
- Fotos de campo
- Tabela de interferências detectadas
- Conclusão

**Outputs:**
- `05_Relatorio/relatorio_vX.docx` no Dropbox
- `05_Relatorio/relatorio_vX.pdf` no Dropbox
- PDF disponível no Supabase Storage para download rápido
- `dados_relatorio_usados.json` (rastreabilidade do que foi usado)

**Versionamento:** cada nova geração cria v1, v2, v3. Versão aprovada vai para `06_Entrega_Cliente/`.

**Decisão pendente P6:** Template oficial de relatório precisa ser mapeado (dados fixos vs. variáveis vs. imagens vs. tabelas vs. planta vs. conclusão).

---

## 15. ESTRUTURA DE PASTAS DROPBOX

```
ScanSOLO_Projetos/
└── 2026/
    └── projeto_ternium_rj_2026-05-20/
        ├── 00_Entrada/
        │   ├── DZT/              ← arquivos brutos georadar (NUNCA apagar)
        │   ├── DZG/              ← GPS do georadar
        │   ├── KML_KMZ/         ← georreferenciamento de campo
        │   ├── DWG_DXF/         ← planta base do cliente
        │   ├── Fotos_Campo/     ← fotos da equipe e do local
        │   ├── PipeLocator/     ← dados Pipe Locator
        │   └── Observacoes/     ← notas, PDFs, planilhas, anexos
        │
        ├── 01_Processamento_GPR/
        │   ├── run_001_2026-05-20_889b717c/
        │   │   ├── imagens_brutas/
        │   │   ├── imagens_processadas/
        │   │   ├── imagens_anotadas/
        │   │   ├── dados_numpy/
        │   │   ├── tabela_alvos.csv
        │   │   ├── index_projeto.csv
        │   │   └── config_used.json
        │   └── run_002_2026-06-01_abc12345/  ← se reprocessado
        │
        ├── 02_IA_Interpretacao/
        │   ├── run_001/
        │   │   ├── crops/
        │   │   ├── json_por_alvo/
        │   │   └── ia_resultado_geral.json
        │   └── run_002/
        │
        ├── 03_Revisao_Tecnica/
        │   └── revisao_final.json
        │
        ├── 04_Cartografia/
        │   ├── alvos_cartografia.csv
        │   ├── alvos_cartografia.kml
        │   ├── alvos_cartografia.geojson
        │   └── alvos_cartografia.dxf
        │
        ├── 05_Relatorio/
        │   ├── relatorio_v1.docx
        │   ├── relatorio_v1.pdf
        │   └── dados_relatorio_usados.json
        │
        ├── 06_Entrega_Cliente/
        │   └── relatorio_final_aprovado.pdf
        │
        ├── 99_Logs/
        │
        └── project_manifest.json
```

**Nome do projeto:** `projeto_{nomecliente}_{estado}_{data}`

> **Código interno opcional:** se o projeto tiver um código de obra ou OS, ele entra como campo adicional no banco de dados (`codigo_interno`) e pode ser usado como sufixo legível no Dropbox, mas **não substitui** o padrão de nomenclatura principal. Exemplo com sufixo: `projeto_ternium_rj_2026-05-20_os1234`. O padrão sem sufixo continua sendo o identificador primário.
Código interno (ex.: `PT-GPR-SOL-036`) é campo adicional no manifest e no Supabase.

---

## 16. SUPABASE: MODELO DE DADOS

### users
```
id uuid PK | name text | email text | role text | active boolean | created_at
role: 'operador_campo' | 'tecnico' | 'socio' | 'admin'
```

### projects
```
id uuid PK | nome text UNIQUE | cliente text | local text | estado text
endereco text | data_levantamento date | codigo_interno text
tipo_servico text | equipamento_gpr text | antena_freq_mhz int
tem_pipe_locator boolean | tem_dzg boolean | tem_kml boolean | tem_dwg boolean
saida_desejada text | observacoes text | prioridade text | prazo_desejado date
status text | dropbox_project_path text
created_by uuid→users | assigned_to uuid→users
created_at | updated_at
```

### project_files
```
id uuid PK | project_id→projects | file_name text | file_type text
extension text | dropbox_path text | supabase_storage_path text
hash_sha256 text | size_bytes bigint | version int DEFAULT 1
uploaded_by→users | status text | created_at
```

### processing_jobs
```
id uuid PK | project_id→projects | job_type text | status text
tentativas int | started_at | finished_at | error_message text
logs_path text | worker_version text | created_at
job_type: 'gpr' | 'ia' | 'cartografia' | 'relatorio'
```

### gpr_profiles
```
id uuid PK | project_id→projects | run_id text (run_001, run_002...)
arquivo_dzt text | n_tracos int | n_amostras int
profundidade_max_m float | distancia_max_m float
velocity_mns float | velocity_calibrada boolean | config_hash text
dropbox_output_path text
imagem_bruta_url text | imagem_processada_url text
imagem_anotada_url text | imagem_alta_conf_url text | csv_alvos_url text
status text | created_at
```

### detected_targets
```
id uuid PK | project_id→projects | profile_id→gpr_profiles
arquivo_dzt text | run_id text | rank int
x_m float | depth_m float | diam_est_m float | diam_confianca text
fit_ok boolean | tipo_material text | confianca_tipo text
evidencia_raw boolean | evidencia_sem_agc boolean | snr_local float
confidence_score int | confidence_label_tecnico text
confidence_label_relatorio text | motivo_confianca text
crop_url text | json_tecnico jsonb | created_at
```

### ai_interpretations
```
id uuid PK | target_id→detected_targets
ia_tipo_sugerido text | ia_descricao text
ia_justificativa_visual text | ia_justificativa_tecnica text
ia_confianca text | ia_recomendacao text
vai_para_planta_sugerido boolean | vai_para_relatorio_sugerido boolean
observacoes text | raw_response_json jsonb
model_usado text | tokens_usados int | custo_usd float
created_at
```

### technical_reviews
```
id uuid PK | target_id→detected_targets
status_review text | tipo_final text
profundidade_ajustada float | diametro_ajustado float
vai_para_planta boolean | vai_para_relatorio boolean
observacao text | reviewed_by→users | reviewed_at
```

### cartography_outputs
```
id uuid PK | project_id→projects | output_type text
dxf_dropbox_path text | kml_dropbox_path text
geojson_path text | csv_path text
dxf_storage_url text | kml_storage_url text
status text | created_at
```

### report_outputs
```
id uuid PK | project_id→projects | version int
docx_dropbox_path text | pdf_dropbox_path text | pdf_storage_url text
dados_usados_json jsonb | status text
generated_by→users | approved_by→users | created_at
```

### audit_logs (append-only)
```
id uuid PK | project_id→projects | user_id→users
action text | entity_type text | entity_id uuid
metadata_json jsonb | ip_address text | created_at
```

---

## 17. SUPABASE STORAGE: O QUE GUARDAR E O QUE NÃO GUARDAR

### Vai para Supabase Storage

> **Papel do Supabase Storage:** é a camada de visualização, download e busca para outputs leves. **Não é a fonte da verdade** do projeto. A fonte da verdade dos arquivos brutos e da pasta completa do projeto é o **Dropbox**. Se houver divergência entre Supabase Storage e Dropbox, o Dropbox prevalece.

| Arquivo | Bucket | Motivo |
|---|---|---|
| `_bruta.png` | `gpr-images` | Visualização no dashboard |
| `_processada.png` | `gpr-images` | Visualização no dashboard |
| `_anotada_completa.png` | `gpr-images` | Visualização no dashboard |
| `_anotada_alta_confianca.png` | `gpr-images` | Visualização no dashboard |
| `crop_alvo_XXX.png` | `crops` | Tela de revisão por alvo |
| `_alvos.csv` | `tabelas` | Download rápido pelo sócio |
| `relatorio_vX.pdf` | `relatorios` | Download pelo sócio/cliente |
| `alvos_cartografia.kml` | `cartografia` | Download rápido |
| Thumbnails | `thumbnails` | Carregamento nas listagens |

### Não vai para Supabase Storage (fica só no Dropbox)

- Arquivos brutos: `.DZT`, `.DZG`, `.KML`, `.DWG` — pesados, não precisam de URL pública
- Matrizes `.npy` — grandes, úteis só para reprocessamento técnico
- `.docx` intermediário do relatório
- Outputs completos de cada run (pasta `01_Processamento_GPR/run_XXX/`)
- Logs de processamento

**Regra prática:** se o front-end precisa exibir ou o sócio precisa fazer download rápido → Supabase Storage. Se é dado técnico bruto ou arquivo pesado → Dropbox.

---

## 18. ESTADOS DO PROJETO

```
criado
  → aguardando_arquivos
  → aguardando_confirmacao_operador
  → backup_em_andamento
  → backup_confirmado
  → aguardando_processamento
  → processando_gpr
  → gpr_concluido
  → processando_ia
  → ia_concluida | ia_pendente_erro
  → aguardando_decisao_revisao
  → revisao_opcional | revisao_em_andamento | revisao_concluida
  → aguardando_cartografia
  → cartografia_concluida | cartografia_pendente_dados
  → aguardando_relatorio
  → relatorio_em_andamento
  → relatorio_gerado
  → aguardando_aprovacao
  → finalizado

Transversais: erro | pendente_dados
```

---

## 19. SEGURANÇA E RLS

**Regras RLS no Supabase (por tabela):**

```sql
-- projects: operador vê apenas seus próprios projetos ativos
-- tecnico vê apenas projetos com assigned_to = uid()
-- socio/admin vê tudo

-- project_files: mesma regra do projeto pai
-- INSERT permitido para operador_campo apenas em projetos que ele criou

-- detected_targets: SELECT para tecnico em projetos atribuídos
-- UPDATE apenas via processing_jobs (worker, não usuário direto)

-- ai_interpretations: SELECT para tecnico e socio
-- technical_reviews: INSERT/UPDATE para tecnico e socio
-- report_outputs: INSERT para socio apenas
-- audit_logs: INSERT para todos, SELECT apenas para socio/admin
```

**Outras regras:**
- Token Dropbox: variável de ambiente do worker, nunca no banco ou frontend
- OpenAI key: variável de ambiente do worker, nunca no banco ou frontend
- Supabase service role key: somente em contextos server-side do Next.js e no worker, nunca exposta ao cliente
- **Regra absoluta:** nenhuma rota, componente ou resposta do frontend pode expor Dropbox token, OpenAI API key ou Supabase service role key. Code review deve verificar isso explicitamente antes de merge.
- Todo acesso ao worker: via Supabase (não há endpoint público do worker)
- audit_logs: toda ação importante gera registro imutável

---

## 20. VERSIONAMENTO POR RUN

**Regra:** todo reprocessamento GPR ou IA gera nova run. Nunca sobrescreve.

```
Dropbox/01_Processamento_GPR/
├── run_001_2026-05-20_889b717c/  ← hash do config_used
├── run_002_2026-05-21_abc12345/  ← reprocessado com preset diferente
└── run_003_2026-06-01_889b717c/  ← reprocessado após calibração

Dropbox/02_IA_Interpretacao/
├── run_001/  ← mesma numeração do GPR correspondente
└── run_002/
```

No Supabase, cada run está associada a um `gpr_profiles.run_id` e a `processing_jobs`. O histórico completo de todos os runs é preservado.

---

## 21. CRITÉRIOS DE ACEITE (por fase)

### Fase 0 — Fundação
- [ ] Login funcionando com roles corretos
- [ ] Operador de campo não consegue ver dashboard geral
- [ ] Formulário Nova Entrada cria projeto e pasta no Dropbox
- [ ] Upload de .DZT via sistema chega ao Dropbox com hash correto
- [ ] Sincronização manual com Dropbox detecta arquivos novos
- [ ] Tela de confirmação mostra resumo correto de arquivos
- [ ] Status do projeto avança corretamente

### Fase 1 — Worker + Pipeline
- [ ] Worker detecta job em até 30s após criação
- [ ] Pipeline processa PATIO_001.DZT e gera todos os outputs esperados
- [ ] Alvos detectados aparecem no Supabase com todos os campos
- [ ] Imagens aparecem no dashboard via Supabase Storage
- [ ] Run versionada corretamente no Dropbox
- [ ] Logs disponíveis no sistema

### Fase 2 — IA
- [ ] IA roda automaticamente após GPR sem intervenção humana
- [ ] Todos os alvos com confidence_label != baixa têm interpretação IA
- [ ] Falha da IA não apaga resultados GPR
- [ ] Sócio consegue ver interpretação IA por alvo

---

## 22. FORA DE ESCOPO (V1)

- App mobile nativo (operador usa browser mobile)
- Integração com Radan (substituído pelo pipeline Python)
- Treinamento de modelo de ML próprio (usa OpenAI)
- Integração com CRM (fora do escopo operacional)
- Portal do cliente para download (entrega é por e-mail/link)
- Automação do WhatsApp (Solução 2, separada)
- Segundo Cérebro (Solução 4, separada)

---

## 23. RISCOS TÉCNICOS

| # | Risco | Prob | Impacto | Mitigação |
|---|---|---|---|---|
| R1 | .DZT corrompido ou incompleto chegando do campo | Alta | Alto | Hash na chegada + tela de confirmação + alerta |
| R2 | Dropbox API rate limit para uploads grandes | Média | Médio | Chunked upload + retry exponencial |
| R3 | Worker Python com readgssi/gprpy difícil de containerizar | Média | Alto | Dockerfile explícito + CI para testar o container |
| R4 | OpenAI falha ou demora em lote grande de alvos | Média | Médio | Retry + status ia_pendente_erro + reprocessamento manual |
| R5 | Custo OpenAI escala com projetos grandes (100+ alvos) | Média | Médio | Filtro: apenas alvos com confidence != baixa vão para IA |
| R6 | .DZG não disponível → cartografia sem georreferenciamento | Alta | Médio | Sistema funciona sem — registra pendência cartográfica |
| R7 | DXF gerado incompatível com padrão do Amilson | Baixa | Alto | Mapear padrão DXF atual antes de implementar Fase 4 |
| R8 | Operador com conexão ruim no campo → upload parcial | Alta | Médio | Upload resumível + confirmação parcial + status visível |
| R9 | Adoção baixa se mudança for percebida como carga extra | Média | Alto | Fase 1 não muda fluxo do Amilson — só adiciona valor |

---

## 24. ROADMAP POR FASES

### Fase 0 — Fundação (2–3 semanas)
Setup Supabase (schema + RLS + Auth), frontend login, formulário Nova Entrada, upload para Dropbox, sincronização manual, tela de confirmação, hash/manifest.  
**Entregável:** operador cadastra projeto e arquivos chegam seguros no Dropbox.

### Fase 1 — Worker + Pipeline (2–3 semanas)
Worker Python no Railway, polling de jobs, download do Dropbox, execução do pipeline_v1.py, gravação no Supabase, upload de imagens para Storage, dashboard com status e resultados.  
**Entregável:** pipeline roda automaticamente, sócio vê imagens e CSV de alvos no sistema.

### Fase 2 — IA (1–2 semanas)
job_ia.py com crops + chamada GPT-4o + gravação de interpretações, tela de resultados IA no frontend, tratamento de erros e reprocessamento.  
**Entregável:** sócio vê interpretação IA por alvo automaticamente.

### Fase 3 — Revisão Técnica (1–2 semanas)
Tela de revisão por alvo, three opções (aceitar/revisar selecionados/revisar tudo), gravação de technical_reviews, marcação vai_para_planta/relatorio.  
**Entregável:** revisão técnica opcional funcionando.

### Fase 4 — Cartografia (2–3 semanas)
Mapeamento do padrão DXF/KML atual com Amilson, job_cartografia.py, geração de DXF/KML/GeoJSON, tela de seleção de saída.  
**Entregável:** arquivos cartográficos gerados automaticamente.

### Fase 5 — Relatório (2–3 semanas)
Mapeamento do template com Marcos, job_relatorio.py, tela de configuração do relatório, geração DOCX/PDF, aprovação e finalização.  
**Entregável:** relatório gerado com um clique após aprovação dos dados.

### Fase 6 — Polimento (1–2 semanas)
Notificações, dashboard de métricas, gerenciamento de usuários, testes end-to-end, deploy em produção.
