"""
Adapter do novo GPR engine para o job_gpr do worker ScanSOLO.

Traduz os outputs do gpr_engine.pipeline.process_dzt para a estrutura
de diretorios esperada por job_gpr._persist_outputs:

  output_dir/
    index_projeto.csv          -- lido por _persist_outputs
    01_Imagens_Brutas/
      {stem}_bruta.png
    02_Imagens_Processadas/
      {stem}_radargrama_cientifico.png
      {stem}_processada.png                         <- varia conforme visual_profile
      {stem}_radargrama_readgssi_reference.png      <- sempre presente (Fase 8.6+)
      {stem}_radargrama_preview_radan_5m.png
      {stem}_anotada_completa.png                   <- quando detector executou
      {stem}_pipeline_metrics.json
    05_Tabela_Alvos/
      {stem}_alvos.csv  (com alvos quando detector encontrou; cabecalhos apenas senao)

Mapeamento de processada.png conforme visual_profile (Fase 8.7):
  visual_profile="readgssi_reference" -> processada.png = readgssi_reference
      (SymLogNorm, arr_raw -> bgr, comparavel ao output visual do readgssi)
  qualquer outro valor (default) -> processada.png = fluxo relatorio
      (dewow+bp+bgremoval+tpow+AGC, comportamento anterior)

Detector de hiperboles (Fase G2):
  Integrado no pipeline.process_dzt via gpr_engine.detector.run_scansolo_detector.
  Quando detector executa e encontra alvos:
    - {stem}_anotada_completa.png e movido para proc_dir
    - {stem}_alvos.csv e gravado com dados reais (nao apenas cabecalhos)
  O CSV populado alimenta _parse_targets -> detected_targets no job_gpr.py.
  Skip IA (skip_ia forcado no job_gpr) permanece ate a integracao da IA.

Nao acessa Supabase. Nao modifica arquivos brutos.
"""
from __future__ import annotations

import csv
import shutil
from pathlib import Path

import structlog

log = structlog.get_logger()

# Cabecalhos compativeis com _parse_targets em job_gpr.py
_CSV_ALVOS_HEADERS = [
    "rank", "arquivo_dzt", "x_m", "depth_m", "diam_est_m", "diam_confianca",
    "fit_ok", "score", "tipo_material", "confianca_tipo",
    "amplitude_relativa_max", "amplitude_relativa_raw", "fase_consistente",
    "evidencia_raw", "evidencia_sem_agc", "snr_local",
    "confidence_score_0_100", "confidence_label_tecnico",
    "confidence_label_relatorio", "motivo_confianca",
]


def _per_file_config(global_config: dict, filename: str) -> dict:
    """
    Retorna a config efetiva para um DZT especifico.

    Mescla a config global com a entrada em _preflight_file_configs[filename]
    (se existir).  engine e sempre forcado para 'readgssi_engine'.

    Fallback seguro: se nao houver entrada para o arquivo (projeto sem preflight
    ou arquivo nao listado), usa a config global com engine forcado —
    comportamento identico ao anterior ao preflight per-file.

    :param global_config: processing_config do projeto (pode ter _preflight_file_configs)
    :param filename:      Basename do arquivo DZT — chave em _preflight_file_configs
    :returns:             Dict de config pronto para process_dzt
    """
    file_configs: dict = global_config.get("_preflight_file_configs") or {}
    file_config: dict = file_configs.get(filename) or {}
    return {**global_config, **file_config, "engine": "readgssi_engine"}


def run_new_engine(
    input_dir: Path,
    output_dir: Path,
    config: dict | None,
    tipo_solo: str,
) -> None:
    """
    Processa todos os DZTs em input_dir com o novo gpr_engine e organiza
    os outputs na estrutura de diretorios esperada por _persist_outputs.

    Para cada DZT encontrado em input_dir (extensao .dzt, case-insensitive):
      1. Resolve config por arquivo via _per_file_config (usa _preflight_file_configs)
      2. Chama process_dzt com a config especifica daquele DZT
      3. Move imagens e metrics para os subdiretorios esperados
      4. Gera _alvos.csv vazio (detector pendente)
      5. Acumula linha em index_projeto.csv

    :param input_dir:  Diretorio com os arquivos .DZT baixados do Storage
    :param output_dir: Diretorio de saida (subdiretorios criados automaticamente)
    :param config:     Dict de configuracao de processamento (pode ser None)
    :param tipo_solo:  Tipo de solo para SNR gate
    :raises RuntimeError: Se nenhum DZT for encontrado em input_dir
    """
    from gpr_engine.pipeline import process_dzt

    global_config = config or {}

    dzt_files = sorted(
        f for f in Path(input_dir).iterdir() if f.suffix.lower() == ".dzt"
    )
    if not dzt_files:
        raise RuntimeError(f"No DZT files found in {input_dir}")

    bruta_dir = Path(output_dir) / "01_Imagens_Brutas"
    proc_dir  = Path(output_dir) / "02_Imagens_Processadas"
    alvos_dir = Path(output_dir) / "05_Tabela_Alvos"
    for d in (bruta_dir, proc_dir, alvos_dir):
        d.mkdir(parents=True, exist_ok=True)

    index_rows: list[dict] = []

    for dzt_path in dzt_files:
        stem = dzt_path.stem
        filename = dzt_path.name  # basename — chave em _preflight_file_configs
        engine_out = Path(output_dir) / "_engine" / stem
        engine_out.mkdir(parents=True, exist_ok=True)

        # Config efetiva: global + override por arquivo (via _preflight_file_configs)
        effective_config = _per_file_config(global_config, filename)

        log.info(
            "new_engine_dzt_start",
            dzt=filename,
            stem=stem,
            velocity_mns=effective_config.get("velocity_mns"),
            antenna_freq_mhz=effective_config.get("antenna_freq_mhz"),
            config_source=effective_config.get("source", "global"),
        )

        result = process_dzt(
            dzt_path=dzt_path,
            output_dir=engine_out,
            config=effective_config,
            tipo_solo=tipo_solo,
            stem=stem,
        )

        # Mover imagens para subdiretorios esperados por _persist_outputs
        _move_if_exists(result.image_paths.get("bruta"),
                        bruta_dir / f"{stem}_bruta.png")
        _move_if_exists(result.image_paths.get("cientifica"),
                        proc_dir / f"{stem}_radargrama_cientifico.png")
        _move_if_exists(result.image_paths.get("preview_radan_5m"),
                        proc_dir / f"{stem}_radargrama_preview_radan_5m.png")
        _move_if_exists(result.metrics_path,
                        proc_dir / f"{stem}_pipeline_metrics.json")

        # readgssi_reference: sempre salvo em proc_dir com seu proprio nome
        ref_dst = proc_dir / f"{stem}_radargrama_readgssi_reference.png"
        _move_if_exists(result.image_paths.get("readgssi_reference"), ref_dst)

        # Processada: visual_profile lido do effective_config (pode diferir por arquivo).
        # Default "readgssi_reference": imagem base fiel ao readgssi sem filtros ScanSOLO.
        visual_profile = effective_config.get("visual_profile", "readgssi_reference")
        processada_dst = proc_dir / f"{stem}_processada.png"
        if visual_profile == "readgssi_reference" and ref_dst.exists():
            # Usa copia do readgssi_reference como imagem processada principal
            shutil.copy2(str(ref_dst), str(processada_dst))
            log.info(
                "new_engine_processada_readgssi_ref",
                dzt=filename,
                visual_profile=visual_profile,
            )
        else:
            # Comportamento padrao: fluxo relatorio (dewow+bp+bgremoval+tpow+AGC)
            _move_if_exists(result.image_paths.get("processada"), processada_dst)

        # Imagem anotada (gerada pelo detector quando executado com alvos)
        _move_if_exists(
            result.image_paths.get("anotada"),
            proc_dir / f"{stem}_anotada_completa.png",
        )

        # CSV de alvos: real quando detector encontrou alvos; cabecalhos apenas senao
        csv_dst = alvos_dir / f"{stem}_alvos.csv"
        if result.detected_targets:
            _write_alvos_csv(csv_dst, result.detected_targets)
            log.info(
                "new_engine_alvos_csv_written",
                dzt=filename,
                n_alvos=len(result.detected_targets),
                detector_status=result.detector_status,
            )
        else:
            _write_empty_alvos_csv(csv_dst)
            log.info(
                "new_engine_alvos_csv_empty",
                dzt=filename,
                detector_status=result.detector_status,
            )

        # Linha para index_projeto.csv (campos lidos por _persist_outputs)
        row = result.index_row
        index_rows.append({
            "arquivo_dzt":        str(row.get("arquivo", filename)),
            "n_tracos":           str(row.get("n_tracos", "")),
            "n_amostras":         "",
            "profundidade_max_m": str(row.get("profundidade_max_m", "")),
            "distancia_max_m":    str(row.get("distancia_max_m", "")),
            "velocity_mns":       str(row.get("velocity_mns", "")),
            "velocity_calibrada": "False",
            "config_hash":        "",
            "snr_imagem_db":      str(row.get("snr_raw_db", "")),
            "snr_imagem_ratio":   str(row.get("snr_raw_ratio", "")),
            "modo_processamento": str(row.get("modo_processamento", "padrao")),
            "tipo_solo":          str(row.get("tipo_solo", "standard")),
        })

        log.info(
            "new_engine_dzt_done",
            dzt=filename,
            n_tracos=row.get("n_tracos"),
            modo=row.get("modo_processamento"),
            snr_db=row.get("snr_raw_db"),
        )

    _write_index_csv(Path(output_dir) / "index_projeto.csv", index_rows)
    log.info("new_engine_index_written", n_dzts=len(index_rows))


def _move_if_exists(src: Path | None, dst: Path) -> None:
    if src is None:
        return
    src_p = Path(src)
    if src_p.exists():
        shutil.move(str(src_p), str(dst))


def _write_index_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_empty_alvos_csv(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_ALVOS_HEADERS)
        writer.writeheader()


def _write_alvos_csv(path: Path, targets: list[dict]) -> None:
    """Escreve CSV de alvos com dados reais do detector."""
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_ALVOS_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(targets)
