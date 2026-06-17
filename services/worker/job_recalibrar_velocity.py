"""
job_recalibrar_velocity — Recalibração de velocity por projeto.

Recebe payload: { "project_id": "...", "velocity_mns": 0.20 }

Fluxo simplificado (sem redesenho de numpy — agendado para próximo processamento completo):
  1. Valida payload
  2. Busca perfis do run mais recente do projeto
  3. Recalcula profundidade com nova velocity
  4. Atualiza gpr_profiles.velocity_mns + profundidade_max_m
  5. Atualiza projects.processing_config.velocity_mns
  6. Marca job concluido

Nota: as imagens PNG NÃO são redesenhadas aqui — elas serão regeneradas no
próximo job GPR completo. O essencial é que processing_config e gpr_profiles
fiquem atualizados para que o pipeline use a nova velocity.
"""

from __future__ import annotations

import structlog

if False:  # type-check only
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()


def handle_recalibrar_velocity_job(job_id: str, payload: dict, supa: "SupabaseClient") -> None:
    project_id = payload.get("project_id")
    velocity_mns_raw = payload.get("velocity_mns")

    if not project_id or velocity_mns_raw is None:
        msg = "payload deve conter project_id e velocity_mns"
        log.error("recalibrar_velocity_payload_invalido", job_id=job_id, msg=msg)
        supa.update_job_status(job_id, "erro", error_message=msg)
        return

    try:
        nova_velocity = float(velocity_mns_raw)
    except (TypeError, ValueError) as exc:
        msg = f"velocity_mns inválido: {velocity_mns_raw}"
        log.error("recalibrar_velocity_valor_invalido", job_id=job_id, error=str(exc))
        supa.update_job_status(job_id, "erro", error_message=msg)
        return

    if not (0.04 <= nova_velocity <= 0.35):
        msg = f"velocity_mns={nova_velocity} fora do intervalo físico válido [0.04, 0.35]"
        log.error("recalibrar_velocity_fora_intervalo", job_id=job_id, nova_velocity=nova_velocity)
        supa.update_job_status(job_id, "erro", error_message=msg)
        return

    supa.update_job_status(job_id, "processando")
    log.info("recalibrar_velocity_start", job_id=job_id, project_id=project_id, nova_velocity=nova_velocity)

    # ── 1. Buscar run_id mais recente ─────────────────────────────────────────
    run_id = supa.get_latest_run_id(project_id)
    if not run_id:
        msg = f"Nenhum run encontrado para project_id={project_id}"
        log.error("recalibrar_velocity_no_run", project_id=project_id)
        supa.update_job_status(job_id, "erro", error_message=msg)
        return

    # ── 2. Buscar perfis do run mais recente ─────────────────────────────────
    all_profiles = supa.get_profiles_for_project(project_id)
    perfis = [p for p in all_profiles if p.get("run_id") == run_id]

    if not perfis:
        msg = f"Nenhum perfil encontrado para run_id={run_id}"
        log.error("recalibrar_velocity_no_profiles", project_id=project_id, run_id=run_id)
        supa.update_job_status(job_id, "erro", error_message=msg)
        return

    log.info("recalibrar_velocity_perfis", n=len(perfis), run_id=run_id)

    # ── 3. Atualizar cada perfil ──────────────────────────────────────────────
    atualizados = 0
    for perfil in perfis:
        profile_id = perfil["id"]
        try:
            # Reconstruir twtt_max_ns a partir da velocity e profundidade antigas
            velocity_antiga = perfil.get("velocity_mns") or 0.10
            prof_antiga = perfil.get("profundidade_max_m")

            if prof_antiga and velocity_antiga:
                twtt_max_ns = prof_antiga * 2.0 / velocity_antiga
                nova_profundidade = round(twtt_max_ns * nova_velocity / 2.0, 2)
            else:
                nova_profundidade = None

            update_payload: dict = {"velocity_mns": nova_velocity}
            if nova_profundidade is not None:
                update_payload["profundidade_max_m"] = nova_profundidade

            supa._client.table("gpr_profiles") \
                .update(update_payload) \
                .eq("id", profile_id) \
                .execute()

            log.info(
                "recalibrar_velocity_perfil_atualizado",
                profile_id=profile_id,
                velocity_antiga=velocity_antiga,
                nova_velocity=nova_velocity,
                prof_antiga=prof_antiga,
                nova_profundidade=nova_profundidade,
            )
            atualizados += 1

        except Exception as exc:
            log.warning("recalibrar_velocity_perfil_falhou", profile_id=profile_id, error=str(exc))

    # ── 4. Atualizar processing_config do projeto ────────────────────────────
    try:
        proj_result = supa._client.table("projects") \
            .select("processing_config") \
            .eq("id", project_id) \
            .single() \
            .execute()
        cfg: dict = dict(proj_result.data.get("processing_config") or {})
        cfg["velocity_mns"] = nova_velocity
        supa._client.table("projects") \
            .update({"processing_config": cfg}) \
            .eq("id", project_id) \
            .execute()
        log.info("recalibrar_velocity_project_config_atualizado", project_id=project_id, nova_velocity=nova_velocity)
    except Exception as exc:
        log.warning("recalibrar_velocity_project_config_falhou", project_id=project_id, error=str(exc))

    log.info(
        "recalibrar_velocity_concluido",
        job_id=job_id,
        project_id=project_id,
        perfis_atualizados=atualizados,
        total_perfis=len(perfis),
        nova_velocity=nova_velocity,
        aviso="Imagens PNG serão redesenhadas no próximo job GPR completo",
    )
    supa.update_job_status(job_id, "concluido")
