# Manual de Operação — ScanSOLO Platform

> Atualizado: 2026-06-05

---

## PARTE 1 — Limpar o sistema e rodar teste do zero

### Passo 1 — Limpar todos os dados de teste no Supabase

Acesse o Supabase → SQL Editor e execute na ordem:

```sql
DELETE FROM ai_interpretations;
DELETE FROM technical_reviews;
DELETE FROM detected_targets;
DELETE FROM gpr_profiles;
DELETE FROM cartography_outputs;
DELETE FROM report_outputs;
DELETE FROM processing_jobs;
DELETE FROM project_files;
DELETE FROM projects;
```

Confirme que limpou:
```sql
SELECT COUNT(*) FROM projects;
-- deve retornar 0
```

---

### Passo 2 — Rodar o sistema localmente

Abrir **dois terminais** dentro de `scansolo-platform/`.

**Terminal 1 — Frontend (Next.js):**
```bash
cd apps/web
npm run dev
```
Aguardar aparecer `Ready on http://localhost:3000`.
Acessar no navegador: **http://localhost:3000**

**Terminal 2 — Worker (Python):**
```bash
cd services/worker
python worker_main.py
```
O worker fica rodando em loop, monitorando jobs na fila do Supabase.
Para parar: `Ctrl+C`

---

### Passo 3 — Criar novo projeto e subir os DZTs

1. Acessar **http://localhost:3000**
2. Fazer login com as credenciais de admin
3. Clicar em **+ Nova entrada** no menu
4. Preencher os dados do projeto (nome, cliente, estado, data)
5. Avançar para a tela de upload
6. Fazer upload dos arquivos `.DZT` do PATIO (ou do projeto real)
7. Confirmar o upload

O worker detecta automaticamente e inicia o pipeline:
- GPR → processa DZTs, gera imagens bruta/processada/anotada
- IA → interpreta os alvos detectados
- O status do projeto atualiza em tempo real na listagem

Acompanhar o progresso em **Projetos** — o status vai avançando:
`Aguardando arquivos` → `Processando GPR` → `GPR concluído` → `IA concluída` → ...

---

### Passo 4 — Validar os resultados

Abrir o projeto processado e verificar:
- Imagens **Bruta**, **Processada** e **Anotada IA** para cada DZT
- Tabela de **Alvos detectados** com filtros Alta/Média/Baixa funcionando
- Painel **Ajustar filtros** disponível por DZT (opcional — só usar se imagem ficou ruim)

---

## PARTE 2 — Deploy em produção

### Pré-requisitos

- Conta no [Vercel](https://vercel.com) (frontend)
- Conta no [Railway](https://railway.app) (worker Python)
- Vercel CLI instalado: `npm i -g vercel`
- Railway CLI instalado: `npm i -g @railway/cli`
- Projeto commitado e pushed no GitHub

---

### Passo 1 — Variáveis de ambiente necessárias

Ter em mãos antes de começar:

| Variável | Onde pegar |
|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase → Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase → Settings → API |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase → Settings → API |
| `OPENAI_API_KEY` | platform.openai.com |
| `DROPBOX_APP_KEY` | Dropbox App Console |
| `DROPBOX_APP_SECRET` | Dropbox App Console |
| `DROPBOX_REFRESH_TOKEN` | gerado via OAuth Dropbox |

---

### Passo 2 — Deploy do frontend no Vercel

```bash
# Dentro de scansolo-platform/apps/web
cd apps/web
vercel login
vercel
```

Nas perguntas interativas:
- "Set up and deploy?" → `Y`
- "Which scope?" → sua conta pessoal ou da organização
- "Link to existing project?" → `N`
- "What's your project name?" → `scansolo-platform`
- "In which directory is your code located?" → `./`

Após o primeiro deploy, configurar as variáveis de ambiente:

```bash
vercel env add NEXT_PUBLIC_SUPABASE_URL
vercel env add NEXT_PUBLIC_SUPABASE_ANON_KEY
vercel env add SUPABASE_SERVICE_ROLE_KEY
```

Ou adicionar pelo painel: **vercel.com → projeto → Settings → Environment Variables**

Fazer o deploy de produção:
```bash
vercel --prod
```

O Vercel fornece uma URL pública (ex: `scansolo-platform.vercel.app`).

---

### Passo 3 — Domínio personalizado no Vercel (opcional)

No painel do Vercel → projeto → Settings → Domains:
1. Clicar em **Add Domain**
2. Digitar o domínio desejado (ex: `app.scansolo.com.br`)
3. Seguir as instruções para apontar o DNS (adicionar registro CNAME no registrador do domínio)
4. Aguardar propagação (até 48h, geralmente minutos)

---

### Passo 4 — Deploy do worker no Railway

```bash
# Na raiz de scansolo-platform/
railway login
railway init
# Selecionar "Empty Project" → dar um nome (ex: scansolo-worker)

railway up
```

Configurar as variáveis de ambiente no Railway:
```bash
railway variables set SUPABASE_URL=https://ayyirgjlotetrqfhpnms.supabase.co
railway variables set SUPABASE_SERVICE_ROLE_KEY=<valor>
railway variables set OPENAI_API_KEY=<valor>
railway variables set DROPBOX_APP_KEY=<valor>
railway variables set DROPBOX_APP_SECRET=<valor>
railway variables set DROPBOX_REFRESH_TOKEN=<valor>
```

Ou configurar pelo painel: **railway.app → projeto → Variables**

O arquivo `railway.toml` já está configurado no projeto — Railway detecta automaticamente o serviço Python e mantém o worker rodando continuamente.

Verificar se o worker subiu:
- Railway → projeto → Deployments → ver logs em tempo real
- Deve aparecer: `worker_main iniciado, aguardando jobs...` (ou similar)

---

### Passo 5 — Verificar integração completa em produção

1. Acessar a URL do Vercel
2. Fazer login
3. Criar um projeto de teste e subir um DZT
4. Verificar nos logs do Railway que o worker pegou o job
5. Acompanhar o status avançando na interface

Se tudo funcionar: **sistema em produção**.

---

## Resumo rápido — comandos do dia a dia

| Ação | Comando |
|---|---|
| Rodar frontend local | `cd apps/web && npm run dev` |
| Rodar worker local | `cd services/worker && python worker_main.py` |
| Parar worker | `Ctrl+C` |
| Deploy frontend | `cd apps/web && vercel --prod` |
| Deploy worker | `railway up` (na raiz) |
| Ver logs Railway | `railway logs` |
| Limpar dados de teste | SQL Editor Supabase (ver Parte 1, Passo 1) |
| Regenerar tipos TS | `npx supabase gen types typescript --project-id ayyirgjlotetrqfhpnms > apps/web/lib/types/database.ts` |
