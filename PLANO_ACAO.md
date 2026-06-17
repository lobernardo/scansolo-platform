# PLANO DE AÇÃO — ScanSOLO GPR Platform
> Gerado em: 2026-06-16  
> Baseado em: KB_MASTER.md v2, CLAUDE.md, pipeline_v1.py v2.0.0, análise Gemini + GPT  
> Objetivo: sistema pronto para produção com aprendizado contínuo

---

## 1. RESUMO EXECUTIVO

**O sistema funciona.** Pipeline GPR rodando, worker no Railway, frontend Next.js, IA GPT-4o integrada, revisão técnica interativa, relatório PDF — tudo operacional.

**O sistema não está pronto para produção** por 3 razões críticas:
1. Profundidades reportadas aos clientes podem estar erradas (time-zero implícito + velocity não calibrada)
2. Classificação de tipo de material não calibrada (metal vs. não-metal com thresholds arbitrários)
3. Nenhum mecanismo de aprendizado — cada projeto é um silo, sem aproveitamento das revisões do Amilson

**Custo estimado para estar pronto:** ~3 sprints de desenvolvimento (2 semanas cada) + 2 sessões com Amilson.

---

## 2. ESTADO ATUAL vs. SISTEMA PRONTO

### ✅ Funciona e pode ir para produção agora
| Item | Confiança |
|---|---|
| Leitura DZT via GPRPy | Alta |
| Pipeline 3 fluxos (científico/relatório/detector) | Alta |
| SNR gate automático | Média (calibrado só para PATIO) |
| Detector Hough+CurveFit+DeltaT com arr_raw | Alta (82% CurveFit) |
| Worker Railway + polling loop | Alta |
| Upload DZT → processamento → resultado na UI | Alta |
| Revisão técnica por alvo (Amilson) | Alta |
| Reprocessamento individual com polling automático | Alta |
| Relatório DOCX + PDF | Alta |
| Cartografia DXF/KML/GeoJSON | Alta |
| Deploy Vercel + Railway | Alta |

### ❌ Bloqueia produção (crítico)
| Gap | Impacto | Esforço |
|---|---|---|
| Time-zero não explícito | Profundidades erradas sistematicamente | 1-2h |
| Velocity não calibrada | Profundidades erradas sistematicamente | Sessão Amilson |
| Física do detector não calibrada | Tipo material errado no relatório | Sessão Amilson |

### ⚠️ Deve ser corrigido antes de escalar
| Gap | Impacto | Esforço |
|---|---|---|
| Distance Normalization ausente | Escala horizontal errada (dados modo-tempo) | 3h |
| Pileup 0.30m em modo MINIMO | Falsos positivos nos DZTs HELPER | 30min |
| Parser .DZX ausente | Perde GPS e marcas de campo | 2-4h |
| Rastreabilidade nenhuma | Impossível auditar resultado de relatório | 4h |
| Prompt GPT-4o sem contexto | 80% alvos = galeria_concreto (viés) | 1h |

### 🔵 Melhoria futura (não bloqueia)
| Gap | Impacto | Esforço |
|---|---|---|
| FIR Triangular (estilo RADAN) | Diferença visual vs RADAN | 1h |
| Análise espectro vertical | QC de RFI | 2h |
| Deconvolução | Ringing residual | Médio |
| SVD/KL clutter | Solo urbano com muito EMI | Alto |
| Dataset HELPER completo | Validação em escala | Sessão Amilson |

---

## 3. SISTEMA DE APRENDIZADO — ARQUITETURA PROPOSTA

Esta é a seção mais estratégica. O ScanSOLO tem uma vantagem única: **Amilson valida cada alvo manualmente**. Cada aprovação/rejeição é dado de treinamento valioso. Hoje esse dado existe na tabela `technical_reviews` mas **não é aproveitado para melhorar o sistema**.

### 3.1 Base de dados de exemplos validados (Ground Truth DB)

#### Estrutura proposta — tabela `gpr_ground_truth`

```sql
CREATE TABLE gpr_ground_truth (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_at      timestamptz DEFAULT now(),
  
  -- Origem
  project_id      uuid REFERENCES projects(id),
  profile_id      uuid REFERENCES gpr_profiles(id),
  target_rank     int NOT NULL,
  
  -- Geometria do alvo (do CSV de alvos)
  x_m             float NOT NULL,
  depth_m         float NOT NULL,
  diam_est_m      float,
  
  -- Dado bruto do detector
  score_detector  int,
  fit_ok          boolean,
  amplitude_relativa_sem_agc float,
  amplitude_relativa_raw     float,
  fase_consistente           boolean,
  freq_dominante_mhz         float,
  
  -- Velocidade usada
  velocity_usada_mns  float,
  
  -- Validação Amilson (ground truth)
  tipo_confirmado      text,  -- tubulacao_agua, tubulacao_gas, cabo_eletrico, etc.
  e_falso_positivo     boolean DEFAULT false,
  profundidade_real_m  float,  -- se conhecido (alvos de referência)
  diam_real_m          float,  -- se conhecido
  observacoes          text,
  validado_por         uuid REFERENCES auth.users(id),
  validado_em          timestamptz,
  
  -- Metadados do processamento
  pipeline_version     text DEFAULT '2.0.0',
  preset_usado         text,
  tipo_solo            text,
  snr_raw_db           float,
  
  -- Imagem do patch (para treino CNN/YOLO futuramente)
  patch_url            text,   -- URL do crop do alvo no radargrama científico
  
  -- Status
  status    text DEFAULT 'pendente' CHECK (status IN ('pendente', 'validado', 'rejeitado', 'duvidoso'))
);

-- Índices
CREATE INDEX ON gpr_ground_truth(project_id);
CREATE INDEX ON gpr_ground_truth(tipo_confirmado);
CREATE INDEX ON gpr_ground_truth(e_falso_positivo);
CREATE INDEX ON gpr_ground_truth(status);
```

#### Fluxo de alimentação (automático + manual)

```
Amilson revisa alvo na UI de revisão técnica
    ↓
[AUTOMÁTICO] job_interpretada.py ou finalizeReview():
    → insere em gpr_ground_truth com dados do detector + tipo_confirmado + validado_por
    → extrai patch 64×64px do radargrama científico → salva em gpr-images/ground_truth/
    ↓
[MANUAL] Pasta de validação externa (ver 3.2)
    → Amilson pode importar CSVs com alvos de projetos anteriores
```

#### Pasta de validação externa (para Amilson preencher)

```
scansolo-platform/
└── KB_ScansoloPlataform/
    └── GROUND_TRUTH/
        ├── README.md                  ← instruções para Amilson
        ├── template_validacao.csv     ← template CSV para preencher
        ├── PATIO/
        │   ├── PATIO_001_alvos_validados.csv
        │   └── PATIO_002_alvos_validados.csv
        ├── HELPER/
        │   └── (a preencher após processar os 126 DZTs)
        └── CALIBRACAO/
            └── alvos_profundidade_conhecida.csv  ← para calibrar velocity
```

**template_validacao.csv:**
```csv
projeto,perfil,rank,x_m,depth_m_sistema,profundidade_real_m,diam_real_m,tipo_confirmado,e_falso_positivo,observacoes
PATIO,PATIO_001,1,2.5,1.2,1.15,0.11,tubulacao_agua,false,"Tubo ferro galvanizado, registro disponível"
PATIO,PATIO_001,2,5.1,0.85,,,"inconclusivo",false,"Hipérbole real mas tipo incerto"
PATIO,PATIO_002,1,3.2,0.30,,,"",true,"Falso positivo - onda direta"
```

### 3.2 Validação no Frontend — melhorias propostas

#### 3.2.1 Campos adicionais na tela de revisão técnica

Na tela `/projetos/[id]/revisao`, adicionar ao formulário por alvo:

```typescript
// Campos novos em ReviewClient.tsx
interface ReviewFormExtra {
  profundidade_real_m?: number;    // "Você sabe a profundidade real?"
  diam_real_m?: number;            // "Você sabe o diâmetro real?"
  confianca_revisao: 'certa' | 'provavel' | 'duvidosa';  // grau de certeza
  motivo_rejeicao?: string;        // obrigatório quando vai_para_relatorio=false
  e_referencia: boolean;           // "Este alvo pode ser usado como referência de calibração?"
}
```

Quando `e_referencia=true`, o sistema automaticamente:
1. Armazena em `gpr_ground_truth` com `status='validado'`
2. Usa para recalcular `velocity_calibrada` se `profundidade_real_m` fornecido
3. Contribui para recalibração dos thresholds de amplitude

#### 3.2.2 Dashboard de qualidade do sistema (nova rota `/admin/qualidade`)

Para Amilson/admin ver o estado do aprendizado:
```
Alvos validados: 47 / 312 (15%)
Falsos positivos confirmados: 8 (17%)
Distribuição de tipos:
  - tubulacao_agua: 12 (26%)
  - tubulacao_gas:   8 (17%)
  - cabo_eletrico:  15 (32%)
  - inconclusivo:   12 (26%)

Velocity calibrada: 0.098 m/ns (±0.003, n=3 referências)
Threshold metal calibrado: 0.71 (vs 0.75 padrão)
Threshold não-metal calibrado: 0.38 (vs 0.40 padrão)

Drift de performance:
  Score médio dos aprovados: 68 → 71 (sprint 1→2)
  Taxa aprovação/total: 38% → 52%
```

### 3.3 Loop de melhoria contínua

```
[Projeto processado]
         ↓
[Amilson valida na UI] → gpr_ground_truth (automático)
         ↓
[Batch mensal - job `recalibrar`]:
  1. Ler todos validados com e_referencia=true
  2. Recalcular velocity_media por tipo_solo
  3. Recalcular fis_amp_metal_thr e fis_amp_nao_metal_thr
  4. Gravar novo preset `auto_calibrado_AAAA-MM` em Supabase
  5. Alertar admin: "Calibração disponível — aplicar?"
         ↓
[Admin aprova] → worker usa novo preset como default
         ↓
[Futuramente — n > 500 exemplos]:
  → Treinar modelo YOLO/CNN com patches dos alvos
  → Integrar como segunda camada de score (score_ml)
  → Score final = 0.6 × score_classico + 0.4 × score_ml
```

---

## 4. PLANO DE AÇÃO — 4 SPRINTS

### SPRINT 1 — Qualidade Técnica (2 semanas) 🔴 CRÍTICO

| # | Tarefa | Arquivo(s) | Esforço | GAP |
|---|---|---|---|---|
| S1-01 | Time-zero correction explícita | `pipeline_v1.py` | 2h | GAP-01 |
| S1-02 | Distance Normalization | `pipeline_v1.py` | 3h | GAP-13 |
| S1-03 | depth_min adaptativo por modo SNR | `pipeline_v1.py` | 30min | GAP-05 |
| S1-04 | Banner "Matrizes V1.2" → "v2.0.0" | `pipeline_v1.py:1222` | 5min | P11 |
| S1-05 | Migration: tabela gpr_ground_truth | `supabase/migrations/` | 1h | novo |
| S1-06 | Rastreabilidade mínima (hash + metrics) | `pipeline_v1.py`, `job_gpr.py` | 4h | GAP-14 |
| S1-07 | Campos extras na revisão técnica | `ReviewClient.tsx` | 2h | novo |
| S1-08 | Alimentação automática gpr_ground_truth | `job_interpretada.py` | 2h | novo |
| S1-09 | Fix P11: banner version | `pipeline_v1.py` | 5min | P11 |

### SPRINT 2 — Sessão Amilson + Calibração (1 semana dev + 1 sessão)

| # | Tarefa | Arquivo(s) | Esforço | GAP |
|---|---|---|---|---|
| S2-01 | Sessão calibração velocity (campo) | — | ½ dia campo | GAP-03 |
| S2-02 | Sessão calibração amplitude metal/não-metal | — | 2h análise | GAP-04 |
| S2-03 | Atualizar preset com valores calibrados | `pipeline_v1.py` | 30min | GAP-04 |
| S2-04 | Prompt GPT-4o com contexto do projeto | `job_ia.py` | 1h | GAP-10 |
| S2-05 | Parser .DZX básico | `pipeline/parse_dzx.py` | 4h | GAP-02 |
| S2-06 | FIR Triangular como opção de bandpass | `pipeline_v1.py` | 1h | GAP-06 |
| S2-07 | Análise espectro vertical (QC) | `pipeline_v1.py` | 2h | GAP-07 |

### SPRINT 3 — Dataset + Presets + Dashboard (2 semanas)

| # | Tarefa | Arquivo(s) | Esforço | GAP |
|---|---|---|---|---|
| S3-01 | Processar 126 DZTs HELPER completos | worker | ½ dia | GAP-11 |
| S3-02 | Script de importação CSV ground truth | `scripts/import_ground_truth.py` | 2h | novo |
| S3-03 | Dashboard qualidade `/admin/qualidade` | `apps/web/` | 4h | novo |
| S3-04 | Presets por objetivo (6 presets) | `pipeline_v1.py` | 4h | GAP-09 |
| S3-05 | Job `recalibrar` (batch mensal) | `worker_main.py`, `job_recalibrar.py` | 6h | novo |
| S3-06 | Storage cleanup no deleteProject | `apps/web/actions/` | 2h | P12 |

### SPRINT 4 — IA Avançada + ML (futuro, quando n > 200 exemplos)

| # | Tarefa | Arquivo(s) | Esforço |
|---|---|---|---|
| S4-01 | Extração de patches por alvo | `pipeline/extrair_patches.py` | 4h |
| S4-02 | Script de geração de dados sintéticos (gprMax) | `scripts/gprmax_gen.py` | 1 semana |
| S4-03 | Treino YOLOv8m/CNN com ground truth | `ml/treinar_detector.py` | 2+ semanas |
| S4-04 | Integração score_ml no detector | `pipeline/detector_hiperboles.py` | 1 semana |
| S4-05 | SVD/KL como opção de bgremoval | `pipeline_v1.py` | 1 semana |

---

## 5. PROMPTS CLAUDE CODE — PRONTOS PARA EXECUTAR

> **Como usar:** Abra Claude Code no terminal dentro de `scansolo-platform/`. Cole o prompt inteiro. Claude Code tem acesso ao código e executa diretamente.

---

### PROMPT S1-01 — Time-Zero Correction Explícita

```
Contexto: Estou desenvolvendo o ScanSOLO, uma plataforma de processamento GPR.
O arquivo principal do pipeline é services/worker/pipeline/pipeline_v1.py (v2.0.0).

Problema: O pipeline não realiza time-zero correction explícita. O GPRPy usa
header['timezero'] implicitamente, mas não validamos se o valor está correto
para cada DZT. Se errado, TODOS os alvos têm profundidade incorreta.

Tarefa: Implementar time-zero correction explícita no início do processamento.

Especificações:
1. Criar função `detectar_time_zero(arr_raw) -> int` que:
   - Calcula a média de todos os traços
   - Aplica envelope de Hilbert
   - Localiza o pico mais proeminente nas primeiras 20% das amostras
   - Retorna o índice da amostra do time-zero

2. Criar função `aplicar_time_zero(arr, time_zero) -> arr` que:
   - Retorna arr[time_zero:, :] (remove amostras antes do zero)
   - Loga um warning se time_zero > 10% do total de amostras

3. Na função `processar_dzt()` (ou equivalente em pipeline_v1.py):
   - Chamar `detectar_time_zero(arr_raw)` ANTES do dewow
   - Chamar `aplicar_time_zero` em arr_raw antes de qualquer filtro
   - Salvar `time_zero_sample` no index_projeto.csv e config_used.json

4. Se GPRPy já aplicou time-zero via header['timezero']:
   - Comparar com o detectado automaticamente
   - Logar diferença em dB se > 5 amostras
   - Preferir o detectado automaticamente (mais confiável)

Critério de aceite: 
- Processar PATIO_001.DZT e comparar profundidade do alvo de maior score
  antes e depois da correção
- Diferença esperada: 0-3 amostras (≈ 0-1ns ≈ 0-5cm) para dados bem coletados
- Registrar `time_zero_sample` no log e no CSV
```

---

### PROMPT S1-02 — Distance Normalization

```
Contexto: ScanSOLO, pipeline GPR em services/worker/pipeline/pipeline_v1.py.
Os DZTs PATIO e HELPER foram coletados com encoder de roda — modo distância.
Novos projetos podem ser coletados em modo tempo (rhf_sps > 0, rhf_spm = 0).

Problema: Sem distance normalization, dados em modo tempo têm traços com
espaçamento irregular (velocidade de caminhada variável), distorcendo as
hipérboles e invalidando coordenadas horizontais.

Tarefa: Implementar detecção automática do modo de coleta e normalização.

Especificações:
1. Criar função `detectar_modo_coleta(header) -> str`:
   - Se header['rhf_spm'] > 0: retorna 'distancia' (encoder, OK)
   - Se header['rhf_sps'] > 0 e rhf_spm == 0: retorna 'tempo' (precisa normalizar)
   - Log qual modo foi detectado

2. Criar função `distance_normalization(arr, header, target_spm=None) -> arr`:
   - Só executa se modo == 'tempo'
   - target_spm padrão: 50 scans/metro (ajustável via filtros_customizados)
   - Interpola array de (n_amostras × n_traços_originais) para (n_amostras × n_traços_normalizados)
   - Usa scipy.interpolate.interp1d com kind='linear' no eixo de traços
   - Retorna array reamostrado + atualiza metadata (n_traces_original, n_traces_normalized)

3. Adicionar step no início do processamento, ANTES do time-zero:
   - detectar_modo_coleta → se 'tempo', aplicar distance_normalization
   - Salvar 'modo_coleta' e 'distance_normalized' no config_used.json

4. Adicionar campo `modo_coleta` no index_projeto.csv

Critério de aceite:
- Teste com DZT em modo tempo simulado (criar array com traços duplicados
  e verificar que a normalização os remove corretamente)
- Não deve alterar nada para dados em modo distância (rhf_spm > 0)
```

---

### PROMPT S1-03 — depth_min Adaptativo por Modo SNR

```
Contexto: ScanSOLO, pipeline GPR, services/worker/pipeline/pipeline_v1.py.

Problema confirmado (P10): 232/341 alvos detectados nos 126 DZTs HELPER
caem exatamente em depth_m = 0.30m (modo MINIMO, bandpass pulado).
Causa: onda direta (airwave) passa pelo filtro de amplitude quando bandpass
é pulado. O limiar fixo 0.30m é justamente onde a onda direta aparece.

Tarefa: Tornar det_depth_min_m adaptativo por modo de processamento.

Especificações:
1. No preset '270mhz' e DEFAULT_PARAMS do detector, substituir:
   "det_depth_min_m": 0.30
   por:
   "det_depth_min_m": None  # será calculado automaticamente

2. Criar função `calcular_depth_min(modo_processamento, preset) -> float`:
   limites = {
     'minimo':    0.50,  # bandpass pulado → mais ruído superficial
     'padrao':    0.30,  # comportamento atual
     'agressivo': 0.20,  # dado muito ruidoso → aceitar raso
   }
   return limites.get(modo_processamento, 0.30)

3. Chamar esta função antes de rodar o detector, passando o modo atual.
   Salvar o valor calculado em index_projeto.csv como 'det_depth_min_m_usado'.

4. Se filtros_customizados contiver 'det_depth_min_m', usar esse valor
   (override manual tem prioridade sobre o automático).

Critério de aceite:
- Rodar pipeline nos DZTs HELPER em modo MINIMO
- Confirmar que alvos em 0.30m exato são eliminados (devem ter depth > 0.50m)
- Contar quantos dos 232 falsos positivos são eliminados
```

---

### PROMPT S1-04 — Rastreabilidade Mínima (Hash + Métricas)

```
Contexto: ScanSOLO, worker em services/worker/pipeline/pipeline_v1.py e job_gpr.py.

Problema: As imagens geradas não têm rastreabilidade. Não é possível saber
com qual versão do pipeline, quais parâmetros, e qual hash do DZT original
cada imagem foi gerada. Isso impossibilita auditoria de relatórios.

Tarefa: Implementar rastreabilidade mínima sem quebrar nada existente.

Especificações:

1. Calcular hash SHA256 do arquivo DZT original:
   import hashlib
   def hash_arquivo(caminho: str) -> str:
     h = hashlib.sha256()
     with open(caminho, 'rb') as f:
       for bloco in iter(lambda: f.read(65536), b''):
         h.update(bloco)
     return h.hexdigest()

2. Criar arquivo `pipeline_metrics.json` por DZT processado, salvo junto
   com os outros arquivos de saída (mesma pasta). Conteúdo:
   {
     "dzt_sha256": "abc123...",
     "pipeline_version": "2.0.0",
     "run_id": "<uuid do run>",
     "timestamp_utc": "2026-06-16T14:30:00Z",
     "preset_usado": "270mhz",
     "filter_overrides": {},
     "modo_processamento": "padrao",
     "tipo_solo": "standard",
     "time_zero_sample": 12,
     "distance_normalized": false,
     "snr_raw_db": 20.6,
     "snr_cientifico_db": 26.1,
     "snr_relatorio_db": 8.3,
     "delta_snr_dewow": 1.2,
     "delta_snr_bandpass": 2.8,
     "delta_snr_tpow": 3.1,
     "n_candidatos_hough": 45,
     "n_candidatos_curvefit": 37,
     "n_alvos_csv": 12,
     "saturacao_pct_relatorio": 1.8,
     "saturacao_pct_cientifico": 0.4
   }

3. Calcular delta_snr por estágio:
   - snr_apos_dewow_db (novo campo intermediário)
   - snr_apos_bandpass_db (novo campo intermediário)
   - delta_snr_dewow = snr_apos_dewow_db - snr_raw_db
   - delta_snr_bandpass = snr_apos_bandpass_db - snr_apos_dewow_db

4. Calcular saturacao_pct (% amostras > 95% do valor máximo):
   def saturacao_pct(arr):
     return float(np.mean(np.abs(arr) > 0.95 * np.max(np.abs(arr))) * 100)

5. Fazer upload do pipeline_metrics.json para gpr-tabelas/{project_id}/{run_id}/
   e salvar URL em gpr_profiles (novo campo: metricas_pipeline_url TEXT).

6. IMPORTANTE: Não quebrar nenhum flow existente. Este é um step adicional
   que não deve alterar o processamento em si.

Critério de aceite:
- Processar PATIO_001 e verificar que pipeline_metrics.json é gerado
- Verificar que dzt_sha256 muda se o arquivo DZT mudar
- Verificar que delta_snr_dewow > 0 (dewow deve aumentar SNR)
```

---

### PROMPT S1-05 — Migration: tabela gpr_ground_truth

```
Contexto: ScanSOLO, banco de dados Supabase em supabase/migrations/.
O projeto usa supabase CLI para migrations. Último arquivo aplicado:
20260615000002 (ia_p2 enum + imagem_interpretada_ia_p2_url).

Tarefa: Criar migration para tabela de ground truth de alvos validados.

Especificações — criar arquivo 20260616000001_ground_truth.sql:

1. Criar tabela gpr_ground_truth com campos:
   - id uuid PK
   - created_at timestamptz DEFAULT now()
   - project_id uuid REFERENCES projects(id) ON DELETE CASCADE
   - profile_id uuid REFERENCES gpr_profiles(id) ON DELETE CASCADE
   - target_rank int NOT NULL
   - x_m float NOT NULL
   - depth_m float NOT NULL
   - diam_est_m float
   - score_detector int
   - fit_ok boolean
   - amplitude_relativa_sem_agc float
   - amplitude_relativa_raw float
   - fase_consistente boolean
   - freq_dominante_mhz float
   - velocity_usada_mns float
   - tipo_confirmado text
   - e_falso_positivo boolean DEFAULT false
   - profundidade_real_m float  -- para calibração de velocity
   - diam_real_m float          -- para calibração de diâmetro
   - confianca_revisao text DEFAULT 'provavel' CHECK (IN ('certa','provavel','duvidosa'))
   - e_referencia boolean DEFAULT false  -- usar para calibração automática
   - motivo_rejeicao text
   - observacoes text
   - validado_por uuid REFERENCES auth.users(id)
   - validado_em timestamptz
   - pipeline_version text DEFAULT '2.0.0'
   - preset_usado text
   - tipo_solo text
   - snr_raw_db float
   - patch_url text  -- crop 64×64 do alvo no radargrama científico
   - status text DEFAULT 'pendente' CHECK (IN ('pendente','validado','rejeitado','duvidoso'))
   - source text DEFAULT 'revisao_tecnica' CHECK (IN ('revisao_tecnica','importacao_csv','canvas'))

2. Criar índices em: project_id, profile_id, tipo_confirmado, e_falso_positivo, status, e_referencia

3. Aplicar RLS:
   - Leitura: socio/admin podem ler tudo; tecnico só os do próprio perfil
   - Escrita: socio/admin e tecnico podem inserir
   - UPDATE/DELETE: só socio/admin

4. Adicionar campo metricas_pipeline_url TEXT na tabela gpr_profiles
   (para salvar URL do pipeline_metrics.json)

5. Aplicar com: supabase db push --password <DB_PASSWORD>

Critério de aceite:
- supabase migration list mostra a nova migration como Applied
- Tabela gpr_ground_truth existe no banco remoto
- RLS funciona: tecnico só vê dados do seu projeto
```

---

### PROMPT S1-06 — Alimentação Automática gpr_ground_truth

```
Contexto: ScanSOLO, worker em services/worker/pipeline/job_interpretada.py.
A tabela gpr_ground_truth já existe (migration S1-05 aplicada).

Situação atual: quando Amilson aprova alvos via finalizeReview(), o sistema
gera a imagem interpretada mas NÃO grava os alvos aprovados em gpr_ground_truth.
A tabela ia_training_examples existe mas é menos estruturada.

Tarefa: Alimentar gpr_ground_truth automaticamente quando alvos são aprovados.

Especificações:

1. Em job_interpretada.py, após gerar a imagem interpretada, para cada alvo
   aprovado (vai_para_relatorio=True ou vai_para_planta=True):
   
   a. Buscar dados completos do alvo em detected_targets
   b. Buscar revisão do alvo em technical_reviews
   c. Buscar metadados do perfil (tipo_solo, snr_raw_db, preset, etc.)
   d. Inserir em gpr_ground_truth com source='revisao_tecnica'
   e. Status='validado' (aprovado pelo Amilson = validado)
   f. Se e_referencia for true na revisão, marcar e_referencia=True

2. Para alvos REJEITADOS (vai_para_relatorio=False):
   - Inserir em gpr_ground_truth com e_falso_positivo=True, status='validado'
   - Isso é igualmente valioso para calibração

3. Fazer upsert (não duplicar se o alvo já existe para este run_id + rank):
   ON CONFLICT (profile_id, target_rank) DO UPDATE SET
     tipo_confirmado = EXCLUDED.tipo_confirmado,
     e_falso_positivo = EXCLUDED.e_falso_positivo,
     validado_por = EXCLUDED.validado_por,
     validado_em = EXCLUDED.validado_em

4. Em ReviewClient.tsx, adicionar campos no formulário de revisão:
   - confianca_revisao (radio: 'certa' / 'provavel' / 'duvidosa')
   - profundidade_real_m (number, opcional, "Profundidade real se conhecida")
   - e_referencia (checkbox, "Usar para calibração do sistema")
   Esses campos devem ser enviados via server action para o job.

Critério de aceite:
- Processar PATIO_001, completar revisão técnica de 3 alvos
- Verificar que gpr_ground_truth contém os 3 alvos com status='validado'
- Verificar que alvos rejeitados também aparecem com e_falso_positivo=True
```

---

### PROMPT S2-04 — Prompt GPT-4o com Contexto do Projeto

```
Contexto: ScanSOLO, worker em services/worker/pipeline/job_ia.py.
O job 'ia' interpreta cada alvo via GPT-4o. Problema conhecido (P7/GAP-10):
GPT-4o classifica ~80% dos alvos como galeria_concreto sem contexto do projeto.

Tarefa: Incluir contexto do projeto no prompt do GPT-4o.

Especificações:

1. No handler handle_ia_job(), antes de montar o prompt, buscar do banco:
   - projects.tipo_obra (novo campo — ver item 3)
   - projects.tipo_solo (do processing_config ou campo direto)
   - projects.antena_freq_mhz
   - projects.area_m2
   - Últimos 10 alvos aprovados do mesmo projeto (tipo_confirmado de gpr_ground_truth)
   - Distribuição de tipos aprovados: {"tubulacao_agua": 3, "cabo_eletrico": 2, ...}

2. Atualizar o prompt do sistema (system message) para incluir:
   ---
   Project context:
   - Work type: {tipo_obra}  (utilities mapping / structural / pavement)
   - Soil type: {tipo_solo}  (standard / argiloso / umido)
   - Antenna: {antena_freq_mhz} MHz
   - Previously confirmed targets in this project: {historico_tipos}
   
   Use this context to bias your classification. In a utilities project with
   confirmed water pipes, a new target is more likely another water pipe than
   a concrete gallery. In a structural project, prioritize concrete/rebar.
   ---

3. Criar migration para adicionar campo `tipo_obra` em projects:
   tipo_obra TEXT DEFAULT 'utilities' CHECK (IN ('utilities','estrutural','pavimento','ambiental','outro'))
   
   Adicionar seleção na tela de Nova Entrada (step 1 do formulário 2-step).

4. Se não houver histórico (primeiro projeto ou ground_truth vazio),
   usar apenas: "No confirmed targets yet in this project."

5. Manter retrocompatibilidade: se busca do histórico falhar, continuar
   com o prompt atual (não bloquear o job).

Critério de aceite:
- Processar um projeto com 3+ alvos já aprovados
- Novo alvo do mesmo projeto deve receber classificação influenciada
  pelo histórico (ex: se 3 aprovados são tubulacao_agua, novo deve ser
  menos provável ser galeria_concreto)
- Comparar distribuição de tipos antes vs depois em 10 alvos
```

---

### PROMPT S2-05 — Parser .DZX Básico

```
Contexto: ScanSOLO, worker Python em services/worker/pipeline/.
O pipeline processa .DZT mas ignora o .DZX companheiro.
O .DZX é XML e contém GPS por waypoint, marcas do usuário e picks do RADAN.

Tarefa: Implementar parser .DZX básico e integrar ao pipeline.

Especificações:
1. Criar arquivo services/worker/pipeline/parse_dzx.py com:

   def parse_dzx(caminho_dzx: str) -> dict:
     """Parse .DZX companheiro de um .DZT.
     Retorna dict com: waypoints, targets, layers, global_props
     """
     # Usar xml.etree.ElementTree
     # Extrair: WayPt com GPS (lat/lon/altitude)
     # Extrair: TargetWayPt (picks do RADAN)
     # Extrair: LayerWayPt (picks de camadas)
     # Extrair: GlobalProperties (dielétrico, unidades)
     # Retornar estrutura normalizada

2. No pipeline_v1.py, ao início do processamento de cada DZT:
   - Verificar se existe .DZX com mesmo nome base
   - Se existe: chamar parse_dzx()
   - Salvar resultado em metadata_dzx.json junto com os outros arquivos
   - Usar rhf_epsr do DZX se disponível (mais confiável que o do header binário)
   - Logar quantos waypoints e targets foram encontrados

3. Se DZX contiver targets (picks do RADAN):
   - Salvar em gpr_profiles como campo radan_picks_url (JSON no storage)
   - Na UI de revisão técnica, mostrar os picks do RADAN sobrepostos à imagem
     (coordenadas scan+depth dos picks do RADAN, como referência para Amilson)

4. Se DZX contiver GPS:
   - Adicionar lat/lon ao CSV de alvos para cada alvo
     (interpolando pela posição x_m do alvo no perfil)
   - Salvar campo gps_disponivel: bool no index_projeto.csv

5. IMPORTANTE: Se .DZX não existir, continuar normalmente (opcional, não obrigatório).

Critério de aceite:
- Encontrar .DZX de teste (verificar se os DZTs PATIO têm .DZX companheiro)
- Se tiver: confirmar que waypoints e picks são extraídos corretamente
- Se não tiver: confirmar que o pipeline não quebra e loga "DZX não encontrado"
```

---

### PROMPT S3-03 — Dashboard de Qualidade `/admin/qualidade`

```
Contexto: ScanSOLO, frontend Next.js em apps/web/.
A tabela gpr_ground_truth já existe com dados (pré-requisito: S1-05, S1-06).

Tarefa: Criar rota /admin/qualidade com dashboard de métricas do sistema.

Especificações:
1. Rota: apps/web/app/admin/qualidade/page.tsx
   Acesso: apenas roles 'socio' e 'admin'

2. Server action para buscar métricas:
   - Total de alvos em gpr_ground_truth por status
   - Distribuição de tipos_confirmados (contagem)
   - Taxa de falsos positivos (e_falso_positivo=true / total)
   - Velocity média dos alvos com e_referencia=true e profundidade_real_m preenchida
     Fórmula: velocity = (2 × profundidade_real_m) / TWTT
     (TWTT pode ser calculado de depth_m e velocity_usada_mns)
   - Threshold de amplitude calibrado: média de amplitude_relativa_sem_agc
     dos alvos com tipo_confirmado IN ('tubulacao_agua','tubulacao_gas','cabo_eletrico')
     vs. amplitude média dos restantes

3. UI mínima (componente React simples, sem biblioteca de charts complexa):
   - Cards com os números principais (total validados, taxa FP, velocity calibrada)
   - Tabela de distribuição de tipos
   - Lista de últimas 10 validações com projeto, perfil, tipo, data
   - Botão "Exportar ground truth CSV" (download de todos os validados)

4. Adicionar link no sidebar de admin (só visível para socio/admin)

5. Server action de exportação CSV:
   - Retorna todos registros validados em formato do template_validacao.csv
   - Inclui campos: projeto, perfil, rank, x_m, depth_m, tipo_confirmado,
     profundidade_real_m, diam_real_m, e_falso_positivo, velocity_usada_mns

Critério de aceite:
- Acessar /admin/qualidade e ver os cards com dados reais
- Clicar em "Exportar" e receber CSV com os dados
- Verificar que usuário role='tecnico' recebe 403 ao acessar
```

---

### PROMPT S3-05 — Job de Recalibração Automática

```
Contexto: ScanSOLO, worker em services/worker/.
A tabela gpr_ground_truth existe e está sendo alimentada (pré-requisito: S1-06).

Tarefa: Criar job 'recalibrar' que recalcula parâmetros do sistema
automaticamente a partir dos exemplos validados.

Especificações:
1. Criar services/worker/pipeline/job_recalibrar.py com:

   def handle_recalibrar_job(job, supabase):
     """
     Recalcula:
     1. velocity_calibrada por tipo_solo
     2. fis_amp_metal_thr
     3. fis_amp_nao_metal_thr
     
     Salva resultado em tabela `calibracoes_sistema` (nova, ver item 3).
     NÃO aplica automaticamente — gera proposta para admin aprovar.
     """

   a. Velocity calibrada (por tipo_solo):
      - Filtrar gpr_ground_truth WHERE e_referencia=True AND profundidade_real_m IS NOT NULL
      - Para cada registro: velocity_real = (2 × profundidade_real_m) / (2 × depth_m / velocity_usada_mns)
        (isolando velocity a partir da equação de profundidade)
      - Agrupar por tipo_solo, calcular média e desvio padrão
      - Reportar só se n >= 3 (mínimo estatístico)

   b. Thresholds de amplitude:
      - Alvos confirmados como metal: tipo_confirmado IN ('tubulacao_agua','tubulacao_gas','cabo_eletrico','cabo_telecom')
      - Alvos confirmados como não-metal: tipo_confirmado IN ('tubulacao_pvc','galeria_concreto','vazio_ar')
      - fis_amp_metal_thr = percentil 25 da amplitude dos metálicos (piso)
      - fis_amp_nao_metal_thr = percentil 75 da amplitude dos não-metálicos (teto)
      - Reportar só se n_metal >= 5 e n_nao_metal >= 5

2. Criar tabela calibracoes_sistema:
   id, created_at, tipo_solo, velocity_calibrada_mns, velocity_n, velocity_stddev,
   fis_amp_metal_thr, fis_amp_nao_metal_thr, n_metal, n_nao_metal,
   status TEXT DEFAULT 'proposta' CHECK (IN ('proposta','aprovada','rejeitada')),
   aprovado_por uuid, aprovado_em timestamptz

3. No admin/qualidade (S3-03), adicionar seção "Calibrações":
   - Lista de propostas de calibração com status
   - Botão "Aprovar" para status='proposta'
   - Quando aprovado: atualizar o preset '270mhz' no código
     (via server action que chama API do Railway para restart do worker com novo preset)
     OU: salvar em tabela `config_sistema` que o worker lê no startup

4. Registrar job_type 'recalibrar' no enum de processing_jobs
   Rodar: manualmente via botão no admin, ou automaticamente a cada 30 dias

Critério de aceite:
- Com pelo menos 5 alvos metálicos e 5 não-metálicos validados:
  rodar job recalibrar e verificar que proposta é gerada com valores calculados
- Admin aprova: verificar que config é salva
- Worker próximo processamento usa nova config
```

---

### PROMPT FIX-P11 — Banner de versão incorreto (5 minutos)

```
Contexto: services/worker/pipeline/pipeline_v1.py, linha aproximada 1222.
Problema: o código imprime "Matrizes V1.2" mas o pipeline é v2.0.0.

Tarefa: Localizar e corrigir o banner de versão incorreto.

1. Buscar por "V1.2" ou "v1.2" ou "Matrizes" no arquivo
2. Corrigir para "v2.0.0"
3. Confirmar que não há outros banners de versão incorretos no arquivo

Critério de aceite: pipeline_v1.py não contém "V1.2" em nenhuma linha de print/log.
```

---

## 6. PASTA DE GROUND TRUTH — ESTRUTURA PARA AMILSON

Criar a seguinte estrutura de arquivos (não requer código):

```
scansolo-platform/KB_ScansoloPlataform/GROUND_TRUTH/
├── README_AMILSON.md
├── template_validacao.csv
├── PATIO/
│   └── (vazio — será preenchido após Sprint 2)
├── HELPER/
│   └── (vazio — será preenchido após processar 126 DZTs)
└── CALIBRACAO/
    └── alvos_referencia.csv
```

**README_AMILSON.md** deve explicar:
1. O que é o ground truth e por que é importante
2. Como preencher o CSV (campo a campo)
3. Como importar via dashboard `/admin/qualidade`
4. Quais alvos priorizar como referência (e_referencia=true):
   - Alvos com profundidade confirmada por registro de obra
   - Alvos que você expôs fisicamente
   - Alvos confirmados por pipe locator

**template_validacao.csv** com header:
```
projeto,perfil,rank,x_m,depth_m_sistema,profundidade_real_m,diam_real_m,tipo_confirmado,e_falso_positivo,e_referencia,confianca,observacoes
```

---

## 7. MÉTRICAS DE SUCESSO — COMO SABER QUE ESTÁ PRONTO

### Técnicas
| Métrica | Hoje | Meta Sprint 1 | Meta Sprint 2 | Meta Sprint 3 |
|---|---|---|---|---|
| Time-zero explícito | ❌ | ✅ | ✅ | ✅ |
| Pileup 0.30m eliminado | ❌ 232/341 FP | < 20 | < 10 | < 5 |
| Velocidade calibrada | Estimada | Estimada | Calibrada (n≥3) | Calibrada (n≥10) |
| Thresholds amplitude | Padrão | Padrão | Calibrado | Auto-calibração ativa |
| Ground truth validados | 0 | 0 | 50+ | 200+ |
| Taxa FP confirmada | Desconhecida | Medida | < 25% | < 15% |

### De produto
| Métrica | Meta |
|---|---|
| Amilson consegue processar projeto completo sem reportar erro de profundidade | Sprint 2 |
| Relatório gerado tem tipo de material correto em > 80% dos alvos | Sprint 2 |
| Sistema sugere calibração quando 5+ exemplos de referência disponíveis | Sprint 3 |
| Score médio dos alvos aprovados cresce com mais dados de treino | Sprint 4 |

---

*Documento gerado em 2026-06-16 para uso interno do projeto ScanSOLO.*  
*Atualizar após cada sprint concluído.*
