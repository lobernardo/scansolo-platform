# Decisões Técnicas — Architecture Decision Records (ADR)

> Projeto: Plataforma Operacional ScanSOLO  
> Versão: 0.1 — Maio 2026  
> Status: Decisões travadas, pré-implementação

---

## Formato de cada ADR

```
Status: Travada | Pendente | Supersedida
Data: YYYY-MM
Contexto: Por que essa decisão precisou ser tomada
Decisão: O que foi decidido
Consequências: Impactos positivos e negativos
```

---

## Índice

| ADR | Título | Status |
|-----|--------|--------|
| [ADR-001](#adr-001) | Stack de frontend: Next.js | Travada |
| [ADR-002](#adr-002) | Backend e banco de dados: Supabase | Travada |
| [ADR-003](#adr-003) | Armazenamento de arquivos brutos: Dropbox | Travada |
| [ADR-004](#adr-004) | Worker de processamento: Railway | Travada |
| [ADR-005](#adr-005) | Modelo de IA: OpenAI GPT-4o | Travada |
| [ADR-006](#adr-006) | Segurança de credenciais: server-side only | Travada |
| [ADR-007](#adr-007) | Controle de acesso: RLS obrigatório no Supabase | Travada |
| [ADR-008](#adr-008) | Imutabilidade de arquivos brutos | Travada |
| [ADR-009](#adr-009) | Versionamento por run | Travada |
| [ADR-010](#adr-010) | Separação Dropbox vs Supabase Storage | Travada |
| [ADR-011](#adr-011) | IA automática e não opcional | Travada |
| [ADR-012](#adr-012) | Nomenclatura de projetos e runs | Travada |
| [ADR-013](#adr-013) | Dois fluxos de entrada: A (upload) e B (Dropbox) | Travada |
| [ADR-014](#adr-014) | Escrita atômica de arquivos .npy | Travada |
| [ADR-015](#adr-015) | Dois confidence labels distintos | Travada |
| [ADR-016](#adr-016) | Objetivo cartográfico: substituir trabalho manual | Travada |
| [ADR-017](#adr-017) | Permissões do operador de campo (restrições explícitas) | Travada |

---

## ADR-001

### Stack de Frontend: Next.js

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
A plataforma precisa de uma interface web acessível por tablet/celular no campo e por analistas no escritório. O sistema tem componentes server-side (autenticação, chamadas seguras a APIs) e client-side (visualização de radargramas, uploads). Precisamos de uma stack moderna com SSR e boa integração com Supabase Auth.

**Decisão:**  
Usar **Next.js (App Router)** como framework de frontend.

- Server Components para páginas que exigem autenticação server-side
- Client Components para interfaces interativas (upload, visualização, revisão)
- API Routes para proxying de chamadas ao worker e ao Dropbox
- Integração nativa com `@supabase/ssr` para auth com cookies httpOnly

**Consequências:**

Positivas:
- SSR elimina exposição de tokens no cliente
- App Router permite layouts aninhados com controle fino de acesso
- Supabase tem SDK oficial para Next.js
- Deploy simples no Vercel

Negativas:
- Curva de aprendizado do App Router para quem conhece apenas Pages Router
- Hidratação pode gerar bugs sutis em componentes que misturam server/client

> **Portabilidade:** decisão travada para implementação inicial. A arquitetura SSR é padrão e não cria lock-in difícil de reverter — migrar para outro framework SSR (SvelteKit, Nuxt) seria trabalho de frontend sem impactar worker, banco ou pipeline.

---

## ADR-002

### Backend e Banco de Dados: Supabase

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
O sistema precisa de: banco de dados relacional com controle de acesso por linha, autenticação multi-perfil (admin, analista, operador), storage para outputs leves, e notificações em tempo real de status do worker. Construir isso do zero seria inviável para a fase atual do projeto.

**Decisão:**  
Usar **Supabase** como backend principal, aproveitando:

- **PostgreSQL** com RLS para dados de projetos, runs, detecções e análises IA
- **Supabase Auth** com JWT para autenticação de todos os perfis
- **Supabase Storage** para outputs leves (PNG, CSV, PDF — máx 50MB por arquivo)
- **Supabase Realtime** para push de atualizações de status do worker ao frontend

**Consequências:**

Positivas:
- RLS enforced no banco — segurança por design, não por código de aplicação
- Auth integrado elimina necessidade de sistema de auth próprio
- Realtime simplifica UX de progresso do processamento
- SDK JavaScript/Python disponível e bem documentado

Negativas:
- Vendor lock-in moderado no Supabase
- Limites de storage no plano free (1GB) — precisa escalar com o volume
- Supabase Storage não é adequado para arquivos > 50MB (arquivos GPR brutos ficam no Dropbox)

> **Portabilidade:** decisão travada para implementação inicial. O Supabase pode ser substituído por Postgres gerenciado (PlanetScale, Neon, RDS) + Auth próprio se custo ou escala exigirem. A separação entre DB, Auth e Storage facilita migração parcial ou total.

---

## ADR-003

### Armazenamento de Arquivos Brutos: Dropbox

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Arquivos GPR brutos (.DZT, .DT1, .SGY) variam de 10MB a vários GB. O time de campo já usa Dropbox hoje — o operador Amilson frequentemente copia arquivos diretamente para uma pasta Dropbox compartilhada. Precisamos suportar esse fluxo existente e não forçar mudança de comportamento do campo.

**Decisão:**  
Usar **Dropbox** como storage primário de todos os arquivos pesados:

- Arquivos brutos em `/projetos/{nome_projeto}/raw/` — imutáveis após criação
- Outputs pesados de runs (`.npy`, binários) em `/projetos/{nome_projeto}/runs/{run_id}/`
- Checksum SHA-256 salvo como arquivo auxiliar `{arquivo}.sha256` e também no Supabase DB

O Dropbox API token fica **exclusivamente** nas variáveis de ambiente do worker (Railway). Nunca no banco de dados, nunca no frontend.

**Consequências:**

Positivas:
- Suporta fluxo existente do campo (Fluxo B) sem mudança de comportamento
- Capacidade praticamente ilimitada para arquivos pesados
- Webhook nativo do Dropbox para detecção automática de novos arquivos
- Backup implícito via versionamento do próprio Dropbox

Negativas:
- Dependência de API externa (rate limits, disponibilidade)
- Webhook requer endpoint público no worker (Railway URL fixa ou Railway Static IP)
- Custo do Dropbox Business escala com volume

---

## ADR-004

### Worker de Processamento: Railway

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
O pipeline GPR (pipeline_v1.py + detector_hiperboles.py) é computacionalmente intenso e requer Python com dependências científicas (numpy, scipy, matplotlib, readgssi). Não pode rodar no frontend. Precisa de um ambiente isolado com acesso a variáveis de ambiente seguras para tokens de Dropbox e OpenAI.

**Decisão:**  
Usar **Railway** como plataforma de deploy do worker Python:

- Worker expõe API HTTP (FastAPI ou Flask) para receber jobs do frontend
- Variáveis de ambiente no Railway: `DROPBOX_TOKEN`, `OPENAI_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`
- Deploy via `railway.toml` com `Dockerfile` ou buildpack Python
- Sleep automático em planos free — considerar plano pago para workloads contínuos

**Consequências:**

Positivas:
- Deploy simples de containers Python com dependências científicas
- Variáveis de ambiente gerenciadas pela plataforma — nunca expostas no código
- URL estática (Railway Static Networking) para receber webhooks do Dropbox
- Logs e métricas nativos

Negativas:
- Cold start se usar sleep automático (Railway Starter plan)
- Custo escala com tempo de CPU — processamento GPR intenso
- Não tem auto-scaling horizontal nativo para jobs paralelos

> **Portabilidade:** decisão travada para implementação inicial, mantendo portabilidade para VPS/Docker. O worker Python é um container padrão — pode ser migrado para EC2, DigitalOcean, Fly.io ou qualquer infraestrutura Docker sem alterar o pipeline. O `railway.toml` e `Dockerfile` são os únicos artefatos Railway-específicos.

---

## ADR-005

### Modelo de IA: OpenAI GPT-4o

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
A plataforma precisa interpretar automaticamente resultados técnicos do GPR (profundidades, diâmetros, confidence scores) e gerar linguagem natural para o relatório. O modelo precisa entender contexto técnico de GPR, interpretar tabelas de detecções e produzir JSON estruturado com interpretação, alertas e recomendações.

**Decisão:**  
Usar **OpenAI GPT-4o** com temperatura 0.2 para análise técnica determinística.

- Input: JSON estruturado com detecções de alta confiança, parâmetros de aquisição, tipo de solo estimado
- Output: JSON estruturado com `{interpretacao, alertas, recomendacoes, confianca_geral, observacoes}`
- A chave OpenAI fica **exclusivamente** nas variáveis de ambiente do worker. Nunca no banco, nunca no frontend.

**Consequências:**

Positivas:
- GPT-4o tem contexto técnico suficiente para GPR e subsurface imaging
- Saída JSON estruturada facilita integração com relatório
- Temperatura 0.2 reduz variabilidade em análises técnicas

Negativas:
- Custo por token — análises longas aumentam custo operacional
- Dependência de API externa (disponibilidade, rate limits)
- Respostas ocasionais fora do formato esperado requerem validação robusta

> **Portabilidade:** decisão travada para implementação inicial. O cliente OpenAI é encapsulado no worker — trocar o modelo (GPT-4o → Claude, Gemini, modelo local via Ollama) requer apenas alterar o módulo `openai_client.py`, sem impacto no pipeline GPR ou no banco. A troca pode ser motivada por custo, escala ou performance.

---

## ADR-006

### Segurança de Credenciais: Server-Side Only

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
O sistema lida com dois tokens críticos: Dropbox API token (acesso a todos os arquivos do cliente) e OpenAI API key (custos diretos, dados técnicos sensíveis). Qualquer exposição no frontend ou no banco de dados representaria risco grave de segurança e vazamento de dados de clientes.

**Decisão:**  
Regra absoluta, sem exceções:

- `DROPBOX_TOKEN` → somente em variáveis de ambiente do worker (Railway). Nunca no DB. Nunca no frontend.
- `OPENAI_API_KEY` → somente em variáveis de ambiente do worker (Railway). Nunca no DB. Nunca no frontend.
- `SUPABASE_SERVICE_ROLE_KEY` → somente no worker e em contextos server-side do Next.js. Nunca exposto ao cliente.
- Frontend usa apenas `SUPABASE_ANON_KEY` com RLS ativo

Code reviews devem incluir verificação explícita de que nenhuma dessas variáveis aparece em código client-side, logs ou respostas de API.

**Regra de verificação:** nenhuma rota, componente ou resposta do frontend pode expor `DROPBOX_TOKEN`, `OPENAI_API_KEY` ou `SUPABASE_SERVICE_ROLE_KEY`. Isso vale para variáveis de ambiente expostas via `NEXT_PUBLIC_*`, respostas de API Routes, logs de console no browser e comentários no bundle JS.

**Consequências:**

Positivas:
- Elimina vetores de ataque mais comuns (token exposure em bundle JS)
- Dados de clientes protegidos mesmo se banco for exposto
- Auditoria clara: qualquer acesso ao Dropbox ou OpenAI passa pelo worker

Negativas:
- Toda operação com Dropbox/OpenAI exige round-trip pelo worker (latência adicional)
- Aumenta criticidade do worker como ponto único de acesso

---

## ADR-007

### Controle de Acesso: RLS Obrigatório no Supabase

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
A plataforma serve múltiplos projetos e clientes. Um operador de campo não pode ver projetos de outros clientes. Um analista só deve ver projetos de sua organização. Sem controle de acesso no banco, qualquer bug no frontend ou na API poderia expor dados de outros clientes.

**Decisão:**  
**Row Level Security (RLS) é obrigatório em todas as tabelas** que contêm dados de projetos:

- `projetos`: operador vê apenas projetos onde é `operador_id`, analista vê projetos de sua `org_id`
- `runs`, `resultados_gpr`, `analise_ia`: herdado via FK de `projetos`
- `audit_logs`: somente admin pode ler; insert permitido para service role
- Nenhuma tabela sensível fica sem RLS habilitado

Política complementar: `audit_logs` registra todas as ações importantes (criação de projeto, geração de relatório, edição de revisão, acesso a dados técnicos).

**Consequências:**

Positivas:
- Segurança enforced no banco — imune a bugs de lógica na aplicação
- Dados multi-tenant isolados por design
- audit_logs cria rastreabilidade completa para conformidade

Negativas:
- Políticas RLS complexas são difíceis de debugar
- Performance pode degradar em tabelas grandes sem índices nas colunas de RLS
- Requer testes específicos de isolamento de tenants

---

## ADR-008

### Imutabilidade de Arquivos Brutos

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Arquivos GPR brutos (.DZT, .DT1, .SGY) são a evidência primária de um levantamento de campo. Uma vez coletados, são irreproduzíveis — uma obra de construção pode ter avançado, o solo pode ter mudado. Qualquer corrupção ou perda desses arquivos é irreversível e pode ter implicações legais.

**Decisão:**  
Arquivos brutos são **imutáveis após criação**. Regras absolutas:

1. **Nunca deletar arquivo bruto** — nem por limpeza de espaço, nem por solicitação de usuário comum
2. **Nunca sobrescrever arquivo bruto** — se arquivo com mesmo nome chegar, criar versão `_v2`, nunca sobrescrever
3. **Checksum SHA-256** calculado imediatamente após recebimento, salvo como arquivo `.sha256` e na tabela `projetos`
4. Deleção só permitida por admin ScanSOLO via painel administrativo, com confirmação dupla e registro em audit_log
5. Pasta `raw/` no Dropbox tem permissão de escrita apenas para o worker (via service token)

**Consequências:**

Positivas:
- Evidência primária preservada para auditoria técnica e legal
- Permite reprocessar com novos algoritmos no futuro
- Checksum detecta corrupção de arquivo em trânsito ou storage

Negativas:
- Custo de storage cresce indefinidamente sem política de arquivamento
- Requer governança clara para casos extremos (cliente pede deleção por LGPD)

---

## ADR-009

### Versionamento por Run

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Parâmetros de processamento GPR (velocidade de propagação, tipo de migração, threshold de detecção) precisam ser ajustados conforme o tipo de solo e condições do levantamento. Um analista pode precisar reprocessar com parâmetros diferentes sem perder os resultados anteriores. Comparar runs é fundamental para validar ajustes.

**Decisão:**  
Cada execução do pipeline cria uma nova **run** versionada com estrutura imutável:

```
run_{NNN}_{data_YYYY-MM-DD}_{hash8_do_bruto}/
├── config_used.json          # parâmetros exatos usados
├── resultados_deteccoes.npy  # array de detecções
├── radargrama_migrado.npy    # radargrama após migração
├── radargrama_agc.npy        # radargrama com AGC
└── index_projeto.csv         # índice consolidado (42 colunas)
```

- `NNN` começa em `001` e incrementa — nunca reutilizado
- Apenas uma run tem `is_active=true` por projeto (a mais recente)
- Runs anteriores ficam com `status=superseded` — nunca deletadas
- O frontend por padrão mostra apenas a run ativa, mas o analista pode navegar no histórico

**Consequências:**

Positivas:
- Histórico completo de processamento preservado
- Reprodutibilidade garantida: `config_used.json` captura todos os parâmetros
- Rollback simples: marcar run anterior como ativa novamente
- Auditabilidade: sempre possível responder "com quais parâmetros foi processado?"

Negativas:
- Consumo de storage cresce com cada reprocessamento
- Complexidade na UI: precisa comunicar claramente qual run está ativa
- Lógica de "qual run mostrar" precisa ser consistente em todas as views

---

## ADR-010

### Separação Dropbox vs Supabase Storage

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
O sistema gera dois tipos de outputs: arquivos pesados e técnicos (arrays numpy, binários GPR processados) e arquivos leves para visualização e distribuição (imagens PNG, CSVs exportáveis, PDFs de relatório). Colocar tudo no mesmo storage seria ineficiente — Supabase Storage tem custo por GB e não é otimizado para arquivos > 50MB.

**Decisão:**  
Divisão clara por tipo de arquivo:

**Dropbox** (arquivos pesados e brutos):
- Arquivos brutos: `.DZT`, `.DT1`, `.SGY` (qualquer tamanho)
- Arrays numpy de runs: `resultados_deteccoes.npy`, `radargrama_migrado.npy`, `radargrama_agc.npy`
- `config_used.json` de cada run
- Regra: qualquer arquivo > 1MB ou que precise ser reprocessado → Dropbox

**Supabase Storage** (camada de visualização e download — **não é fonte da verdade**):
- Imagens PNG: radargrama anotado, perfil de profundidade, mapa preview
- CSVs de exportação: `deteccoes_export.csv`
- Relatórios PDF: `relatorio_v{N}.pdf`
- Regra: qualquer arquivo servido diretamente ao frontend → Supabase Storage
- **Fonte da verdade:** o Dropbox. Se houver divergência entre Supabase Storage e Dropbox, o Dropbox prevalece. O Supabase Storage pode ser reconstruído a partir do Dropbox.

**Consequências:**

Positivas:
- Frontend só precisa de URL do Supabase Storage (com autenticação via RLS) para renderizar imagens
- Custos de storage otimizados para cada tipo
- Não expõe URL do Dropbox ao frontend (segurança adicional)

Negativas:
- Dois sistemas de storage aumentam complexidade operacional
- Sincronia pode ficar inconsistente se worker falhar entre salvar no Dropbox e no Supabase Storage

---

## ADR-011

### IA Automática e Não Opcional

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
A proposta de valor central da plataforma é reduzir trabalho manual. Se a análise de IA fosse opcional, a maioria dos usuários não a ativaria por inércia, eliminando o benefício. Além disso, o custo de chamada à OpenAI é pequeno comparado ao valor gerado por análise automática.

**Decisão:**  
A análise de IA com GPT-4o é **sempre executada automaticamente** após o processamento GPR bem-sucedido. Não existe botão "analisar com IA" — é parte do pipeline padrão.

A IA gera a **interpretação operacional padrão** dos resultados. Revisão humana é disponível para controle, exceções, ajustes e aprovação final — não é obrigatória. O analista pode sobrescrever, complementar ou ignorar a interpretação da IA. A análise IA sempre acontece; a revisão manual é opcional.

Em caso de falha na API OpenAI (timeout, rate limit, erro): o sistema faz até 3 retentativas com backoff exponencial. Após 3 falhas, o projeto avança para `aguardando_revisao` com flag `ia_failed=true`. O analista é notificado e pode solicitar retry manual.

**Consequências:**

Positivas:
- Toda revisão tem contexto de IA disponível — analista não começa do zero
- Consistência: todos os projetos têm análise IA, facilita comparação
- Custo previsível: uma chamada por run processada

Negativas:
- Custo de IA em projetos que o analista não precisa de interpretação
- Falhas na API OpenAI bloqueiam temporariamente o fluxo (mitigado pelo fallback)

---

## ADR-012

### Nomenclatura de Projetos e Runs

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Com múltiplos projetos, clientes e versões de processamento, nomes ambíguos causam confusão. Precisamos de uma convenção que seja: legível por humanos, única, ordenável cronologicamente e que identifique o cliente sem precisar consultar o banco.

**Decisão:**  
**Nomenclatura de projetos:**
```
projeto_{nomecliente}_{estado}_{data}
```
Exemplos:
- `projeto_ternium_rj_2026-05-20`
- `projeto_vale_mg_2026-06-15`
- `projeto_petrobras_es_2026-03-01`

- `{nomecliente}`: nome curto do cliente em minúsculas, sem espaços (snake_case). Se houver código interno de obra ou OS, ele entra como campo adicional no banco (`codigo_interno`) e pode aparecer como sufixo opcional: `projeto_ternium_rj_2026-05-20_os1234`. O sufixo não substitui o padrão principal.
- `{estado}`: sigla do estado brasileiro em minúsculas (`rj`, `sp`, `mg`, etc.)
- `{data}`: data do levantamento de campo no formato `YYYY-MM-DD`

**Nomenclatura de runs:**
```
run_{NNN}_{data_processamento}_{hash8}
```
Exemplos:
- `run_001_2026-05-20_a1b2c3d4`
- `run_002_2026-05-21_a1b2c3d4`

- `{NNN}`: número sequencial com zero-padding (001, 002, ..., 099, 100)
- `{data_processamento}`: data em que o processamento foi executado (`YYYY-MM-DD`)
- `{hash8}`: primeiros 8 caracteres do SHA-256 do arquivo bruto (identifica que o arquivo base é o mesmo)

**Consequências:**

Positivas:
- Nomes legíveis nos logs do worker e no Dropbox sem precisar consultar o banco
- Ordenação cronológica natural por data
- Hash8 na run permite verificar que duas runs usaram o mesmo arquivo bruto

Negativas:
- Se um projeto tiver dois levantamentos do mesmo cliente no mesmo dia → precisará de sufixo `_a`, `_b`
- Nomes de clientes com caracteres especiais precisam ser normalizados

---

## ADR-013

### Dois Fluxos de Entrada: A (Upload) e B (Dropbox)

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Existem dois padrões de comportamento no campo: alguns operadores preferem usar o sistema web para enviar arquivos; outros (como o atual fluxo do Amilson) preferem copiar arquivos diretamente para uma pasta Dropbox. Forçar um único fluxo exigiria mudança de comportamento e resistência.

**Decisão:**  
A plataforma suporta **dois fluxos de entrada mutuamente exclusivos**:

**Fluxo A — Upload pelo Sistema:**
- Operador acessa o frontend, seleciona arquivo, faz upload
- Frontend → Worker → Dropbox `/raw/` → Pipeline
- Sistema cria o projeto automaticamente

**Fluxo B — Arquivo Já no Dropbox:**
- Sub-fluxo B1 (Manual): Analista clica "Assimilar Dropbox", escolhe pasta, sistema processa
- Sub-fluxo B2 (Webhook): Dropbox notifica worker via webhook quando arquivo cai na pasta monitorada; sistema processa automaticamente após janela de estabilização de 30 segundos

Ambos os fluxos convergem no mesmo pipeline de processamento após criação do projeto no Supabase.

**Consequências:**

Positivas:
- Zero resistência de adoção — suporta comportamento atual do campo
- B2 (webhook) permite automação total sem intervenção do analista
- Fluxos convergem: lógica de processamento é a mesma, apenas a entrada difere

Negativas:
- B2 requer endpoint público e verificação de assinatura HMAC do Dropbox webhook
- Possibilidade de duplicação se arquivo cair via Fluxo B2 e analista também assimilar manualmente via B1 — precisa de deduplicação por hash

---

## ADR-014

### Escrita Atômica de Arquivos .npy

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
O pipeline GPR pode ser interrompido (crash do worker, timeout, OOM) no meio da escrita de um arquivo `.npy`. Um arquivo parcialmente escrito é corrompido e silenciosamente inválido — `np.load()` carrega sem erro mas retorna dados errados. Em produção, isso levaria a análises incorretas sem detecção.

**Decisão:**  
Toda escrita de arquivo `.npy` usa o padrão de **escrita atômica via arquivo temporário + rename**:

```python
def _salvar_npy_seguro(arr, caminho):
    import tempfile
    caminho = Path(caminho)
    fd, tmp = tempfile.mkstemp(dir=str(caminho.parent), suffix=".npy")
    try:
        os.close(fd)
        np.save(tmp, arr)
        os.replace(tmp, str(caminho))
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

- `tempfile.mkstemp(suffix=".npy")`: garante que numpy salva para `{tmp}.npy` (numpy adiciona extensão apenas se não houver)

**Nota importante:** `suffix=".npy"` é obrigatório. Com `suffix=".npy.tmp"`, numpy criaria `{tmp}.npy.tmp.npy`, e `os.replace` moveria o arquivo temporário vazio para o destino, resultando em `.npy` de 0 bytes. Este bug foi identificado e corrigido na V1.1.

- `os.replace()` é atômico em sistemas POSIX — o destino nunca fica em estado parcial
- Se qualquer erro ocorrer, o arquivo temporário é removido e o destino original (se existia) permanece intacto

**Consequências:**

Positivas:
- Impossível ter arquivo `.npy` corrompido por interrupção de escrita
- Crash-safe: pipeline pode ser reiniciado sem risco de ler arquivo parcial
- Idempotente: reprocessar a mesma run produz o mesmo resultado

Negativas:
- Requer espaço temporário igual ao arquivo sendo salvo (dois arquivos no disco simultaneamente)
- Ligeiramente mais lento que escrita direta (overhead do rename)

---

## ADR-015

### Dois Confidence Labels Distintos

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Detectores de hipérboles precisam servir dois públicos com necessidades diferentes: o analista técnico quer ver todas as detecções, inclusive as de média confiança, para avaliação completa; o relatório ao cliente deve conter apenas detecções com evidências sólidas o suficiente para embasar decisões de obra. Um único threshold não serve a ambos.

**Decisão:**  
O sistema mantém **dois labels de confiança independentes** para cada detecção:

**`confidence_label_tecnico`** (para análise técnica):
- Baseado em score numérico (0–100) com múltiplos critérios ponderados
- Categorias: `alta` (≥70), `média` (40–69), `baixa` (<40)
- Inclui todas as detecções relevantes para o analista avaliar

**`confidence_label_relatorio`** (para relatório ao cliente):
- Binário: `alta` ou `baixa`
- Requer **todos** os seguintes critérios simultaneamente:
  1. `fit_ok=True` — ajuste parabólico passou
  2. `diam_alta=True` — diâmetro dentro do range aceitável
  3. `evidencia_raw=True` — visível no radargrama bruto
  4. `evidencia_sem_agc=True` — visível sem processamento AGC
- Sem shortcut: todos os 4 critérios são obrigatórios para `alta` no relatório

**Regra derivada:** Toda detecção `confidence_label_relatorio=alta` também tem `confidence_label_tecnico=alta`, mas não o inverso.

**Consequências:**

Positivas:
- Analista vê universo completo de detecções para análise técnica aprofundada
- Relatório ao cliente só contém detecções com evidência dupla sólida
- Reduz risco de falso positivo no relatório (consequências legais e de reputação)

Negativas:
- Complexidade extra: dois labels a manter consistentes
- Risco de confusão na UI se não comunicado claramente para cada perfil

---

## ADR-016

### Objetivo Cartográfico: Substituir Trabalho Manual

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
Atualmente o Amilson (analista) gasta ~4 horas por projeto criando manualmente mapas de interferências subterrâneas a partir dos resultados GPR. Isso é um gargalo operacional: limita a capacidade de projetos simultâneos e cria dependência de uma pessoa específica. O objetivo não é apenas "gerar um mapa bonito" — é eliminar essa etapa manual.

**Decisão:**  
A cartografia da plataforma tem como **objetivo explícito substituir o trabalho manual do analista** na produção de mapas de interferências, não apenas complementá-lo.

Isso implica:

1. **Output DXF nativo** compatível com AutoCAD — não apenas imagem PNG
2. **GeoJSON** para compatibilidade com SIG (QGIS, ArcGIS)
3. **Georreferenciamento automático** por correlação temporal entre detecções GPR e track GPS
4. **Classificação automática** de tipo de interferência (tubulação, cabo, estrutura) baseada em diâmetro e profundidade
5. **QA pelo analista** — o Amilson passa a fazer revisão de qualidade do mapa gerado, não produção manual

A meta de qualidade é: mapa gerado automaticamente que o analista assina sem precisar recriar do zero em 80% dos projetos.

A integração com o fluxo atual do Amilson é **apenas etapa de compatibilidade e validação** — não é o destino final. O objetivo é que, após validação do output DXF, o Amilson deixe de fazer produção manual de plantas e passe a fazer exclusivamente QA dos mapas gerados pelo sistema.

**Consequências:**

Positivas:
- Ganho operacional: de ~4h para ~10min por projeto
- Escalabilidade: número de projetos simultâneos não limitado pelo Amilson
- Amilson faz QA de alto valor, não trabalho mecânico

Negativas:
- Requer integração GPS + GPR por correlação temporal — mais complexo que apenas plotar detecções
- 20% dos projetos ainda precisarão de intervenção manual (casos especiais, GPS impreciso, solos problemáticos)
- Validação do DXF output requer comparação com trabalho manual existente

---

## ADR-017

### Permissões do Operador de Campo (Restrições Explícitas)

**Status:** Travada  
**Data:** 2026-05

**Contexto:**  
O operador de campo (perfil mais restrito) precisa apenas: criar projetos, fazer upload de arquivos e ver o status de andamento do seu próprio projeto. Qualquer acesso além disso representa risco de vazamento de dados técnicos de clientes, acesso indevido a interpretações de IA, ou modificação de resultados.

**Decisão:**  
O operador de campo tem acesso explicitamente **negado** às seguintes funcionalidades:

| Funcionalidade | Operador pode? |
|----------------|----------------|
| Ver todos os projetos da org | ❌ NÃO |
| Ver resultados técnicos GPR | ❌ NÃO |
| Ver análise de IA | ❌ NÃO |
| Gerar relatório | ❌ NÃO |
| Editar revisão técnica | ❌ NÃO |
| Acessar dados de outros projetos | ❌ NÃO |
| Acessar configurações da plataforma | ❌ NÃO |
| Fluxo B (assimilar Dropbox) | ❌ NÃO |
| Upload de arquivos (Fluxo A) | ✅ SIM |
| Ver status do próprio projeto | ✅ SIM (somente status, sem dados técnicos) |
| Criar novo projeto | ✅ SIM |

Essas restrições são enforced em dois níveis:
1. **UI**: componentes não renderizados para o perfil operador
2. **RLS no Supabase**: mesmo se o operador burlar a UI, o banco rejeita qualquer query além de status dos próprios projetos

**Consequências:**

Positivas:
- Isolamento de dados técnicos de clientes — operador de campo não tem acesso a informações sensíveis
- Conformidade com princípio de menor privilégio
- Reduz superfície de ataque: conta de campo comprometida tem acesso mínimo

Negativas:
- Operador não consegue ver se há problema no processamento (além de status genérico)
- Requer UI específica para o perfil operador — mais trabalho de frontend

---

*Arquivo gerado como parte da documentação-mãe da plataforma ScanSOLO.*  
*Para diagramas de arquitetura, ver `ARQUITETURA_VISUAL_ScanSOLO.md`.*  
*Para requisitos completos do produto, ver `PRD_ScanSOLO_Plataforma_Operacional.md`.*
