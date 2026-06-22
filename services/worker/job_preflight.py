"""
job_preflight.py — Job leve de preflight DZT-first.

Responsabilidade:
  1. Baixar os DZTs do projeto do Storage para um tmpdir
  2. Para cada DZT: rodar extract_dzt_metadata + recommend_processing_config
  3. Salvar resultado em projects.processing_config._preflight (JSONB, sem migration)
  4. Atualizar status do projeto para "aguardando_confirmacao"
  5. Atualizar status do job para "concluido"

O que este job NAO faz:
  - Nao chama process_dzt (nenhum processamento de sinal)
  - Nao gera imagens
  - Nao cria gpr_profiles
  - Nao cria job GPR pesado
  - Nao altera pipeline_v1.py nem o motor legado

Fluxo de status:
  job:     aguardando -> processando -> concluido | erro
  projeto: (qualquer) -> aguardando_preflight -> aguardando_confirmacao | erro
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

from gpr_engine.preflight import extract_dzt_metadata, recommend_processing_config

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()


def handle_preflight_job(supa: "SupabaseClient", job: dict) -> None:
    """
    Handler do job de preflight leve.

    Chamado pelo dispatcher do worker quando job_type='preflight'.
    Lê o DZT via DZTReader (somente header + array bruto), extrai metadados
    físicos e gera recomendações de configuração sem rodar o processamento pesado.

    :param supa: SupabaseClient com service role key
    :param job:  Row de processing_jobs (dict com id, project_id, payload)
    """
    job_id     = job["id"]
    project_id = job["project_id"]

    log.info("preflight_job_start", job_id=job_id, project_id=project_id)

    supa.update_job_status(job_id, "processando")
    supa.update_project_status(project_id, "aguardando_preflight")

    tmp_dir: str | None = None

    try:
        # ── 1. Buscar arquivos DZT do projeto ───────────────────────────────
        dzt_files = supa.get_dzt_files(project_id)
        if not dzt_files:
            raise RuntimeError(f"Nenhum DZT confirmado para o projeto {project_id}")

        log.info("preflight_dzts_found", count=len(dzt_files), project_id=project_id)

        # ── 2. Ler processing_config + preset do projeto ────────────────────
        proj_row = supa.get_project(project_id)
        current_config: dict = (proj_row or {}).get("processing_config") or {}
        preset_id: str | None = (proj_row or {}).get("preset_id")

        # Contexto de frequência para o recomendador — necessário para frequency_mismatch.
        # Prioridade: (1) override explícito em processing_config; (2) preset do projeto.
        # Sem isso, mismatch nunca dispara quando a Nova Entrada usa preset 270 MHz
        # e o DZT detecta 350 MHz.
        selected_preset: dict = {}
        if current_config.get("antenna_freq_mhz"):
            selected_preset["antenna_freq_mhz"] = int(current_config["antenna_freq_mhz"])
        elif preset_id:
            try:
                pr = (
                    supa._client.table("gpr_presets")
                    .select("antenna_freq_mhz, name")
                    .eq("id", preset_id)
                    .single()
                    .execute()
                )
                preset_freq = (pr.data or {}).get("antenna_freq_mhz")
                preset_name = (pr.data or {}).get("name", "")
                if preset_freq:
                    selected_preset["antenna_freq_mhz"] = int(preset_freq)
                    log.info(
                        "preflight_preset_freq_loaded",
                        preset_id=preset_id,
                        preset_name=preset_name,
                        antenna_freq_mhz=preset_freq,
                    )
            except Exception as exc:
                log.warning(
                    "preflight_preset_fetch_failed",
                    preset_id=preset_id,
                    error=str(exc),
                )

        # ── 3. Baixar DZTs e rodar preflight por arquivo ─────────────────────
        tmp_dir = tempfile.mkdtemp(prefix="scansolo_preflight_")
        preflight_results: dict = {}

        for f in dzt_files:
            filename   = f["file_name"]
            stor_path  = f["supabase_storage_path"]

            log.info("preflight_dzt_download", filename=filename)
            raw_bytes = supa.download_file("gpr-uploads", stor_path)
            dzt_path  = Path(tmp_dir) / filename
            dzt_path.write_bytes(raw_bytes)

            log.info("preflight_dzt_read", filename=filename, bytes=len(raw_bytes))
            metadata = extract_dzt_metadata(dzt_path)

            recommendation = recommend_processing_config(
                metadata,
                selected_preset=selected_preset,
                project_config=current_config,
            )

            # Avisos de preflight para o log
            for w in metadata.get("warnings", []):
                log.warning("preflight_metadata_warning", filename=filename, msg=w)
            if recommendation.get("frequency_mismatch"):
                log.warning(
                    "preflight_frequency_mismatch",
                    filename=filename,
                    detected=recommendation.get("detected_freq_mhz"),
                    selected=recommendation.get("selected_preset_freq_mhz"),
                )

            preflight_results[filename] = {
                "dzt_metadata":   metadata,
                "recommendation": recommendation,
            }

            log.info(
                "preflight_dzt_done",
                filename=filename,
                antenna_freq_mhz_detected=metadata.get("antenna_freq_mhz_detected"),
                velocity_header_mns=metadata.get("velocity_header_mns"),
                header_confidence=metadata.get("header_confidence"),
                recommended_velocity_mns=recommendation.get("recommended_velocity_mns"),
                frequency_mismatch=recommendation.get("frequency_mismatch"),
            )

        # ── 4. Salvar _preflight em processing_config (JSONB, sem migration) ─
        # Preserva todos os campos existentes (engine, preset, overrides, etc.)
        # Os campos com _ são internos; o pipeline GPR ignora chaves desconhecidas
        new_config: dict = {
            **current_config,
            "_preflight":      preflight_results,
            "_preflight_done": True,
        }

        supa._client \
            .table("projects") \
            .update({"processing_config": new_config}) \
            .eq("id", project_id) \
            .execute()

        log.info(
            "preflight_config_saved",
            project_id=project_id,
            n_files=len(preflight_results),
            keys_preserved=list(current_config.keys()),
        )

        # ── 5. Atualizar status ───────────────────────────────────────────────
        supa.update_project_status(project_id, "aguardando_confirmacao")
        supa.update_job_status(job_id, "concluido")

        log.info(
            "preflight_job_done",
            job_id=job_id,
            project_id=project_id,
            n_files=len(preflight_results),
        )

    except Exception as exc:
        log.error("preflight_job_failed", job_id=job_id, error=str(exc))
        try:
            supa.update_job_status(job_id, "erro", error_message=str(exc))
        except Exception as e:
            log.warning("preflight_update_job_status_failed", job_id=job_id, error=str(e))
        try:
            supa.update_project_status(project_id, "erro")
        except Exception as e:
            log.warning("preflight_update_project_status_failed", project_id=project_id, error=str(e))
        raise

    finally:
        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
