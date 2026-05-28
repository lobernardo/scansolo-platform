# ScanSOLO Platform

Plataforma operacional para automação do fluxo GPR da ScanSOLO: do dado bruto de campo ao relatório técnico entregue ao cliente.

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│  apps/web  (Next.js App Router + Tailwind)                  │
│  → Deploy: Vercel                                           │
│  → Auth: Supabase Auth (httpOnly cookies via @supabase/ssr) │
│  → Dados: Supabase PostgreSQL + RLS                         │
│  → Assets: Supabase Storage (outputs leves: PNG, CSV, PDF)  │
└────────────────────────┬────────────────────────────────────┘
                         │ Supabase DB (polling de jobs)
┌────────────────────────▼────────────────────────────────────┐
│  services/worker  (Python 3.13)                             │
│  → Deploy: Railway (portável para VPS/Docker)               │
│  → Pipeline GPR: pipeline_v1.py + detector_hiperboles.py    │
│  → IA: OpenAI GPT-4o                                        │
│  → Storage bruto: Dropbox (fonte da verdade dos arquivos)   │
└─────────────────────────────────────────────────────────────┘

Supabase Storage = camada de visualização/download (não é fonte da verdade)
Dropbox = fonte da verdade de todos os arquivos brutos e runs
```

**Regra de segurança absoluta:** `DROPBOX_APP_SECRET`, `DROPBOX_REFRESH_TOKEN`, `OPENAI_API_KEY` e `SUPABASE_SERVICE_ROLE_KEY` existem **apenas** nas variáveis de ambiente do worker (Railway) e em contextos server-side do Next.js. Nunca em código client-side, logs de browser ou respostas de API pública.

---

## Estrutura do Monorepo

```
scansolo-platform/
├── apps/
│   └── web/                  ← Next.js App Router (TypeScript + Tailwind)
├── services/
│   └── worker/               ← Worker Python (polling + pipeline + IA)
│       ├── clients/          ← Supabase, Dropbox, OpenAI clients
│       ├── pipeline/         ← pipeline_v1.py e detector_hiperboles.py (Fase 1)
│       ├── worker_main.py
│       ├── job_gpr.py
│       ├── requirements.txt
│       └── Dockerfile
├── supabase/
│   └── migrations/           ← SQL migrations versionadas
├── packages/
│   └── shared/               ← Tipos TypeScript compartilhados
├── docs/                     ← Cópias dos docs de referência
├── .env.example
└── README.md
```

---

## Como rodar localmente

### Pré-requisitos

- Node.js ≥ 22
- Python ≥ 3.13
- [Supabase CLI](https://supabase.com/docs/guides/cli) instalado
- npm

### 1. Clonar e configurar variáveis

```bash
git clone <repo-url>
cd scansolo-platform
cp .env.example .env.local   # preencher com valores reais
```

### 2. Rodar o frontend (Next.js)

```bash
cd apps/web
npm install
npm run dev
```

Acessa em: `http://localhost:3000`

### 3. Rodar o Supabase local

```bash
# Instalar Supabase CLI se necessário
npm install -g supabase

# Iniciar instância local
supabase start

# Aplicar migrations
supabase db reset
```

Painel local em: `http://localhost:54323`

As variáveis locais do Supabase são geradas pelo `supabase start` — preencher em `.env.local`:
- `NEXT_PUBLIC_SUPABASE_URL=http://localhost:54321`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY=<output do supabase start>`
- `SUPABASE_SERVICE_ROLE_KEY=<output do supabase start>`

### 4. Rodar o worker Python

```bash
cd services/worker

# Opcional mas recomendado: criar virtualenv
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
.venv\Scripts\activate           # Windows

# Instalar dependências
# ATENÇÃO: gprpy não está no PyPI, será instalado do GitHub automaticamente
pip install -r requirements.txt

# Configurar variáveis de ambiente
cp .env.example .env             # preencher SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY

# Rodar
python worker_main.py
```

O worker faz polling no Supabase a cada `WORKER_POLL_INTERVAL_SECONDS` segundos (padrão: 10).

#### Observações de instalação

- **`gprpy`** não está no PyPI. O `requirements.txt` usa `gprpy @ git+https://github.com/NSGeophysics/GPRPy.git`. Requer Git instalado.
- **Redes corporativas com inspeção TLS** (ex: Zscaler): instalar `truststore` (já no requirements.txt). Ele injeta o Windows Certificate Store no Python, resolvendo `CERTIFICATE_VERIFY_FAILED` sem desabilitar SSL. Não é necessário em produção (Railway/VPS).

#### Como verificar jobs no Supabase

```sql
-- Ver jobs pendentes
SELECT id, job_type, status, created_at FROM processing_jobs ORDER BY created_at DESC LIMIT 10;

-- Resetar job travado (ex: processo morto durante processamento)
UPDATE processing_jobs SET status = 'aguardando', started_at = NULL WHERE id = '<job_id>';
```

Via Supabase CLI:
```bash
npx supabase db query "SELECT id, job_type, status FROM processing_jobs ORDER BY created_at DESC LIMIT 5;" --linked
```

---

## Secrets necessários

| Variável | Onde usar | Descrição |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Frontend + Worker | URL pública do projeto Supabase |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Frontend apenas | Chave anon (com RLS) |
| `SUPABASE_SERVICE_ROLE_KEY` | Worker + Next.js server-side | Bypassa RLS — nunca expor ao cliente |
| `DROPBOX_APP_KEY` | Worker apenas | App key do Dropbox OAuth2 |
| `DROPBOX_APP_SECRET` | Worker apenas | App secret do Dropbox OAuth2 |
| `DROPBOX_REFRESH_TOKEN` | Worker apenas | Refresh token OAuth2 |
| `OPENAI_API_KEY` | Worker apenas | Chave da API OpenAI |
| `WORKER_POLL_INTERVAL_SECONDS` | Worker | Intervalo de polling (padrão: 10) |

> **Atenção:** variáveis sem prefixo `NEXT_PUBLIC_` nunca chegam ao bundle do browser. Confirmar antes de cada merge que nenhuma secret está exposta.

---

## Regras de segurança

1. **RLS obrigatório** em todas as tabelas com dados de projetos.
2. **Operador de campo** acessa apenas: criar projeto, upload de arquivos, ver status do próprio projeto.
3. **Técnico** acessa apenas projetos com `assigned_to = seu_uid`.
4. **Sócio/Admin** acessa tudo.
5. **Arquivos brutos nunca são apagados** — apenas versionados.
6. **Reprocessamento** gera nova run (run_001, run_002...) — nunca sobrescreve.
7. **Dropbox é fonte da verdade** — Supabase Storage é camada de visualização.
8. **audit_logs** é append-only: sem UPDATE, sem DELETE.

---

## Fases de desenvolvimento

| Fase | Descrição | Status |
|---|---|---|
| **Fase 0** | Fundação: monorepo, schema, RLS, stubs | ✅ Concluída |
| **Fase 1A** | Conexão Supabase real, tipos TypeScript, build validado | ✅ Concluída |
| **Fase 1B** | Upload .DZT → Storage → Worker → Pipeline → resultados no front | ✅ Concluída |
| Fase 2 | IA automática (GPT-4o) | Pendente |
| Fase 3 | Revisão técnica opcional | Pendente |
| Fase 4 | Cartografia (DXF/KML/GeoJSON) | Pendente |
| Fase 5 | Relatório automático (DOCX/PDF) | Pendente |
| Fase 6 | Polimento, notificações, deploy produção | Pendente |

---

## Documentação técnica

- `docs/PRD_ScanSOLO_Plataforma_Operacional.md` — requisitos completos do produto
- `docs/ARQUITETURA_VISUAL_ScanSOLO.md` — diagramas Mermaid de todos os fluxos
- `docs/DECISOES_TECNICAS_ADR.md` — decisões de arquitetura (ADR-001 a ADR-017)
