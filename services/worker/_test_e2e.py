"""
_test_e2e.py — Teste ponta a ponta do pipeline ScanSOLO
Pipeline: Criar projeto -> Upload DZT -> GPR -> IA (auto-aceite) ->
          Interpretada -> Cartografia -> Relatorio

Uso: cd services/worker && python _test_e2e.py
     python _test_e2e.py --skip-ia    (pula OpenAI, insere reviews manualmente)
"""

import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))

try:
    import truststore; truststore.inject_into_ssl()
except ImportError:
    pass
from dotenv import load_dotenv
load_dotenv()

from pathlib import Path
from datetime import datetime, date, timezone

os.chdir(Path(__file__).parent)

from clients.supabase_client import SupabaseClient
from job_gpr import handle_gpr_job
from job_ia import handle_ia_job
from job_cartografia import handle_cartografia_job
from job_relatorio import handle_relatorio_job
from job_interpretada import handle_interpretada_job

SKIP_IA = "--skip-ia" in sys.argv

DZT_PATH = Path(
    r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO"
    r"\Solução01_Pipeline_operacional_automatizado\Exemplos_dados_brutos_georadar"
    r"\PATIO___001 (1).DZT"
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def sep(titulo):
    print(f"\n{'='*62}\n  {titulo}\n{'='*62}")

def ok(msg=""):
    print(f"  OK  {msg}")

def fail(msg):
    print(f"  FALHOU: {msg}")
    sys.exit(1)

def status(supa, pid):
    p = supa.get_project(pid)
    return (p or {}).get("status", "??")

def await_job(supa, pid, job_type):
    r = (supa._client.table("processing_jobs").select("*")
         .eq("project_id", pid).eq("job_type", job_type)
         .eq("status", "aguardando").limit(1).execute())
    return r.data[0] if r.data else None


# ── ETAPA 1 — Criar projeto ───────────────────────────────────────────────────
sep("ETAPA 1 — Criar projeto")
supa = SupabaseClient()
ts = datetime.now().strftime("%H%M%S")
r = supa._client.table("projects").insert({
    "nome":              f"E2E_Test_{ts}",
    "cliente":           "Teste Automatico",
    "estado":            "RJ",
    "data_levantamento": str(date.today()),
    "codigo_projeto":    f"E2E-{ts}",
    "status":            "aguardando_arquivos",
    "auto_accept_ia":    not SKIP_IA,
    "antena_freq_mhz":   270,
    "tem_pipe_locator":  False,
}).execute()
project_id = r.data[0]["id"]
ok(f"id={project_id}  nome=E2E_Test_{ts}")


# ── ETAPA 2 — Upload DZT ─────────────────────────────────────────────────────
sep("ETAPA 2 — Upload DZT")
if not DZT_PATH.exists():
    fail(f"DZT não encontrado: {DZT_PATH}")

dzt_bytes = DZT_PATH.read_bytes()
storage_path = f"{project_id}/{DZT_PATH.name}"
supa.upload_file("gpr-uploads", storage_path, dzt_bytes, "application/octet-stream")
supa._client.table("project_files").insert({
    "project_id":            project_id,
    "file_name":             DZT_PATH.name,
    "extension":             "dzt",
    "supabase_storage_path": storage_path,
    "size_bytes":            len(dzt_bytes),
    "status":                "confirmado",
}).execute()
ok(f"{DZT_PATH.name}  ({len(dzt_bytes)/1024:.0f} KB)  ->  gpr-uploads/{storage_path}")


# ── ETAPA 3 — Job GPR ────────────────────────────────────────────────────────
sep("ETAPA 3 — Job GPR (readgssi + detector Hough + fisica)")
supa.update_project_status(project_id, "aguardando_processamento")
gpr_job = supa.create_job(project_id, "gpr")
t0 = time.time()
handle_gpr_job(supa, gpr_job)
elapsed = time.time() - t0

profiles = supa.get_profiles_for_project(project_id)
total_targets = 0
for p in profiles:
    targets = supa.get_targets_for_profile(p["id"])
    total_targets += len(targets)
    alta  = sum(1 for t in targets if t.get("confidence_label_relatorio") == "alta")
    media = sum(1 for t in targets if t.get("confidence_label_relatorio") == "media")
    print(f"  {p['arquivo_dzt']:34s}  {len(targets):3d} alvos  (alta={alta} media={media})")

ok(f"{len(profiles)} profile(s)  |  {total_targets} alvos  |  {elapsed:.1f}s  |  status={status(supa, project_id)}")

if not profiles:
    fail("Nenhum profile gerado pelo GPR job.")


# ── ETAPA 4 — Job IA ─────────────────────────────────────────────────────────
sep(f"ETAPA 4 — Job IA  ({'SKIP — reviews manuais' if SKIP_IA else 'GPT-4o + auto_accept_ia=True'})")

run_id    = supa.get_latest_run_id(project_id)
profiles  = [p for p in supa.get_profiles_for_project(project_id) if p["run_id"] == run_id]
ia_job    = await_job(supa, project_id, "ia")

if SKIP_IA:
    # Marcar job IA como concluido sem rodar e inserir reviews manualmente
    if ia_job:
        supa.update_job_status(ia_job["id"], "concluido")
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    for p in profiles:
        for t in supa.get_targets_for_profile(p["id"]):
            lbl = t.get("confidence_label_relatorio", "baixa")
            rows.append({
                "target_id":        t["id"],
                "status_review":    "aprovado",
                "tipo_final":       "inconclusivo",
                "vai_para_planta":  lbl in ("alta", "media"),
                "vai_para_relatorio": lbl in ("alta", "media"),
                "reviewed_at":      now,
            })
    if rows:
        supa._client.table("technical_reviews").insert(rows).execute()
    supa.update_project_status(project_id, "revisao_concluida")
    ok(f"{len(rows)} reviews inseridas manualmente  |  status={status(supa, project_id)}")

elif ia_job:
    t0 = time.time()
    handle_ia_job(supa, ia_job)
    elapsed = time.time() - t0

    # Contar interpretações geradas
    for p in profiles:
        target_ids = [t["id"] for t in supa.get_targets_for_profile(p["id"])]
        ai_r = (supa._client.table("ai_interpretations").select("ia_tipo_sugerido")
                .in_("target_id", target_ids).execute())
        print(f"  {p['arquivo_dzt']:34s}  {len(ai_r.data or []):3d} interpretações IA")
        img = p.get("imagem_interpretada_url") or "(sem url)"
        print(f"    interpretada_ia: {img[:70]}")

    ok(f"{elapsed:.1f}s  |  status={status(supa, project_id)}")
else:
    ok(f"nenhum job IA pendente (já foi criado/processado)  |  status={status(supa, project_id)}")


# ── ETAPA 5 — Job Interpretada ────────────────────────────────────────────────
sep("ETAPA 5 — Job Interpretada (desenha marcadores sobre imagem revisada)")

# Garantir que o projeto está em revisao_concluida antes de criar o job
if status(supa, project_id) not in ("revisao_concluida", "processando_interpretada"):
    supa.update_project_status(project_id, "revisao_concluida")

supa._client.table("processing_jobs").insert({
    "project_id": project_id,
    "job_type":   "interpretada",
    "status":     "aguardando",
}).execute()
supa.update_project_status(project_id, "processando_interpretada")

interp_job = await_job(supa, project_id, "interpretada")
if interp_job:
    t0 = time.time()
    handle_interpretada_job(supa, interp_job)
    elapsed = time.time() - t0

    profiles = supa.get_profiles_for_project(project_id)
    for p in profiles:
        ist = p.get("imagem_interpretada_status", "N/A")
        url = (p.get("imagem_interpretada_url") or "(sem url)")[:70]
        print(f"  {p['arquivo_dzt']:34s}  status={ist}")
        print(f"    url: {url}")

    ok(f"{elapsed:.1f}s  |  status={status(supa, project_id)}")
else:
    print("  AVISO: job interpretada não encontrado (pode ter sido consumido já)")


# ── ETAPA 6 — Job Cartografia ─────────────────────────────────────────────────
sep("ETAPA 6 — Job Cartografia (DXF + KML + GeoJSON + CSV)")
supa.update_project_status(project_id, "aguardando_cartografia")
cart_job = supa.create_job(project_id, "cartografia")
t0 = time.time()
handle_cartografia_job(supa, cart_job)
elapsed = time.time() - t0

out = supa.get_cartography_output(project_id)
if out:
    print(f"  mode:    {out.get('cartography_mode')}")
    print(f"  status:  {out.get('status')}")
    print(f"  csv:     {out.get('csv_path', 'N/A')}")
    print(f"  geojson: {out.get('geojson_path', 'N/A')}")
    print(f"  dxf:     {out.get('dxf_dropbox_path', 'N/A')}")
    print(f"  kml:     {out.get('kml_dropbox_path', 'N/A')}")
    ok(f"{elapsed:.1f}s  |  status={status(supa, project_id)}")
else:
    print(f"  AVISO: nenhum output de cartografia gerado  |  status={status(supa, project_id)}")


# ── ETAPA 7 — Job Relatório ───────────────────────────────────────────────────
sep("ETAPA 7 — Job Relatório (DOCX + PDF)")
supa.update_project_status(project_id, "aguardando_relatorio")
rel_job = supa.create_job(project_id, "relatorio")
t0 = time.time()
handle_relatorio_job(supa, rel_job)
elapsed = time.time() - t0

proj_final = supa.get_project(project_id)
print(f"  docx_url: {(proj_final or {}).get('docx_storage_url', 'N/A')}")
print(f"  pdf_url:  {(proj_final or {}).get('pdf_storage_url', 'N/A')}")
ok(f"{elapsed:.1f}s  |  status={status(supa, project_id)}")


# ── RESULTADO FINAL ───────────────────────────────────────────────────────────
sep("RESULTADO FINAL")
proj_final   = supa.get_project(project_id)
status_final = (proj_final or {}).get("status", "??")
passou = status_final in ("relatorio_gerado", "finalizado")

print(f"  projeto_id:  {project_id}")
print(f"  status:      {status_final}")
print(f"  pipeline:    {'OK — ponta a ponta concluido' if passou else 'INCOMPLETO — ver etapas acima'}")

sys.exit(0 if passou else 1)
