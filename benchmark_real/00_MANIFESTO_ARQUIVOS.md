# Manifesto de Arquivos — benchmark_real/
> Atualizado: 2026-06-12
> Propósito: rastrear origem, integridade e uso de cada conjunto de dados nesta pasta.

---

## Arquivos ORIGINAIS — não tocar

### PATIO/ (4 DZTs)
| Arquivo | Origem | Status |
|---------|--------|--------|
| `PATIO/PATIO/PATIO___001 (1).DZT` | Campo ScanSOLO — projeto Patio | ✅ Intacto |
| `PATIO/PATIO/PATIO___002.DZT` | Campo ScanSOLO — projeto Patio | ✅ Intacto |
| `PATIO/PATIO/PATIO___003.DZT` | Campo ScanSOLO — projeto Patio | ✅ Intacto |
| `PATIO/PATIO/PATIO___004 (1).DZT` | Campo ScanSOLO — projeto Patio | ✅ Intacto |

### HELPER/ (126 DZTs + 126 imagens RADAN)
| Conjunto | Conteúdo | Status |
|----------|----------|--------|
| `HELPER/HELPER.PRJ_DZT/HELPER_0001.dzt` a `HELPER_0126.DZT` | 126 DZTs brutos do projeto HELPER | ✅ Intactos — leitura somente |
| `HELPER/HELPAVPA_imagens_processadas_radan/HELPER_XXXX_radargrama.jpg` | 126 radargramas processados pelo RADAN (software Amilson) — referência de qualidade | ✅ Intactos — não alterar |

### EXEMPLOS_GERAIS_SAÍDAS_ATUAIS_CLIENTE/
| Conteúdo | Status |
|----------|--------|
| 12 imagens JPEG — exemplos de saídas entregues a clientes | ✅ Intactos |

---

## Saídas geradas pelo pipeline — podem ser recriadas

### services/worker/pipeline/benchmark_real/04_benchmarks_detector/

| Pasta | DZTs | Modo | Tamanho | Status |
|-------|------|------|---------|--------|
| `PATIO/raw/` | 4/4 | raw (82% CF) | ~180M | ✅ Completo |
| `PATIO/raw_dewow_bandpass/` | 4/4 | raw+dewow+bp (75% CF) | ~180M | ✅ Completo |
| `PATIO/sem_agc/` | 4/4 | sem_agc (70% CF) | ~180M | ✅ Completo |
| `PATIO/proc_agc_atual/` | 4/4 | proc+AGC (24% CF) | ~180M | ✅ Completo |
| `HELPER/raw/` | 126/126 | raw | ~733M | ✅ Completo |
| `HELPER/raw_dewow_bandpass/` | 121/126 | raw+dewow+bp | ~751M | ✅ Completo |
| `HELPER/sem_agc/` | 126/126 | sem_agc | ~762M | ✅ Completo |
| `HELPER/proc_agc_atual/` | 126/126 | proc+AGC | ~772M | ✅ Completo |

**Total gerado:** ~3.8G em `04_benchmarks_detector/`

### services/worker/pipeline/_test_v2_output/
Saída de teste do pipeline v2.0.0 em PATIO (4 DZTs). Arquivo-chave: `index_projeto.csv`.

---

## Pacote de validação para Amilson

### benchmark_real/05_validacao_amilson/pacote_visual_v2/
| Pasta | Conteúdo |
|-------|----------|
| `PATIO/` | PATIO_001 e PATIO_003 — bruta, científica, relatório, anotada, CSV |
| `HELPER/` | 5 exemplos com mais alvos (0081, 0075, 0053, 0013, 0012) — bruta, científica, relatório, anotada, CSV + RADAN correspondente |
| `paineis_comparativos/` | 7 painéis PNG com RADAN vs Científico vs Relatório vs Anotada lado a lado |

---

## Documentação técnica

| Arquivo | Conteúdo |
|---------|----------|
| `06_docs/IMPLEMENTACAO_ARQUITETURA_GPR_V2.md` | Descrição técnica das mudanças v2.0.0 |
| `06_docs/DECISOES_TECNICAS.md` | 10 decisões técnicas documentadas |
| `06_docs/PACOTE_VALIDACAO_AMILSON_V2.md` | Documento de validação para Amilson |
| `00_MANIFESTO_ARQUIVOS.md` | Este arquivo |

---

## Regra de integridade

**NUNCA:**
- Apagar arquivos da pasta `HELPER/HELPER.PRJ_DZT/`
- Apagar arquivos da pasta `PATIO/PATIO/`
- Apagar imagens RADAN da pasta `HELPER/HELPAVPA_imagens_processadas_radan/`
- Sobrescrever arquivos originais com saídas de processamento

**PODE:**
- Recriar qualquer pasta em `04_benchmarks_detector/` rodando o pipeline novamente
- Recriar qualquer pasta em `05_validacao_amilson/` com o script de cópia
- Adicionar novas pastas de benchmark sem apagar as existentes
