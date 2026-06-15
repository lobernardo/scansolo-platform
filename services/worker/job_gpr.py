"""
GPR job handler — Fase 1B + reprocessamento por perfil individual.

Flow (job completo, sem payload.profile_id):
  1. Fetch DZT file records for the project
  2. Download each DZT from Storage into a temp directory
  3. Run pipeline_v1.py via subprocess
  4. Parse CSV outputs → insert gpr_profiles + detected_targets
  5. Upload PNG images and CSV to Storage
  6. Clean up temp directory

Flow (reprocessamento, com payload.profile_id):
  1. Fetch apenas o DZT do perfil especificado
  2. Baixar e rodar pipeline com filtros customizados (se fornecidos)
  3. Persistir novos resultados e atualizar filtros_customizados para rastreabilidade
  4. NÃO altera status do projeto nem cria job de IA
"""

from __future__ import annotations

import csv
import json
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


# ── Entry point ───────────────────────────────────────────────────────────────

def handle_gpr_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    # Reprocessamento por perfil individual (payload com profile_id)
    payload: dict = job.get("payload") or {}
    profile_id_reprocess: str | None = payload.get("profile_id")
    filtros_customizados: dict | None = payload.get("filtros_customizados")
    is_reprocess = bool(profile_id_reprocess)

    if is_reprocess:
        log.info(
            "gpr_reprocess_start",
            job_id=job_id,
            project_id=project_id,
            profile_id=profile_id_reprocess,
        )
        supa.update_job_status(job_id, "processando")
        # Não altera status do projeto no reprocessamento de perfil individual
    else:
        log.info("gpr_job_start", job_id=job_id, project_id=project_id)
        supa.update_job_status(job_id, "processando_gpr")
        supa.update_project_status(project_id, "processando_gpr")

    tmp_dir = tempfile.mkdtemp(prefix="scansolo_gpr_")
    try:
        input_dir = Path(tmp_dir) / "input"
        output_dir = Path(tmp_dir) / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        # Selecionar DZTs a processar
        if is_reprocess:
            dzt_files = _get_profile_dzt(supa, project_id, profile_id_reprocess)
            if not dzt_files:
                raise RuntimeError(
                    f"DZT não encontrado para o perfil {profile_id_reprocess}"
                )
        else:
            dzt_files = supa.get_dzt_files(project_id)
            if not dzt_files:
                raise RuntimeError(f"No confirmed DZT files for project {project_id}")

        log.info("downloading_dzt_files", count=len(dzt_files))
        for f in dzt_files:
            data = supa.download_file("gpr-uploads", f["supabase_storage_path"])
            (input_dir / f["file_name"]).write_bytes(data)

        # Determinar config de processamento
        raw_config = _get_processing_config(supa, project_id)
        tipo_solo = (raw_config or {}).get("tipo_solo", "standard")

        if filtros_customizados:
            processing_config = _filtros_to_pipeline_config(filtros_customizados)
            log.info("reprocess_custom_filters", filters=filtros_customizados, config=processing_config)
        else:
            processing_config = raw_config

        _run_pipeline(input_dir, output_dir, processing_config=processing_config, tipo_solo=tipo_solo)

        run_id = str(uuid.uuid4())
        new_profiles = _persist_outputs(
            supa, project_id, run_id, output_dir,
            existing_profile_id=profile_id_reprocess if is_reprocess else None,
        )

        # Gravar filtros_customizados nos perfis criados (rastreabilidade)
        if is_reprocess and filtros_customizados and new_profiles:
            for p in new_profiles:
                try:
                    supa._client.table("gpr_profiles") \
                        .update({"filtros_customizados": filtros_customizados}) \
                        .eq("id", p["id"]).execute()
                except Exception as exc:
                    log.warning("filtros_customizados_update_failed", profile_id=p["id"], error=str(exc))

        supa.update_job_status(job_id, "concluido")

        if is_reprocess:
            log.info("gpr_reprocess_done", job_id=job_id, run_id=run_id, profiles=len(new_profiles))
        else:
            supa.update_project_status(project_id, "gpr_concluido")
            log.info("gpr_job_done", job_id=job_id, run_id=run_id)
            skip_ia = (raw_config or {}).get("skip_ia", False)
            if skip_ia:
                log.info("gpr_skip_ia", project_id=project_id)
            else:
                supa.create_job(project_id, "ia")

    except Exception as exc:
        log.error("gpr_job_failed", job_id=job_id, error=str(exc))
        supa.update_job_status(job_id, "erro", error_message=str(exc))
        if not is_reprocess:
            supa.update_project_status(project_id, "erro")
        raise

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── Helpers de configuração ───────────────────────────────────────────────────

def _get_processing_config(supa: "SupabaseClient", project_id: str) -> dict | None:
    """Lê processing_config do projeto (preset configurado na UI de nova entrada)."""
    try:
        result = (
            supa._client.table("projects")
            .select("processing_config")
            .eq("id", project_id)
            .single()
            .execute()
        )
        cfg = (result.data or {}).get("processing_config")
        if cfg and isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    return None


def _get_profile_dzt(
    supa: "SupabaseClient", project_id: str, profile_id: str
) -> list[dict]:
    """Retorna o registro de project_files correspondente ao DZT de um perfil específico."""
    try:
        r = (
            supa._client.table("gpr_profiles")
            .select("arquivo_dzt")
            .eq("id", profile_id)
            .single()
            .execute()
        )
        if not r.data:
            return []
        arquivo_dzt: str = r.data["arquivo_dzt"]

        r2 = (
            supa._client.table("project_files")
            .select("file_name, supabase_storage_path")
            .eq("project_id", project_id)
            .eq("file_name", arquivo_dzt)
            .eq("status", "confirmado")
            .limit(1)
            .execute()
        )
        return r2.data or []
    except Exception as exc:
        log.warning("get_profile_dzt_failed", profile_id=profile_id, error=str(exc))
        return []


def _filtros_to_pipeline_config(filtros: dict) -> dict:
    """
    Converte FilterState (frontend) em dict de override para o preset do pipeline.

    Convenção para desativar filtros: valor 0 → pipeline pula a etapa.
      dewow_window=0      → sem dewow
      bgremoval_traces=0  → sem background removal
      bandpass_low_mhz=0  → sem bandpass
      tpow_power=0        → sem tpow gain
    """
    cfg: dict = {}

    # Dewow
    if not filtros.get("dewow", True):
        cfg["dewow_window"] = 0

    # Background removal
    if not filtros.get("background_removal", True):
        cfg["bgremoval_traces"] = 0

    # Bandpass
    if filtros.get("bandpass", True):
        if "bandpass_low" in filtros:
            cfg["bandpass_low_mhz"] = int(filtros["bandpass_low"])
        if "bandpass_high" in filtros:
            cfg["bandpass_high_mhz"] = int(filtros["bandpass_high"])
    else:
        cfg["bandpass_low_mhz"] = 0  # desativa no pipeline

    # Gain
    if filtros.get("gain", True):
        gain_type = filtros.get("gain_type", "linear")
        # tpow_power=0 usa AGC; valores positivos = tpow linear/exponencial
        if gain_type == "agc":
            cfg["tpow_power"] = 0  # pipeline usará só AGC
        # Para linear/exponencial, mantém o preset (tpow já é o padrão)
    else:
        cfg["tpow_power"] = 0  # desativa tpow; AGC ainda é aplicado internamente

    # Contraste
    if "contrast" in filtros:
        cfg["contrast"] = float(filtros["contrast"])

    return cfg


# ── Pipeline subprocess ───────────────────────────────────────────────────────

def _run_pipeline(
    input_dir: Path,
    output_dir: Path,
    processing_config: dict | None = None,
    tipo_solo: str = "standard",
) -> None:
    cmd = [
        sys.executable,
        str(PIPELINE_SCRIPT),
        "--input", str(input_dir),
        "--output", str(output_dir),
        "--preset", DEFAULT_PRESET,
        "--solo", tipo_solo,
    ]

    if processing_config:
        cfg_path = output_dir / "filter_config.json"
        cfg_path.write_text(json.dumps(processing_config), encoding="utf-8")
        cmd += ["--filter-config", str(cfg_path)]
        log.info("pipeline_filter_config", config=processing_config)
    else:
        cmd.append("--sem-ia-imagem")

    log.info("pipeline_start", cmd=" ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        log.error("pipeline_stderr", stderr=result.stderr)
        raise RuntimeError(f"pipeline_v1.py exited {result.returncode}: {result.stderr[-1000:]}")
    log.info("pipeline_done", stdout_tail=result.stdout[-500:])


# ── Persistência ──────────────────────────────────────────────────────────────

def _persist_outputs(
    supa: "SupabaseClient", project_id: str, run_id: str, output_dir: Path,
    existing_profile_id: str | None = None,
) -> list[dict]:
    """
    Lê index_projeto.csv, sobe imagens/CSVs e insere/atualiza gpr_profiles + detected_targets.

    existing_profile_id: quando fornecido (reprocessamento individual), atualiza o perfil
    existente em vez de inserir um novo.

    Retorna a lista de perfis processados (cada item tem ao menos {"id": ..., "arquivo_dzt": ...}).
    """
    index_path = output_dir / "index_projeto.csv"
    targets_dir = output_dir / "05_Tabela_Alvos"
    images_bruta_dir = output_dir / "01_Imagens_Brutas"
    images_proc_dir = output_dir / "02_Imagens_Processadas"

    if not index_path.exists():
        raise RuntimeError("Pipeline produced no index_projeto.csv")

    with open(index_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        index_rows = list(reader)

    created_profiles: list[dict] = []

    for row in index_rows:
        dzt_name: str = row["arquivo_dzt"]
        stem = Path(dzt_name).stem

        if existing_profile_id:
            profile_id = existing_profile_id
        else:
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
                # v1.2.0: campos SNR
                "snr_imagem_db":      _float(row.get("snr_imagem_db")),
                "snr_imagem_ratio":   _float(row.get("snr_imagem_ratio")),
                "modo_processamento": row.get("modo_processamento") or "padrao",
                "tipo_solo":          row.get("tipo_solo") or "standard",
            }
            profile = supa.insert_gpr_profile(profile_payload)
            profile_id = profile["id"]
        created_profiles.append({"id": profile_id, "arquivo_dzt": dzt_name})

        img_prefix = f"{project_id}/{run_id}/{profile_id[:8]}"

        img_updates: dict = {}
        for filename, col in [
            (f"{stem}_bruta.png", "imagem_bruta_url"),
            (f"{stem}_processada.png", "imagem_processada_url"),
            (f"{stem}_anotada_completa.png", "imagem_anotada_url"),
            (f"{stem}_anotada_alta_confianca.png", "imagem_alta_conf_url"),
            (f"{stem}_radargrama_preview_radan_5m.png", "imagem_preview_radan_5m_url"),
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

        # v1.2.0: SNR fields — inclui reprocessamento individual (sem profile_payload insert)
        if existing_profile_id:
            if row.get("snr_imagem_db") is not None:
                img_updates["snr_imagem_db"] = _float(row.get("snr_imagem_db"))
            if row.get("snr_imagem_ratio") is not None:
                img_updates["snr_imagem_ratio"] = _float(row.get("snr_imagem_ratio"))
            img_updates["modo_processamento"] = row.get("modo_processamento") or "padrao"
            img_updates["tipo_solo"] = row.get("tipo_solo") or "standard"

        if img_updates:
            supa._client.table("gpr_profiles").update(img_updates).eq("id", profile_id).execute()

        if csv_path.exists():
            if existing_profile_id:
                supa._client.table("detected_targets").delete().eq("profile_id", profile_id).execute()
                log.info("targets_deleted_for_reprocess", profile_id=profile_id)
            targets = _parse_targets(csv_path, project_id, profile_id, run_id)
            supa.insert_detected_targets(targets)
            log.info("targets_inserted", profile_id=profile_id, count=len(targets))

    return created_profiles


def _upload_image(supa: "SupabaseClient", prefix: str, path: Path) -> str | None:
    if not path.exists():
        return None
    storage_path = f"{prefix}/{path.name}"
    supa.upload_file("gpr-images", storage_path, path.read_bytes(), "image/png")
    return supa.get_public_url("gpr-images", storage_path)


def _parse_targets(
    csv_path: Path, project_id: str, profile_id: str, run_id: str
) -> list[dict]:
    targets = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        log.info("csv_fieldnames", path=str(csv_path), fields=list(reader.fieldnames or []))
        for row in reader:
            raw_rel = (row.get("confidence_label_relatorio") or "").strip()
            raw_tec = (row.get("confidence_label_tecnico") or "").strip()
            log.debug(
                "csv_row_labels",
                rank=row.get("rank"),
                label_tec=raw_tec,
                label_rel=raw_rel,
            )
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
                "confidence_label_tecnico": _clamp_label_tecnico(raw_tec),
                "confidence_label_relatorio": _clamp_label_relatorio(raw_rel),
                "motivo_confianca": row.get("motivo_confianca"),
            })
    return targets


# ── Relatório de inferências ──────────────────────────────────────────────────

def gerar_relatorio_inferencias(
    df_campo: list[dict],
    projeto: dict,
    preset: str = "270mhz",
) -> str:
    """Gera relatório .txt de inferências (alta + média confiança) para revisão técnica."""
    from datetime import date as _date

    def _f(row: dict, key: str, dec: int = 2) -> str:
        v = row.get(key)
        if v is None or str(v).strip() in ("", "None", "nan"):
            return "—"
        try:
            return f"{float(v):.{dec}f}"
        except (ValueError, TypeError):
            return str(v)

    campo = [
        r for r in df_campo
        if r.get("confidence_label_tecnico") in ("alta", "media")
    ]
    campo.sort(key=lambda r: (r.get("arquivo_dzt") or "", int(float(r.get("rank") or 0))))

    n_alta = sum(1 for r in campo if r.get("confidence_label_tecnico") == "alta")
    n_media = len(campo) - n_alta

    nome = projeto.get("nome") or "—"
    codigo = projeto.get("codigo_projeto") or nome
    data_str = _date.today().strftime("%d/%m/%Y")

    SEP = "=" * 102
    DIV = "-" * 102

    col_header = (
        f"{'Linha':<22} | {'#':>3} | {'Dist.(m)':>8} | {'P.Topo(m)':>9} | "
        f"{'P.Eixo(m)':>9} | {'Diâm.(m)':>8} | {'Larg.(m)':>8} | {'Tam.':<8} | "
        f"{'Material':<16} | Conf."
    )

    lines = [
        "RELATÓRIO DE INFERÊNCIAS — ScanSOLO",
        f"Projeto : {nome}  |  Código: {codigo}",
        f"Data    : {data_str}  |  Preset: {preset}",
        "",
        SEP,
        "INTERFERÊNCIAS DETECTADAS  (alta + média confiança)",
        SEP,
        "",
        col_header,
        DIV,
    ]

    for row in campo:
        arquivo = (row.get("arquivo_dzt") or "—")[:22]
        rank = row.get("rank") or "—"
        x_m = _f(row, "x_m")
        depth_m_str = _f(row, "depth_m")

        pt_raw = row.get("prof_topo_m")
        if pt_raw is None or str(pt_raw).strip() in ("", "None", "nan"):
            try:
                d = float(row.get("depth_m") or 0)
                dm = float(row.get("diam_est_m") or 0)
                pt_str = f"{d - dm / 2:.2f}"
            except (ValueError, TypeError):
                pt_str = "—"
        else:
            pt_str = _f(row, "prof_topo_m")

        largura_str = _f(row, "largura_hiperbole_m")
        tam = (row.get("tipo_tamanho") or "—")[:8]
        material = (row.get("tipo_material") or "—")[:16]
        conf = row.get("confidence_label_tecnico") or "—"

        lines.append(
            f"{arquivo:<22} | {str(rank):>3} | {x_m:>8} | {pt_str:>9} | "
            f"{depth_m_str:>9} | {_f(row, 'diam_est_m', 3):>8} | {largura_str:>8} | "
            f"{tam:<8} | {material:<16} | {conf}"
        )

    total_label = "interferência" if len(campo) == 1 else "interferências"
    lines += [
        "",
        SEP,
        f"Total: {len(campo)} {total_label}  ({n_alta} alta, {n_media} média)",
        "",
        "LEGENDA",
        DIV,
        "P.Topo(m)   Profundidade da geratriz superior (topo da interferência)",
        "P.Eixo(m)   Profundidade do eixo central estimado",
        "Diâm.(m)    Diâmetro aparente estimado pelo ajuste de hipérbole",
        "Larg.(m)    Largura da hipérbole medida no radargrama",
        "Tam.        Classificação por tamanho (pequeno / medio / grande)",
        "Conf.       Nível de confiança técnico (alta / media)",
        "",
        "AVISOS DE CALIBRAÇÃO",
        DIV,
        "* Velocity usada: estimada por semblance. Calibrar com escavação de referência antes de confiar nas profundidades.",
        "* Profundidades e diâmetros são estimativas — variação esperada de ±10–15%.",
        "* Interferências de confiança baixa foram excluídas desta tabela.",
        "* Interferências superficiais (< 0,30m) podem corresponder a ruído de superfície.",
        "* Confirmar resultados por sondagem ou escavação controlada antes de escavar.",
        "",
        "Gerado por ScanSOLO Pipeline v1.1.0",
    ]

    return "\n".join(lines)


def handle_inferencias_job(supa: "SupabaseClient", job: dict) -> None:
    """Gera o relatório de inferências .txt e sobe para gpr-tabelas/{project_id}/inferencias.txt."""
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    log.info("inferencias_job_start", job_id=job_id, project_id=project_id)
    supa.update_job_status(job_id, "processando")

    try:
        project = supa.get_project(project_id)
        if not project:
            raise RuntimeError(f"Project {project_id} not found")

        profiles = supa.get_profiles_for_project(project_id)
        run_id = supa.get_latest_run_id(project_id)
        profiles = [p for p in profiles if p.get("run_id") == run_id]
        if not profiles:
            raise RuntimeError("No profiles found for latest run")

        import io as _io
        all_rows: list[dict] = []
        for profile in profiles:
            csv_path = profile.get("csv_alvos_url")
            if not csv_path:
                continue
            try:
                data = supa.download_file("gpr-tabelas", csv_path)
                reader = csv.DictReader(_io.StringIO(data.decode("utf-8")))
                all_rows.extend(reader)
            except Exception as exc:
                log.warning("inferencias_csv_skip", profile_id=profile["id"], error=str(exc))

        if not all_rows:
            log.warning("inferencias_fallback_db", project_id=project_id)
            profile_ids = [p["id"] for p in profiles]
            r = (
                supa._client.table("detected_targets")
                .select("*")
                .in_("profile_id", profile_ids)
                .order("rank")
                .execute()
            )
            all_rows = r.data or []

        processing_config = _get_processing_config(supa, project_id)
        preset = (processing_config or {}).get("preset", DEFAULT_PRESET)

        texto = gerar_relatorio_inferencias(all_rows, project, preset)

        storage_path = f"{project_id}/inferencias.txt"
        supa.upload_file("gpr-tabelas", storage_path, texto.encode("utf-8"), "text/plain")
        log.info("inferencias_uploaded", path=storage_path)

        supa.update_job_status(job_id, "concluido")
        log.info("inferencias_job_done", job_id=job_id)

    except Exception as exc:
        log.error("inferencias_job_failed", job_id=job_id, error=str(exc))
        supa.update_job_status(job_id, "erro", error_message=str(exc))
        raise


# ── Utilitários ───────────────────────────────────────────────────────────────

def _clamp_label_tecnico(v: str | None) -> str | None:
    return v if v in ("alta", "media", "baixa") else None


def _clamp_label_relatorio(v: str | None) -> str:
    return v if v in ("alta", "media", "baixa") else "baixa"


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
