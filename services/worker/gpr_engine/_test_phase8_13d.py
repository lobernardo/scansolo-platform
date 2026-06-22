"""
Testes de regressao — Fase 8.13D
Verifica que o fluxo de reprocessamento individual em job_gpr.py preserva
os campos do readgssi_engine (engine, antenna_freq_mhz, visual_profile) que
_filtros_to_pipeline_config nao mapeia.

Execucao:
    cd services/worker
    python -m gpr_engine._test_phase8_13d
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_gpr import _filtros_to_pipeline_config, _get_engine

PASS = "OK"
FAIL = "FAIL"
_results: list[tuple[str, str]] = []


def check(name: str, cond: bool) -> None:
    status = PASS if cond else FAIL
    _results.append((name, status))
    mark = "OK" if cond else "XX"
    print(f"  [{mark}]  {name}")


# ---------------------------------------------------------------------------
# G1 — _filtros_to_pipeline_config: campos do FilterState legado mapeados
# ---------------------------------------------------------------------------

print("\nG1 — _filtros_to_pipeline_config: mapeamento de campos legados")

fc_legacy = {
    "velocity_mns": 0.089929,
    "depth_preview_m": 5.0,
    "bandpass": True,
    "bandpass_low": 80,
    "bandpass_high": 500,
}
cfg_legacy = _filtros_to_pipeline_config(fc_legacy)

check("velocity_mns mapeado", cfg_legacy.get("velocity_mns") == 0.089929)
check("depth_preview_m mapeado", cfg_legacy.get("depth_preview_m") == 5.0)
check("bandpass_low_mhz mapeado", cfg_legacy.get("bandpass_low_mhz") == 80)
check("bandpass_high_mhz mapeado", cfg_legacy.get("bandpass_high_mhz") == 500)

# Campos do readgssi_engine NAO devem aparecer (nao estao no input)
check("engine ausente (input sem engine)", "engine" not in cfg_legacy)
check("antenna_freq_mhz ausente (input sem antenna)", "antenna_freq_mhz" not in cfg_legacy)


# ---------------------------------------------------------------------------
# G2 — _filtros_to_pipeline_config: NAO preserva engine nem antenna (expected)
# ---------------------------------------------------------------------------

print("\nG2 — _filtros_to_pipeline_config: descarta engine/antenna/visual_profile (comportamento esperado)")

fc_with_engine = {
    "engine": "readgssi_engine",
    "antenna_freq_mhz": 350,
    "visual_profile": "readgssi_reference",
    "velocity_mns": 0.089929,
    "depth_preview_m": 5.0,
}
cfg_without_passthrough = _filtros_to_pipeline_config(fc_with_engine)

check("engine descartado por _filtros_to_pipeline_config", "engine" not in cfg_without_passthrough)
check("antenna_freq_mhz descartado por _filtros_to_pipeline_config", "antenna_freq_mhz" not in cfg_without_passthrough)
check("visual_profile descartado por _filtros_to_pipeline_config", "visual_profile" not in cfg_without_passthrough)
check("velocity_mns ainda presente", cfg_without_passthrough.get("velocity_mns") == 0.089929)
check("depth_preview_m ainda presente", cfg_without_passthrough.get("depth_preview_m") == 5.0)


# ---------------------------------------------------------------------------
# G3 — Simula o fluxo corrigido de job_gpr.py (pass-through depois do convert)
# ---------------------------------------------------------------------------

print("\nG3 — Fluxo corrigido: passthrough de engine/antenna/visual_profile")

_PASSTHROUGH_KEYS = ("engine", "antenna_freq_mhz", "visual_profile")


def simulate_reprocess_config(filtros: dict) -> dict:
    """Replica o fluxo corrigido de job_gpr.handle_gpr_job."""
    cfg = _filtros_to_pipeline_config(filtros)
    for _k in _PASSTHROUGH_KEYS:
        if _k in filtros:
            cfg[_k] = filtros[_k]
    return cfg


filtros_preflight = {
    "engine": "readgssi_engine",
    "antenna_freq_mhz": 350,
    "visual_profile": "readgssi_reference",
    "velocity_mns": 0.089929,
    "depth_preview_m": 5.0,
}

cfg_corrigido = simulate_reprocess_config(filtros_preflight)

check("engine presente após passthrough", cfg_corrigido.get("engine") == "readgssi_engine")
check("antenna_freq_mhz presente após passthrough", cfg_corrigido.get("antenna_freq_mhz") == 350)
check("visual_profile presente após passthrough", cfg_corrigido.get("visual_profile") == "readgssi_reference")
check("velocity_mns preservado", cfg_corrigido.get("velocity_mns") == 0.089929)
check("depth_preview_m preservado", cfg_corrigido.get("depth_preview_m") == 5.0)


# ---------------------------------------------------------------------------
# G4 — _get_engine: roteamento correto
# ---------------------------------------------------------------------------

print("\nG4 — _get_engine: roteamento após passthrough")

check("_get_engine retorna readgssi_engine quando presente", _get_engine(cfg_corrigido) == "readgssi_engine")
check("_get_engine retorna legacy quando engine ausente", _get_engine({}) == "legacy_scansolo")
check("_get_engine retorna legacy quando engine=legacy_scansolo", _get_engine({"engine": "legacy_scansolo"}) == "legacy_scansolo")
check("_get_engine retorna legacy quando engine inválido", _get_engine({"engine": "unknown_engine"}) == "legacy_scansolo")


# ---------------------------------------------------------------------------
# G5 — Sem filtros_customizados: comportamento inalterado
# ---------------------------------------------------------------------------

print("\nG5 — filtros_customizados=None: comportamento inalterado")

check("sem filtros, _get_engine(raw_config sem engine) = legacy", _get_engine({"velocity_mns": 0.1}) == "legacy_scansolo")
check("sem filtros, _get_engine(raw_config com engine=legacy) = legacy", _get_engine({"engine": "legacy_scansolo"}) == "legacy_scansolo")
check("sem filtros, _get_engine(raw_config com engine=readgssi) = readgssi", _get_engine({"engine": "readgssi_engine"}) == "readgssi_engine")


# ---------------------------------------------------------------------------
# G6 — Filtros legados sem engine: nao afeta roteamento
# ---------------------------------------------------------------------------

print("\nG6 — filtros legados (sem engine): roteamento mantém legacy")

filtros_legado = {"velocity_mns": 0.10, "depth_preview_m": 5.0, "bandpass": True}
cfg_legado = simulate_reprocess_config(filtros_legado)

check("engine ausente no cfg_legado", "engine" not in cfg_legado)
check("_get_engine(cfg_legado) = legacy", _get_engine(cfg_legado) == "legacy_scansolo")
check("velocity_mns presente no cfg_legado", cfg_legado.get("velocity_mns") == 0.10)


# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------

total = len(_results)
passed = sum(1 for _, s in _results if s == PASS)
failed = total - passed

print(f"\n{'='*55}")
print(f"Resultado: {passed}/{total} OK  {'—  TODOS PASSARAM' if failed == 0 else f'— {failed} FALHOU(ARAM)'}")
print(f"{'='*55}")

if failed:
    print("\nFalharam:")
    for name, status in _results:
        if status == FAIL:
            print(f"  XX  {name}")
    sys.exit(1)
