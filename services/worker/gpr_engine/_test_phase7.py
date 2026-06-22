"""
Fase 7 -- testes de aceite do gpr_engine.pipeline.

Valida process_dzt() e ProcessResult com um DZT sintetico (sem arquivo real),
usando mock de DZTReader para simular a leitura.

Opcionally, se um .DZT real for fornecido via CLI ou encontrado em
services/worker/pipeline/benchmark_real/, tambem roda o pipeline real.

Uso:
  python -m gpr_engine._test_phase7
  python -m gpr_engine._test_phase7 C:\\caminho\\arquivo.DZT
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

import numpy as np

# ---------------------------------------------------------------------------
# Descoberta automatica de DZT real
# ---------------------------------------------------------------------------

_BENCHMARK_DIR = Path(__file__).resolve().parent.parent / "pipeline" / "benchmark_real"

_REAL_DZT: Path | None = None
if len(sys.argv) > 1:
    _REAL_DZT = Path(sys.argv[1])
elif _BENCHMARK_DIR.exists():
    _found = sorted(_BENCHMARK_DIR.glob("*.DZT"))
    if _found:
        _REAL_DZT = _found[0]

# ---------------------------------------------------------------------------
# Campos obrigatorios
# ---------------------------------------------------------------------------

_REQUIRED_PROCESS_RESULT_FIELDS = [
    "dzt_data", "flow_arrays", "image_paths", "array_paths",
    "metrics_path", "metrics", "output_dir", "index_row",
]

_REQUIRED_INDEX_ROW_FIELDS = [
    "arquivo", "n_tracos", "distancia_max_m", "profundidade_max_m",
    "snr_raw_db", "snr_raw_ratio", "modo_processamento", "tipo_solo",
    "velocity_mns", "engine_name", "pipeline_version",
    "imagem_bruta", "imagem_cientifica", "imagem_relatorio",
    "imagem_preview_radan_5m", "metrics_path",
]

_REQUIRED_METRICS_FIELDS = [
    "dzt_filename", "pipeline_version", "engine_name",
    "modo_processamento", "tipo_solo", "n_tracos", "dist_total_m",
    "profundidade_max_m", "snr_raw_db", "snr_raw_ratio", "snr_stages_db",
    "filtros_customizados", "imagem_bruta_ok", "imagem_cientifica_ok",
    "imagem_relatorio_ok", "imagem_preview_radan_5m_ok", "imagem_anotada_ok",
    "detector_input_mode", "det_depth_min_m_usado", "dzt_sha256", "outputs",
]

_EXPECTED_IMAGE_KEYS = [
    "bruta", "cientifica", "relatorio", "processada", "preview_radan_5m",
]

_EXPECTED_ARRAY_KEYS = [
    "raw", "radargrama_cientifico", "processado_sem_agc",
    "processado_visual", "processado",
]

# ---------------------------------------------------------------------------
# Helpers de output
# ---------------------------------------------------------------------------

_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_NPY_MAGIC = b"\x93NUMPY"


def _ok(msg: str) -> None:
    print(f"  [PASS] {msg}")


def _fail(msg: str, detail: str = "") -> None:
    suffix = f": {detail}" if detail else ""
    print(f"  [FAIL] {msg}{suffix}", file=sys.stderr)


def _section(name: str) -> None:
    print(f"\n-- {name} --")


def _is_valid_png(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with open(path, "rb") as fh:
        return fh.read(8) == _PNG_SIG


def _is_valid_npy(path: Path) -> bool:
    if not path.exists() or path.stat().st_size == 0:
        return False
    with open(path, "rb") as fh:
        return fh.read(6) == _NPY_MAGIC


# ---------------------------------------------------------------------------
# DZTData sintetico
# ---------------------------------------------------------------------------

def _make_dzt_data():
    from gpr_engine._types import DZTData
    rng = np.random.default_rng(42)
    n_samples, n_traces = 128, 40
    arr_raw = rng.standard_normal((n_samples, n_traces)).astype(np.float32)
    dt_ns = 64.0 / n_samples        # 0.5 ns por amostra
    samp_freq_hz = 1.0 / (dt_ns * 1e-9)   # 2 GHz
    return DZTData(
        arr_raw=arr_raw,
        n_samples=n_samples,
        n_traces=n_traces,
        twtt_max_ns=64.0,
        dt_ns=dt_ns,
        samp_freq_hz=samp_freq_hz,
        dist_total_m=8.5,
        dist_per_trace_m=8.5 / n_traces,
        modo_coleta="distancia",
        antfreq_mhz=270,
        rhf_epsr=9.0,
        wave_speed_mns=0.10,
        rhf_spm=float(n_traces) / 8.5,
        rhf_sps=100.0,
        rhf_range_ns=64.0,
        timezero_sample=5,
        dzt_filename="SYNTHETIC.DZT",
        dzt_sha256="0" * 64,
        has_dzg=False,
        has_dzx=False,
        dzx_marks=[],
    )


# ---------------------------------------------------------------------------
# Runner do pipeline sintetico (executa uma vez, compartilhado entre testes)
# ---------------------------------------------------------------------------

def _run_synthetic(out_dir: Path):
    """Roda process_dzt com DZTReader mockado. Retorna ProcessResult."""
    from gpr_engine.pipeline import process_dzt

    fake_dzt = out_dir / "SYNTHETIC.DZT"
    fake_dzt.write_bytes(b"x")
    dzt_data = _make_dzt_data()

    with patch("gpr_engine.pipeline.DZTReader") as MockReader:
        MockReader.return_value.read.return_value = dzt_data
        result = process_dzt(
            dzt_path=fake_dzt,
            output_dir=out_dir / "output",
        )
    return result


# ---------------------------------------------------------------------------
# 1. Imports e ausencia de GPRPy / pipeline_v1 nos modulos carregados
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    _section("imports")
    ok = True

    try:
        from gpr_engine.pipeline import process_dzt, ProcessResult  # noqa: F401
    except Exception as exc:
        _fail("importar process_dzt + ProcessResult", str(exc))
        return False
    _ok("gpr_engine.pipeline exporta process_dzt e ProcessResult")

    bad = [m for m in sys.modules if "gprpy" in m.lower()]
    if bad:
        _fail(f"GPRPy importado apos import pipeline: {bad}")
        ok = False
    else:
        _ok("GPRPy nao importado apos import pipeline")

    return ok


# ---------------------------------------------------------------------------
# 2. ProcessResult tem todos os campos esperados
# ---------------------------------------------------------------------------

def test_process_result_fields() -> bool:
    _section("ProcessResult -- campos do dataclass")
    from gpr_engine.pipeline import ProcessResult
    ok = True

    actual_fields = {f.name for f in dataclasses.fields(ProcessResult)}
    for name in _REQUIRED_PROCESS_RESULT_FIELDS:
        if name in actual_fields:
            _ok(f"campo '{name}' presente")
        else:
            _fail(f"campo '{name}' ausente em ProcessResult")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 3. run_detector=True deve lancar NotImplementedError
# ---------------------------------------------------------------------------

def test_run_detector_raises() -> bool:
    _section("run_detector=True -> NotImplementedError")
    from gpr_engine.pipeline import process_dzt

    ok = True
    dzt_data = _make_dzt_data()

    with tempfile.TemporaryDirectory() as tmp:
        fake_dzt = Path(tmp) / "SYNTHETIC.DZT"
        fake_dzt.write_bytes(b"x")

        with patch("gpr_engine.pipeline.DZTReader") as MockReader:
            MockReader.return_value.read.return_value = dzt_data
            try:
                process_dzt(
                    dzt_path=fake_dzt,
                    output_dir=Path(tmp) / "out",
                    run_detector=True,
                )
                _fail("run_detector=True nao lancou excecao")
                ok = False
            except NotImplementedError as exc:
                _ok(f"NotImplementedError: {str(exc)[:60]}")
            except Exception as exc:
                _fail(f"excecao errada ({type(exc).__name__})", str(exc))
                ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. process_dzt sintetico: estrutura do ProcessResult
# ---------------------------------------------------------------------------

def test_synthetic_structure(result) -> bool:
    _section("process_dzt sintetico -- estrutura do ProcessResult")
    if result is None:
        _fail("result e None (pipeline sintetico falhou na inicializacao)")
        return False

    ok = True

    for name in _REQUIRED_PROCESS_RESULT_FIELDS:
        val = getattr(result, name, None)
        if val is not None:
            _ok(f"result.{name} preenchido ({type(val).__name__})")
        else:
            _fail(f"result.{name} e None")
            ok = False

    if isinstance(result.output_dir, Path) and result.output_dir.exists():
        _ok(f"output_dir existe: {result.output_dir.name}")
    else:
        _fail("output_dir nao existe ou nao e Path")
        ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. index_row: campos obrigatorios presentes e com tipo correto
# ---------------------------------------------------------------------------

def test_index_row_fields(result) -> bool:
    _section("index_row -- campos obrigatorios")
    if result is None:
        _fail("result e None")
        return False

    ok = True
    row = result.index_row

    for key in _REQUIRED_INDEX_ROW_FIELDS:
        if key in row:
            _ok(f"'{key}' presente: {str(row[key])[:50]}")
        else:
            _fail(f"'{key}' ausente em index_row")
            ok = False

    if ok:
        # Validacoes de tipo nos campos numericos
        checks = [
            ("n_tracos",          int),
            ("distancia_max_m",   float),
            ("profundidade_max_m", float),
            ("snr_raw_db",        (int, float)),
            ("velocity_mns",      float),
        ]
        for key, expected_type in checks:
            val = row.get(key)
            if isinstance(val, expected_type):
                _ok(f"'{key}' tipo correto: {type(val).__name__}={val}")
            else:
                _fail(f"'{key}' tipo errado: {type(val).__name__} (esperado {expected_type})")
                ok = False

    return ok


# ---------------------------------------------------------------------------
# 6. Imagens PNG: existencia e validade
# ---------------------------------------------------------------------------

def test_image_outputs(result) -> bool:
    _section("imagens PNG -- existencia e validade")
    if result is None:
        _fail("result e None")
        return False

    ok = True
    for key in _EXPECTED_IMAGE_KEYS:
        p = result.image_paths.get(key)
        if p is None:
            _fail(f"image_paths['{key}'] ausente")
            ok = False
            continue
        if not Path(p).exists():
            _fail(f"'{key}': arquivo nao existe: {Path(p).name}")
            ok = False
        elif not _is_valid_png(Path(p)):
            _fail(f"'{key}': PNG invalido ou vazio: {Path(p).name}")
            ok = False
        else:
            sz = Path(p).stat().st_size
            _ok(f"'{key}': PNG valido ({sz} bytes): {Path(p).name}")

    return ok


# ---------------------------------------------------------------------------
# 7. Arrays .npy: existencia e validade
# ---------------------------------------------------------------------------

def test_array_outputs(result) -> bool:
    _section("arrays .npy -- existencia e validade")
    if result is None:
        _fail("result e None")
        return False

    ok = True
    for key in _EXPECTED_ARRAY_KEYS:
        p = result.array_paths.get(key)
        if p is None:
            _fail(f"array_paths['{key}'] ausente")
            ok = False
            continue
        if not Path(p).exists():
            _fail(f"'{key}': arquivo nao existe: {Path(p).name}")
            ok = False
        elif not _is_valid_npy(Path(p)):
            _fail(f"'{key}': .npy invalido ou vazio: {Path(p).name}")
            ok = False
        else:
            sz = Path(p).stat().st_size
            _ok(f"'{key}': .npy valido ({sz} bytes): {Path(p).name}")

    # processado.npy deve ser alias de processado_visual.npy (conteudo identico)
    p_vis = result.array_paths.get("processado_visual")
    p_prc = result.array_paths.get("processado")
    if p_vis and p_prc and Path(p_vis).exists() and Path(p_prc).exists():
        arr_vis = np.load(str(p_vis), allow_pickle=False)
        arr_prc = np.load(str(p_prc), allow_pickle=False)
        if np.array_equal(arr_vis, arr_prc):
            _ok("processado.npy == processado_visual.npy (alias correto)")
        else:
            _fail("processado.npy != processado_visual.npy (alias incorreto)")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 8. pipeline_metrics.json: existencia, JSON valido, campos obrigatorios
# ---------------------------------------------------------------------------

def test_metrics_json(result) -> bool:
    _section("pipeline_metrics.json -- JSON valido e campos")
    if result is None:
        _fail("result e None")
        return False

    ok = True
    mp = result.metrics_path

    if not isinstance(mp, Path) or not mp.exists():
        _fail(f"metrics_path nao existe: {mp}")
        return False
    _ok(f"metrics_path existe: {mp.name} ({mp.stat().st_size} bytes)")

    try:
        loaded = json.loads(mp.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail("metrics.json nao e JSON valido", str(exc))
        return False
    _ok("pipeline_metrics.json e JSON valido")

    for field in _REQUIRED_METRICS_FIELDS:
        if field in loaded:
            v = loaded[field]
            short = str(v)[:40] if not isinstance(v, dict) else "{...}"
            _ok(f"'{field}' presente: {short}")
        else:
            _fail(f"'{field}' ausente no pipeline_metrics.json")
            ok = False

    # imagem_anotada_ok deve ser False (detector nao integrado)
    if loaded.get("imagem_anotada_ok") is False:
        _ok("imagem_anotada_ok = False (correto -- detector nao integrado)")
    else:
        _fail(f"imagem_anotada_ok = {loaded.get('imagem_anotada_ok')} (esperado False)")
        ok = False

    # imagens geradas devem estar marcadas como ok
    for img_key in ("imagem_bruta_ok", "imagem_cientifica_ok",
                    "imagem_relatorio_ok", "imagem_preview_radan_5m_ok"):
        if loaded.get(img_key) is True:
            _ok(f"{img_key} = True")
        else:
            _fail(f"{img_key} = {loaded.get(img_key)} (esperado True)")
            ok = False

    return ok


# ---------------------------------------------------------------------------
# 9. DZT real (opcional) -- so roda se _REAL_DZT for encontrado
# ---------------------------------------------------------------------------

def test_real_dzt(dzt_path: Path) -> bool:
    _section(f"DZT real -- {dzt_path.name}")

    try:
        from gpr_engine.pipeline import process_dzt
    except Exception as exc:
        _fail("import process_dzt falhou", str(exc))
        return False

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "output"

        print(f"  Processando: {dzt_path}")
        try:
            result = process_dzt(dzt_path=dzt_path, output_dir=out_dir)
        except Exception as exc:
            _fail("process_dzt lancou excecao", str(exc))
            return False

        ok = True

        # Imagens PNG
        for key in _EXPECTED_IMAGE_KEYS:
            p = result.image_paths.get(key)
            if p and _is_valid_png(Path(p)):
                _ok(f"PNG '{key}': {Path(p).stat().st_size} bytes")
            else:
                _fail(f"PNG '{key}' ausente ou invalido")
                ok = False

        # Arrays .npy
        for key in _EXPECTED_ARRAY_KEYS:
            p = result.array_paths.get(key)
            if p and _is_valid_npy(Path(p)):
                _ok(f"npy '{key}': {Path(p).stat().st_size} bytes")
            else:
                _fail(f"npy '{key}' ausente ou invalido")
                ok = False

        # Metrics JSON
        if result.metrics_path.exists():
            _ok(f"pipeline_metrics.json: {result.metrics_path.stat().st_size} bytes")
        else:
            _fail("pipeline_metrics.json nao gerado")
            ok = False

        # index_row campos obrigatorios
        for key in _REQUIRED_INDEX_ROW_FIELDS:
            if key not in result.index_row:
                _fail(f"index_row ausente: '{key}'")
                ok = False
        if ok:
            _ok("index_row: todos os campos obrigatorios presentes")

        # Resumo
        row = result.index_row
        print(f"  n_tracos={row.get('n_tracos')} "
              f"dist={row.get('distancia_max_m'):.1f}m "
              f"prof={row.get('profundidade_max_m'):.2f}m "
              f"snr={row.get('snr_raw_db'):.1f}dB "
              f"modo={row.get('modo_processamento')}")

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 7 -- testes de aceite (pipeline.py)")
    print("=" * 60)

    if _REAL_DZT:
        print(f"\nDZT real: {_REAL_DZT}")
    else:
        print("\nDZT real: nao encontrado -- rodando apenas testes sinteticos")

    # Testes independentes de DZT
    results = []
    results.append(("imports",              test_imports()))
    results.append(("ProcessResult fields", test_process_result_fields()))
    results.append(("run_detector raises",  test_run_detector_raises()))

    # Pipeline sintetico (roda uma vez; resultado compartilhado nos testes 4-8)
    print("\n-- Inicializando pipeline sintetico --")
    synth_result = None
    with tempfile.TemporaryDirectory() as tmp:
        try:
            synth_result = _run_synthetic(Path(tmp))
            print("  Pipeline sintetico: OK")
        except Exception as exc:
            print(f"  Pipeline sintetico FALHOU: {exc}", file=sys.stderr)

        results.append(("structure",     test_synthetic_structure(synth_result)))
        results.append(("index_row",     test_index_row_fields(synth_result)))
        results.append(("image outputs", test_image_outputs(synth_result)))
        results.append(("array outputs", test_array_outputs(synth_result)))
        results.append(("metrics JSON",  test_metrics_json(synth_result)))

    # DZT real (opcional)
    if _REAL_DZT:
        results.append(("real DZT", test_real_dzt(_REAL_DZT)))

    # Resumo
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
