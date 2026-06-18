# Manual de Uso — ScanSOLO Platform
> Versão: 2026-06-18 (Fase 15 + estabilização)

---

## Visão geral do fluxo

```
Nova Entrada → Upload DZTs → [processamento automático] → Revisar → Cartografia → Relatório
                                         ↓
                              Ajustar Filtros (por perfil)
                              Pipeline Log (por perfil)
```

Cada projeto passa por uma sequência de jobs automáticos:

| Etapa | Status do projeto | O que acontece |
|---|---|---|
| 1 | `processando_gpr` | Pipeline GPR: filtragem, detector, 5 imagens por DZT |
| 2 | `processando_ia` | GPT-4o interpreta cada alvo detectado |
| 3 | `ia_concluida` | Aguarda revisão técnica do Amilson |
| 4 | `revisao_concluida` | Gera imagem interpretada com alvos aprovados |
| 5 | `aguardando_cartografia` | Exporta DXF, KML, GeoJSON, CSV |
| 6 | `aguardando_relatorio` | Gera DOCX + PDF |

---

## As 5 saídas de imagem por DZT

Cada arquivo DZT gera 5 imagens distintas, disponíveis nas abas da tela do projeto.

### Bruta

**O que é:** Visualização do dado bruto sem nenhum filtro aplicado. Gerada com GPRPy diretamente do DZT.

**Quando usar:** Diagnóstico — verificar se o equipamento registrou o dado corretamente. Referência para comparar o antes/depois dos filtros.

**O que NÃO está nessa imagem:** Sem correção de ganho, sem dewow, sem bandpass.

---

### Técnica (`_radargrama_cientifico.png`)

**O que é:** Resultado após dewow + bandpass + tpow (ganho linear com o tempo). Sem AGC, sem bgremoval.

**Quando usar:** Revisão técnica pelo Amilson. Base para as anotações do detector. A ausência de AGC preserva as amplitudes relativas reais — essencial para classificar material (metal vs. plástico vs. vazio).

**O que NÃO está nessa imagem:** Sem AGC (sem nivelamento de amplitude com profundidade). Por isso parecer mais escura nas camadas profundas comparada à imagem Relatório.

**Interpretação:** Hipérboles aparecem mais "limpas" porque o AGC não distorce os picos. Conteúdo energético no topo = sinal direto/reflexão superficial.

---

### Relatório (`_radargrama_relatorio.png` / `_processada.png`)

**O que é:** Resultado após dewow + bandpass + bgremoval + tpow + AGC. Otimizada visualmente para cliente.

**Quando usar:** Apresentação ao cliente, impressão no relatório PDF.

**O que NÃO está nessa imagem:** Amplitudes absolutas foram equalizadas pelo AGC — não use para classificar material.

**bgremoval:** Remove faixas horizontais de ruído de fundo. Melhora legibilidade mas também remove parte do sinal de reflexões horizontais (como pisos).

---

### Visual (`_radargrama_preview_radan_5m.png`)

**O que é:** Visualização equivalente ao output do RADAN (software GSSI), para comparação direta com o que o campo já conhece. Pipeline: arr_dewow_bp → AGC(window=80), profundidade configurável (padrão: 5 m).

**Quando usar:** Comparação visual lado a lado com o RADAN. Validação de que o pipeline produz resultado similar ao software comercial.

**Profundidade:** Por padrão 5 m (independente da velocity). Configurável em "Ajustar filtros" (`depth_preview_m`) e em Nova Entrada.

**Nota honesta:** A janela AGC=80 foi escolhida empiricamente para aproximar o estilo visual do RADAN. Não é uma calibração rigorosa — pode variar entre modelos de equipamento.

---

### Anotada IA (`_anotada_completa.png`)

**O que é:** Imagem Técnica com as hipérboles detectadas sobrepostas como anotações — posição, profundidade, diâmetro estimado, score de confiança, tipo de material.

**Quando usar:** Inspeção do resultado do detector. Verificar quais alvos foram detectados e com qual confiança.

**Score:** 0–100. Alvos com score ≥ 40 aparecem na imagem. Alvos com score ≥ 30 vão para o CSV (revisão técnica).

**Tipo de material:** Classificado por amplitude relativa (metal: alta, não-metal: média-baixa) usando coeficientes de Fresnel. **Atenção: esta classificação ainda não foi validada com alvos de tipo conhecido. Ver P6 em known_issues.md.**

---

## Presets de processamento

Presets são conjuntos de parâmetros do pipeline. Cada projeto usa um preset como base, com possibilidade de sobrescrita por projeto.

### Presets do sistema (is_system=true)

| Preset | Uso típico | Diferença principal |
|---|---|---|
| `270mhz` | Solo misto, padrão | Base para os demais |
| `270mhz_clay` | Solo argiloso/úmido | velocity=0.07, bgremoval=20 |
| `270mhz_sandy` | Solo arenoso/seco | velocity=0.13, AGC=200 |
| `270mhz_deep` | Alvos 3–5 m | tpow=0.80, AGC=100 |
| `270mhz_void` | Vazios, galerias | bandpass triangular FIR |
| `270mhz_concrete` | Laje/piso concreto | velocity=0.107, det_h_max=0.50 |

### Como criar um preset personalizado

**Opção 1 — Via Nova Entrada:**
1. Selecione um preset base
2. Personalize os parâmetros no accordion "Personalizar parâmetros"
3. Clique "+ Salvar como novo preset" antes de enviar o formulário
4. Dê um nome e confirme — o novo preset aparece no dropdown imediatamente

**Opção 2 — Via Ajustar filtros (após processamento):**
1. Na tela do projeto, abra "Ajustar filtros" de um perfil
2. Configure os filtros e reprocesse
3. Se o resultado for satisfatório, clique "Salvar como preset"

**Opção 3 — Via /presets:**
1. Acesse a página de presets
2. Clique em "Novo preset" ou "Duplicar" em um preset existente
3. Edite os parâmetros no modal

Presets do sistema são read-only — não podem ser editados ou deletados pela UI.

### Versionamento

Presets personalizados têm versionamento (`version`) e campo de validação (`validated_by/at`). Um preset pode ser marcado como "validado" após ser testado com dados reais (via botão "Validar" na página /presets).

---

## Velocity e escala de profundidade

### O que é velocity

A velocity eletromagnética no solo (m/ns) relaciona o tempo de chegada do eco (ns) com a profundidade física:

```
profundidade (m) = twtt_ns × velocity (m/ns) / 2
```

onde twtt = tempo total de viagem (ida + volta).

### Valores por tipo de solo (literatura)

| Solo | velocity_mns | εr ref |
|---|---|---|
| Padrão / misto | 0.100 | ~9 |
| Arenoso / seco | 0.130 | ~5 |
| Argiloso | 0.070 | ~18 |
| Úmido / encharcado | 0.060 | ~28 |
| Pedregoso | 0.115 | ~6 |

**Nota honesta:** Esses valores são derivados de literatura (USACE 1995, Daniels 2004, Reynolds 1997). Não foram validados com dados reais do ScanSOLO. Para projetos críticos, calibrar com alvos de profundidade conhecida.

### De onde vem a velocity usada

O Pipeline Log (seção "Escala e Profundidade") mostra a velocity e sua fonte:

| Fonte exibida | Significa |
|---|---|
| `preset` | Definida no preset selecionado |
| `VELOCITY_POR_SOLO[tipo]` | Derivada automaticamente do tipo de solo |
| `filtros_customizados` | Sobrescrita via "Ajustar filtros" ou ao criar o projeto |

Hierarquia de precedência: `filtros_customizados` > `preset` > `VELOCITY_POR_SOLO[tipo]`

### Atualizar velocity após processamento

**Atualizar velocity global do projeto** (painel "Atualizar velocity do projeto"):
- Recalcula e salva `profundidade_max_m` nos metadados de todos os perfis
- Salva a nova velocity em `processing_config` para próximos processamentos
- **NÃO regenera as imagens** — as imagens PNG existentes não mudam
- Use isso para corrigir o registro histórico de profundidade sem reprocessar

**Regenerar imagens com nova velocity** (via "Ajustar filtros" por perfil):
- Abra "Ajustar filtros" no perfil desejado
- Altere `velocity_mns`
- Clique "Reaplicar filtros"
- O worker reprocessa o DZT com a nova velocity e atualiza todas as imagens

### Preview Visual (5 m)

A imagem Visual usa a velocity do preset para calcular a escala, mas a profundidade do eixo Y é configurável (`depth_preview_m`). Por padrão: 5 m. Isso é independente da profundidade real do levantamento.

O Pipeline Log mostra:
- **Visual — eixo Y:** profundidade configurada (ex: 5.00 m, configurado ou padrão)
- **Visual — prof. física:** profundidade real calculada pela velocity (twtt × v/2)
- Se eixo Y > prof. física: a parte inferior da imagem Visual será "espaço vazio" (sem sinal)

---

## Ajustar filtros por perfil

O painel "Ajustar filtros" permite reprocessar um DZT individual com parâmetros diferentes do preset original.

### Parâmetros disponíveis

| Grupo | Parâmetro | Efeito |
|---|---|---|
| Filtragem | `dewow_window` | Remove deriva de baixa frequência |
| Filtragem | Bandpass ON/OFF + range | Filtra fora da banda da antena |
| Filtragem | `bgremoval_traces` | Remove fundo horizontal (ruído sistemático) |
| Filtragem | `tpow_power` | Ganho linear com profundidade |
| Filtragem | `agc_window` | Equalização de amplitude |
| Velocity | `velocity_mns` | Escala de profundidade |
| Visual | `depth_preview_m` | Profundidade do eixo Y da imagem Visual |
| Visual | `agc_window_preview` | AGC da imagem Visual |
| Contraste | `contrast` | Contraste das imagens |
| Detector | `det_amp_threshold` | Limiar de amplitude para detecção |
| Detector | `det_h_max_m` | Profundidade máxima de busca |
| Detector | `det_depth_min_m` | Profundidade mínima (evita onda direta) |

### Quando usar bandpass OFF

O bandpass filtra frequências fora da banda principal da antena (padrão: 80–500 MHz). Deve ser desligado apenas quando o DZT tem SNR muito alto e hipérboles estão sendo distorcidas pelo ringing do filtro. Na maioria dos levantamentos, deixar ligado.

**Regra:** DZTs ruidosos precisam do bandpass. DZTs com sinal limpo e forte (ex: HELPER — solo seco/pedregoso) podem se beneficiar de desligar.

### Reprocessamento

Após clicar "Reaplicar filtros", o worker cria um novo `run_id` e reprocessa o DZT. A UI faz polling a cada 5 s e recarrega automaticamente quando o job conclui. As imagens antigas ficam preservadas no Storage (nunca sobrescritas).

O Pipeline Log mostra o "Estado atual" (antes de reprocessar) e, após o reprocessamento, exibe um diff antes/depois das contagens de alvos.

---

## Pipeline Log

O Pipeline Log (colapsável por perfil, na seção de imagens) mostra:

### Modo compacto (linha horizontal)
Exibe: modo de processamento (mínimo/padrão/agressivo), SNR ratio, contagem de alvos ≥30 (alta + média).

### Modo completo (timeline vertical)

| Seção | O que mostra |
|---|---|
| Leitura do DZT | Preset, arquivo, traços, distância |
| Bandpass | Status (ativo/desativado), range MHz, tipo (butterworth/triangular) |
| Escala e Profundidade | Velocity, fonte, prof. técnica, prof. e velocity da imagem Visual |
| SNR Gate | SNR raw (dB), ratio, modo selecionado (mínimo/padrão/agressivo) |
| SNR Pós-Filtros | SNR após cada estágio de filtragem |
| Migração F-K | Kirchhoff numpy (disponível/não disponível) |
| Detector | Modo de entrada, score mínimo, prof. mínima |
| Imagens Geradas | Flags ✓/✗ para cada uma das 5 imagens |

**"Log não disponível"** aparece para perfis processados antes da Fase 11 (quando o upload do `pipeline_metrics.json` foi implementado). O log fica disponível após reprocessar o perfil.

---

## Detector de hipérboles

O detector passa por três estágios:

1. **Hough:** Detecta candidatos (arcos de hipérbole) por transformada de Hough adaptada
2. **CurveFit:** Ajuste de mínimos quadrados para confirmar a hipérbole e estimar velocity local
3. **DeltaT:** Estima diâmetro do objeto pela diferença temporal entre reflexão no topo e no fundo

### Score (0–100)

Combinação ponderada de: ajuste geométrico da hipérbole (CurveFit R²), amplitude relativa, consistência física (fase, tipo de material), SNR local.

| Score | Label técnico | Label relatório |
|---|---|---|
| ≥ 70 | alta | alta |
| 40–69 | media | média |
| 30–39 | baixa | baixa |
| < 30 | rejeitado | não aparece |

### Modo de entrada do detector

Por padrão (v2.0.0): o detector opera sobre o dado bruto (`arr_raw`). Isso resultou em 82% de CurveFit vs. 24% com AGC, e reduziu falsos positivos em ~46% nos dados PATIO.

**Nota honesta:** Essa calibração foi feita com o dataset PATIO (4 DZTs). Ainda não validado com dados de solo argiloso, úmido ou pedregoso.

### Profundidade mínima (`det_depth_min_m`)

Padrão: 0.30 m. Evita detectar a onda direta (sinal que vai pelo ar de Tx para Rx diretamente). Em solos com SNR muito alto, pode ser necessário aumentar para 0.40–0.50 m.

---

## Interpretação de IA (GPT-4o)

Após a detecção, o GPT-4o recebe cada alvo (crop da imagem + dados físicos) e classifica:

**Categorias:** `tubulacao_agua`, `tubulacao_gas`, `tubulacao_esgoto`, `cabo_eletrico`, `cabo_telecom`, `galeria_concreto`, `vazio_ar`, `rocha`, `inconclusivo`

O prompt injeta contexto do projeto: tipo de obra, área, frequência da antena.

**Nota honesta:** O GPT-4o tem viés para `galeria_concreto` em contextos sem projeto definido (observado em dataset HELPAVPA). Injetar o contexto do projeto mitiga esse viés, mas não foi validado em dados de produção.

**Revisão obrigatória:** A IA fornece sugestão inicial. Toda classificação deve ser revisada pelo Amilson na tela de revisão técnica antes de ir para o relatório.

---

## Dashboard de qualidade e recalibração

### Acesso
`/admin/qualidade` — visível apenas para `socio` e `admin`.

### Loop de aprendizado

1. Amilson valida alvos manualmente (via `/treinamento` — wizard 4 passos)
2. Validações são salvas em `gpr_ground_truth`
3. Com ≥ 20 amostras: botão "Disparar recalibração" → `job_recalibrar`
4. O job otimiza thresholds (score, amplitude, prof. mínima) por F1-score
5. Candidato JSON é gerado em Storage — **não aplicado automaticamente**
6. Revisar candidato no modal em `/treinamento` → se aprovado, "Aplicar ao preset"

**Nota:** A recalibração automática ainda não tem amostras suficientes para gerar resultados confiáveis. Prioridade: acumular ≥ 20 validações com o Amilson antes de usar.

---

## Personas e permissões

| Ação | operador_campo | tecnico | socio / admin |
|---|---|---|---|
| Criar projeto (Nova Entrada) | ✓ | ✓ | ✓ |
| Ver/reprocessar projetos próprios | ✓ | — | — |
| Ver/reprocessar projetos assigned_to | — | ✓ | — |
| Ver todos os projetos | — | — | ✓ |
| Criar/editar presets | — | — | ✓ |
| Dashboard qualidade | — | — | ✓ |
| Deletar projetos | — | — | ✓ |

---

## Pendências conhecidas e limitações

Ver lista completa em [docs/known_issues.md](known_issues.md).

**As mais relevantes para uso em produção:**

| Item | Resumo |
|---|---|
| P2 | Velocity não calibrada com alvos de profundidade conhecida — usar tabela literatura |
| P6 | Classificação metal/não-metal não validada em campo |
| P8 | Detector validado com 13/126 imagens HELPAVPA — parcial |
| P12 | Deletar projeto não remove arquivos do Storage |

---

## Perguntas frequentes

**O Pipeline Log mostra "Log não disponível" — o que significa?**
O perfil foi processado antes da Fase 11 (sem upload do `pipeline_metrics.json`). Reprocessar o perfil via "Ajustar filtros" resolve.

**Cliquei em "Atualizar velocity" mas as imagens não mudaram — por quê?**
O botão só atualiza metadados no banco (profundidade em metros). Para regenerar as imagens com a nova escala, use "Ajustar filtros" no perfil e clique "Reaplicar filtros" com a nova velocity.

**Posso processar sem a IA do GPT-4o?**
Sim: marque "Pular IA (skip_ia)" em Nova Entrada. O pipeline roda normalmente mas o job de IA não é criado.

**O que acontece se reprocessar um perfil já revisado?**
O reprocessamento gera um novo `run_id`. As revisões anteriores (technical_reviews) ficam no banco referenciando o run antigo. As novas imagens são geradas, mas a revisão precisa ser refeita se necessário.

**Bandpass ON ou OFF para dados HELPER?**
HELPER tem solo pedregoso/seco (SNR alto). Se o detector estiver gerando muitos falsos positivos ou as hipérboles estiverem com ringing visível, teste com bandpass OFF. Mas comece com ON e monitore o resultado.
