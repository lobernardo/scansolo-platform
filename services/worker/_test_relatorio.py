"""
Teste ponta a ponta — Fase 5B: Relatório DOCX + PDF.
Usa projeto teste_01 (deve estar em cartografia_concluida ou relatorio_gerado).
"""
import sys, os

LOG_PATH = r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO\scansolo-platform\services\worker\_test_relatorio.log"
sys.stdout = open(LOG_PATH, "w", buffering=1, encoding="utf-8")
sys.stderr = sys.stdout

import truststore; truststore.inject_into_ssl()
from dotenv import load_dotenv
load_dotenv(r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO\scansolo-platform\services\worker\.env")

os.chdir(r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO\scansolo-platform\services\worker")

project_id = "a9260663-daa8-4f4e-aedb-6d0c0b44c44a"  # teste_01

from clients.supabase_client import SupabaseClient
supa = SupabaseClient()

# ── Estado inicial ──────────────────────────────────────────────────────────
print("=== ESTADO INICIAL ===")
proj = supa.get_project(project_id)
print(f"Projeto: {proj['nome']} | Status: {proj['status']}")

# ── Garantir reviews existentes ─────────────────────────────────────────────
print("\n=== REVIEWS ===")
run_id = supa.get_latest_run_id(project_id)
profiles = [p for p in supa.get_profiles_for_project(project_id) if p.get("run_id") == run_id]
print(f"Profiles no run atual: {len(profiles)}")

profile_ids = [p["id"] for p in profiles]
if profile_ids:
    t_r = supa._client.table("detected_targets").select("id").in_("profile_id", profile_ids).execute()
    target_ids = [t["id"] for t in (t_r.data or [])]
    print(f"Targets detectados: {len(target_ids)}")

    if target_ids:
        rev_r = supa._client.table("technical_reviews").select("target_id").in_("target_id", target_ids).execute()
        existing_reviews = {r["target_id"] for r in (rev_r.data or [])}
        print(f"Reviews já existentes: {len(existing_reviews)}")

        missing = [tid for tid in target_ids if tid not in existing_reviews]
        if missing:
            from datetime import datetime, timezone
            ai_r = supa._client.table("ai_interpretations").select(
                "target_id,ia_tipo_sugerido,vai_para_planta_sugerido,vai_para_relatorio_sugerido"
            ).in_("target_id", missing).execute()
            ai_map = {a["target_id"]: a for a in (ai_r.data or [])}
            now = datetime.now(timezone.utc).isoformat()
            rows = [
                {
                    "target_id": tid,
                    "status_review": "aprovado",
                    "tipo_final": ai_map.get(tid, {}).get("ia_tipo_sugerido"),
                    "vai_para_planta": bool(ai_map.get(tid, {}).get("vai_para_planta_sugerido", False)),
                    "vai_para_relatorio": bool(ai_map.get(tid, {}).get("vai_para_relatorio_sugerido", True)),
                    "reviewed_at": now,
                }
                for tid in missing
            ]
            supa._client.table("technical_reviews").insert(rows).execute()
            print(f"Reviews inseridos para {len(rows)} targets faltantes")

# ── Preparar status do projeto ──────────────────────────────────────────────
print("\n=== PREPARAR PROJETO ===")
supa.update_project_status(project_id, "aguardando_relatorio")
print("Projeto -> aguardando_relatorio")

# ── Criar job relatorio ─────────────────────────────────────────────────────
print("\n=== CRIAR JOB RELATORIO ===")
# Cancelar jobs travados
jobs_r = supa._client.table("processing_jobs").select("id,status").eq("project_id", project_id).eq("job_type", "relatorio").execute()
for j in (jobs_r.data or []):
    if j["status"] in ("processando", "aguardando"):
        supa._client.table("processing_jobs").update({"status": "erro"}).eq("id", j["id"]).execute()
        print(f"Job {j['id']} marcado como erro (era {j['status']})")

job = supa.create_job(project_id, "relatorio")
print(f"Job criado: {job['id']}")

# ── Rodar o job diretamente ─────────────────────────────────────────────────
print("\n=== EXECUTAR handle_relatorio_job ===")
from job_relatorio import handle_relatorio_job
handle_relatorio_job(supa, job)

# ── Verificar outputs ───────────────────────────────────────────────────────
print("\n=== VERIFICAR OUTPUTS ===")
proj_final = supa.get_project(project_id)
print(f"Status final do projeto: {proj_final['status']}")

output = supa.get_latest_report_output(project_id)
if output:
    print(f"report_output id:         {output['id']}")
    print(f"  version:                {output['version']}")
    print(f"  status:                 {output['status']}")
    print(f"  docx_dropbox_path:      {output.get('docx_dropbox_path')}")
    print(f"  docx_storage_url:       {output.get('docx_storage_url')}")
    print(f"  pdf_dropbox_path:       {output.get('pdf_dropbox_path')}")
    print(f"  pdf_storage_url:        {output.get('pdf_storage_url')}")
    print(f"  dados_usados_json:      {output.get('dados_usados_json')}")
else:
    print("ERRO: nenhum report_output gerado")

# ── Baixar DOCX e validar ───────────────────────────────────────────────────
print("\n=== VALIDAR DOCX ===")
if output and output.get("docx_dropbox_path"):
    try:
        docx_bytes = supa.download_file("gpr-tabelas", output["docx_dropbox_path"])
        print(f"DOCX baixado: {len(docx_bytes)} bytes")

        import io
        from docx import Document
        doc = Document(io.BytesIO(docx_bytes))
        full_text = "\n".join(p.text for p in doc.paragraphs)

        checks = {
            "Capa com 'Relatório de Levantamento'": "Relatório de Levantamento" in full_text,
            "Seção 3.1 com texto definitivo (hipérbole)": "hipérbole" in full_text,
            "Seção 3.2 com texto definitivo (Pipe Locator)": "proteção catódica" in full_text,
            "Conclusão definitiva (geratriz superior)": "geratriz superior" in full_text,
            "Seção Resultados presente": "RESULTADOS" in full_text,
            "Sem boilerplate antigo (GPR method)": "ondas eletromagnéticas de radiofrequência" not in full_text,
        }
        for label, ok in checks.items():
            print(f"  {'✓' if ok else '✗'} {label}")

        # Salvar DOCX localmente para inspeção
        out_path = r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO\scansolo-platform\services\worker\_relatorio_gerado.docx"
        with open(out_path, "wb") as f:
            f.write(docx_bytes)
        print(f"\nDOCX salvo em: {out_path}")
    except Exception as e:
        print(f"ERRO ao baixar/validar DOCX: {e}")
        import traceback; traceback.print_exc()
else:
    print("SKIP: docx_dropbox_path não encontrado no output")

# ── Verificar PDF ───────────────────────────────────────────────────────────
print("\n=== VERIFICAR PDF ===")
if output and output.get("pdf_storage_url"):
    print(f"PDF gerado: {output['pdf_storage_url']}")
    pdf_bytes = supa.download_file("gpr-tabelas", output["pdf_dropbox_path"])
    print(f"PDF baixado: {len(pdf_bytes)} bytes")
    out_pdf = r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO\scansolo-platform\services\worker\_relatorio_gerado.pdf"
    with open(out_pdf, "wb") as f:
        f.write(pdf_bytes)
    print(f"PDF salvo em: {out_pdf}")
else:
    print("PDF não gerado (LibreOffice ausente ou falhou — comportamento esperado se não instalado)")

print("\n=== DONE ===")
sys.stdout.flush()
