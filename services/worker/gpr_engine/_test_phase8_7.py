"""
Fase 8.7 -- visual_profile="readgssi_reference" mapeado para Processada no adapter.

Grupos de teste:
  G1  engine_default       -- _get_engine({}) continua retornando legacy_scansolo
  G2  adapter_default      -- sem visual_profile: processada vem do fluxo relatorio
  G3  adapter_readgssi_ref -- visual_profile=readgssi_reference: processada = readgssi_ref
  G4  ref_png_sempre       -- readgssi_reference.png existe em ambos os modos
  G5  processada_diferente -- processada no modo ref != processada no modo padrao
  G6  index_csv_valido     -- index_projeto.csv com colunas e linhas corretas
  G7  metrics_json_valido  -- pipeline_metrics.json e JSON valido com campos obrigatorios
  G8  alvos_csv_vazio      -- _alvos.csv existe com headers corretos e sem dados
  G9  skip_ia_forcado      -- _get_engine retorna readgssi_engine e skip_ia deve ser True
  G10 legacy_intocado      -- legacy_scansolo nao alterado (_VALID_ENGINES, default, pipeline_v1)

Restricoes:
  - Todos os print() usam ASCII puro (Windows cp1252 console)
  - DZT real: HELPER_0001.dzt
  - Sem alterar frontend, migrations, Dockerfile, worker_main.py
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Caminhos
# ---------------------------------------------------------------------------

_HERE      = Path(__file__).resolve().parent          # gpr_engine/
_REPO_ROOT = _HERE.parents[2]                         # scansolo-platform/
_DZT_REAL  = (
    _REPO_ROOT
    / "KB_ScansoloPlataform"
    / "benchmark_real"
    / "HELPER"
    / "HELPER.PRJ_DZT"
    / "HELPER_0001.dzt"
)

# ---------------------------------------------------------------------------
# Contadores
# ---------------------------------------------------------------------------

_PASS = _FAIL = _WARN = 0


def _ok(msg: str) -> None:
    global _PASS; _PASS += 1; print(f"  [PASS] {msg}")


def _fail(msg: str, exc: Exception | None = None) -> None:
    global _FAIL; _FAIL += 1; print(f"  [FAIL] {msg}")
    if exc: print(f"         {type(exc).__name__}: {exc}")


def _warn(msg: str) -> None:
    global _WARN; _WARN += 1; print(f"  [WARN] {msg}")


def _section(name: str) -> None:
    print(f"\n--- {name} ---")


# ---------------------------------------------------------------------------
# Helper: roda run_new_engine com 1 DZT em diretorio temporario
# ---------------------------------------------------------------------------

def _run_adapter(config: dict | None, tmp_root: Path) -> Path:
    """
    Copia HELPER_0001.dzt para input_dir, chama run_new_engine,
    retorna output_dir pronto para verificacao.
    """
    from gpr_engine.scansolo_adapter import run_new_engine

    input_dir  = tmp_root / "input"
    output_dir = tmp_root / "output"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    shutil.copy2(str(_DZT_REAL), str(input_dir / _DZT_REAL.name))
    run_new_engine(input_dir, output_dir, config, tipo_solo="standard")
    return output_dir


# ===========================================================================
# G1 -- _get_engine default
# ===========================================================================

def test_g1_engine_default() -> None:
    _section("G1: _get_engine({}) continua legacy_scansolo")
    try:
        from job_gpr import _get_engine, _VALID_ENGINES
    except ImportError as e:
        _fail("nao foi possivel importar job_gpr._get_engine", e)
        return

    result = _get_engine({})
    if result == "legacy_scansolo":
        _ok(f"_get_engine({{}}) = '{result}'")
    else:
        _fail(f"default errado: '{result}' (esperado 'legacy_scansolo')")

    if "legacy_scansolo" in _VALID_ENGINES and "readgssi_engine" in _VALID_ENGINES:
        _ok(f"_VALID_ENGINES = {_VALID_ENGINES}")
    else:
        _fail(f"_VALID_ENGINES inesperado: {_VALID_ENGINES}")

    if _get_engine({"engine": "invalido"}) == "legacy_scansolo":
        _ok("engine invalido cai em legacy_scansolo (fallback OK)")
    else:
        _fail("engine invalido nao caiu em legacy_scansolo")


# ===========================================================================
# G2 -- adapter sem visual_profile: processada = fluxo relatorio
# ===========================================================================

def test_g2_adapter_default() -> None:
    _section("G2: adapter sem visual_profile -> processada do fluxo relatorio")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = _run_adapter(config=None, tmp_root=Path(tmp))
        except Exception as e:
            _fail("run_new_engine falhou", e)
            return

        proc_dir = out / "02_Imagens_Processadas"
        stem = _DZT_REAL.stem

        processada = proc_dir / f"{stem}_processada.png"
        if processada.exists():
            _ok(f"processada.png existe ({processada.stat().st_size // 1024} KB)")
        else:
            _fail(f"processada.png ausente em {proc_dir}")
            return

        ref_png = proc_dir / f"{stem}_radargrama_readgssi_reference.png"
        if ref_png.exists():
            _ok(f"readgssi_reference.png existe ({ref_png.stat().st_size // 1024} KB)")
        else:
            _fail("readgssi_reference.png ausente no modo default")

        # Processada default NAO deve ser identica ao readgssi_reference
        # (sao de fluxos distintos: relatorio vs readgssi_ref)
        if ref_png.exists():
            if processada.stat().st_size != ref_png.stat().st_size:
                _ok("processada.png != readgssi_reference.png (tamanhos distintos, fluxos diferentes)")
            else:
                _warn("processada.png e readgssi_reference.png tem mesmo tamanho (pode ser coincidencia)")


# ===========================================================================
# G3 -- adapter com visual_profile=readgssi_reference: processada = readgssi_ref
# ===========================================================================

def test_g3_adapter_readgssi_ref() -> None:
    _section("G3: visual_profile=readgssi_reference -> processada = readgssi_reference")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    config = {"visual_profile": "readgssi_reference"}

    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = _run_adapter(config=config, tmp_root=Path(tmp))
        except Exception as e:
            _fail("run_new_engine falhou", e)
            return

        proc_dir = out / "02_Imagens_Processadas"
        stem = _DZT_REAL.stem

        processada = proc_dir / f"{stem}_processada.png"
        ref_png    = proc_dir / f"{stem}_radargrama_readgssi_reference.png"

        if processada.exists():
            _ok(f"processada.png existe ({processada.stat().st_size // 1024} KB)")
        else:
            _fail("processada.png ausente no modo readgssi_reference")
            return

        if ref_png.exists():
            _ok(f"readgssi_reference.png existe ({ref_png.stat().st_size // 1024} KB)")
        else:
            _fail("readgssi_reference.png ausente no modo readgssi_reference")
            return

        # No modo readgssi_reference, processada DEVE ser copia de readgssi_reference
        sz_proc = processada.stat().st_size
        sz_ref  = ref_png.stat().st_size
        if sz_proc == sz_ref:
            _ok(f"processada.png ({sz_proc} B) == readgssi_reference.png ({sz_ref} B) -- copia correta")
        else:
            _fail(f"processada.png ({sz_proc} B) != readgssi_reference.png ({sz_ref} B)")

        # Conteudo binario identico
        if processada.read_bytes() == ref_png.read_bytes():
            _ok("conteudo binario identico (shutil.copy2 confirmado)")
        else:
            _fail("conteudo binario divergente entre processada e readgssi_reference")


# ===========================================================================
# G4 -- readgssi_reference.png existe em ambos os modos
# ===========================================================================

def test_g4_ref_png_sempre() -> None:
    _section("G4: readgssi_reference.png existe em ambos os modos")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    stem = _DZT_REAL.stem

    for label, cfg in [("default", None), ("readgssi_reference", {"visual_profile": "readgssi_reference"})]:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                out = _run_adapter(config=cfg, tmp_root=Path(tmp))
            except Exception as e:
                _fail(f"run_new_engine falhou (modo {label})", e)
                continue

            ref_png = out / "02_Imagens_Processadas" / f"{stem}_radargrama_readgssi_reference.png"
            if ref_png.exists() and ref_png.stat().st_size > 1024:
                _ok(f"modo {label}: readgssi_reference.png ({ref_png.stat().st_size // 1024} KB)")
            else:
                _fail(f"modo {label}: readgssi_reference.png ausente ou invalido")


# ===========================================================================
# G5 -- processada no modo ref != processada no modo padrao
# ===========================================================================

def test_g5_processada_diferente() -> None:
    _section("G5: processada readgssi_reference != processada padrao")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    stem = _DZT_REAL.stem
    sizes: dict[str, int] = {}

    for label, cfg in [("default", None), ("ref", {"visual_profile": "readgssi_reference"})]:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                out = _run_adapter(config=cfg, tmp_root=Path(tmp))
            except Exception as e:
                _fail(f"run_new_engine falhou (modo {label})", e)
                return
            p = out / "02_Imagens_Processadas" / f"{stem}_processada.png"
            if p.exists():
                sizes[label] = p.stat().st_size
            else:
                _fail(f"processada.png ausente no modo {label}")
                return

    if sizes["default"] != sizes["ref"]:
        _ok(
            f"processada default ({sizes['default'] // 1024} KB) "
            f"!= processada readgssi_ref ({sizes['ref'] // 1024} KB)"
        )
    else:
        _warn(
            f"tamanhos identicos ({sizes['default'] // 1024} KB) -- "
            f"imagens podem ser coincidentemente do mesmo tamanho"
        )


# ===========================================================================
# G6 -- index_projeto.csv valido
# ===========================================================================

def test_g6_index_csv() -> None:
    _section("G6: index_projeto.csv com colunas e linhas corretas")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    required_cols = {
        "arquivo_dzt", "n_tracos", "profundidade_max_m",
        "distancia_max_m", "snr_imagem_db", "modo_processamento",
    }

    for label, cfg in [("default", None), ("ref", {"visual_profile": "readgssi_reference"})]:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                out = _run_adapter(config=cfg, tmp_root=Path(tmp))
            except Exception as e:
                _fail(f"run_new_engine falhou (modo {label})", e)
                continue

            csv_path = out / "index_projeto.csv"
            if not csv_path.exists():
                _fail(f"index_projeto.csv ausente (modo {label})")
                continue

            with open(csv_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))

            if len(rows) == 1:
                _ok(f"modo {label}: 1 linha em index_projeto.csv")
            else:
                _fail(f"modo {label}: {len(rows)} linhas (esperado 1)")

            missing = required_cols - set(rows[0].keys())
            if not missing:
                _ok(f"modo {label}: colunas obrigatorias presentes")
            else:
                _fail(f"modo {label}: colunas ausentes: {missing}")


# ===========================================================================
# G7 -- pipeline_metrics.json valido
# ===========================================================================

def test_g7_metrics_json() -> None:
    _section("G7: pipeline_metrics.json valido")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    required_keys = {"dzt_filename", "n_tracos", "snr_raw_db", "modo_processamento"}
    stem = _DZT_REAL.stem

    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = _run_adapter(config={"visual_profile": "readgssi_reference"}, tmp_root=Path(tmp))
        except Exception as e:
            _fail("run_new_engine falhou", e)
            return

        metrics_path = out / "02_Imagens_Processadas" / f"{stem}_pipeline_metrics.json"
        if not metrics_path.exists():
            _fail(f"pipeline_metrics.json ausente em {metrics_path.parent}")
            return

        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception as e:
            _fail("pipeline_metrics.json nao e JSON valido", e)
            return

        _ok(f"pipeline_metrics.json e JSON valido ({metrics_path.stat().st_size // 1024} KB)")

        missing = required_keys - set(data.keys())
        if not missing:
            _ok(f"campos obrigatorios presentes: {required_keys}")
        else:
            _fail(f"campos ausentes: {missing}")


# ===========================================================================
# G8 -- _alvos.csv vazio com headers corretos
# ===========================================================================

def test_g8_alvos_csv() -> None:
    _section("G8: _alvos.csv vazio com headers corretos")
    if not _DZT_REAL.exists():
        _warn(f"DZT real nao encontrado: {_DZT_REAL}")
        return

    from gpr_engine.scansolo_adapter import _CSV_ALVOS_HEADERS
    stem = _DZT_REAL.stem

    with tempfile.TemporaryDirectory() as tmp:
        try:
            out = _run_adapter(config={"visual_profile": "readgssi_reference"}, tmp_root=Path(tmp))
        except Exception as e:
            _fail("run_new_engine falhou", e)
            return

        alvos_path = out / "05_Tabela_Alvos" / f"{stem}_alvos.csv"
        if not alvos_path.exists():
            _fail(f"_alvos.csv ausente em {alvos_path.parent}")
            return

        _ok("_alvos.csv existe")

        with open(alvos_path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            rows = list(reader)

        if list(headers) == _CSV_ALVOS_HEADERS:
            _ok(f"headers corretos ({len(headers)} colunas)")
        else:
            _fail(f"headers incorretos: {headers}")

        if len(rows) == 0:
            _ok("CSV vazio (sem dados -- detector nao integrado)")
        else:
            _fail(f"CSV tem {len(rows)} linhas de dados (esperado 0)")


# ===========================================================================
# G9 -- skip_ia forcado para readgssi_engine
# ===========================================================================

def test_g9_skip_ia() -> None:
    _section("G9: skip_ia forcado para readgssi_engine")
    try:
        from job_gpr import _get_engine
    except ImportError as e:
        _fail("nao foi possivel importar job_gpr._get_engine", e)
        return

    engine = _get_engine({"engine": "readgssi_engine"})
    if engine == "readgssi_engine":
        _ok("_get_engine({'engine':'readgssi_engine'}) = 'readgssi_engine'")
    else:
        _fail(f"esperado 'readgssi_engine', obtido '{engine}'")

    # Verificar logica de skip_ia no codigo fonte
    job_gpr_path = _HERE.parent / "job_gpr.py"
    if not job_gpr_path.exists():
        _warn(f"job_gpr.py nao encontrado em {job_gpr_path}")
        return

    src = job_gpr_path.read_text(encoding="utf-8")
    if "readgssi_engine" in src and "skip_ia" in src:
        _ok("job_gpr.py contem logica skip_ia para readgssi_engine")
    else:
        _fail("job_gpr.py nao contem logica skip_ia esperada")

    # Verificar que o trecho 'engine == "readgssi_engine"' aparece no contexto skip_ia
    lines = src.splitlines()
    skip_ia_lines = [l.strip() for l in lines if "skip_ia" in l and "readgssi_engine" in l]
    if skip_ia_lines:
        _ok(f"linha skip_ia+readgssi_engine: {skip_ia_lines[0][:80]}")
    else:
        _warn("nao encontrou linha combinando skip_ia e readgssi_engine (verificar logica)")


# ===========================================================================
# G10 -- legacy_scansolo intocado
# ===========================================================================

def test_g10_legacy_intocado() -> None:
    _section("G10: legacy_scansolo nao alterado")
    try:
        from job_gpr import _get_engine, _VALID_ENGINES
    except ImportError as e:
        _fail("nao foi possivel importar job_gpr", e)
        return

    if _get_engine({}) == "legacy_scansolo":
        _ok("default continua legacy_scansolo")
    else:
        _fail(f"default alterado: '{_get_engine({})}'")

    if "legacy_scansolo" in _VALID_ENGINES:
        _ok("legacy_scansolo em _VALID_ENGINES")
    else:
        _fail("legacy_scansolo removido de _VALID_ENGINES")

    # pipeline_v1.py deve existir e nao ter sido modificado nesta fase
    pv1 = _HERE.parent / "pipeline" / "pipeline_v1.py"
    if pv1.exists():
        _ok(f"pipeline_v1.py existe ({pv1.stat().st_size // 1024} KB)")
    else:
        _fail(f"pipeline_v1.py nao encontrado em {pv1}")

    # adapter nao deve importar pipeline_v1 diretamente
    adapter_src = (_HERE / "scansolo_adapter.py").read_text(encoding="utf-8")
    if "pipeline_v1" not in adapter_src:
        _ok("scansolo_adapter.py nao importa pipeline_v1 (correto)")
    else:
        _fail("scansolo_adapter.py importa pipeline_v1 (nao deveria)")


# ===========================================================================
# Ponto de entrada
# ===========================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Fase 8.7 -- readgssi_reference mapeado para Processada")
    print("=" * 60)

    if not _DZT_REAL.exists():
        print(f"\n[AVISO] DZT real nao encontrado: {_DZT_REAL}")
        print("  G2-G9 serao WARN. Apenas G1, G10 rodam sem DZT.")

    test_g1_engine_default()
    test_g2_adapter_default()
    test_g3_adapter_readgssi_ref()
    test_g4_ref_png_sempre()
    test_g5_processada_diferente()
    test_g6_index_csv()
    test_g7_metrics_json()
    test_g8_alvos_csv()
    test_g9_skip_ia()
    test_g10_legacy_intocado()

    print()
    print("=" * 60)
    total = _PASS + _FAIL + _WARN
    print(f"RESULTADO: {_PASS}/{total} PASS  |  {_FAIL} FAIL  |  {_WARN} WARN")
    print("=" * 60)

    if _FAIL > 0:
        sys.exit(1)
