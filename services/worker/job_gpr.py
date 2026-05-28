"""
GPR job handler — Fase 1B.

Flow:
  1. Fetch DZT file records for the project
  2. Download each DZT from Storage into a temp directory
  3. Run pipeline_v1.py via subprocess
  4. Parse CSV outputs → insert gpr_profiles + detected_targets
  5. Upload PNG images and CSV to Storage
  6. Clean up temp directory
"""

from __future__ import annotations

import csv
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

PIPELINE_SCRIPT = Path(__file__).parent / "pipeline" / "pipeline_v1.py"
DEFAULT_PRESET = "270mhz"


def handle_gpr_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    log.info("gpr_job_start", job_id=job_id, project_id=project_id, status_novo="processando_gpr")
    supa.update_job_status(job_id, "processando_gpr")
    supa.update_project_status(project_id, "processando_gpr")

    tmp_dir = tempfile.mkdtemp(prefix="scansolo_gpr_")
    try:
        input_dir = Path(tmp_dir) / "input"
        output_dir = Path(tmp_dir) / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        dzt_files = supa.get_dzt_files(project_id)
        if not dzt_files:
            raise RuntimeError(f"No confirmed DZT files for project {project_id}")

        log.info("downloading_dzt_files", count=len(dzt_files))
        for f in dzt_files:
            data = supa.download_file("gpr-uploads", f["supabase_storage_path"])
            (input_dir / f["file_name"]).write_bytes(data)

        _run_pipeline(input_dir, output_dir)

        run_id = str(uuid.uuid4())
        _persist_outputs(supa, project_id, run_id, output_dir)

        supa.update_job_status(job_id, "concluido")
        supa.update_project_status(project_id, "gpr_concluido")
        log.info("gpr_job_done", job_id=job_id, run_id=run_id, status_novo="concluido")

        supa.create_job(project_id, "ia")

    except Exception as exc:
        log.error("gpr_job_failed", job_id=job_id, error=str(exc), status_novo="erro")
        supa.update_job_status(job_id, "erro", error_message=str(exc))
        supa.update_project_status(project_id, "erro")
        raise

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _run_pipeline(input_dir: Path, output_dir: Path) -> None:
    cmd = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--input", str(input_dir),
        "--output", str(output_dir),
        "--preset", DEFAULT_PRESET,
    ]
    log.info("pipeline_start", cmd=" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("pipeline_stderr", stderr=result.stderr[-2000:])
        raise RuntimeError(f"pipeline_v1.py exited {result.returncode}: {result.stderr[-500:]}")
    log.info("pipeline_done", stdout_tail=result.stdout[-500:])


def _persist_outputs(supa: "SupabaseClient", project_id: str, run_id: str, output_dir: Path) -> None:
    index_path = output_dir / "index_projeto.csv"
    targets_dir = output_dir / "05_Tabela_Alvos"
    images_bruta_dir = output_dir / "01_Imagens_Brutas"
    images_proc_dir = output_dir / "02_Imagens_Processadas"

    if not index_path.exists():
        raise RuntimeError("Pipeline produced no index_projeto.csv")

    with open(index_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        index_rows = list(reader)

    for row in index_rows:
        dzt_name: str = row["arquivo_dzt"]
        stem = Path(dzt_name).stem

        profile_payload = {
            "project_id": project_id,
            "run_id": run_id,
            "arquivo_dzt": dzt_name,
            "n_tracos": _int(row.get("n_tracos")),
            "n_amostras": _int(row.get("n_amostras")),
            "profundidade_max_m": _float(row.get("profundidade_max_m")),
            "distancia_max_m": _float(row.get("distancia_max_m")),
            "velocity_mns": _float(row.get("velocity_mns")),
            "velocity_calibrada": row.get("velocity_calibrada") == "True",
            "config_hash": row.get("config_hash"),
        }
        profile = supa.insert_gpr_profile(profile_payload)
        profile_id: str = profile["id"]

        # Include profile_id in path to avoid collision when a DZT has multiple channels
        img_prefix = f"{project_id}/{run_id}/{profile_id[:8]}"

        img_updates: dict = {}
        for filename, col in [
            (f"{stem}_bruta.png", "imagem_bruta_url"),
            (f"{stem}_processada.png", "imagem_processada_url"),
            (f"{stem}_anotada_completa.png", "imagem_anotada_url"),
            (f"{stem}_anotada_alta_confianca.png", "imagem_alta_conf_url"),
        ]:
            src_dir = images_bruta_dir if "bruta" in filename else images_proc_dir
            url = _upload_image(supa, img_prefix, src_dir / filename)
            if url:
                img_updates[col] = url

        csv_path = targets_dir / f"{stem}_alvos.csv"
        if csv_path.exists():
            csv_storage_path = f"{project_id}/{run_id}/{profile_id[:8]}/{stem}_alvos.csv"
            supa.upload_file("gpr-tabelas", csv_storage_path, csv_path.read_bytes(), "text/csv")
            img_updates["csv_alvos_url"] = csv_storage_path

        if img_updates:
            supa._client.table("gpr_profiles").update(img_updates).eq("id", profile_id).execute()

        if csv_path.exists():
            targets = _parse_targets(csv_path, project_id, profile_id, run_id)
            supa.insert_detected_targets(targets)
            log.info("targets_inserted", profile_id=profile_id, count=len(targets))


def _upload_image(supa: "SupabaseClient", prefix: str, path: Path) -> str | None:
    if not path.exists():
        return None
    storage_path = f"{prefix}/{path.name}"
    supa.upload_file("gpr-images", storage_path, path.read_bytes(), "image/png")
    return supa.get_public_url("gpr-images", storage_path)


def _parse_targets(csv_path: Path, project_id: str, profile_id: str, run_id: str) -> list[dict]:
    targets = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            targets.append({
                "project_id": project_id,
                "profile_id": profile_id,
                "run_id": run_id,
                "arquivo_dzt": row.get("arquivo_dzt", ""),
                "rank": _int(row.get("rank")),
                "x_m": _float(row.get("x_m")),
                "depth_m": _float(row.get("depth_m")),
                "diam_est_m": _float(row.get("diam_est_m")),
                "diam_confianca": row.get("diam_confianca"),
                "fit_ok": row.get("fit_ok") == "True",
                "tipo_material": row.get("tipo_material"),
                "confianca_tipo": row.get("confianca_tipo"),
                "evidencia_raw": row.get("evidencia_raw") == "True",
                "evidencia_sem_agc": row.get("evidencia_sem_agc") == "True",
                "snr_local": _float(row.get("snr_local")),
                "confidence_score": _int(row.get("confidence_score_0_100")),
                "confidence_label_tecnico": _clamp_label_tecnico(row.get("confidence_label_tecnico")),
                "confidence_label_relatorio": _clamp_label_relatorio(row.get("confidence_label_relatorio")),
                "motivo_confianca": row.get("motivo_confianca"),
            })
    return targets


def _clamp_label_tecnico(v: str | None) -> str | None:
    return v if v in ("alta", "media", "baixa") else None


def _clamp_label_relatorio(v: str | None) -> str | None:
    return v if v in ("alta", "baixa") else None


def _int(v: str | None) -> int | None:
    try:
        return int(float(v)) if v is not None else None
    except (ValueError, TypeError):
        return None


def _float(v: str | None) -> float | None:
    try:
        return float(v) if v is not None else None
    except (ValueError, TypeError):
        return None
