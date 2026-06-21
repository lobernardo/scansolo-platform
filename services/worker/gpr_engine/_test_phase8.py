"""
Fase 8 -- testes de aceite da integracao gpr_engine no job_gpr.py.

Valida:
  - _get_engine: selecao correta de motor por processing_config
  - scansolo_adapter.run_new_engine: estrutura de saida compativel com _persist_outputs
  - caminho legacy ainda presente e intacto em job_gpr.py
  - zero imports reais de GPRPy/pipeline_v1 em gpr_engine

Uso:
  python -m gpr_engine._test_phase8
  python -m gpr_engine._test_phase8 C:\\caminho\\arquivo.DZT
"""
from __future__ import annotations

import csv
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

# ---------------------------------------------------------------------------
# DZT real (opcional) -- procura em HELPER benchmark
# ---------------------------------------------------------------------------

_HELPER_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "KB_ScansoloPlataform" / "benchmark_real" / "HELPER" / "HELPER.PRJ_DZT"
)

_REAL_DZT: Path | None = None
if len(sys.argv) > 1:
    _REAL_DZT = Path(sys.argv[1])
elif _HELPER_DIR.exists():
    found = sorted(_HELPER_DIR.glob("*.DZT")) + sorted(_HELPER_DIR.glob("*.dzt"))
    if found:
        _REAL_DZT = found[0]

# ---------------------------------------------------------------------------
# Helpers de output
# ---------------------------------------------------------------------------

_PNG_SIG = b"\x89PNG\r\n\x1a\n"


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


# ---------------------------------------------------------------------------
# DZTData sintetico
# ---------------------------------------------------------------------------

def _make_dzt_data(filename: str = "TEST.DZT"):
    from gpr_engine._types import DZTData
    import numpy as np
    rng = np.random.default_rng(8)
    n_samples, n_traces = 64, 20
    arr = rng.standard_normal((n_samples, n_traces)).astype(np.float32)
    dt_ns = 32.0 / n_samples
    return DZTData(
        arr_raw=arr, n_samples=n_samples, n_traces=n_traces,
        twtt_max_ns=32.0, dt_ns=dt_ns, samp_freq_hz=1.0 / (dt_ns * 1e-9),
        dist_total_m=4.0, dist_per_trace_m=0.2, modo_coleta="distancia",
        antfreq_mhz=270, rhf_epsr=9.0, wave_speed_mns=0.10,
        rhf_spm=5.0, rhf_sps=100.0, rhf_range_ns=32.0,
        timezero_sample=2, dzt_filename=filename,
        dzt_sha256="0" * 64, has_dzg=False, has_dzx=False, dzx_marks=[],
    )


# ---------------------------------------------------------------------------
# 1. Imports e ausencia de GPRPy
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    _section("imports e ausencia de GPRPy")
    ok = True

    try:
        from gpr_engine.scansolo_adapter import run_new_engine  # noqa: F401
    except Exception as exc:
        _fail("importar gpr_engine.scansolo_adapter", str(exc))
        return False
    _ok("gpr_engine.scansolo_adapter importa run_new_engine")

    try:
        from job_gpr import _get_engine  # noqa: F401
    except Exception as exc:
        _fail("importar job_gpr._get_engine", str(exc))
        return False
    _ok("job_gpr._get_engine importavel")

    bad = [m for m in sys.modules if "gprpy" in m.lower()]
    if bad:
        _fail(f"GPRPy importado apos imports: {bad}")
        ok = False
    else:
        _ok("GPRPy nao importado apos imports")

    return ok


# ---------------------------------------------------------------------------
# 2. _get_engine -- selecao de motor por config
# ---------------------------------------------------------------------------

def test_get_engine() -> bool:
    _section("_get_engine -- selecao de motor")
    from job_gpr import _get_engine
    ok = True

    cases = [
        ({},                              "legacy_scansolo", "ausente -> legacy_scansolo"),
        ({"engine": "legacy_scansolo"},   "legacy_scansolo", "explicito legacy_scansolo"),
        ({"engine": "readgssi_engine"},   "readgssi_engine", "explicito readgssi_engine"),
        ({"engine": "motor_invalido"},    "legacy_scansolo", "invalido -> fallback legacy"),
        ({"engine": ""},                  "legacy_scansolo", "vazio -> fallback legacy"),
        ({"engine": "READGSSI_ENGINE"},   "legacy_scansolo", "case diferente -> fallback legacy"),
    ]

    for cfg, expected, label in cases:
        result = _get_engine(cfg)
        if result == expected:
            _ok(f"{label}: '{result}'")
        else:
            _fail(f"{label}: esperado '{expected}', obtido '{result}'")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 3. Caminho legacy intacto em job_gpr.py
# ---------------------------------------------------------------------------

def test_legacy_path_present() -> bool:
    _section("caminho legacy intacto em job_gpr.py")
    ok = True

    source = (_worker_dir / "job_gpr.py").read_text(encoding="utf-8")

    checks = [
        ("PIPELINE_SCRIPT",          "PIPELINE_SCRIPT definido"),
        ("_run_pipeline",            "funcao _run_pipeline presente"),
        ("pipeline_v1.py",           "referencia a pipeline_v1.py preservada"),
        ("legacy_scansolo",          "string 'legacy_scansolo' presente"),
        ("readgssi_engine",          "string 'readgssi_engine' presente"),
        ("_get_engine",              "funcao _get_engine presente"),
        ("run_new_engine",           "branch readgssi_engine chama run_new_engine"),
        ("gpr_skip_ia",              "log gpr_skip_ia presente"),
    ]
    for token, label in checks:
        if token in source:
            _ok(label)
        else:
            _fail(f"{label}: '{token}' nao encontrado em job_gpr.py")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. Adapter sintetico -- estrutura de saida sem DZT real
# ---------------------------------------------------------------------------

def test_adapter_synthetic() -> bool:
    _section("adapter sintetico -- estrutura de saida")
    from gpr_engine.scansolo_adapter import run_new_engine

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        fake_dzt = input_dir / "TEST.DZT"
        fake_dzt.write_bytes(b"x")
        dzt_data = _make_dzt_data("TEST.DZT")

        with patch("gpr_engine.pipeline.DZTReader") as MockReader:
            MockReader.return_value.read.return_value = dzt_data
            try:
                run_new_engine(input_dir, output_dir, config=None, tipo_solo="standard")
            except Exception as exc:
                _fail("run_new_engine lancou excecao", str(exc))
                return False
        _ok("run_new_engine concluiu sem excecao")

        # index_projeto.csv
        index_path = output_dir / "index_projeto.csv"
        if index_path.exists():
            _ok(f"index_projeto.csv gerado ({index_path.stat().st_size} bytes)")
            with open(index_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            if len(rows) == 1:
                _ok("index_projeto.csv: 1 linha (1 DZT)")
            else:
                _fail(f"index_projeto.csv: esperado 1 linha, obtido {len(rows)}")
                ok = False
            for col in ("arquivo_dzt", "n_tracos", "snr_imagem_db", "modo_processamento"):
                if col in (rows[0] if rows else {}):
                    _ok(f"coluna '{col}' presente: {(rows[0] if rows else {}).get(col, '')[:30]}")
                else:
                    _fail(f"coluna '{col}' ausente em index_projeto.csv")
                    ok = False
        else:
            _fail("index_projeto.csv nao gerado")
            ok = False

        # Subdiretorios
        for d in ("01_Imagens_Brutas", "02_Imagens_Processadas", "05_Tabela_Alvos"):
            if (output_dir / d).is_dir():
                _ok(f"subdir '{d}' criado")
            else:
                _fail(f"subdir '{d}' ausente")
                ok = False

        # PNGs
        png_checks = [
            ("01_Imagens_Brutas",      "TEST_bruta.png"),
            ("02_Imagens_Processadas", "TEST_radargrama_cientifico.png"),
            ("02_Imagens_Processadas", "TEST_processada.png"),
            ("02_Imagens_Processadas", "TEST_radargrama_preview_radan_5m.png"),
        ]
        for subdir, fname in png_checks:
            p = output_dir / subdir / fname
            if _is_valid_png(p):
                _ok(f"PNG valido: {subdir}/{fname} ({p.stat().st_size} bytes)")
            else:
                _fail(f"PNG ausente ou invalido: {subdir}/{fname}")
                ok = False

        # Metrics JSON em 02_Imagens_Processadas
        mp = output_dir / "02_Imagens_Processadas" / "TEST_pipeline_metrics.json"
        if mp.exists():
            try:
                m = json.loads(mp.read_text(encoding="utf-8"))
                _ok(f"pipeline_metrics.json valido: {len(m)} campos")
                if m.get("engine_name") == "readgssi_engine":
                    _ok("engine_name=readgssi_engine")
                else:
                    _fail(f"engine_name='{m.get('engine_name')}' (esperado readgssi_engine)")
                    ok = False
                if m.get("imagem_anotada_ok") is False:
                    _ok("imagem_anotada_ok=False (detector nao integrado)")
                else:
                    _fail(f"imagem_anotada_ok={m.get('imagem_anotada_ok')} (esperado False)")
                    ok = False
            except Exception as exc:
                _fail("pipeline_metrics.json invalido", str(exc))
                ok = False
        else:
            _fail("TEST_pipeline_metrics.json nao encontrado em 02_Imagens_Processadas")
            ok = False

        # CSV de alvos vazio
        ap = output_dir / "05_Tabela_Alvos" / "TEST_alvos.csv"
        if ap.exists():
            raw = ap.read_text(encoding="utf-8")
            with open(ap, newline="", encoding="utf-8") as fh:
                data_rows = list(csv.DictReader(fh))
            if "rank" in raw and "arquivo_dzt" in raw:
                _ok(f"TEST_alvos.csv: cabecalhos presentes, {len(data_rows)} linhas de dados (esperado 0)")
            else:
                _fail("TEST_alvos.csv: cabecalhos ausentes")
                ok = False
            if len(data_rows) == 0:
                _ok("TEST_alvos.csv: vazio como esperado (sem detector)")
            else:
                _fail(f"TEST_alvos.csv: esperado 0 linhas, obtido {len(data_rows)}")
                ok = False
        else:
            _fail("TEST_alvos.csv nao gerado")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. Adapter com DZT real (opcional)
# ---------------------------------------------------------------------------

def test_adapter_real_dzt(dzt_path: Path) -> bool:
    _section(f"adapter DZT real -- {dzt_path.name}")
    from gpr_engine.scansolo_adapter import run_new_engine

    ok = True
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        input_dir = tmp_path / "input"
        output_dir = tmp_path / "output"
        input_dir.mkdir()
        output_dir.mkdir()

        shutil.copy2(dzt_path, input_dir / dzt_path.name)
        stem = dzt_path.stem
        print(f"  Processando: {dzt_path.name} (stem={stem})")

        try:
            run_new_engine(input_dir, output_dir, config=None, tipo_solo="standard")
        except Exception as exc:
            _fail("run_new_engine lancou excecao", str(exc))
            return False
        _ok("run_new_engine concluiu sem excecao")

        # index_projeto.csv
        index_path = output_dir / "index_projeto.csv"
        if index_path.exists():
            with open(index_path, newline="", encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            _ok(f"index_projeto.csv: {len(rows)} linha(s)")
            if rows:
                r = rows[0]
                print(f"  arquivo_dzt={r.get('arquivo_dzt')} "
                      f"n_tracos={r.get('n_tracos')} "
                      f"dist={r.get('distancia_max_m')}m "
                      f"prof={r.get('profundidade_max_m')}m "
                      f"snr={r.get('snr_imagem_db')}dB "
                      f"modo={r.get('modo_processamento')}")
                if r.get("arquivo_dzt"):
                    _ok("arquivo_dzt preenchido")
                else:
                    _fail("arquivo_dzt vazio no index_projeto.csv")
                    ok = False
        else:
            _fail("index_projeto.csv nao gerado")
            ok = False

        # PNGs esperados
        png_checks = [
            (f"01_Imagens_Brutas/{stem}_bruta.png",                        "bruta"),
            (f"02_Imagens_Processadas/{stem}_radargrama_cientifico.png",   "cientifica"),
            (f"02_Imagens_Processadas/{stem}_processada.png",              "processada"),
            (f"02_Imagens_Processadas/{stem}_radargrama_preview_radan_5m.png", "preview"),
        ]
        for rel, label in png_checks:
            p = output_dir / rel
            if _is_valid_png(p):
                _ok(f"PNG '{label}': {p.stat().st_size} bytes")
            else:
                _fail(f"PNG '{label}' ausente ou invalido: {rel}")
                ok = False

        # Metrics JSON
        mp = output_dir / "02_Imagens_Processadas" / f"{stem}_pipeline_metrics.json"
        if mp.exists():
            m = json.loads(mp.read_text(encoding="utf-8"))
            _ok(f"pipeline_metrics.json: {len(m)} campos")
            checks_m = [
                ("engine_name", "readgssi_engine"),
                ("imagem_anotada_ok", False),
            ]
            for key, expected in checks_m:
                if m.get(key) == expected:
                    _ok(f"{key}={m.get(key)}")
                else:
                    _fail(f"{key}={m.get(key)} (esperado {expected})")
                    ok = False
        else:
            _fail(f"pipeline_metrics.json nao encontrado: {mp.name}")
            ok = False

        # CSV de alvos
        ap = output_dir / "05_Tabela_Alvos" / f"{stem}_alvos.csv"
        if ap.exists():
            with open(ap, newline="", encoding="utf-8") as fh:
                data_rows = list(csv.DictReader(fh))
            _ok(f"_alvos.csv: {len(data_rows)} alvos (esperado 0 -- sem detector)")
        else:
            _fail(f"_alvos.csv nao gerado: {ap.name}")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 8 -- testes de aceite (integracao job_gpr)")
    print("=" * 60)

    if _REAL_DZT:
        print(f"\nDZT real: {_REAL_DZT}")
    else:
        print("\nDZT real: nao encontrado -- rodando apenas testes sinteticos")

    results = []
    results.append(("imports",             test_imports()))
    results.append(("_get_engine",         test_get_engine()))
    results.append(("legacy path",         test_legacy_path_present()))
    results.append(("adapter sintetico",   test_adapter_synthetic()))

    if _REAL_DZT:
        results.append(("adapter DZT real",  test_adapter_real_dzt(_REAL_DZT)))

    print("\n" + "=" * 60)
    print(f"{'Grupo':<25} {'Resultado'}")
    print("-" * 40)
    for name, passed in results:
        status = "PASS" if passed else "FAIL"
        print(f"  {name:<23} {status}")

    passed_n = sum(1 for _, r in results if r)
    total_n = len(results)
    print("-" * 40)
    print(f"Resultado: {passed_n}/{total_n} grupos passaram")
    return 0 if all(r for _, r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
