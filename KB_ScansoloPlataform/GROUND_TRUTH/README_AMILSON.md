# GROUND TRUTH — Guia para Amilson

Esta pasta é onde você registra **o que você sabe que é verdade** sobre alvos detectados em projetos GPR.

O sistema usa esses registros para:
1. Calibrar automaticamente os parâmetros do detector (amplitudes, profundidade mínima)
2. Validar se as profundidades calculadas pelo pipeline estão corretas
3. Melhorar as classificações futuras (metal vs. PVC vs. vazio)

---

## Como adicionar validações

### Opção 1 — Via UI (mais fácil)

Na tela de Revisão Técnica de qualquer projeto:
- Marque **"É referência"** num alvo onde você sabe a profundidade real
- Preencha **"Profundidade real (m)"** com o valor medido/documentado
- Salva automaticamente em `gpr_ground_truth`

### Opção 2 — Via CSV (para validações em lote ou histórico)

1. Copie o arquivo `template_validacao.csv` desta pasta
2. Preencha com seus dados
3. Execute:

```bash
cd scansolo-platform/services/worker
SUPABASE_URL=<url> SUPABASE_SERVICE_ROLE_KEY=<key> \
python scripts/import_ground_truth.py --csv GROUND_TRUTH/PATIO/validacoes_patio.csv

# Para testar sem gravar:
python scripts/import_ground_truth.py --csv validacoes.csv --dry-run
```

---

## Colunas do CSV

| Coluna | Obrigatório | Descrição |
|---|---|---|
| `projeto` | Sim | Código do projeto (ex: PT-GPR-SOL-036) |
| `perfil` | Sim | Nome do DZT sem extensão (ex: PATIO_001) |
| `rank` | Sim | Número do alvo conforme CSV do pipeline |
| `x_m` | Não | Posição horizontal do alvo em metros |
| `depth_m_sistema` | Não | Profundidade calculada pelo sistema |
| `profundidade_real_m` | Não | **Profundidade real medida/confirmada** |
| `tipo_confirmado` | Não | Tipo real do alvo (ver lista abaixo) |
| `e_falso_positivo` | Não | `true` se o alvo é ruído/artefato (não existe) |
| `observacoes` | Não | Notas livres (fonte da informação, método de verificação) |

**Tipos aceitos:** `tubulacao_agua`, `tubulacao_gas`, `tubulacao_esgoto`, `cabo_eletrico`, `cabo_telecom`, `galeria_concreto`, `vazio_ar`, `rocha`, `inconclusivo`, `desconhecido`

---

## Exemplos de fontes válidas

- Registro de obra ou as-built confirmando posição de tubulação
- Escavação de confirmação (potholing)
- Pipe locator confirmando existência e profundidade
- Levantamento anterior de referência (RADAN com cota conhecida)
- Inspeção visual de caixa de passagem ou manholo

---

## Estrutura de pastas sugerida

```
GROUND_TRUTH/
├── README_AMILSON.md          ← este arquivo
├── template_validacao.csv     ← template em branco
├── PATIO/
│   └── validacoes_patio.csv   ← validações do projeto PATIO
├── HELPER/
│   └── validacoes_helper.csv  ← validações do dataset HELPER
└── CALIBRACAO/
    └── alvos_referencia.csv   ← alvos com profundidade confirmada por escavação
```

---

## Pergunta frequente

**"Preciso preencher tudo?"**

Não. Cada coluna opcional que você preencher torna o sistema mais inteligente numa dimensão diferente:
- `profundidade_real_m` → calibra velocity do solo
- `tipo_confirmado` → calibra classificação por material
- `e_falso_positivo = true` → calibra threshold de amplitude e profundidade mínima

Um registro com só `profundidade_real_m` já é valioso. Preencha o que você sabe.
