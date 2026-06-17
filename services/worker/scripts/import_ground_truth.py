#!/usr/bin/env python3
"""
import_ground_truth.py — Importa validações históricas para gpr_ground_truth

Permite ao Amilson importar registros de projetos anteriores (com profundidade conhecida,
tipo de material confirmado, ou marcações de falso positivo) sem precisar usar a UI.

Uso:
    python import_ground_truth.py --csv validacoes.csv [--dry-run]

Formato do CSV (ver template_validacao.csv):
    projeto, perfil, rank, x_m, depth_m_sistema, profundidade_real_m,
    tipo_confirmado, e_falso_positivo, observacoes

Variáveis de ambiente necessárias:
    SUPABASE_URL            (mesmo do worker)
    SUPABASE_SERVICE_ROLE_KEY

Saída:
    - upsert em gpr_ground_truth ON CONFLICT (profile_id, target_rank)
    - relatório resumido no stdout
"""

import os
import sys
import csv
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone

# Tenta importar supabase
try:
    from supabase import create_client
except ImportError:
    print("ERRO: instale supabase-py:  pip install supabase")
    sys.exit(1)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO,
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Categorias de tipo aceitas (mesmo enum do sistema)
TIPOS_VALIDOS = {
    "tubulacao_agua", "tubulacao_gas", "tubulacao_esgoto",
    "cabo_eletrico", "cabo_telecom", "galeria_concreto",
    "vazio_ar", "rocha", "inconclusivo", "desconhecido",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes", "sim", "s", "t")


def _float_or_none(val: str):
    val = val.strip()
    if not val or val.lower() in ("", "null", "none", "-"):
        return None
    try:
        return float(val)
    except ValueError:
        return None


def _required(row: dict, col: str, row_num: int) -> str:
    val = row.get(col, "").strip()
    if not val:
        raise ValueError(f"Linha {row_num}: coluna obrigatória '{col}' está vazia")
    return val


# ---------------------------------------------------------------------------
# Busca profile_id pelo nome do perfil (stem do DZT)
# ---------------------------------------------------------------------------

def resolver_profile_id(supa, projeto: str, perfil: str) -> str | None:
    """
    Busca gpr_profiles.id a partir do código do projeto e do stem do arquivo.
    Aceita: perfil = "PATIO_001" → ilike match em nome_arquivo ou path.
    """
    # Primeiro tenta via projects.codigo_projeto
    res = (
        supa.table("gpr_profiles")
        .select("id, nome_arquivo, project_id, projects!inner(codigo_projeto)")
        .ilike("nome_arquivo", f"%{perfil}%")
        .execute()
    )
    rows = res.data or []
    # Filtra pelo projeto se especificado
    if projeto:
        rows = [
            r for r in rows
            if r.get("projects", {}).get("codigo_projeto", "").upper() == projeto.upper()
            or projeto.upper() in (r.get("nome_arquivo") or "").upper()
        ]
    if len(rows) == 1:
        return rows[0]["id"]
    if len(rows) > 1:
        logger.warning(f"  '{perfil}' ambíguo ({len(rows)} perfis). Usando o mais recente.")
        # Usa o mais recente (maior id alfabético = uuid v4 mais recente não é ordenável,
        # então usa o último da lista como fallback)
        return rows[-1]["id"]
    return None


# ---------------------------------------------------------------------------
# Processamento do CSV
# ---------------------------------------------------------------------------

def processar_csv(filepath: Path, supa, dry_run: bool) -> dict:
    stats = {"total": 0, "ok": 0, "erro": 0, "skip": 0}

    with open(filepath, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    logger.info(f"CSV: {len(rows)} linhas encontradas")

    for i, row in enumerate(rows, start=2):  # start=2: linha 1 = header
        stats["total"] += 1
        try:
            projeto  = row.get("projeto", "").strip()
            perfil   = _required(row, "perfil", i)
            rank     = int(_required(row, "rank", i))
            x_m      = _float_or_none(row.get("x_m", ""))
            depth_m_sistema    = _float_or_none(row.get("depth_m_sistema", ""))
            profundidade_real  = _float_or_none(row.get("profundidade_real_m", ""))
            tipo_confirmado    = row.get("tipo_confirmado", "").strip() or None
            e_falso_positivo   = _bool(row.get("e_falso_positivo", "false"))
            observacoes        = row.get("observacoes", "").strip() or None

            # Validação do tipo
            if tipo_confirmado and tipo_confirmado not in TIPOS_VALIDOS:
                logger.warning(
                    f"  Linha {i}: tipo_confirmado='{tipo_confirmado}' não reconhecido. "
                    f"Valores aceitos: {sorted(TIPOS_VALIDOS)}"
                )
                stats["skip"] += 1
                continue

            # Resolve profile_id
            profile_id = resolver_profile_id(supa, projeto, perfil)
            if not profile_id:
                logger.warning(f"  Linha {i}: perfil '{perfil}' não encontrado no banco. Pulando.")
                stats["skip"] += 1
                continue

            record = {
                "profile_id":          profile_id,
                "target_rank":         rank,
                "x_m":                 x_m,
                "depth_m_sistema":     depth_m_sistema,
                "profundidade_real_m": profundidade_real,
                "tipo_confirmado":     tipo_confirmado,
                "e_falso_positivo":    e_falso_positivo,
                "amplitude_relativa_sem_agc": None,  # não disponível em importação manual
                "fonte":               "importacao_csv",
                "observacao":          observacoes,
                "created_at":          datetime.now(timezone.utc).isoformat(),
            }

            if dry_run:
                logger.info(f"  [DRY-RUN] Linha {i}: profile_id={profile_id[:8]}… rank={rank} "
                            f"tipo={tipo_confirmado} fp={e_falso_positivo}")
                stats["ok"] += 1
                continue

            # Upsert (update on conflict)
            supa.table("gpr_ground_truth").upsert(
                record,
                on_conflict="profile_id,target_rank"
            ).execute()
            logger.info(f"  ✓ Linha {i}: {perfil} rank={rank} → profile {profile_id[:8]}…")
            stats["ok"] += 1

        except Exception as e:
            logger.error(f"  ✗ Linha {i}: {e}")
            stats["erro"] += 1

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Importa validações históricas para gpr_ground_truth"
    )
    parser.add_argument("--csv",     required=True, help="Caminho para o CSV de validações")
    parser.add_argument("--dry-run", action="store_true",
                        help="Simula sem gravar no banco")
    args = parser.parse_args()

    filepath = Path(args.csv)
    if not filepath.exists():
        logger.error(f"Arquivo não encontrado: {filepath}")
        sys.exit(1)

    url = os.environ.get("SUPABASE_URL") or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        logger.error("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY são obrigatórios")
        sys.exit(1)

    supa = create_client(url, key)

    logger.info(f"{'[DRY-RUN] ' if args.dry_run else ''}Importando {filepath.name}…")
    stats = processar_csv(filepath, supa, dry_run=args.dry_run)

    print("\n" + "=" * 50)
    print(f"RESULTADO {'(dry-run)' if args.dry_run else ''}")
    print(f"  Total:    {stats['total']}")
    print(f"  ✓ OK:     {stats['ok']}")
    print(f"  ⚠ Skip:   {stats['skip']}")
    print(f"  ✗ Erro:   {stats['erro']}")
    print("=" * 50)

    if stats["erro"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
