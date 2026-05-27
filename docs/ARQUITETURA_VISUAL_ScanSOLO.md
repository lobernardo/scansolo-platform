# Arquitetura Visual — Plataforma ScanSOLO

> Versão: 0.1 — Maio 2026  
> Status: Decisões travadas, pré-implementação  
> Todos os diagramas em Mermaid (compatível GitHub / Obsidian / Notion)

---

## Índice

1. [Diagrama Geral da Plataforma](#1-diagrama-geral-da-plataforma)
2. [Fluxo Nova Entrada](#2-fluxo-nova-entrada)
3. [Fluxo A — Upload pelo Sistema](#3-fluxo-a--upload-pelo-sistema)
4. [Fluxo B — Arquivos já no Dropbox](#4-fluxo-b--arquivos-já-no-dropbox)
5. [Dropbox vs Supabase Storage](#5-dropbox-vs-supabase-storage)
6. [Worker Python — Processamento GPR](#6-worker-python--processamento-gpr)
7. [IA Automática — Pipeline Completo](#7-ia-automática--pipeline-completo)
8. [Revisão Opcional pelo Analista](#8-revisão-opcional-pelo-analista)
9. [Cartografia — Objetivo Final](#9-cartografia--objetivo-final)
10. [Geração de Relatório](#10-geração-de-relatório)
11. [Permissões por Perfil](#11-permissões-por-perfil)
12. [Estados do Projeto](#12-estados-do-projeto)
13. [Versionamento por Run](#13-versionamento-por-run)

---

## 1. Diagrama Geral da Plataforma

Visão macro de todos os componentes e suas integrações.

```mermaid
graph TB
    subgraph CAMPO["Campo / Operador"]
        OP[Operador de campo]
        TABLET[Tablet / Celular]
    end

    subgraph FRONTEND["Frontend — Next.js"]
        UI_UPLOAD[Upload de arquivos]
        UI_PROJ[Gestão de projetos]
        UI_CART[Visualizador cartografia]
        UI_REL[Gerador de relatório]
        UI_REV[Revisão analista]
    end

    subgraph SUPABASE["Supabase"]
        AUTH[Auth + RLS]
        DB[(PostgreSQL)]
        STORAGE[Storage\noutputs leves]
        REALTIME[Realtime\nstatus worker]
    end

    subgraph DROPBOX["Dropbox"]
        RAW[Arquivos brutos\n.DZT / .DT1 / .SGY]
        RUNS[Runs versionadas\nrun_001_... / run_002_...]
    end

    subgraph WORKER["Worker Python — Railway"]
        PIPELINE[pipeline_v1.py\ndetector_hiperboles.py]
        OPENAI_CLIENT[Cliente OpenAI]
    end

    OPENAI[OpenAI GPT-4o]

    OP -->|usa| TABLET
    TABLET -->|acessa| FRONTEND
    UI_UPLOAD -->|autentica via| AUTH
    UI_UPLOAD -->|envia arquivo| WORKER
    WORKER -->|salva bruto| RAW
    WORKER -->|processa GPR| PIPELINE
    PIPELINE -->|resultados| RUNS
    PIPELINE -->|outputs leves| STORAGE
    PIPELINE -->|atualiza status| DB
    WORKER -->|chama| OPENAI_CLIENT
    OPENAI_CLIENT -->|API| OPENAI
    OPENAI -->|interpretação| WORKER
    WORKER -->|salva análise IA| DB
    DB -->|RLS| FRONTEND
    STORAGE -->|imagens/CSV/PDF| FRONTEND
    REALTIME -->|push status| FRONTEND
```

> **Nota de portabilidade:** Next.js, Supabase, Railway e OpenAI GPT-4o estão aprovados para implementação inicial. A arquitetura preserva portabilidade futura: worker Python pode ser migrado para VPS/Docker sem alterar o pipeline; modelo de IA pode ser substituído se custo, escala ou performance exigirem.

---

## 2. Fluxo Nova Entrada

Decisão de roteamento quando um arquivo ou projeto novo chega ao sistema.

```mermaid
flowchart TD
    START([Novo arquivo detectado]) --> Q1{Origem?}

    Q1 -->|Upload via sistema| FLUXO_A[Fluxo A]
    Q1 -->|Já no Dropbox| FLUXO_B[Fluxo B]

    FLUXO_A --> A1[Frontend recebe arquivo]
    A1 --> A2[Valida extensão\n.DZT / .DT1 / .SGY]
    A2 -->|inválido| ERR_A[Erro: formato não suportado]
    A2 -->|válido| A3[Cria registro projeto\nno Supabase]
    A3 --> A4[Envia para Worker\nvia API call]
    A4 --> WORKER_ENTRY[Worker: inicia processamento]

    FLUXO_B --> B_Q{Detecção?}
    B_Q -->|Manual: botão\n'Assimilar Dropbox'| B1[Fluxo B1 — Manual]
    B_Q -->|Webhook Dropbox| B2[Fluxo B2 — Automático]

    B1 --> B1a[Analista escolhe pasta]
    B1a --> B1b[Sistema lê metadados\narquivos na pasta]
    B1b --> B1c[Cria registro projeto\nno Supabase]
    B1c --> WORKER_ENTRY

    B2 --> B2a[Webhook recebe evento\ncreate/modify]
    B2a --> B2b{Pasta monitorada?}
    B2b -->|não| IGNORE[Ignora]
    B2b -->|sim| B2c[Aguarda 30s\nstabilization window]
    B2c --> B2d[Cria registro projeto\nautomático]
    B2d --> WORKER_ENTRY

    WORKER_ENTRY --> PROC[Processamento GPR + IA]
```

---

## 3. Fluxo A — Upload pelo Sistema

Detalhe do caminho quando o arquivo sobe diretamente pelo frontend.

```mermaid
sequenceDiagram
    actor OP as Operador
    participant FE as Frontend Next.js
    participant SB as Supabase DB
    participant WK as Worker Railway
    participant DB as Dropbox
    participant ST as Supabase Storage

    OP->>FE: Seleciona arquivo .DZT
    FE->>FE: Valida extensão e tamanho
    FE->>SB: INSERT projeto (status=aguardando_arquivo)
    FE->>WK: POST /ingest {projeto_id, arquivo_base64}
    
    WK->>WK: Calcula SHA-256 do arquivo
    WK->>DB: Salva bruto em /projetos/{nome}/raw/
    WK->>SB: UPDATE projeto (status=arquivo_salvo, checksum=...)
    
    WK->>WK: Cria run_001_{data}_{hash8}/
    WK->>WK: Executa pipeline_v1.py
    WK->>SB: UPDATE projeto (status=processando_gpr)
    
    Note over WK: GPR processing...
    
    WK->>DB: Salva outputs run em /projetos/{nome}/runs/run_001.../
    WK->>ST: Upload imagens PNG e CSV leve
    WK->>SB: INSERT resultados_gpr
    WK->>SB: UPDATE projeto (status=aguardando_ia)
    
    WK->>WK: Monta prompt com resultados
    WK->>WK: Chama OpenAI GPT-4o
    WK->>SB: INSERT analise_ia
    WK->>SB: UPDATE projeto (status=aguardando_revisao)
    
    SB-->>FE: Realtime push: status atualizado
    FE-->>OP: Notificação: projeto pronto para revisão
```

---

## 4. Fluxo B — Arquivos já no Dropbox

Os dois sub-fluxos (manual e webhook) para arquivos que chegam diretamente ao Dropbox.

```mermaid
flowchart LR
    subgraph B1["Fluxo B1 — Manual"]
        B1_START([Analista clica\n'Assimilar Dropbox'])
        B1_LIST[Frontend lista pastas\nnão assimiladas]
        B1_SELECT[Analista seleciona pasta]
        B1_META[Worker lê metadados\narquivos na pasta]
        B1_CREATE[Cria projeto no DB]
    end

    subgraph B2["Fluxo B2 — Webhook"]
        B2_START([Dropbox dispara\nwebhook])
        B2_VERIFY[Worker verifica\nassinatura HMAC]
        B2_CHECK{Pasta\nmonitorada?}
        B2_WAIT[Aguarda 30s\njanela estabilização]
        B2_DUP{Projeto já\nexiste?}
        B2_CREATE2[Cria projeto\nautomático]
        B2_IGNORE([Ignora])
    end

    subgraph COMMON["Processamento Comum"]
        HASH[Calcula checksum\nSHA-256]
        RUN[Cria run_001_...]
        PIPELINE[Executa pipeline GPR]
        IA[Executa análise IA]
        STATUS[Atualiza status\nno Supabase]
    end

    B1_START --> B1_LIST --> B1_SELECT --> B1_META --> B1_CREATE --> HASH
    B2_START --> B2_VERIFY --> B2_CHECK
    B2_CHECK -->|não| B2_IGNORE
    B2_CHECK -->|sim| B2_WAIT --> B2_DUP
    B2_DUP -->|sim| B2_IGNORE
    B2_DUP -->|não| B2_CREATE2 --> HASH
    HASH --> RUN --> PIPELINE --> IA --> STATUS
```

---

## 5. Dropbox vs Supabase Storage

Regra clara de onde cada tipo de arquivo vive.

```mermaid
graph TB
    subgraph DROPBOX["Dropbox — Arquivos Pesados e Brutos"]
        direction TB
        D1["📁 /projetos/{nome_projeto}/"]
        D2["  📁 raw/\n  └── arquivo_original.DZT\n  └── arquivo_original.DZT.sha256"]
        D3["  📁 runs/\n  └── run_001_{data}_{hash8}/\n      ├── resultados.npy\n      ├── radargrama_processado.npy\n      └── config_used.json"]
        D1 --> D2
        D1 --> D3
    end

    subgraph SUPABASE["Supabase Storage — Camada de Visualização (não é fonte da verdade)"]
        direction TB
        S1["📁 /projetos/{nome_projeto}/"]
        S2["  📁 runs/run_001.../\n  ├── radargrama_anotado.png\n  ├── perfil_profundidade.png\n  ├── deteccoes_export.csv\n  └── mapa_preview.png"]
        S3["  📁 relatorios/\n  └── relatorio_v1.pdf"]
        S1 --> S2
        S1 --> S3
    end

    subgraph REGRA["Regra de Decisão"]
        R1["Dropbox: arquivos brutos,\nbinários pesados,\nnpy de runs\n> 1MB"]
        R2["Supabase Storage: imagens PNG,\nCSV exportáveis, PDFs de relatório\n< 50MB por arquivo\n(visualização — Dropbox é fonte da verdade)"]
        R3["Nunca: deletar arquivo bruto\nNunca: sobrescrever sem versionar"]
    end

    DROPBOX -.->|regra| REGRA
    SUPABASE -.->|regra| REGRA
```

---

## 6. Worker Python — Processamento GPR

Fluxo interno do worker durante o processamento de um arquivo GPR.

```mermaid
flowchart TD
    START([Worker recebe job]) --> LOAD[Baixa arquivo .DZT\ndo Dropbox]
    LOAD --> HASH[Calcula SHA-256\nverifica integridade]
    HASH --> READ[readgssi / segyio\nlê arquivo binário]
    READ --> RADARGRAMA[Monta matriz 2D\n radargrama bruto]
    RADARGRAMA --> GAINS[Aplica ganhos\nAGC + SEC + spread]
    GAINS --> MIGRATION[Migração Kirchhoff\nou F-K]
    MIGRATION --> DETECT[detector_hiperboles.py\ndetecta hipérboles]

    subgraph DETECTOR["Detector de Hipérboles"]
        D1[Janela deslizante\nHough Transform]
        D2[Ajuste parabólico\nfit_hyperbola]
        D3[Score multi-critério\n5 dimensões]
        D4[confidence_label_tecnico\nalta/média/baixa]
        D5[confidence_label_relatorio\nrequer fit+diam+ev_raw+ev_sem_agc]
        D1 --> D2 --> D3 --> D4
        D3 --> D5
    end

    DETECT --> DETECTOR
    DETECTOR --> NPY["Salva .npy atômico\ntempfile + os.replace"]
    NPY --> PNG[Gera PNGs anotados\nplotar_deteccoes]
    PNG --> CSV[Exporta CSV\n23 colunas]
    CSV --> INDEX[Atualiza index_projeto.csv\n42 colunas]
    INDEX --> DB_SAVE[Salva resultados\nno Supabase DB]
    DB_SAVE --> STORAGE[Upload outputs leves\nSupabase Storage]
    STORAGE --> DONE([Job concluído\nstatus=aguardando_ia])
```

---

## 7. IA Automática — Pipeline Completo

A análise de IA é sempre automática após o GPR. Não é opcional.

```mermaid
sequenceDiagram
    participant WK as Worker
    participant SB as Supabase DB
    participant AI as OpenAI GPT-4o

    Note over WK: GPR processing complete
    WK->>SB: SELECT resultados_gpr WHERE projeto_id=X
    WK->>WK: Filtra detecções confidence_label_relatorio='alta'
    WK->>WK: Monta contexto: profundidades, diâmetros,\nvelocidade GPR, tipo solo estimado

    WK->>WK: Constrói prompt estruturado:
    Note over WK: - Dados técnicos do projeto\n- Tabela de detecções alta confiança\n- Parâmetros de aquisição\n- Instruções de interpretação

    WK->>AI: POST /chat/completions\n{model: gpt-4o, temperature: 0.2}
    AI-->>WK: Resposta JSON estruturada:\n{interpretacao, alertas, recomendacoes,\nconfianca_geral, observacoes}

    WK->>WK: Valida estrutura da resposta
    WK->>SB: INSERT analise_ia\n{projeto_id, run_id, modelo, tokens,\nresposta_json, criado_em}
    WK->>SB: UPDATE projetos SET status='aguardando_revisao'

    Note over WK,SB: IA gera interpretação operacional padrão.\nRevisão humana disponível para controle, exceções e aprovação final.
```

---

## 8. Revisão Opcional pelo Analista

O analista pode revisar, ajustar ou validar os resultados da IA. É opcional — o projeto pode ir para relatório sem revisão manual.

```mermaid
flowchart TD
    STATUS([Projeto: aguardando_revisao]) --> Q{Analista\ndeseja revisar?}

    Q -->|Não — vai direto| RELATORIO[Gerar Relatório]
    Q -->|Sim| REV_OPEN[Analista abre\npainel de revisão]

    REV_OPEN --> VIZ[Visualiza:\n- Radargrama anotado\n- Detecções com scores\n- Análise IA\n- Preview cartografia]

    VIZ --> ACTIONS{Ação do analista}

    ACTIONS -->|Aprovar detecção| APROVA[Marca como aprovada\nmanualmente]
    ACTIONS -->|Rejeitar detecção| REJEITA[Marca como rejeitada\ncom motivo]
    ACTIONS -->|Ajustar parâmetro| AJUSTA[Edita profundidade,\ndiâmetro, tipo]
    ACTIONS -->|Adicionar nota| NOTA[Adiciona observação\ntécnica livre]
    ACTIONS -->|Solicitar reprocessamento| REPRO[Dispara nova run\ncom parâmetros diferentes]

    APROVA --> SALVA[Salva revisão\nno Supabase]
    REJEITA --> SALVA
    AJUSTA --> SALVA
    NOTA --> SALVA
    REPRO --> NOVA_RUN[Cria run_002_...\nNUNCA sobrescreve run anterior]

    SALVA --> STATUS_REV([Status: em_revisao → revisado])
    STATUS_REV --> RELATORIO

    NOVA_RUN --> WORKER[Worker reprocessa]
    WORKER --> STATUS
```

---

## 9. Cartografia — Objetivo Final

**Meta: substituir completamente o trabalho manual de montagem de planta/croqui.** A integração com o fluxo atual do Amilson é etapa de compatibilidade e validação — não é o destino final. Após validação, o sistema produz o entregável cartográfico de forma autônoma.

```mermaid
flowchart LR
    subgraph INPUT["Inputs"]
        DET[Detecções aprovadas\n+ coordenadas GPS]
        GPS[Track GPS\n.GPX / .KML]
        REF[Referências existentes\nshapefiles, plantas]
    end

    subgraph PROCESS["Processamento Cartográfico"]
        GEOREF[Georreferencia detecções\nUTM / WGS84]
        INTERSECT[Correlaciona com\ntrack GPS por tempo]
        CLASSIFY[Classifica interferências:\ntubulações, cabos, estruturas]
        EXPORT[Exporta camadas\nDXF / GeoJSON / KML]
    end

    subgraph OUTPUT["Outputs"]
        DXF_FILE["📄 arquivo.DXF\n(AutoCAD compatível)"]
        GEOJSON["📄 deteccoes.geojson\n(GIS compatível)"]
        MAP_IMG["🗺️ mapa_preview.png\n(visualização rápida)"]
        REPORT_MAP["📋 Mapa no relatório PDF"]
    end

    subgraph META["Objetivo Estratégico"]
        ANTES["ANTES:\nAmilson faz manualmente\n~4h por projeto"]
        DEPOIS["DEPOIS:\nSistema gera automaticamente\n~2min por projeto"]
        GANHO["Ganho: escalabilidade\nAmilson faz QA, não produção"]
    end

    INPUT --> PROCESS
    PROCESS --> OUTPUT
    META -.->|contexto| OUTPUT
```

---

## 10. Geração de Relatório

Fluxo de composição e entrega do relatório final ao cliente.

```mermaid
flowchart TD
    START([Analista solicita\ngeração de relatório]) --> CHECK{Revisão\nconcluída?}

    CHECK -->|Não — sem revisão| AUTO[Usa resultados IA\ndiretamente]
    CHECK -->|Sim — revisado| MANUAL[Usa resultados\nrevisados pelo analista]

    AUTO --> COMPOSE[Compõe relatório]
    MANUAL --> COMPOSE

    subgraph COMPOSE["Composição do Relatório"]
        C1[Capa: cliente, projeto, data, versão]
        C2[Sumário executivo\ngerado por IA]
        C3[Tabela de detecções\nalta confiança]
        C4[Imagens: radargrama anotado\nPNG de cada linha]
        C5[Mapa cartográfico\nDXF preview como PNG]
        C6[Parâmetros de aquisição\ne processamento]
        C7[Notas técnicas\ndo analista]
        C8[Rodapé: ScanSOLO,\nversão do software, hash da run]
        C1 --> C2 --> C3 --> C4 --> C5 --> C6 --> C7 --> C8
    end

    COMPOSE --> PDF[Gera PDF\ncom WeasyPrint ou ReportLab]
    PDF --> STORE[Salva em\nSupabase Storage /relatorios/]
    PDF --> DB_REG[Registra em\ntabela relatorios no DB]
    DB_REG --> NOTIFY[Notifica analista:\nrelatório disponível]
    NOTIFY --> DOWNLOAD[Analista baixa / envia ao cliente]
```

---

## 11. Permissões por Perfil

Matrix de acesso: o que cada perfil pode e não pode fazer.

> **Regra de segurança absoluta:** nenhuma rota, componente ou resposta do frontend pode expor `DROPBOX_TOKEN`, `OPENAI_API_KEY` ou `SUPABASE_SERVICE_ROLE_KEY`. Essas credenciais existem exclusivamente em variáveis de ambiente server-side (worker Railway e Next.js Server Components). Code review deve verificar isso antes de qualquer merge.

```mermaid
graph TB
    subgraph PERFIS["Perfis de Usuário"]
        ADMIN[👑 Admin ScanSOLO]
        ANALISTA[🔬 Analista Técnico]
        OPERADOR[👷 Operador de Campo]
    end

    subgraph ACOES["Ações do Sistema"]
        A01[Ver todos os projetos]
        A02[Ver projeto específico]
        A03[Upload de arquivos]
        A04[Fluxo B: assimilar Dropbox]
        A05[Ver resultados técnicos GPR]
        A06[Ver análise IA]
        A07[Revisar / editar detecções]
        A08[Gerar relatório]
        A09[Ver relatório gerado]
        A10[Acessar configurações]
        A11[Gerenciar usuários]
        A12[Ver dados de outros projetos]
    end

    ADMIN -->|✅| A01
    ADMIN -->|✅| A02
    ADMIN -->|✅| A03
    ADMIN -->|✅| A04
    ADMIN -->|✅| A05
    ADMIN -->|✅| A06
    ADMIN -->|✅| A07
    ADMIN -->|✅| A08
    ADMIN -->|✅| A09
    ADMIN -->|✅| A10
    ADMIN -->|✅| A11
    ADMIN -->|✅| A12

    ANALISTA -->|✅ próprios| A01
    ANALISTA -->|✅| A02
    ANALISTA -->|✅| A03
    ANALISTA -->|✅| A04
    ANALISTA -->|✅| A05
    ANALISTA -->|✅| A06
    ANALISTA -->|✅| A07
    ANALISTA -->|✅| A08
    ANALISTA -->|✅| A09
    ANALISTA -->|❌| A10
    ANALISTA -->|❌| A11
    ANALISTA -->|❌| A12

    OPERADOR -->|❌| A01
    OPERADOR -->|✅ só status| A02
    OPERADOR -->|✅| A03
    OPERADOR -->|❌| A04
    OPERADOR -->|❌| A05
    OPERADOR -->|❌| A06
    OPERADOR -->|❌| A07
    OPERADOR -->|❌| A08
    OPERADOR -->|❌| A09
    OPERADOR -->|❌| A10
    OPERADOR -->|❌| A11
    OPERADOR -->|❌| A12
```

---

## 12. Estados do Projeto

Máquina de estados completa de um projeto desde a criação até o arquivamento.

```mermaid
stateDiagram-v2
    [*] --> aguardando_arquivo : projeto criado

    aguardando_arquivo --> arquivo_salvo : arquivo recebido\n+ checksum calculado
    aguardando_arquivo --> erro_upload : falha no upload

    arquivo_salvo --> processando_gpr : worker inicia pipeline
    arquivo_salvo --> cancelado : analista cancela

    processando_gpr --> aguardando_ia : GPR concluído com sucesso
    processando_gpr --> erro_processamento : falha no pipeline
    processando_gpr --> processando_gpr : reprocessando\n(nova run)

    erro_processamento --> processando_gpr : analista solicita\nreprocessamento

    aguardando_ia --> aguardando_revisao : IA concluída
    aguardando_ia --> erro_ia : falha na API OpenAI
    erro_ia --> aguardando_revisao : retry automático\nou skip IA

    aguardando_revisao --> em_revisao : analista abre revisão
    aguardando_revisao --> gerando_relatorio : vai sem revisão

    em_revisao --> revisado : analista conclui revisão
    em_revisao --> processando_gpr : solicita reprocessamento\n(cria nova run)

    revisado --> gerando_relatorio : gera relatório

    gerando_relatorio --> relatorio_disponivel : PDF gerado e salvo
    gerando_relatorio --> erro_relatorio : falha na geração

    erro_relatorio --> gerando_relatorio : retry

    relatorio_disponivel --> arquivado : projeto encerrado
    relatorio_disponivel --> em_revisao : revisão adicional

    cancelado --> [*]
    arquivado --> [*]
```

---

## 13. Versionamento por Run

Como runs são criadas, nunca sobrescritas, e como o sistema mantém histórico completo.

```mermaid
flowchart TD
    subgraph PROJETO["Projeto: projeto_ternium_rj_2026-05-20"]
        subgraph RAW["raw/ — imutável"]
            R1["arquivo_original.DZT\n29.3 MB"]
            R2["arquivo_original.DZT.sha256\nsha256: a1b2c3d4..."]
        end

        subgraph RUNS["runs/ — histórico completo"]
            subgraph RUN1["run_001_2026-05-20_a1b2c3d4/"]
                RUN1_A["config_used.json\nparâmetros originais"]
                RUN1_B["resultados_deteccoes.npy\n(19 detecções)"]
                RUN1_C["radargrama_migrado.npy"]
                RUN1_D["radargrama_agc.npy"]
            end

            subgraph RUN2["run_002_2026-05-21_a1b2c3d4/"]
                RUN2_A["config_used.json\nvelocidade ajustada: 0.09→0.10"]
                RUN2_B["resultados_deteccoes.npy\n(22 detecções)"]
                RUN2_C["radargrama_migrado.npy"]
                RUN2_D["radargrama_agc.npy"]
                RUN2_E["⭐ run ativa\n(mais recente)"]
            end
        end

        subgraph DB_RUNS["Supabase: tabela runs"]
            DB1["run_001: status=superseded"]
            DB2["run_002: status=active\n(is_active=true)"]
        end
    end

    subgraph REGRAS["Regras de Versionamento"]
        RL1["✅ Nova run sempre cria nova pasta"]
        RL2["✅ run anterior fica em status=superseded"]
        RL3["✅ Apenas uma run is_active=true por projeto"]
        RL4["❌ NUNCA deletar run anterior"]
        RL5["❌ NUNCA sobrescrever arquivos existentes"]
        RL6["❌ NUNCA deletar arquivo bruto em raw/"]
    end

    RUN1 -.->|supersedida por| RUN2
    RAW -.->|hash consistente| RUN1
    RAW -.->|hash consistente| RUN2
    RUNS -.->|espelhado em| DB_RUNS
```

---

*Arquivo gerado como parte da documentação-mãe da plataforma ScanSOLO.*  
*Para decisões técnicas detalhadas, ver `DECISOES_TECNICAS_ADR.md`.*  
*Para requisitos completos do produto, ver `PRD_ScanSOLO_Plataforma_Operacional.md`.*
