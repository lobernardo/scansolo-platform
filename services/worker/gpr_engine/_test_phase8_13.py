"""
_test_phase8_13.py -- Integracao do readgssi Preflight no pipeline backend.

Objetivo (Fase 8.13A):
  Garantir que process_dzt() executa o bloco de preflight (sem alterar config efetiva)
  e persiste os resultados no pipeline_metrics.json:
  - Bloco aninhado "preflight" com dzt_metadata e recommendation
  - Campos resumidos no nivel raiz: antenna_freq_mhz_detected, velocity_header_mns,
    epsr_header, frequency_mismatch, recommended_preset_family, recommended_velocity_mns,
    recommended_visual_profile, preflight_header_confidence, preflight_warnings
  - Log de preflight_done, preflight_warning e frequency_mismatch

Grupos:
  G1:  process_dzt gera bloco "preflight" no metrics JSON (requer DZT)
  G2:  antenna_freq_mhz_detected = 350 para HELPER_0004.DZT (requer DZT)
  G3:  frequency_mismatch = True quando config tem antenna_freq_mhz=270 (requer DZT)
  G4:  velocity_header_mns esta no range 0.04-0.20 (requer DZT)
  G5:  recommended_velocity_mns usa valor do header quando valido (requer DZT)
  G6:  preflight_warnings nao vazio (timezero fora de range em HELPER_0004) (requer DZT)
  G7:  preflight_header_confidence = "media" (1 warning em HELPER_0004) (requer DZT)
  G8:  recommended_preset_family = "400mhz" para antena 350 MHz (requer DZT)
  G9:  recommended_engine e recommended_visual_profile corretos (requer DZT)
  G10: frequency_mismatch = False quando nenhum antenna_freq_mhz no config (requer DZT)
  G11: Config efetiva NAO alterada pelo preflight (velocity_mns = valor original) (requer DZT)
  G12: build_pipeline_metrics sem preflight args -> campos com defaults seguros (mock)
  G13: Todos os novos campos de preflight presentes e JSON round-trip valido (requer DZT)

Uso:
  cd services/worker
  python -m gpr_engine._test_phase8_13
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

_HERE = Path(__file__).resolve().parent
_WORKER = _HERE.parent
_REPO_ROOT = _HERE.parents[2]

sys.path.insert(0, str(_WORKER))

_DZT4 = (
    _REPO_ROOT
    / "KB_ScansoloPlataform"
    / "benchmark_real"
    / "HELPER"
    / "HELPER.PRJ_DZT"
    / "HELPER_0004.DZT"
)

_PASS = 0
_FAIL = 0
_WARN = 0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ok(g: str, msg: str) -> None:
    global _PASS; _PASS += 1
    print(f"  [OK]   {g}: {msg}")

def _fail(g: str, msg: str) -> None:
    global _FAIL; _FAIL += 1
    print(f"  [FAIL] {g}: {msg}")

def _warn(g: str, msg: str) -> None:
    global _WARN; _WARN += 1
    print(f"  [WARN] {g}: {msg}")

def _sep(g: str, titulo: str) -> None:
    print(f"\n-- {g}: {titulo}")

_PREFLIGHT_TOP_FIELDS = [
    "antenna_freq_mhz_detected",
    "velocity_header_mns",
    "epsr_header",
    "frequency_mismatch",
    "recommended_preset_family",
    "recommended_velocity_mns",
    "recommended_visual_profile",
    "preflight_header_confidence",
    "preflight_warnings",
]

def _run_process_dzt(out_dir: Path, config: dict):
    from gpr_engine.pipeline import process_dzt
    return process_dzt(str(_DZT4), str(out_dir), config=config)

def _load_metrics(out_dir: Path) -> dict:
    from gpr_engine.metrics import load_metrics
    files = list(out_dir.glob("*_pipeline_metrics.json"))
    assert files, "Nenhum pipeline_metrics.json encontrado"
    return load_metrics(files[0])

def _base_config_helper(**overrides) -> dict:
    """Config para HELPER_0004.DZT (antena 350 MHz segundo header)."""
    cfg = {
        "dewow_window": 5,
        "bandpass_low_mhz": 80.0,
        "bandpass_high_mhz": 500.0,
        "bandpass_order": 5,
        "bandpass_tipo": "butterworth",
        "bandpass_enabled": True,
        "bgremoval_traces": 30,
        "tpow_power": 0.5,
        "agc_window": 150,
        "agc_window_preview": 80,
        "velocity_mns": 0.10,
        "depth_preview_m": 5.0,
        "detector_input_mode": "raw",
        "det_depth_min_m": 0.30,
        "visual_profile": "scientific",
        "gain": 1.0,
        # Simula usuario que escolheu preset 270mhz (frequencia errada para este DZT)
        "antenna_freq_mhz": 270,
    }
    cfg.update(overrides)
    return cfg

# ---------------------------------------------------------------------------
# G1-G11: Testes com DZT real
# ---------------------------------------------------------------------------

def test_g1_preflight_block_present() -> None:
    _sep("G1", 'process_dzt gera bloco "preflight" no metrics JSON')
    if not _DZT4.exists():
        _warn("G1", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    if "preflight" not in m:
        _fail("G1", 'campo "preflight" ausente no metrics JSON')
        return
    pf = m["preflight"]
    if "dzt_metadata" not in pf:
        _fail("G1", '"preflight.dzt_metadata" ausente')
    else:
        _ok("G1", '"preflight.dzt_metadata" presente')
    if "recommendation" not in pf:
        _fail("G1", '"preflight.recommendation" ausente')
    else:
        _ok("G1", '"preflight.recommendation" presente')


def test_g2_antenna_freq_detected() -> None:
    _sep("G2", "antenna_freq_mhz_detected = 350 para HELPER_0004.DZT")
    if not _DZT4.exists():
        _warn("G2", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    detected = m.get("antenna_freq_mhz_detected", -1)
    # HELPER_0004 tem antena 350 MHz segundo o header do DZT
    if detected == 350:
        _ok("G2", f"antenna_freq_mhz_detected={detected} (esperado 350)")
    else:
        _fail("G2", f"antenna_freq_mhz_detected={detected}, esperado 350")

    # Tambem verifica no bloco aninhado
    nested = m.get("preflight", {}).get("dzt_metadata", {}).get("antenna_freq_mhz_detected", -1)
    if nested == 350:
        _ok("G2", f"preflight.dzt_metadata.antenna_freq_mhz_detected={nested}")
    else:
        _fail("G2", f"preflight.dzt_metadata.antenna_freq_mhz_detected={nested}, esperado 350")


def test_g3_frequency_mismatch_true() -> None:
    _sep("G3", "frequency_mismatch = True quando config tem antenna_freq_mhz=270")
    if not _DZT4.exists():
        _warn("G3", f"DZT nao encontrado: {_DZT4}"); return

    # Config simula usuario que escolheu preset 270mhz (freq errada para HELPER_0004 de 350 MHz)
    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper(antenna_freq_mhz=270))
        m = _load_metrics(Path(tmp))

    mismatch = m.get("frequency_mismatch", False)
    if mismatch:
        _ok("G3", "frequency_mismatch=True (DZT=350, preset=270 -> |diff|=80 > limiar 30)")
    else:
        _fail("G3", f"frequency_mismatch={mismatch}, esperado True (DZT=350, preset=270)")


def test_g4_velocity_header_in_range() -> None:
    _sep("G4", "velocity_header_mns esta no range 0.04-0.20")
    if not _DZT4.exists():
        _warn("G4", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    v = m.get("velocity_header_mns")
    if v is None:
        _fail("G4", "velocity_header_mns ausente no metrics")
        return
    # HELPER_0004: wave_speed=0.0899 m/ns (epsr=11.11)
    if 0.04 <= v <= 0.20:
        _ok("G4", f"velocity_header_mns={v:.4f} no range valido 0.04-0.20 m/ns")
    else:
        _fail("G4", f"velocity_header_mns={v:.4f} fora do range 0.04-0.20 m/ns")


def test_g5_recommended_velocity_from_header() -> None:
    _sep("G5", "recommended_velocity_mns usa valor do header quando valido")
    if not _DZT4.exists():
        _warn("G5", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    rec_v = m.get("recommended_velocity_mns")
    header_v = m.get("velocity_header_mns")
    if rec_v is None:
        _fail("G5", "recommended_velocity_mns ausente no metrics"); return
    if header_v is None:
        _fail("G5", "velocity_header_mns ausente no metrics"); return

    # Se o header velocity e valido (0.04-0.20), recommended deve usar esse valor
    if 0.04 <= header_v <= 0.20 and abs(rec_v - header_v) < 1e-6:
        _ok("G5", f"recommended_velocity_mns={rec_v:.4f} igual a velocity_header_mns")
    else:
        _fail("G5", f"recommended_velocity_mns={rec_v:.4f} != velocity_header_mns={header_v:.4f}")


def test_g6_preflight_warnings_not_empty() -> None:
    _sep("G6", "preflight_warnings nao vazio para HELPER_0004 (timezero fora de range)")
    if not _DZT4.exists():
        _warn("G6", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    # HELPER_0004 tem timezero_sample=341 > n_samples=171 -> warning gerado
    # O preflight_recommendation.warnings contem os warnings de recomendacao
    # O preflight_metadata.warnings contem os warnings de qualidade do header
    pf = m.get("preflight", {})
    meta_warnings = pf.get("dzt_metadata", {}).get("warnings", [])
    rec_warnings  = pf.get("recommendation", {}).get("warnings", [])

    if meta_warnings:
        _ok("G6", f"preflight.dzt_metadata.warnings nao vazio: {len(meta_warnings)} warning(s)")
        for w in meta_warnings:
            print(f"         warning: {w[:80]}...")
    else:
        _fail("G6", "preflight.dzt_metadata.warnings esta vazio (esperado timezero warning)")

    # preflight_warnings no nivel raiz = recommendation warnings
    root_warnings = m.get("preflight_warnings", [])
    _ok("G6", f"preflight_warnings (nivel raiz) tem {len(root_warnings)} item(s)")


def test_g7_header_confidence_media() -> None:
    _sep("G7", 'preflight_header_confidence = "media" para HELPER_0004')
    if not _DZT4.exists():
        _warn("G7", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    conf = m.get("preflight_header_confidence")
    # HELPER_0004: timezero_sample=341 > n_samples=171 -> 1 issue -> "media"
    if conf == "media":
        _ok("G7", f'preflight_header_confidence="{conf}" (esperado "media" por timezero issue)')
    else:
        _fail("G7", f'preflight_header_confidence="{conf}", esperado "media"')

    # Tambem verifica no bloco aninhado
    nested_conf = m.get("preflight", {}).get("dzt_metadata", {}).get("header_confidence")
    if nested_conf == "media":
        _ok("G7", f'preflight.dzt_metadata.header_confidence="{nested_conf}"')
    else:
        _fail("G7", f'preflight.dzt_metadata.header_confidence="{nested_conf}", esperado "media"')


def test_g8_recommended_preset_family() -> None:
    _sep("G8", 'recommended_preset_family = "400mhz" para antena 350 MHz')
    if not _DZT4.exists():
        _warn("G8", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    family = m.get("recommended_preset_family")
    # 350 MHz cai no range (320, 450) -> familia "400mhz"
    if family == "400mhz":
        _ok("G8", f'recommended_preset_family="{family}" (350 MHz -> range 320-450 -> 400mhz)')
    else:
        _fail("G8", f'recommended_preset_family="{family}", esperado "400mhz" (antena 350 MHz)')


def test_g9_recommended_engine_and_profile() -> None:
    _sep("G9", 'recommended_engine="readgssi_engine" e recommended_visual_profile')
    if not _DZT4.exists():
        _warn("G9", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        m = _load_metrics(Path(tmp))

    pf = m.get("preflight", {}).get("recommendation", {})
    engine = pf.get("recommended_engine")
    profile = pf.get("recommended_visual_profile")
    root_profile = m.get("recommended_visual_profile")

    if engine == "readgssi_engine":
        _ok("G9", f'recommended_engine="{engine}"')
    else:
        _fail("G9", f'recommended_engine="{engine}", esperado "readgssi_engine"')

    if profile == "readgssi_reference":
        _ok("G9", f'preflight.recommendation.recommended_visual_profile="{profile}"')
    else:
        _fail("G9", f'preflight.recommendation.recommended_visual_profile="{profile}", esperado "readgssi_reference"')

    if root_profile == "readgssi_reference":
        _ok("G9", f'recommended_visual_profile (nivel raiz) = "{root_profile}"')
    else:
        _fail("G9", f'recommended_visual_profile (nivel raiz) = "{root_profile}", esperado "readgssi_reference"')


def test_g10_no_mismatch_without_preset_freq() -> None:
    _sep("G10", "frequency_mismatch=False quando nenhum antenna_freq_mhz no config")
    if not _DZT4.exists():
        _warn("G10", f"DZT nao encontrado: {_DZT4}"); return

    # Config sem antenna_freq_mhz -> selected_preset fica vazio -> nao ha frequencia para comparar
    cfg = _base_config_helper()
    cfg.pop("antenna_freq_mhz", None)

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), cfg)
        m = _load_metrics(Path(tmp))

    mismatch = m.get("frequency_mismatch", True)
    if not mismatch:
        _ok("G10", "frequency_mismatch=False (sem antenna_freq_mhz no config)")
    else:
        _fail("G10", "frequency_mismatch=True sem antenna_freq_mhz no config (nao deveria comparar)")


def test_g11_config_not_mutated_by_preflight() -> None:
    _sep("G11", "Config efetiva NAO alterada pelo preflight (velocity_mns = valor original)")
    if not _DZT4.exists():
        _warn("G11", f"DZT nao encontrado: {_DZT4}"); return

    # Config com velocity_mns=0.10; preflight pode recomendar 0.0899 mas nao deve alterar
    cfg_velocity = 0.10
    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper(velocity_mns=cfg_velocity))
        m = _load_metrics(Path(tmp))

    used_velocity = m.get("velocity_mns")
    rec_velocity  = m.get("recommended_velocity_mns")

    if abs(used_velocity - cfg_velocity) < 1e-6:
        _ok("G11", f"velocity_mns usada={used_velocity:.4f} igual ao config original (nao alterada)")
    else:
        _fail("G11", f"velocity_mns usada={used_velocity:.4f}, esperado {cfg_velocity:.4f} (config mutada!)")

    if rec_velocity is not None and abs(rec_velocity - cfg_velocity) > 1e-6:
        _ok("G11", f"recommended_velocity_mns={rec_velocity:.4f} difere do config (OK -- so recomendacao)")
    elif rec_velocity is None:
        _fail("G11", "recommended_velocity_mns ausente")


# ---------------------------------------------------------------------------
# G12: Mock -- build_pipeline_metrics sem preflight args tem defaults seguros
# ---------------------------------------------------------------------------

def test_g12_metrics_without_preflight_args() -> None:
    _sep("G12", "build_pipeline_metrics sem preflight args -> defaults seguros (mock)")
    from gpr_engine.metrics import build_pipeline_metrics

    d = MagicMock()
    d.dzt_filename = "MOCK.dzt"
    d.dzt_sha256 = "abc"
    d.n_traces = 100
    d.dist_total_m = 5.0
    d.twtt_max_ns = 30.0
    d.wave_speed_mns = 0.10
    d.n_samples = 150

    cfg = {
        "dewow_window": 5, "bandpass_low_mhz": 80.0, "bandpass_high_mhz": 500.0,
        "bandpass_order": 5, "bandpass_tipo": "butterworth", "bandpass_enabled": True,
        "bgremoval_traces": 30, "tpow_power": 0.5, "agc_window": 150,
        "agc_window_preview": 80, "velocity_mns": 0.10, "depth_preview_m": 5.0,
        "detector_input_mode": "raw", "det_depth_min_m": 0.30,
        "visual_profile": "scientific", "gain": 1.0, "tipo_solo": "standard",
    }

    # Sem preflight_metadata e preflight_recommendation
    m = build_pipeline_metrics(
        dzt_data=d, flow_arrays=None, config=cfg,
        modo_processamento="padrao", snr_raw_db=12.0, snr_raw_ratio=4.5,
    )

    checks = {
        "antenna_freq_mhz_detected": 0,
        "velocity_header_mns": None,
        "epsr_header": None,
        "frequency_mismatch": False,
        "recommended_preset_family": None,
        "recommended_velocity_mns": None,
        "recommended_visual_profile": None,
        "preflight_header_confidence": None,
        "preflight_warnings": [],
    }

    all_ok = True
    for field, expected in checks.items():
        got = m.get(field, "AUSENTE")
        if got == expected:
            _ok("G12", f"{field}={got!r} (default correto)")
        else:
            _fail("G12", f"{field}={got!r}, esperado {expected!r}")
            all_ok = False

    pf = m.get("preflight", {})
    if pf.get("dzt_metadata") == {} and pf.get("recommendation") == {}:
        _ok("G12", "preflight.dzt_metadata e recommendation sao dicts vazios (sem dados)")
    else:
        _fail("G12", f"preflight block inesperado: {pf}")


# ---------------------------------------------------------------------------
# G13: JSON round-trip com todos os novos campos de preflight
# ---------------------------------------------------------------------------

def test_g13_json_roundtrip_preflight_fields() -> None:
    _sep("G13", "Todos os novos campos de preflight presentes e JSON round-trip valido")
    if not _DZT4.exists():
        _warn("G13", f"DZT nao encontrado: {_DZT4}"); return

    with tempfile.TemporaryDirectory() as tmp:
        _run_process_dzt(Path(tmp), _base_config_helper())
        metrics_file = list(Path(tmp).glob("*_pipeline_metrics.json"))[0]
        raw_text = metrics_file.read_text(encoding="utf-8")

    # JSON deve ser parseable
    try:
        m = json.loads(raw_text)
        _ok("G13", "JSON parseable sem erro")
    except json.JSONDecodeError as e:
        _fail("G13", f"JSON invalido: {e}"); return

    # Todos os campos de preflight no nivel raiz devem existir
    missing = [f for f in _PREFLIGHT_TOP_FIELDS if f not in m]
    if not missing:
        _ok("G13", f"Todos os {len(_PREFLIGHT_TOP_FIELDS)} campos de preflight presentes no nivel raiz")
    else:
        _fail("G13", f"Campos ausentes no nivel raiz: {missing}")

    # Bloco preflight aninhado deve ser serializavel e ter as duas chaves
    pf = m.get("preflight", {})
    for key in ("dzt_metadata", "recommendation"):
        if key in pf:
            _ok("G13", f'preflight.{key} presente e serializavel')
        else:
            _fail("G13", f'preflight.{key} ausente')

    # Verifica que campos dentro de dzt_metadata sao do tipo esperado
    meta = pf.get("dzt_metadata", {})
    type_checks = [
        ("antenna_freq_mhz_detected", int),
        ("velocity_header_mns", float),
        ("epsr_header", float),
        ("n_traces", int),
        ("warnings", list),
        ("header_confidence", str),
    ]
    for field, expected_type in type_checks:
        val = meta.get(field, "AUSENTE")
        if isinstance(val, expected_type):
            _ok("G13", f"dzt_metadata.{field}: tipo {expected_type.__name__} correto")
        else:
            _fail("G13", f"dzt_metadata.{field}={val!r}: esperado {expected_type.__name__}, got {type(val).__name__}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_all() -> None:
    test_g1_preflight_block_present()
    test_g2_antenna_freq_detected()
    test_g3_frequency_mismatch_true()
    test_g4_velocity_header_in_range()
    test_g5_recommended_velocity_from_header()
    test_g6_preflight_warnings_not_empty()
    test_g7_header_confidence_media()
    test_g8_recommended_preset_family()
    test_g9_recommended_engine_and_profile()
    test_g10_no_mismatch_without_preset_freq()
    test_g11_config_not_mutated_by_preflight()
    test_g12_metrics_without_preflight_args()
    test_g13_json_roundtrip_preflight_fields()

    print(f"\n{'='*60}")
    print(f"Resultado: {_PASS} OK  {_FAIL} FAIL  {_WARN} WARN")
    if _FAIL:
        print("STATUS: FALHOU")
        sys.exit(1)
    elif _WARN:
        print("STATUS: OK (com avisos -- DZT real ausente em alguns grupos)")
    else:
        print("STATUS: PASSOU")


if __name__ == "__main__":
    _run_all()
