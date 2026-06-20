"""
Modulo de persistencia de arrays numpy para o ScanSOLO GPR Engine.

Salva/carrega matrizes .npy de forma segura e atomica:
  - Escrita em arquivo temporario + os.replace() atomico
  - Diretorio pai criado automaticamente
  - Nomes compativeis com o pipeline atual

Nomes de arquivo salvos por save_engine_arrays():
  raw.npy                  -- arr_raw bruto (se fornecido)
  radargrama_cientifico.npy -- arr_cientifico (dewow+bp+tpow, sem AGC)
  processado_sem_agc.npy   -- arr_sem_agc (bgremoval+tpow, sem AGC)
  processado_visual.npy    -- arr_relatorio (com AGC completo)
  processado.npy           -- alias de processado_visual.npy (backward compat)

Todas as funcoes:
  - Nao importam GPRPy
  - Nao dependem de pipeline_v1.py
  - Nao modificam arrays de entrada
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import numpy as np

from gpr_engine.flows import FlowArrays


# ---------------------------------------------------------------------------
# Escrita e leitura atomica de arrays
# ---------------------------------------------------------------------------

def save_array_atomic(arr: np.ndarray, path: str | Path) -> Path:
    """
    Salva um array numpy em .npy via escrita atomica.

    Estrategia: salva em arquivo temporario no mesmo diretorio e depois
    substitui via os.replace() (atomico em POSIX; best-effort no Windows
    quando src e dst estao na mesma particao).

    :param arr:  Array numpy de qualquer dtype/shape
    :param path: Caminho de destino (.npy); diretorio pai criado automaticamente
    :returns:    Path do arquivo salvo
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=out_path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            np.save(fh, arr)
        os.replace(tmp_path, out_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    return out_path


def load_array(path: str | Path) -> np.ndarray:
    """
    Carrega um array numpy de um arquivo .npy.

    :param path: Caminho do arquivo .npy
    :returns:    np.ndarray (dtype e shape originais preservados)
    :raises FileNotFoundError: Se o arquivo nao existir
    """
    return np.load(str(Path(path)), allow_pickle=False)


# ---------------------------------------------------------------------------
# Salvar conjunto de arrays do engine
# ---------------------------------------------------------------------------

def save_engine_arrays(
    flow_arrays: FlowArrays,
    output_dir: str | Path,
    stem: str,
    arr_raw: np.ndarray | None = None,
) -> dict[str, Path]:
    """
    Salva os arrays de saida do motor GPR com nomes compativeis com o pipeline.

    Mapeamento:
      raw.npy                   <- arr_raw (opcional)
      radargrama_cientifico.npy <- flow_arrays.arr_cientifico
      processado_sem_agc.npy    <- flow_arrays.arr_sem_agc
      processado_visual.npy     <- flow_arrays.arr_relatorio
      processado.npy            <- flow_arrays.arr_relatorio (alias backward compat)

    O parametro stem (nome base do DZT) e aceito para consistencia da API
    mas nao e usado como prefixo nos nomes: cada DZT tem seu proprio output_dir.

    :param flow_arrays: Resultado de process_flows()
    :param output_dir:  Diretorio de saida (criado automaticamente)
    :param stem:        Nome base do DZT (ex: "PATIO___001"), para referencia
    :param arr_raw:     Array bruto pre-filtros (opcional; raw.npy nao salvo se None)
    :returns:           Dict mapeando nome_logico -> Path do arquivo salvo
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    saved: dict[str, Path] = {}

    if arr_raw is not None:
        saved["raw"] = save_array_atomic(arr_raw, out_dir / "raw.npy")

    saved["radargrama_cientifico"] = save_array_atomic(
        flow_arrays.arr_cientifico,
        out_dir / "radargrama_cientifico.npy",
    )
    saved["processado_sem_agc"] = save_array_atomic(
        flow_arrays.arr_sem_agc,
        out_dir / "processado_sem_agc.npy",
    )
    saved["processado_visual"] = save_array_atomic(
        flow_arrays.arr_relatorio,
        out_dir / "processado_visual.npy",
    )
    # processado.npy e alias de processado_visual.npy para backward compat
    saved["processado"] = save_array_atomic(
        flow_arrays.arr_relatorio,
        out_dir / "processado.npy",
    )

    return saved
