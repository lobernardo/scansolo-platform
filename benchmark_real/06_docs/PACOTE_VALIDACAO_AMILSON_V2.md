# Pacote de Validação para Amilson — Pipeline v2.0.0
> Preparado por: Leo / Claude Code
> Data: 2026-06-12
> Objetivo: validação técnica das imagens e detecções geradas pelo pipeline ScanSOLO v2.0.0

---

## O que mudou na v2.0.0 (resumo para Amilson)

### Antes (v1.2.0)
O pipeline gerava uma única imagem processada por DZT, usando a cadeia completa:
```
DZT → dewow → bandpass → bgremoval → tpow → AGC → imagem_processada.png
```
O detector de hipérboles recebia esse mesmo array com AGC.

**Problema identificado:** O AGC (Automatic Gain Control) distorce o formato das hipérboles.
O CurveFit (ajuste de curva nos candidatos) estava convergindo em apenas 24% dos casos.
46% dos candidatos eram falsos positivos da airwave superficial (<0.18m de profundidade)
equalizada pelo AGC.

### Depois (v2.0.0) — TRÊS IMAGENS por DZT
```
DZT → dewow → bandpass → [BIFURCAÇÃO]
                              |
              [tpow]          |         [bgremoval → tpow → AGC]
                |             |                   |
    _radargrama_cientifico    |         _radargrama_relatorio
    (SEM bgremoval, SEM AGC)  |         (com bgremoval + AGC)
                              |
              DETECTOR usa dado RAW (bruto, sem filtros)
              → CurveFit sobe de 24% para 82%
              → Filtro depth_min=0.30m descarta candidatos superficiais
              → Anotações desenhadas sobre radargrama_cientifico
```

---

## Por que agora existem imagem científica e imagem de relatório?

| | Científica | Relatório |
|---|---|---|
| **Filtros** | dewow + bandpass + tpow | dewow + bandpass + bgremoval + tpow + AGC |
| **BGRemoval** | NÃO — preserva refletores horizontais | SIM — remove fundo, limpa imagem |
| **AGC** | NÃO — preserva amplitude real | SIM — equaliza profundidade, visual uniforme |
| **Para que serve** | Revisão técnica do Amilson | Entrega ao cliente / PDF do relatório |
| **Parece com RADAN?** | Mais ruidosa, mais informação real | Mais limpa, mais parecida com RADAN |
| **Anotações** | Sim — candidatos desenhados sobre ela | Não |

**A imagem científica mostra mais. A imagem de relatório parece melhor visualmente.**

---

## Por que o detector não usa mais a imagem processada com AGC?

Experimento com os 4 DZTs PATIO, comparando a taxa de CurveFit por modo de entrada:

| Modo de entrada | Taxa CurveFit | Score médio | Falsos positivos |
|-----------------|---------------|-------------|-----------------|
| RAW (v2.0.0) | **82%** | 56.8 | baixo |
| Raw + Dewow + BP | 75% | 51.6 | baixo |
| Sem AGC (bgremoval+tpow) | 70% | 42.7 | médio |
| **Com AGC (v1.2.0)** | **24%** | 28.0 | **ALTO (46%)** |

O AGC equaliza a amplitude de cima a baixo — isso distorce o formato físico das hipérboles.
O CurveFit falha porque o shape que ele tenta ajustar foi deformado.

No dado RAW, o formato hiperbolico é preservado. CurveFit converge 3x mais.

---

## Resultados PATIO — v2.0.0 (solo padrão, 270 MHz)

| DZT | SNR raw | SNR cient | SNR rel | Alvos | Alta | Média | fit_ok% | depth_min rm |
|-----|---------|-----------|---------|-------|------|-------|---------|--------------|
| PATIO_001 | 20.6 dB | 26.1 dB | -4.1 dB | 24 | 1 | 21 | 96% | 0 |
| PATIO_002 | 17.5 dB | 23.5 dB | -4.1 dB | 21 | 5 | 16 | 100% | 0 |
| PATIO_003 | 18.7 dB | 24.9 dB | -1.7 dB | 19 | 4 | 12 | 79% | 1 |
| PATIO_004 | 17.5 dB | 23.8 dB | -3.2 dB | 22 | 4 | 17 | 95% | 0 |
| **TOTAL** | **18.6 dB** | **24.6 dB** | **-3.3 dB** | **86** | **14** | **66** | **93%** | **1** |

**Modo de processamento:** PADRAO (SNR raw 17-20 dB → normal para solo de pátio)
**Detector:** arr_raw, depth_min=0.30m

---

## Resultados HELPER — v2.0.0, modo RAW (solo padrão, 270 MHz → MINIMO)

**Observação importante:** O dataset HELPER tem SNR raw médio de 50.8 dB (vs 18.6 dB no PATIO).
O pipeline entrou em modo MINIMO para 120/126 DZTs, o que significa:
- Bandpass PULADO (sinal muito limpo, bandpass pode inserir artefatos)
- TPow reduzido (0.3 em vez de 0.5)
- AGC janela maior (300 em vez de 150)

| Métrica | Valor |
|---------|-------|
| DZTs processados | 126/126 |
| DZTs com alvos detectados | 90/126 (71%) |
| DZTs sem alvos (0) | 30/126 (24%) |
| Total alvos (score ≥ 30) | 331 |
| CurveFit ok | 170/331 (51%) |
| Candidatos removidos pelo depth_min | **492** |
| SNR raw médio | 50.8 dB |
| SNR científico médio | 37.1 dB |
| SNR relatório médio | 26.4 dB |

**ALERTA depth_min:** foram removidos 492 candidatos com depth < 0.30m no dataset HELPER.
No PATIO foram apenas 1. Isso indica que o HELPER pode ter:
a) Muitas tubulações rasas (< 0.30m) que o filtro está removendo
b) Ou a airwave está sendo detectada como candidatos neste solo (diferente do PATIO)
**Amilson precisa confirmar qual é o caso.**

---

## Arquivos para Amilson abrir primeiro

### Pasta: `05_validacao_amilson/pacote_visual_v2/paineis_comparativos/`
*(Painéis lado a lado — abrir como imagem no Windows ou Fotos)*

| Arquivo | Conteúdo | Prioridade |
|---------|----------|-----------|
| `painel_HELPER_0013.png` | RADAN vs Científico vs Relatório vs Anotada — caso com RADAN conhecido | 1 |
| `painel_HELPER_0081.png` | 15 alvos detectados — caso mais rico do HELPER | 2 |
| `painel_PATIO___001 (1).png` | PATIO — solo de pátio, sem RADAN | 3 |
| `painel_HELPER_0012.png` | RADAN vs Científico vs Relatório vs Anotada | 4 |
| `painel_PATIO___003.png` | PATIO — 1 candidato removido pelo depth_min | 5 |
| `painel_HELPER_0075.png` | 11 alvos — exemplo HELPER intermediário | 6 |
| `painel_HELPER_0053.png` | 7 alvos — exemplo HELPER menor | 7 |

### Pasta: `05_validacao_amilson/pacote_visual_v2/HELPER/`
Para cada stem (0081, 0075, 0053, 0013, 0012):
- `HELPER_XXXX_radargrama.jpg` — RADAN original
- `HELPER_XXXX_radargrama_cientifico.png` — ScanSOLO v2.0.0 científico
- `HELPER_XXXX_radargrama_relatorio.png` — ScanSOLO v2.0.0 relatório
- `HELPER_XXXX_anotada_completa.png` — candidatos detectados
- `HELPER_XXXX_alvos.csv` — tabela de alvos

---

## Perguntas para Amilson responder

### P1 — A imagem científica preserva melhor informação?
Compare `_radargrama_cientifico.png` com a imagem RADAN correspondente.
A imagem científica (dewow+bp+tpow, sem bgremoval/AGC) mostra os refletores horizontais
e o decaimento de amplitude real. Parece mais útil para análise do que a processada com AGC?

### P2 — A imagem de relatório está boa para o cliente?
Compare `_radargrama_relatorio.png` com a imagem RADAN.
Esta imagem vai para o PDF final. Está visualmente adequada para entregar ao cliente?
Tem ruído excessivo? Contraste adequado?

### P3 — A anotada está legível?
Abra `_anotada_completa.png`. Os círculos/marcadores dos candidatos são visíveis?
A profundidade estimada parece razoável para os alvos que você reconhece no radargrama?

### P4 — Há excesso de alvos?
PATIO: 19-24 alvos por DZT (média 21.5).
HELPER top: até 15 por DZT, com muitos DZTs com 0 alvos.
O volume parece adequado ou precisa ajustar threshold?

### P5 — O filtro depth_min=0.30m removeu apenas airwave ou removeu alvo útil?
PATIO: apenas 1 candidato removido.
HELPER: 492 candidatos removidos!
No HELPER, há tubulações rasas (<0.30m) que deveriam aparecer nos radargramas?
Se sim, qual seria o depth_min mais adequado para esse tipo de solo?

### P6 — O modo detector RAW parece aceitável?
O detector agora recebe o dado bruto (sem filtros). Os candidatos detectados fazem sentido
fisicamente? Prefere que use Raw+Dewow+Bandpass (75% CurveFit) como alternativa?

---

## Contexto técnico (para referência)

**O que é CurveFit?**
Após o Hough detectar candidatos de hipérboles, rodamos um ajuste por mínimos quadrados
(CurveFit) para confirmar o formato hiperbólico. CurveFit ok = candidato tem shape de hipérbole real.
CurveFit falhou = candidato foi descartado ou recebeu score baixo.

**O que é depth_min?**
Profundidade mínima dos candidatos. Candidatos com `depth_m < 0.30m` são descartados antes
do CSV e do plot. Criado para eliminar a airwave (reflexão direta da onda no primeiro ns).

**Por que SNR científico > SNR raw?**
Dewow + Bandpass removem ruído (DC offset e frequências fora da banda). O sinal fica mais
limpo. SNR sobe +5-6 dB em PATIO.

**Por que SNR relatório < SNR raw?**
BGRemoval subtrai a média de 30 traços adjacentes — remove o fundo E parte do sinal.
O SNR em dB fica negativo. Isso é esperado e correto: o que importa é o resultado visual,
não o SNR absoluto pós-bgremoval.

---

## Como fornecer feedback

1. Abrir os painéis em `paineis_comparativos/`
2. Anotar observações por número do arquivo (ex: "HELPER_0013: a anotada tem 2 candidatos corretos e 1 errado na esquerda")
3. Enviar para Leo via WhatsApp ou email

**Se quiser ver mais exemplos:** avisar qual DZT do HELPER tem interesse e Leo gera o painel individual.

---

*Pacote preparado por Leo / Claude Code (Sonnet 4.6) em 2026-06-12*
*Não distribuir fora da ScanSOLO — contém dados de campo proprietários*
