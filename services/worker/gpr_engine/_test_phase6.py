"""
Fase 6 -- testes de aceite de gpr_engine.arrays e gpr_engine.metrics.

Valida:
  arrays.py:
  - save_array_atomic cria arquivo .npy carregavel
  - load_array retorna np.ndarray correto
  - save_engine_arrays salva todos os nomes esperados
  - processado.npy e processado_visual.npy existem e tem mesmo conteudo
  - diretorio pai criado automaticamente

  metrics.py:
  - build_pipeline_metrics gera todos os campos obrigatorios
  - imagem_bruta_ok/cientifica_ok/relatorio_ok derivados de image_paths
  - imagem_anotada_ok sempre False (detector nao integrado)
  - save_metrics_atomic cria JSON valido
  - load_metrics le corretamente
  - Path e numpy scalars serializados sem erro
  - profundidade_max_m calculada de twtt_max_ns x velocity / 2

  Geral:
  - nenhum import de GPRPy

Uso:
  python -m gpr_engine._test_phase6
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

_worker_dir = Path(__file__).resolve().parent.parent
if str(_worker_dir) not in sys.path:
    sys.path.insert(0, str(_worker_dir))

import numpy as np


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


def _tmpdir() -> Path:
    return Path(tempfile.mkdtemp())


def _make_arr(seed: int = 42, shape: tuple = (128, 40)) -> np.ndarray:
    return np.random.default_rng(seed).standard_normal(shape).astype(np.float32)


def _make_dzt_data(n_traces: int = 40, n_samples: int = 128) -> "DZTData":
    """Cria DZTData minimo e valido para testes."""
    from gpr_engine._types import DZTData
    arr = _make_arr(shape=(n_samples, n_traces))
    return DZTData(
        arr_raw=arr,
        n_samples=n_samples,
        n_traces=n_traces,
        twtt_max_ns=60.0,
        dt_ns=60.0 / n_samples,
        samp_freq_hz=1.0 / (60.0 / n_samples / 1e9),
        dist_total_m=8.5,
        dist_per_trace_m=8.5 / n_traces,
        modo_coleta="distancia",
        antfreq_mhz=270,
        rhf_epsr=9.0,
        wave_speed_mns=0.1,
        rhf_spm=4.7,
        rhf_sps=100.0,
        rhf_range_ns=60.0,
        timezero_sample=5,
        dzt_filename="PATIO___001.DZT",
        dzt_sha256="abc123def456",
        has_dzg=False,
        has_dzx=False,
        dzx_marks=[],
    )


def _make_flow_arrays() -> "FlowArrays":
    """Cria FlowArrays sintetico para testes."""
    from gpr_engine.flows import FlowArrays
    arr = _make_arr(seed=99)
    return FlowArrays(
        arr_dewow_bp=arr + 0.1,
        arr_cientifico=arr + 0.2,
        arr_sem_agc=arr + 0.3,
        arr_relatorio=arr + 0.4,
        arr_preview_radan=arr + 0.5,
    )


_BASE_CONFIG: dict = {
    "velocity_mns":        0.1,
    "tipo_solo":           "standard",
    "detector_input_mode": "raw",
    "det_depth_min_m":     0.30,
    "dewow_window":        5,
    "bandpass_low_mhz":    80.0,
    "bandpass_high_mhz":   500.0,
    "bandpass_order":      5,
    "bgremoval_traces":    30,
    "tpow_power":          0.5,
    "agc_window":          150,
}


# ---------------------------------------------------------------------------
# 1. Imports e ausencia de GPRPy
# ---------------------------------------------------------------------------

def test_imports() -> bool:
    _section("imports")
    ok = True

    try:
        from gpr_engine.arrays import (  # noqa: F401
            save_array_atomic,
            load_array,
            save_engine_arrays,
        )
    except Exception as exc:
        _fail("importar gpr_engine.arrays", str(exc)); return False
    _ok("gpr_engine.arrays: 3 funcoes importadas")

    try:
        from gpr_engine.metrics import (  # noqa: F401
            build_pipeline_metrics,
            save_metrics_atomic,
            load_metrics,
        )
    except Exception as exc:
        _fail("importar gpr_engine.metrics", str(exc)); return False
    _ok("gpr_engine.metrics: 3 funcoes importadas")

    gprpy = [m for m in sys.modules if "gprpy" in m.lower()]
    if gprpy:
        _fail(f"GPRPy importado: {gprpy}"); ok = False
    else:
        _ok("GPRPy nao importado")

    return ok


# ---------------------------------------------------------------------------
# 2. save_array_atomic -- cria arquivo carregavel
# ---------------------------------------------------------------------------

def test_save_array_atomic() -> bool:
    _section("save_array_atomic")
    from gpr_engine.arrays import save_array_atomic, load_array

    arr = _make_arr(seed=1)
    out = _tmpdir() / "atomic.npy"
    ok = True

    try:
        result = save_array_atomic(arr, out)
    except Exception as exc:
        _fail("save_array_atomic: excecao", str(exc)); return False

    if result == out:
        _ok("retorna Path correto")
    else:
        _fail(f"retorno {result} != {out}"); ok = False

    if out.exists() and out.stat().st_size > 0:
        _ok(f"arquivo criado ({out.stat().st_size} bytes)")
    else:
        _fail("arquivo nao criado ou vazio"); ok = False

    loaded = load_array(out)
    if isinstance(loaded, np.ndarray):
        _ok("load_array retorna np.ndarray")
    else:
        _fail(f"load_array retornou {type(loaded).__name__}"); ok = False

    if loaded.shape == arr.shape:
        _ok(f"shape preservado: {loaded.shape}")
    else:
        _fail(f"shape {loaded.shape} != {arr.shape}"); ok = False

    if np.allclose(loaded, arr):
        _ok("conteudo identico ao original")
    else:
        _fail("conteudo diverge do original"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 3. load_array -- FileNotFoundError em arquivo inexistente
# ---------------------------------------------------------------------------

def test_load_array_missing() -> bool:
    _section("load_array -- arquivo inexistente")
    from gpr_engine.arrays import load_array

    out = _tmpdir() / "nao_existe.npy"
    ok = True

    try:
        load_array(out)
        _fail("deveria ter levantado FileNotFoundError"); ok = False
    except FileNotFoundError:
        _ok("FileNotFoundError levantado corretamente")
    except Exception as exc:
        _fail(f"excecao inesperada: {type(exc).__name__}: {exc}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 4. save_engine_arrays -- todos os nomes esperados
# ---------------------------------------------------------------------------

def test_save_engine_arrays_names() -> bool:
    _section("save_engine_arrays -- nomes de arquivo")
    from gpr_engine.arrays import save_engine_arrays

    fa = _make_flow_arrays()
    arr_raw = _make_arr(seed=2)
    out_dir = _tmpdir()
    ok = True

    try:
        saved = save_engine_arrays(fa, out_dir, stem="PATIO___001", arr_raw=arr_raw)
    except Exception as exc:
        _fail("save_engine_arrays: excecao", str(exc)); return False

    expected_keys = {
        "raw", "radargrama_cientifico", "processado_sem_agc",
        "processado_visual", "processado",
    }
    for key in expected_keys:
        if key in saved:
            _ok(f"chave '{key}' presente no retorno")
        else:
            _fail(f"chave '{key}' ausente no retorno"); ok = False

    expected_files = [
        "raw.npy", "radargrama_cientifico.npy", "processado_sem_agc.npy",
        "processado_visual.npy", "processado.npy",
    ]
    for fname in expected_files:
        p = out_dir / fname
        if p.exists() and p.stat().st_size > 0:
            _ok(f"arquivo {fname} existe")
        else:
            _fail(f"arquivo {fname} nao encontrado ou vazio"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 5. processado.npy == processado_visual.npy
# ---------------------------------------------------------------------------

def test_processado_alias() -> bool:
    _section("processado.npy == processado_visual.npy")
    from gpr_engine.arrays import load_array, save_engine_arrays

    fa = _make_flow_arrays()
    out_dir = _tmpdir()
    save_engine_arrays(fa, out_dir, stem="TEST")
    ok = True

    arr_visual = load_array(out_dir / "processado_visual.npy")
    arr_proc   = load_array(out_dir / "processado.npy")

    if np.array_equal(arr_visual, arr_proc):
        _ok("processado.npy conteudo == processado_visual.npy")
    else:
        _fail("processado.npy difere de processado_visual.npy"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 6. save_engine_arrays sem arr_raw -- raw.npy nao deve existir
# ---------------------------------------------------------------------------

def test_save_engine_arrays_no_raw() -> bool:
    _section("save_engine_arrays sem arr_raw")
    from gpr_engine.arrays import save_engine_arrays

    fa = _make_flow_arrays()
    out_dir = _tmpdir()
    saved = save_engine_arrays(fa, out_dir, stem="TEST")
    ok = True

    if "raw" not in saved:
        _ok("chave 'raw' ausente no retorno (esperado)")
    else:
        _fail("chave 'raw' nao deveria estar no retorno quando arr_raw=None"); ok = False

    if not (out_dir / "raw.npy").exists():
        _ok("raw.npy nao criado (correto)")
    else:
        _fail("raw.npy nao deveria ter sido criado"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 7. build_pipeline_metrics -- campos obrigatorios
# ---------------------------------------------------------------------------

def test_build_pipeline_metrics_fields() -> bool:
    _section("build_pipeline_metrics -- campos obrigatorios")
    from gpr_engine.metrics import build_pipeline_metrics

    dzt = _make_dzt_data()
    fa  = _make_flow_arrays()
    img_paths = {
        "bruta":           Path("/tmp/bruta.png"),
        "cientifica":      Path("/tmp/cientifica.png"),
        "relatorio":       None,
        "preview_radan_5m": Path("/tmp/preview.png"),
    }
    snr_stages = {"raw": 20.6, "dewow_bp": 25.1, "cientifico": 26.0}

    metrics = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=fa,
        config=_BASE_CONFIG,
        modo_processamento="padrao",
        snr_raw_db=20.6,
        snr_raw_ratio=10.7,
        snr_stages_db=snr_stages,
        image_paths=img_paths,
    )

    ok = True
    required = [
        "dzt_filename", "pipeline_version", "engine_name",
        "modo_processamento", "tipo_solo", "n_tracos",
        "dist_total_m", "profundidade_max_m",
        "snr_raw_db", "snr_raw_ratio", "snr_stages_db",
        "filtros_customizados",
        "imagem_bruta_ok", "imagem_cientifica_ok",
        "imagem_relatorio_ok", "imagem_preview_radan_5m_ok",
        "imagem_anotada_ok", "detector_input_mode",
        "det_depth_min_m_usado", "dzt_sha256", "outputs",
    ]
    for field in required:
        if field in metrics:
            _ok(f"campo '{field}' presente")
        else:
            _fail(f"campo '{field}' ausente"); ok = False

    # Valores esperados
    checks = [
        ("n_tracos",              40),
        ("dzt_filename",          "PATIO___001.DZT"),
        ("engine_name",           "readgssi_engine"),
        ("modo_processamento",    "padrao"),
        ("tipo_solo",             "standard"),
        ("imagem_bruta_ok",       True),
        ("imagem_cientifica_ok",  True),
        ("imagem_relatorio_ok",   False),   # path=None
        ("imagem_preview_radan_5m_ok", True),
        ("imagem_anotada_ok",     False),   # detector nao integrado
        ("detector_input_mode",   "raw"),
    ]
    for field, expected in checks:
        actual = metrics.get(field)
        if actual == expected:
            _ok(f"{field} == {expected!r}")
        else:
            _fail(f"{field} = {actual!r} != {expected!r}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 8. profundidade_max_m calculada corretamente
# ---------------------------------------------------------------------------

def test_profundidade_calc() -> bool:
    _section("profundidade_max_m = twtt_max_ns * velocity / 2")
    from gpr_engine.metrics import build_pipeline_metrics

    dzt = _make_dzt_data()  # twtt_max_ns=60.0, wave_speed_mns=0.1
    config = {**_BASE_CONFIG, "velocity_mns": 0.1}
    # Esperado: 60.0 * 0.1 / 2 = 3.0 m
    expected = 3.0

    metrics = build_pipeline_metrics(
        dzt_data=dzt, flow_arrays=None, config=config,
        modo_processamento="padrao", snr_raw_db=20.0, snr_raw_ratio=10.0,
    )
    actual = metrics.get("profundidade_max_m", None)
    ok = True

    if actual is not None and abs(float(actual) - expected) < 1e-3:
        _ok(f"profundidade_max_m = {actual} (esperado {expected})")
    else:
        _fail(f"profundidade_max_m = {actual!r} != {expected}"); ok = False

    # Testar com velocity alternativa
    config2 = {**_BASE_CONFIG, "velocity_mns": 0.07}
    # Esperado: 60.0 * 0.07 / 2 = 2.1 m
    expected2 = 2.1
    m2 = build_pipeline_metrics(
        dzt_data=dzt, flow_arrays=None, config=config2,
        modo_processamento="padrao", snr_raw_db=20.0, snr_raw_ratio=10.0,
    )
    actual2 = m2.get("profundidade_max_m", None)
    if actual2 is not None and abs(float(actual2) - expected2) < 1e-3:
        _ok(f"profundidade_max_m (v=0.07) = {actual2} (esperado {expected2})")
    else:
        _fail(f"profundidade_max_m (v=0.07) = {actual2!r} != {expected2}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 9. save_metrics_atomic + load_metrics -- JSON valido
# ---------------------------------------------------------------------------

def test_save_load_metrics() -> bool:
    _section("save_metrics_atomic + load_metrics")
    from gpr_engine.metrics import build_pipeline_metrics, load_metrics, save_metrics_atomic

    dzt = _make_dzt_data()
    metrics = build_pipeline_metrics(
        dzt_data=dzt, flow_arrays=None, config=_BASE_CONFIG,
        modo_processamento="padrao", snr_raw_db=20.6, snr_raw_ratio=10.7,
        image_paths={"bruta": Path("/tmp/x.png")},
    )

    out = _tmpdir() / "metrics.json"
    ok = True

    try:
        result = save_metrics_atomic(metrics, out)
    except Exception as exc:
        _fail("save_metrics_atomic: excecao", str(exc)); return False

    if result == out:
        _ok("retorna Path correto")
    else:
        _fail(f"retorno {result} != {out}"); ok = False

    if out.exists() and out.stat().st_size > 0:
        _ok(f"arquivo criado ({out.stat().st_size} bytes)")
    else:
        _fail("arquivo nao criado ou vazio"); ok = False

    # Verificar que e JSON valido
    try:
        raw = out.read_text(encoding="utf-8")
        parsed = json.loads(raw)
    except Exception as exc:
        _fail("JSON invalido", str(exc)); return False
    _ok("conteudo e JSON valido")

    # load_metrics
    try:
        loaded = load_metrics(out)
    except Exception as exc:
        _fail("load_metrics: excecao", str(exc)); return False

    if loaded.get("dzt_filename") == "PATIO___001.DZT":
        _ok("load_metrics retorna dados corretos")
    else:
        _fail(f"dzt_filename={loaded.get('dzt_filename')!r}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 10. Serializacao de Path e numpy scalars
# ---------------------------------------------------------------------------

def test_json_serialization() -> bool:
    _section("Path e numpy scalars serializados sem erro")
    from gpr_engine.metrics import build_pipeline_metrics, save_metrics_atomic

    dzt = _make_dzt_data()
    # Injetar numpy scalars no config e SNR
    config_np = {
        "velocity_mns":     np.float32(0.1),
        "bandpass_low_mhz": np.float64(80.0),
        "bandpass_order":   np.int32(5),
        "tipo_solo":        "standard",
    }
    snr_stages = {"raw": np.float32(20.6), "dewow_bp": np.float64(25.1)}
    img_paths = {"bruta": Path("/tmp/bruta.png"), "cientifica": None}

    metrics = build_pipeline_metrics(
        dzt_data=dzt,
        flow_arrays=None,
        config=config_np,
        modo_processamento="padrao",
        snr_raw_db=np.float32(20.6),
        snr_raw_ratio=np.float64(10.7),
        snr_stages_db=snr_stages,
        image_paths=img_paths,
    )

    out = _tmpdir() / "np_scalars.json"
    ok = True

    try:
        save_metrics_atomic(metrics, out)
    except TypeError as exc:
        _fail("TypeError ao serializar numpy scalars/Path", str(exc)); return False
    except Exception as exc:
        _fail("excecao inesperada", str(exc)); return False
    _ok("save_metrics_atomic com numpy scalars: sem excecao")

    try:
        loaded = json.loads(out.read_text(encoding="utf-8"))
    except Exception as exc:
        _fail("JSON invalido", str(exc)); return False
    _ok("JSON valido com numpy scalars convertidos")

    # Path deve virar string
    bruta = loaded.get("outputs", {}).get("images", {}).get("bruta")
    if isinstance(bruta, str):
        _ok(f"Path convertido para str: {bruta!r}")
    else:
        _fail(f"Path nao convertido: {bruta!r}"); ok = False

    return ok


# ---------------------------------------------------------------------------
# 11. Diretorio pai criado automaticamente (arrays e metrics)
# ---------------------------------------------------------------------------

def test_parent_dirs_created() -> bool:
    _section("diretorio pai criado automaticamente")
    from gpr_engine.arrays import save_array_atomic
    from gpr_engine.metrics import save_metrics_atomic

    base = _tmpdir()
    ok = True

    # arrays.py
    arr_path = base / "deep" / "nested" / "arr.npy"
    assert not arr_path.parent.exists()
    try:
        save_array_atomic(_make_arr(), arr_path)
    except Exception as exc:
        _fail("save_array_atomic: dir pai nao criado", str(exc)); ok = False
    if arr_path.exists():
        _ok("save_array_atomic: dir pai criado")
    else:
        _fail("save_array_atomic: arquivo nao criado"); ok = False

    # metrics.py
    met_path = base / "also" / "deep" / "metrics.json"
    assert not met_path.parent.exists()
    try:
        save_metrics_atomic({"test": True}, met_path)
    except Exception as exc:
        _fail("save_metrics_atomic: dir pai nao criado", str(exc)); ok = False
    if met_path.exists():
        _ok("save_metrics_atomic: dir pai criado")
    else:
        _fail("save_metrics_atomic: arquivo nao criado"); ok = False

    return ok


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> int:
    print("=" * 60)
    print("gpr_engine  Fase 6 -- testes de aceite (arrays.py + metrics.py)")
    print("=" * 60)

    results = [
        test_imports(),
        test_save_array_atomic(),
        test_load_array_missing(),
        test_save_engine_arrays_names(),
        test_processado_alias(),
        test_save_engine_arrays_no_raw(),
        test_build_pipeline_metrics_fields(),
        test_profundidade_calc(),
        test_save_load_metrics(),
        test_json_serialization(),
        test_parent_dirs_created(),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"Resultado: {passed}/{total} grupos passaram")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
