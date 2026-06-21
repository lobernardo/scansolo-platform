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
      {stem}_pipeline_metrics.json
    05_Tabela_Alvos/
      {stem}_alvos.csv  (cabecalhos apenas -- detector nao integrado nesta fase)

Mapeamento de processada.png conforme visual_profile (Fase 8.7):
  visual_profile="readgssi_reference" -> processada.png = readgssi_reference
      (SymLogNorm, arr_raw -> bgr, comparavel ao output visual do readgssi)
  qualquer outro valor (default) -> processada.png = fluxo relatorio
      (dewow+bp+bgremoval+tpow+AGC, comportamento anterior)

Em ambos os casos:
  - {stem}_radargrama_readgssi_reference.png e sempre salvo em proc_dir
  - os demais outputs (bruta, cientifica, preview, metrics, alvos) nao mudam

Decisao sobre CSV de alvos e job de IA:
  O detector de hiperboles nao esta integrado ao novo engine nesta fase.
  Portanto, _alvos.csv e gerado vazio (somente cabecalhos) e o job_gpr.py
  nao cria job de IA quando engine=readgssi_engine (skip_ia forcado).
  Quando o detector for integrado (fase futura), o CSV sera populado e
  o flag skip_ia podera ser removido.

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
      1. Chama process_dzt com output separado por stem
      2. Move imagens e metrics para os subdiretorios esperados
      3. Gera _alvos.csv vazio (detector pendente)
      4. Acumula linha em index_projeto.csv

    :param input_dir:  Diretorio com os arquivos .DZT baixados do Storage
    :param output_dir: Diretorio de saida (subdiretorios criados automaticamente)
    :param config:     Dict de configuracao de processamento (pode ser None)
    :param tipo_solo:  Tipo de solo para SNR gate
    :raises RuntimeError: Se nenhum DZT for encontrado em input_dir
    """
    from gpr_engine.pipeline import process_dzt

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
        engine_out = Path(output_dir) / "_engine" / stem
        engine_out.mkdir(parents=True, exist_ok=True)

        log.info("new_engine_dzt_start", dzt=dzt_path.name, stem=stem)

        result = process_dzt(
            dzt_path=dzt_path,
            output_dir=engine_out,
            config=dict(config) if config else None,
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

        # Processada: conteudo depende de visual_profile
        visual_profile = (config or {}).get("visual_profile", "scientific")
        processada_dst = proc_dir / f"{stem}_processada.png"
        if visual_profile == "readgssi_reference" and ref_dst.exists():
            # Usa copia do readgssi_reference como imagem processada principal
            shutil.copy2(str(ref_dst), str(processada_dst))
            log.info(
                "new_engine_processada_readgssi_ref",
                dzt=dzt_path.name,
                visual_profile=visual_profile,
            )
        else:
            # Comportamento padrao: fluxo relatorio (dewow+bp+bgremoval+tpow+AGC)
            _move_if_exists(result.image_paths.get("processada"), processada_dst)

        # CSV de alvos vazio (detector nao integrado nesta fase)
        _write_empty_alvos_csv(alvos_dir / f"{stem}_alvos.csv")

        # Linha para index_projeto.csv (campos lidos por _persist_outputs)
        row = result.index_row
        index_rows.append({
            "arquivo_dzt":        str(row.get("arquivo", dzt_path.name)),
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
            dzt=dzt_path.name,
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
