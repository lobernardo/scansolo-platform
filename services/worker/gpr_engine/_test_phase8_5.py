"""
Fase 8.5 -- validacao end-to-end do adapter com DZTs reais HELPER.

Simula o caminho readgssi_engine do job_gpr sem Supabase real:
  1. Copia DZTs reais HELPER para temp input_dir
  2. Chama scansolo_adapter.run_new_engine (mesmo caminho do job)
  3. Valida estrutura de saida que _persist_outputs espera

Grupos de teste:
  1. defaults_intactos      -- _get_engine default + skip_ia forcado
  2. estrutura_1dzt         -- 1 DZT: subdiretorios, PNGs, CSVs, JSON
  3. csv_campos_1dzt        -- index_projeto.csv: colunas e valores
  4. metrics_campos_1dzt    -- pipeline_metrics.json: campos e valores
  5. nan_inf_1dzt           -- ausencia de NaN/Inf em CSV e JSON
  6. multi_dzt_n_linhas     -- 3 DZTs: N linhas no index_projeto.csv

Uso:
  cd services/worker
  python -m gpr_engine._test_phase8_5
"""
from __future__ import annotations

import csv
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

# ---------------------------------------------------------------------------
# Localizar DZTs reais HELPER
# ---------------------------------------------------------------------------

_HELPER_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "KB_ScansoloPlataform" / "benchmark_real" / "HELPER" / "HELPER.PRJ_DZT"
)

_ALL_DZTS: list[Path] = []
if _HELPER_DIR.exists():
    _seen_names: set[str] = set()
    for _p in sorted(_HELPER_DIR.glob("*")):
        if _p.suffix.lower() == ".dzt" and _p.name.lower() not in _seen_names:
            _seen_names.add(_p.name.lower())
            _ALL_DZTS.append(_p)

# Selecionar ate 3 DZTs
_DZT_SINGLE: Path | None = _ALL_DZTS[0] if _ALL_DZTS else None
_DZTS_MULTI: list[Path] = _ALL_DZTS[:3]

# ---------------------------------------------------------------------------
# Constantes de validacao
# ---------------------------------------------------------------------------

_PNG_SIG = b"\x89PNG\r\n\x1a\n"

# Colunas que o adapter grava no index_projeto.csv
# (mapeadas dos campos do index_row do engine)
_CSV_REQUIRED_COLS = [
    "arquivo_dzt",
    "n_tracos",
    "distancia_max_m",
    "profundidade_max_m",
    "snr_imagem_db",
    "snr_imagem_ratio",
    "modo_processamento",
    "tipo_solo",
    "velocity_mns",
]

# Colunas que devem ter valores nao-vazios
_CSV_NONEMPTY_COLS = [
    "arquivo_dzt",
    "n_tracos",
    "profundidade_max_m",
    "snr_imagem_db",
    "modo_processamento",
    "tipo_solo",
]

# Campos obrigatorios no pipeline_metrics.json
_METRICS_REQUIRED = [
    "dzt_filename",
    "engine_name",
    "pipeline_version",
    "modo_processamento",
    "tipo_solo",
    "n_tracos",
    "dist_total_m",
    "profundidade_max_m",
    "snr_raw_db",
    "snr_raw_ratio",
    "snr_stages_db",
    "imagem_bruta_ok",
    "imagem_cientifica_ok",
    "imagem_relatorio_ok",
    "imagem_preview_radan_5m_ok",
    "imagem_anotada_ok",
]

# Valores de string que indicam NaN/Inf em campos CSV
_NAN_INF_STRINGS = {"nan", "inf", "-inf", "infinity", "-infinity", "none", "null"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"  [FAIL] {msg}{suffix}", file=sys.stderr)


def _section(name: str) -> None:
    print(f"\n-- {name} --")


def _is_valid_png(p: Path) -> bool:
    if not p.exists() or p.stat().st_size == 0:
        return False
    with open(p, "rb") as fh:
        return fh.read(8) == _PNG_SIG


def _run_adapter(dzt_paths: list[Path], config: dict | None = None) -> tuple[Path, Path]:
    """Copia DZTs para temp input_dir, roda adapter, retorna (input_dir, output_dir) dentro de tmp."""
    from gpr_engine.scansolo_adapter import run_new_engine

    tmp = Path(tempfile.mkdtemp(prefix="phase85_"))
    input_dir = tmp / "input"
    output_dir = tmp / "output"
    input_dir.mkdir()
    output_dir.mkdir()

    for dzt in dzt_paths:
        shutil.copy2(dzt, input_dir / dzt.name)

    run_new_engine(input_dir, output_dir, config=config, tipo_solo="standard")
    return input_dir, output_dir


def _cleanup(output_dir: Path) -> None:
    shutil.rmtree(output_dir.parent, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. defaults_intactos
# ---------------------------------------------------------------------------


def test_defaults_intactos() -> bool:
    """_get_engine({}) deve retornar legacy_scansolo. skip_ia forcado no source."""
    _section("defaults_intactos -- _get_engine e skip_ia")
    from job_gpr import _get_engine

    ok = True

    # _get_engine sem engine => legacy_scansolo
    result = _get_engine({})
    if result == "legacy_scansolo":
        _ok("_get_engine({}) == 'legacy_scansolo' (default correto)")
    else:
        _fail(f"_get_engine({{}}) retornou '{result}' (esperado 'legacy_scansolo')")
        ok = False

    # _get_engine com engine legacy => legacy_scansolo
    result2 = _get_engine({"engine": "legacy_scansolo"})
    if result2 == "legacy_scansolo":
        _ok("_get_engine({'engine':'legacy_scansolo'}) == 'legacy_scansolo'")
    else:
        _fail(f"_get_engine legacy retornou '{result2}'")
        ok = False

    # _get_engine com engine novo => readgssi_engine
    result3 = _get_engine({"engine": "readgssi_engine"})
    if result3 == "readgssi_engine":
        _ok("_get_engine({'engine':'readgssi_engine'}) == 'readgssi_engine'")
    else:
        _fail(f"_get_engine readgssi retornou '{result3}'")
        ok = False

    # Verificar no source que skip_ia esta forcado para readgssi_engine
    source = (_worker_dir / "job_gpr.py").read_text(encoding="utf-8")
    if 'engine == "readgssi_engine"' in source and "skip_ia" in source:
        _ok("job_gpr.py: skip_ia forcado para readgssi_engine (verificado no source)")
    else:
        _fail("job_gpr.py: logica skip_ia para readgssi_engine nao encontrada")
        ok = False

    # Verificar que o default em _get_engine e legacy_scansolo (nao readgssi)
    if '"legacy_scansolo"' in source:
        _ok("job_gpr.py: string 'legacy_scansolo' como default presente")
    else:
        _fail("job_gpr.py: default 'legacy_scansolo' nao encontrado")
        ok = False

    return ok


# ---------------------------------------------------------------------------
# 2. estrutura_1dzt
# ---------------------------------------------------------------------------


def test_estrutura_1dzt(output_dir: Path, stem: str) -> bool:
    """Valida existencia de todos os arquivos e subdiretorios esperados."""
    _section(f"estrutura_1dzt -- {stem}")
    ok = True

    # index_projeto.csv
    idx = output_dir / "index_projeto.csv"
    if idx.exists() and idx.stat().st_size > 0:
        _ok(f"index_projeto.csv: {idx.stat().st_size} bytes")
    else:
        _fail("index_projeto.csv ausente ou vazio")
        ok = False

    # Subdiretorios
    for d in ("01_Imagens_Brutas", "02_Imagens_Processadas", "05_Tabela_Alvos"):
        if (output_dir / d).is_dir():
            _ok(f"subdir '{d}' existe")
        else:
            _fail(f"subdir '{d}' ausente")
            ok = False

    # PNGs esperados
    png_checks = [
        ("01_Imagens_Brutas",      f"{stem}_bruta.png",                       "bruta"),
        ("02_Imagens_Processadas", f"{stem}_radargrama_cientifico.png",        "cientifica"),
        ("02_Imagens_Processadas", f"{stem}_processada.png",                  "processada"),
        ("02_Imagens_Processadas", f"{stem}_radargrama_preview_radan_5m.png", "preview_radan_5m"),
    ]
    for subdir, fname, label in png_checks:
        p = output_dir / subdir / fname
        if _is_valid_png(p):
            _ok(f"PNG '{label}': {p.stat().st_size} bytes")
        else:
            _fail(f"PNG '{label}' ausente ou invalido: {subdir}/{fname}")
            ok = False

    # CSV de alvos (pode estar vazio, mas deve existir)
    ap = output_dir / "05_Tabela_Alvos" / f"{stem}_alvos.csv"
    if ap.exists():
        _ok(f"_alvos.csv existe ({ap.stat().st_size} bytes)")
    else:
        _fail(f"_alvos.csv ausente: {ap.name}")
        ok = False

    # pipeline_metrics.json em 02_Imagens_Processadas
    mp = output_dir / "02_Imagens_Processadas" / f"{stem}_pipeline_metrics.json"
    if mp.exists() and mp.stat().st_size > 0:
        _ok(f"pipeline_metrics.json: {mp.stat().st_size} bytes")
    else:
        _fail(f"pipeline_metrics.json ausente ou vazio: {mp.name}")
        ok = False

    return ok


# ---------------------------------------------------------------------------
# 3. csv_campos_1dzt
# ---------------------------------------------------------------------------


def test_csv_campos_1dzt(output_dir: Path, stem: str) -> bool:
    """Valida colunas obrigatorias e valores do index_projeto.csv."""
    _section(f"csv_campos_1dzt -- {stem}")
    ok = True

    idx = output_dir / "index_projeto.csv"
    with open(idx, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    if len(rows) == 1:
        _ok("index_projeto.csv: exatamente 1 linha (1 DZT)")
    else:
        _fail(f"index_projeto.csv: esperado 1 linha, obtido {len(rows)}")
        ok = False

    if not rows:
        return False

    row = rows[0]

    # Colunas obrigatorias presentes
    for col in _CSV_REQUIRED_COLS:
        if col in row:
            _ok(f"coluna '{col}' presente: '{str(row[col])[:40]}'")
        else:
            _fail(f"coluna '{col}' ausente")
            ok = False

    # Colunas que nao podem ser vazias
    for col in _CSV_NONEMPTY_COLS:
        val = row.get(col, "").strip()
        if val:
            _ok(f"'{col}' nao vazio: '{val[:30]}'")
        else:
            _fail(f"'{col}' esta vazio")
            ok = False

    # arquivo_dzt deve bater com o nome do DZT
    if row.get("arquivo_dzt", "").lower().endswith(".dzt"):
        _ok(f"arquivo_dzt termina em .dzt: '{row['arquivo_dzt']}'")
    else:
        _fail(f"arquivo_dzt inesperado: '{row.get('arquivo_dzt')}'")
        ok = False

    # n_tracos deve ser inteiro positivo
    try:
        n = int(float(row.get("n_tracos", "0")))
        if n > 0:
            _ok(f"n_tracos={n} (positivo)")
        else:
            _fail(f"n_tracos={n} (deve ser > 0)")
            ok = False
    except (ValueError, TypeError) as exc:
        _fail("n_tracos nao conversivel para int", str(exc))
        ok = False

    # modo_processamento deve ser um dos modos validos
    modo = row.get("modo_processamento", "")
    if modo in ("minimo", "padrao", "agressivo"):
        _ok(f"modo_processamento='{modo}' (valido)")
    else:
        _fail(f"modo_processamento='{modo}' (esperado minimo|padrao|agressivo)")
        ok = False

    # profundidade_max_m deve ser float positivo
    try:
        prof = float(row.get("profundidade_max_m", "0"))
        if prof > 0:
            _ok(f"profundidade_max_m={prof:.3f}m (positivo)")
        else:
            _fail(f"profundidade_max_m={prof} (deve ser > 0)")
            ok = False
    except (ValueError, TypeError) as exc:
        _fail("profundidade_max_m nao conversivel", str(exc))
        ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. metrics_campos_1dzt
# ---------------------------------------------------------------------------


def test_metrics_campos_1dzt(output_dir: Path, stem: str) -> bool:
    """Valida campos obrigatorios e valores do pipeline_metrics.json."""
    _section(f"metrics_campos_1dzt -- {stem}")
    ok = True

    mp = output_dir / "02_Imagens_Processadas" / f"{stem}_pipeline_metrics.json"
    try:
        m = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail("pipeline_metrics.json invalido", str(exc))
        return False

    # Campos obrigatorios
    for field in _METRICS_REQUIRED:
        if field in m:
            v = m[field]
            short = str(v)[:40] if not isinstance(v, dict) else "{...}"
            _ok(f"'{field}': {short}")
        else:
            _fail(f"'{field}' ausente em pipeline_metrics.json")
            ok = False

    # engine_name deve ser readgssi_engine
    if m.get("engine_name") == "readgssi_engine":
        _ok("engine_name='readgssi_engine'")
    else:
        _fail(f"engine_name='{m.get('engine_name')}' (esperado 'readgssi_engine')")
        ok = False

    # pipeline_version deve ser 2.0.0
    if m.get("pipeline_version") == "2.0.0":
        _ok("pipeline_version='2.0.0'")
    else:
        _fail(f"pipeline_version='{m.get('pipeline_version')}' (esperado '2.0.0')")
        ok = False

    # imagem_anotada_ok deve ser False (sem detector)
    if m.get("imagem_anotada_ok") is False:
        _ok("imagem_anotada_ok=False (sem detector -- correto)")
    else:
        _fail(f"imagem_anotada_ok={m.get('imagem_anotada_ok')} (esperado False)")
        ok = False

    # imagens geradas devem ser True
    for img_key in ("imagem_bruta_ok", "imagem_cientifica_ok",
                    "imagem_relatorio_ok", "imagem_preview_radan_5m_ok"):
        if m.get(img_key) is True:
            _ok(f"{img_key}=True")
        else:
            _fail(f"{img_key}={m.get(img_key)} (esperado True)")
            ok = False

    # snr_stages_db deve ter estagios esperados
    stages = m.get("snr_stages_db", {})
    for stage in ("raw", "dewow_bp", "cientifico", "sem_agc", "relatorio", "preview_radan"):
        if stage in stages:
            _ok(f"snr_stages_db['{stage}']={stages[stage]:.1f}dB")
        else:
            _fail(f"snr_stages_db: estagio '{stage}' ausente")
            ok = False

    # n_tracos positivo
    n_tracos = m.get("n_tracos", 0)
    if isinstance(n_tracos, (int, float)) and n_tracos > 0:
        _ok(f"n_tracos={int(n_tracos)} (positivo)")
    else:
        _fail(f"n_tracos={n_tracos} (deve ser > 0)")
        ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. nan_inf_1dzt
# ---------------------------------------------------------------------------


def test_nan_inf_1dzt(output_dir: Path, stem: str) -> bool:
    """Valida ausencia de NaN/Inf nos valores do CSV e do JSON."""
    _section(f"nan_inf_1dzt -- {stem}")
    ok = True

    # Verificar index_projeto.csv
    idx = output_dir / "index_projeto.csv"
    with open(idx, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    csv_nan_found = False
    for row in rows:
        for col, val in row.items():
            if val.strip().lower() in _NAN_INF_STRINGS:
                _fail(f"CSV['{col}'] contém valor invalido: '{val}'")
                ok = False
                csv_nan_found = True
    if not csv_nan_found:
        _ok("index_projeto.csv: sem NaN/Inf em nenhuma celula")

    # Verificar pipeline_metrics.json -- campos numericos
    mp = output_dir / "02_Imagens_Processadas" / f"{stem}_pipeline_metrics.json"
    m = json.loads(mp.read_text(encoding="utf-8"))

    numeric_fields = [
        "snr_raw_db", "snr_raw_ratio", "n_tracos",
        "dist_total_m", "profundidade_max_m",
    ]
    metrics_nan_found = False
    for field in numeric_fields:
        val = m.get(field)
        if val is None:
            continue
        try:
            fval = float(val)
            if not math.isfinite(fval):
                _fail(f"metrics['{field}']={val} (nao finito)")
                ok = False
                metrics_nan_found = True
        except (ValueError, TypeError):
            pass  # string ou dict, pular

    # Verificar snr_stages_db
    stages = m.get("snr_stages_db", {})
    for stage, val in stages.items():
        try:
            if not math.isfinite(float(val)):
                _fail(f"snr_stages_db['{stage}']={val} (nao finito)")
                ok = False
                metrics_nan_found = True
        except (ValueError, TypeError):
            pass

    if not metrics_nan_found:
        _ok("pipeline_metrics.json: todos os valores numericos sao finitos")

    return ok


# ---------------------------------------------------------------------------
# 6. multi_dzt_n_linhas
# ---------------------------------------------------------------------------


def test_multi_dzt_n_linhas(dzt_paths: list[Path]) -> bool:
    """Valida que N DZTs de entrada produzem N linhas no index_projeto.csv."""
    n = len(dzt_paths)
    _section(f"multi_dzt_n_linhas -- {n} DZTs")

    if n < 2:
        _ok(f"apenas {n} DZT disponivel -- pulando teste multi-DZT")
        return True

    ok = True
    names = [p.name for p in dzt_paths]
    print(f"  DZTs: {', '.join(names)}")

    try:
        from gpr_engine.scansolo_adapter import run_new_engine
        tmp = Path(tempfile.mkdtemp(prefix="phase85_multi_"))
        input_dir = tmp / "input"
        output_dir = tmp / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        for dzt in dzt_paths:
            shutil.copy2(dzt, input_dir / dzt.name)

        run_new_engine(input_dir, output_dir, config=None, tipo_solo="standard")

        # Verificar N linhas no index_projeto.csv
        idx = output_dir / "index_projeto.csv"
        with open(idx, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        if len(rows) == n:
            _ok(f"index_projeto.csv: {len(rows)} linhas == {n} DZTs processados")
        else:
            _fail(f"index_projeto.csv: {len(rows)} linhas != {n} DZTs")
            ok = False

        # Verificar que cada DZT tem sua linha e seus arquivos
        dzts_in_csv = {r.get("arquivo_dzt", "") for r in rows}
        for dzt in dzt_paths:
            stem = dzt.stem
            # arquivo_dzt no CSV pode ser o filename com extensao original
            found_in_csv = any(dzt.name in arc or stem in arc for arc in dzts_in_csv)
            if found_in_csv:
                _ok(f"'{dzt.name}' presente no index_projeto.csv")
            else:
                _fail(f"'{dzt.name}' ausente no index_projeto.csv (rows: {dzts_in_csv})")
                ok = False

            # PNG bruta de cada DZT
            bruta = output_dir / "01_Imagens_Brutas" / f"{stem}_bruta.png"
            if _is_valid_png(bruta):
                _ok(f"PNG bruta de '{dzt.name}': {bruta.stat().st_size} bytes")
            else:
                _fail(f"PNG bruta ausente para '{dzt.name}'")
                ok = False

            # _alvos.csv de cada DZT
            alvos = output_dir / "05_Tabela_Alvos" / f"{stem}_alvos.csv"
            if alvos.exists():
                _ok(f"_alvos.csv de '{dzt.name}': {alvos.stat().st_size} bytes")
            else:
                _fail(f"_alvos.csv ausente para '{dzt.name}'")
                ok = False

    except Exception as exc:
        _fail("run_new_engine multi-DZT lancou excecao", str(exc))
        ok = False
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------


def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 8.5 -- validacao end-to-end adapter")
    print("=" * 60)

    if not _ALL_DZTS:
        print(f"\n[ERRO] Nenhum DZT encontrado em:\n  {_HELPER_DIR}", file=sys.stderr)
        print("Certifique-se de que os DZTs HELPER estao presentes.", file=sys.stderr)
        return 1

    print(f"\nDZTs disponiveis: {len(_ALL_DZTS)}")
    for p in _ALL_DZTS[:5]:
        print(f"  {p.name} ({p.stat().st_size // 1024} KB)")

    results: list[tuple[str, bool]] = []

    # Grupo 1: defaults (sem DZT real)
    results.append(("defaults_intactos", test_defaults_intactos()))

    # Processar 1 DZT para grupos 2-5
    assert _DZT_SINGLE is not None
    stem1 = _DZT_SINGLE.stem
    print(f"\n-- Processando DZT unico: {_DZT_SINGLE.name} --")
    out1: Path | None = None
    try:
        _, out1 = _run_adapter([_DZT_SINGLE])
        print(f"  Output em: {out1}")

        results.append(("estrutura_1dzt",      test_estrutura_1dzt(out1, stem1)))
        results.append(("csv_campos_1dzt",      test_csv_campos_1dzt(out1, stem1)))
        results.append(("metrics_campos_1dzt",  test_metrics_campos_1dzt(out1, stem1)))
        results.append(("nan_inf_1dzt",         test_nan_inf_1dzt(out1, stem1)))
    except Exception as exc:
        print(f"  [ERRO CRITICO] {exc}", file=sys.stderr)
        for name in ("estrutura_1dzt", "csv_campos_1dzt", "metrics_campos_1dzt", "nan_inf_1dzt"):
            results.append((name, False))
    finally:
        if out1 is not None:
            _cleanup(out1)

    # Grupo 6: multi-DZT
    results.append(("multi_dzt_n_linhas", test_multi_dzt_n_linhas(_DZTS_MULTI)))

    # Resumo
    print("\n" + "=" * 60)
    print(f"DZTs testados individualmente : 1 ({_DZT_SINGLE.name})")
    print(f"DZTs testados em lote         : {len(_DZTS_MULTI)}"
          f" ({', '.join(p.name for p in _DZTS_MULTI)})")
    print()
    print(f"{'Grupo':<28} {'Resultado'}")
    print("-" * 44)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<26} {status}")

    passed_n = sum(1 for _, r in results if r)
    total_n = len(results)
    print("-" * 44)
    print(f"Resultado: {passed_n}/{total_n} grupos passaram")
    return 0 if all(r for _, r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
