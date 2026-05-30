"""Teste ponta a ponta Fase 4 — cartografia (versão limpa)."""
import truststore; truststore.inject_into_ssl()
from dotenv import load_dotenv; load_dotenv()
from clients.supabase_client import SupabaseClient
from datetime import datetime, timezone

supa = SupabaseClient()
project_id = 'a9260663-daa8-4f4e-aedb-6d0c0b44c44a'  # teste_01

print("=== ETAPA 1: Estado do projeto ===")
proj = supa.get_project(project_id)
print(f"Projeto: {proj['nome']} | Status: {proj['status']}")

# ── Limpar reviews duplicados ────────────────────────────────────────────────
print("\n=== LIMPEZA: Reviews duplicados ===")
run_id = supa.get_latest_run_id(project_id)
profiles = [p for p in supa.get_profiles_for_project(project_id) if p['run_id'] == run_id]
t_r = supa._client.table('detected_targets').select('id').in_('profile_id', [p['id'] for p in profiles]).execute()
target_ids = [t['id'] for t in (t_r.data or [])]

rev_r = supa._client.table('technical_reviews').select('id, target_id, reviewed_at').in_('target_id', target_ids).order('reviewed_at', desc=True).execute()
all_reviews = rev_r.data or []
print(f"Reviews encontrados: {len(all_reviews)} para {len(target_ids)} targets")

# Manter apenas o mais recente por target
seen: set[str] = set()
to_delete: list[str] = []
for rv in all_reviews:
    if rv['target_id'] in seen:
        to_delete.append(rv['id'])
    else:
        seen.add(rv['target_id'])

if to_delete:
    supa._client.table('technical_reviews').delete().in_('id', to_delete).execute()
    print(f"Removidos {len(to_delete)} reviews duplicados. Restam: {len(all_reviews) - len(to_delete)}")
else:
    print(f"Sem duplicados. Reviews ok: {len(all_reviews)}")

# ── Garantir reviews para todos os targets ───────────────────────────────────
print("\n=== ETAPA 2: Garantir reviews ===")
existing_ids = {rv['target_id'] for rv in all_reviews if rv['id'] not in to_delete}
missing = [tid for tid in target_ids if tid not in existing_ids]
if missing:
    ai_r = supa._client.table('ai_interpretations').select('target_id,ia_tipo_sugerido,vai_para_planta_sugerido,vai_para_relatorio_sugerido').in_('target_id', missing).execute()
    ai_map = {a['target_id']: a for a in (ai_r.data or [])}
    now = datetime.now(timezone.utc).isoformat()
    rows = [{'target_id': tid, 'status_review': 'aprovado', 'tipo_final': ai_map.get(tid, {}).get('ia_tipo_sugerido'), 'vai_para_planta': bool(ai_map.get(tid, {}).get('vai_para_planta_sugerido', False)), 'vai_para_relatorio': bool(ai_map.get(tid, {}).get('vai_para_relatorio_sugerido', True)), 'reviewed_at': now} for tid in missing]
    supa._client.table('technical_reviews').insert(rows).execute()
    print(f"Inseridos {len(rows)} reviews faltantes")
else:
    print(f"Todos os {len(target_ids)} targets já têm review")

# ── Verificar targets elegíveis ──────────────────────────────────────────────
print("\n=== ETAPA 3: Targets para cartografia ===")
targets = supa.get_reviewed_targets(project_id)
print(f"Targets elegíveis (vai_planta OR vai_rel): {len(targets)}")
from collections import Counter
tipos = Counter(t.get('tipo_final') for t in targets)
print(f"Tipos: {dict(tipos)}")
print(f"vai_para_planta=True: {sum(1 for t in targets if t.get('vai_para_planta'))}")
print(f"vai_para_relatorio=True: {sum(1 for t in targets if t.get('vai_para_relatorio'))}")

# ── Garantir status revisao_concluida ────────────────────────────────────────
print("\n=== ETAPA 4: Status do projeto ===")
if proj['status'] not in ('revisao_concluida', 'aguardando_cartografia', 'cartografia_concluida'):
    supa.update_project_status(project_id, 'revisao_concluida')
    print("Status -> revisao_concluida")
else:
    print(f"Status atual: {proj['status']}")

# ── Criar/resetar job cartografia ───────────────────────────────────────────
print("\n=== ETAPA 5: Job cartografia ===")
# Cancelar jobs pendentes anteriores (status processando pode ter ficado travado)
old_jobs = supa._client.table('processing_jobs').select('id,status').eq('project_id', project_id).eq('job_type', 'cartografia').in_('status', ['aguardando', 'processando']).execute()
for j in (old_jobs.data or []):
    supa._client.table('processing_jobs').update({'status': 'erro', 'error_message': 'cancelado para re-teste'}).eq('id', j['id']).execute()
    print(f"Job {j['id'][:8]}… cancelado")

new_job = supa.create_job(project_id, 'cartografia')
supa.update_project_status(project_id, 'aguardando_cartografia')
print(f"Novo job criado: {new_job['id']}")

# ── Executar job ─────────────────────────────────────────────────────────────
print("\n=== ETAPA 6: Executar job cartografia ===")
from job_cartografia import handle_cartografia_job
jobs = supa.fetch_pending_jobs(1)
if jobs and jobs[0]['job_type'] == 'cartografia':
    handle_cartografia_job(supa, jobs[0])
    print("Job concluído")
else:
    print(f"ERRO: job esperado não encontrado. Encontrado: {jobs}")

# ── Verificar outputs ────────────────────────────────────────────────────────
print("\n=== ETAPA 7: Outputs gerados ===")
out = supa.get_cartography_output(project_id)
if out:
    print(f"ID:         {out['id']}")
    print(f"mode:       {out.get('cartography_mode')}")
    print(f"confidence: {out.get('cartography_confidence')}")
    print(f"source:     {out.get('cartography_source')}")
    print(f"status:     {out.get('status')}")
    csv_p   = out.get('csv_path')
    geo_p   = out.get('geojson_path')
    dxf_p   = out.get('dxf_dropbox_path')
    kml_p   = out.get('kml_dropbox_path')
    print(f"CSV:        {'OK -> ' + csv_p if csv_p else 'NAO GERADO'}")
    print(f"GeoJSON:    {'OK -> ' + geo_p if geo_p else 'NAO GERADO'}")
    print(f"DXF:        {'OK -> ' + dxf_p if dxf_p else 'NAO GERADO'}")
    print(f"KML:        {'OK (bloqueado sem GPS) -> ' + kml_p if kml_p else 'NAO GERADO (correto para DZT-only)'}")
    print(f"notes:      {(out.get('cartography_notes') or '')[:160]}")
    # Validar critérios de aceite
    print("\n=== CRITÉRIOS DE ACEITE ===")
    print(f"[{'OK' if csv_p else 'FALHOU'}] CSV gerado")
    print(f"[{'OK' if geo_p else 'FALHOU'}] GeoJSON gerado")
    print(f"[{'OK' if dxf_p else 'FALHOU'}] DXF gerado")
    print(f"[{'OK' if not kml_p else 'REVISAR'}] KML bloqueado sem GPS (kml_path={'None' if not kml_p else kml_p})")
    print(f"[{'OK' if out.get('cartography_mode') == 'profile_local' else 'REVISAR'}] Modo profile_local detectado")
    print(f"[{'OK' if out.get('cartography_confidence') == 'alta' else 'REVISAR'}] Confidence alta")
else:
    print("ERRO CRÍTICO: nenhum cartography_output encontrado no banco")
