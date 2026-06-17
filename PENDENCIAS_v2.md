# PENDÊNCIAS v2 — ScanSOLO GPR Platform
> Gerado em: 2026-06-17  
> Premissa: **minimizar dependência do Amilson**. Tudo que tem base em literatura GPR publicada é implementado agora. Amilson valida e ajusta em produção pelo próprio sistema.

---

## CONCLUSÃO DIRETA

**Das 3 sessões que "precisavam de Amilson", 2 podem ser eliminadas** com tabelas publicadas de física de GPR (velocidade EM + coeficiente de reflexão). O sistema já tem o loop de auto-calibração construído — bastaa alimentar com valores iniciais fisicamente corretos em vez de arbitrários.

---

## CATEGORIA A — Implementar agora (sem Amilson, base em literatura)

### A1 — Tabela de velocidade por tipo de solo ⬅ CRÍTICO
**Problema atual:** `velocity_mns = 0.10` para TODOS os solos. Profundidades erradas em projetos não-standard.

**Solução (literatura publicada):**

| Tipo de Solo | εr (publicado) | Velocidade (m/ns) | Fonte |
|---|---|---|---|
| `standard` (aterro urbano misto) | 7–10 | **0.100** | USACE 1995; GuidelineGEO |
| `arenoso` (areia seca/cascalho) | 4–6 | **0.130** | USACE; CLU-IN; Daniels 2004 |
| `argiloso` (argila úmida) | 14–22 | **0.070** | USACE; Reynolds 1997 |
| `umido` (solo saturado) | 22–35 | **0.060** | USACE; GPR Rental Table |
| `pedregoso` (rocha/cascalho) | 5–8 | **0.115** | ResearchGate; EOAS UBC |

**Fórmula base:** v = c / √εr onde c = 0.3 m/ns (NIST constant)

**Impacto:** erro de profundidade atual em solo argiloso = +43% (0.10 vs 0.07). Em arenoso = -30% (0.10 vs 0.13).

**Implementação:** adicionar dict `VELOCITY_POR_SOLO` ao preset em `pipeline_v1.py`. Se `velocity_mns` não estiver em `filtros_customizados`, usar valor do dict pela chave `tipo_solo`.

**Auto-calibração em produção:** quando Amilson marcar `e_referencia=True` + `profundidade_real_m` na revisão, o `job_recalibrar` usa esses pontos para ajustar o valor real. O sistema converge para a velocity real do projeto sem sessão de campo dedicada.

---

### A2 — Thresholds de amplitude por física EM ⬅ IMPORTANTE
**Problema atual:** `fis_amp_metal_thr=0.75` e `fis_amp_nao_metal_thr=0.40` são arbitrários. Threshold de 0.40 para não-metais é ALTO DEMAIS — tubos PVC/PE têm coeficiente de reflexão R≈0.27 e seriam classificados como inconclusivos.

**Solução (coeficiente de reflexão de Fresnel):**

R = (√ε_solo − √ε_alvo) / (√ε_solo + √ε_alvo)

| Material | εr | R (solo padrão ε=9) | Amplitude normalizada esperada |
|---|---|---|---|
| Metal (condutor perfeito) | ∞ | 1.00 | > 0.70 |
| Cabo elétrico (cobre) | — | ≈ 0.95 | > 0.70 |
| Vazio/ar | 1 | 0.50 | 0.40–0.65 |
| Tubo c/ água | 81 | 0.50 | 0.40–0.65 |
| Tubo PE/HDPE | 2.3 | 0.33 | 0.22–0.42 |
| Tubo PVC | 3.0 | 0.27 | 0.18–0.36 |
| Galeria concreto | 7.0 | 0.06 | < 0.18 |
| Solo com variação | — | < 0.10 | < 0.12 |

**Thresholds sugeridos (física):**
```python
"fis_amp_metal_thr":      0.65,  # era 0.75 — captura metal E cabos, rejeita vazios
"fis_amp_nao_metal_thr":  0.22,  # era 0.40 — captura PVC/PE que antes eram perdidos
```

**Lógica de classificação revisada:**
- `amplitude > 0.65` → `metal` (condutor alto)
- `0.22 ≤ amplitude ≤ 0.65` → `nao_metal` (dielétrico — PVC, PE, vazio, água)
- `amplitude < 0.22` → `inconclusivo` (baixo contraste — concreto, variação de solo)

**Implementação:** atualizar os dois valores no preset `270mhz` em `pipeline_v1.py`.

**Auto-calibração:** `job_recalibrar` ajusta esses thresholds a partir de `gpr_ground_truth.amplitude_relativa_sem_agc` dos VP/FP confirmados pelo Amilson.

---

### A3 — 6 presets por objetivo ⬅ MÉDIO
**Problema atual:** só existe `270mhz`. Todo projeto usa o mesmo preset independente do objetivo.

**Presets baseados em literatura de processamento GPR (270 MHz GSSI):**

| Preset | Caso de Uso | Diferenças vs. 270mhz |
|---|---|---|
| `270mhz` | Utilitários urbanos padrão (0–3m) | — base |
| `270mhz_clay` | Solo argiloso/úmido | velocity=0.07, bgremoval_traces=20, tpow_power=0.7 |
| `270mhz_sandy` | Solo arenoso/seco | velocity=0.13, agc_window=200 (sinal atenua menos) |
| `270mhz_deep` | Alvos profundos (3–5m) | tpow_power=0.8, agc_window=100, det_h_max_m=5.0 |
| `270mhz_void` | Detecção de vazios/galerias | fis_amp_metal_thr=0.30, fis_amp_nao_metal_thr=0.45 (prioriza vazio>PVC) |
| `270mhz_concrete` | Laje/piso de concreto | velocity=0.11, det_h_max_m=0.50, dewow_window=3 |

**Implementação:** adicionar 5 dicts novos em `pipeline_v1.py` (PRESETS dict), selecionar via `--preset` flag.

---

### A4 — FIR Triangular como opção de bandpass ⬅ BAIXO
**O que é:** o RADAN usa um bandpass com resposta triangular em frequência (rampa linear de fl→fc→fh) em vez de Butterworth. Resultado: menos ringing (artefatos na hipérbole), borda mais suave.

**Implementação:** `scipy.signal.firwin2` com frequências [0, fl, fc, fh, nyq] e ganhos [0, 0, 1, 0, 0] — ~10 linhas. Ativar via `"bandpass_tipo": "triangular"` no preset.

**Quando usar:** preset `270mhz_void` e `270mhz_concrete` onde ringing é problemático.

---

### A5 — Script importação CSV ground truth ⬅ MÉDIO
**O que faz:** permite Amilson importar validações de projetos anteriores (ex: PATIO com registros de obra) direto para `gpr_ground_truth` via CSV.

**Arquivo:** `scripts/import_ground_truth.py`

**Formato esperado:**
```csv
projeto,perfil,rank,x_m,depth_m_sistema,profundidade_real_m,tipo_confirmado,e_falso_positivo,observacoes
PATIO,PATIO_001,1,2.5,1.20,1.15,tubulacao_agua,false,"Tubo ferro galvanizado — registro de obra confirma"
```

**Implementação:** script Python standalone com argparse, lê CSV, valida campos obrigatórios, faz upsert em `gpr_ground_truth` via Supabase Python client.

---

### A6 — GROUND_TRUTH folder + README para Amilson ⬅ RÁPIDO
**O que é:** criar a estrutura de pasta e instruções claras para Amilson adicionar validações históricas.

**Estrutura:**
```
KB_ScansoloPlataform/GROUND_TRUTH/
├── README_AMILSON.md          ← instruções simples
├── template_validacao.csv     ← template com exemplos
├── PATIO/                     ← validações do projeto PATIO
├── HELPER/                    ← validações do dataset HELPER
└── CALIBRACAO/                ← alvos com profundidade conhecida
```

---

### A7 — Rodar os 126 DZTs HELPER no pipeline ⬅ OPERACIONAL
**O que é:** tarefa operacional — não requer código novo. Basta criar um job GPR para cada DZT HELPER e o worker existente processa.

**Como fazer:** script SQL ou server action que cria N processing_jobs em batch para os DZTs já no Storage.

---

## CATEGORIA B — Auto-calibração em produção (zero intervenção manual dedicada)

Estes itens **não precisam de sessão separada com Amilson**. Acontecem naturalmente conforme o sistema é usado:

| Item | Como funciona | Gatilho |
|---|---|---|
| Velocity por projeto | Amilson marca `e_referencia=True` + `profundidade_real_m` na revisão normal | Qualquer projeto com alvo de profundidade conhecida |
| Thresholds amplitude | `job_recalibrar` ajusta com VP/FP acumulados | Disparado mensalmente ou quando n≥50 amostras |
| Viés GPT-4o por tipo de obra | Acumula padrões em `gpr_ground_truth.tipo_confirmado` | Cada projeto validado |
| SNR gate por solo | Amilson ajusta `tipo_solo` na UI de Nova Entrada, feedback acumula | A cada projeto |

---

## CATEGORIA C — Realmente precisa de Amilson (e está OK diferir)

| Item | Por que precisa | Quando |
|---|---|---|
| Validação visual comparativa (pipeline v2.0.0 vs RADAN) | Julgamento técnico subjetivo | Primeiro projeto real |
| Confirmar qualidade dos 126 DZTs HELPER | Verificar se falsos positivos são reais | Após rodar os DZTs |
| Calibrar preset por tipo de solo em campo | Verificar velocity estimada vs. real em obra conhecida | 2º ou 3º projeto |

---

## ORDEM DE IMPLEMENTAÇÃO

| # | Item | Esforço | Impacto | Claude Code? |
|---|---|---|---|---|
| 1 | A1 — Velocity por solo (tabela publicada) | 30min | 🔴 Crítico | Sim |
| 2 | A2 — Amplitude thresholds (física EM) | 15min | 🔴 Crítico | Sim (junto com A1) |
| 3 | A3 — 6 presets por objetivo | 1h | 🟡 Alto | Sim |
| 4 | A5 — Script importação CSV ground truth | 1h | 🟡 Alto | Sim |
| 5 | A6 — GROUND_TRUTH folder + README | 15min | 🟢 Médio | Não (criar aqui) |
| 6 | A7 — Rodar 126 DZTs HELPER | 30min | 🟡 Alto | SQL simples |
| 7 | A4 — FIR Triangular bandpass | 1h | 🟢 Baixo | Sim |

---

## O QUE NÃO VAMOS IMPLEMENTAR AGORA

| Item | Razão |
|---|---|
| SVD/KL clutter removal | Risco: remove sinal real em solo urbano. Só após dataset > 200 projetos. |
| SEC gain | Diferença marginal vs tpow+AGC atual. Validar com Amilson primeiro. |
| Stolt migration | Requer `irlib` do GPRPy. Kirchhoff numpy atual é suficiente. |
| Deconvolução | Complexo. Ganho real incerto sem validação quantitativa. |
| YOLO/CNN em patches | Precisa de n > 500 alvos validados. Horizonte 6–12 meses. |

---

## TABELA DE REFERÊNCIA — Velocidade EM (publicada)

Baseado em USACE (1995), Daniels (2004), Reynolds (1997), GuidelineGEO, CLU-IN EPA:

| Material | εr min | εr max | v min (m/ns) | v max (m/ns) | v recomendado (m/ns) |
|---|---|---|---|---|---|
| Ar | 1 | 1 | 0.300 | 0.300 | — |
| Água doce | 81 | 81 | 0.033 | 0.033 | — |
| Areia seca | 4 | 6 | 0.122 | 0.150 | **0.130** |
| Areia saturada | 20 | 30 | 0.055 | 0.067 | 0.060 |
| Aterro urbano (padrão) | 7 | 10 | 0.095 | 0.113 | **0.100** |
| Argila seca | 9 | 14 | 0.080 | 0.100 | 0.090 |
| Argila úmida | 14 | 22 | 0.064 | 0.080 | **0.070** |
| Argila saturada | 22 | 35 | 0.051 | 0.064 | 0.060 |
| Solo úmido/saturado | 22 | 40 | 0.047 | 0.064 | **0.060** |
| Cascalho/rocha seca | 5 | 8 | 0.106 | 0.134 | **0.115** |
| Concreto | 6 | 10 | 0.095 | 0.122 | 0.107 |
| Asfalto seco | 3 | 5 | 0.134 | 0.173 | 0.150 |

Nosso mapeamento atual: todos usam 0.10 — correto apenas para `standard`.

---

## TABELA DE REFERÊNCIA — Coeficiente de Reflexão (física EM)

R = (√ε₁ − √ε₂) / (√ε₁ + √ε₂), com ε₁ = solo padrão (εr=9)

| Objeto Enterrado | εr | R (magnitude) | Classificação sugerida |
|---|---|---|---|
| Metal (condutor perfeito) | ∞ | 1.00 | metal |
| Cabo elétrico cobre | ∞ | ≈ 0.95 | metal |
| Tubo aço galvanizado | ∞ | ≈ 0.92 | metal |
| Vazio / ar | 1 | 0.50 | nao_metal (vazio) |
| Tubo com água | 81 | 0.50 | nao_metal (água) |
| Tubo HDPE/PE | 2.3 | 0.33 | nao_metal |
| Tubo PVC | 3.0 | 0.27 | nao_metal |
| Galeria de concreto | 7.0 | 0.06 | inconclusivo |
| Variação de solo | — | < 0.10 | descartado |

**Thresholds derivados:**
- `fis_amp_metal_thr = 0.65` (gap entre metal≥0.90 e vazio≈0.50)
- `fis_amp_nao_metal_thr = 0.22` (gap entre PVC≈0.27 e concreto≈0.06)
