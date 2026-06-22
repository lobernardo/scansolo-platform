"""
Testes de regressao — Fase 8.15
Verifica que _get_engine resolve readgssi_engine para todos os fluxos da UI
e legacy_scansolo somente para fallback tecnico explicito.

Execucao:
    cd services/worker
    python -m gpr_engine._test_phase8_15
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from job_gpr import _get_engine

PASS = "OK"
FAIL = "FAIL"
_results: list[tuple[str, str]] = []


def check(name: str, cond: bool) -> None:
    status = PASS if cond else FAIL
    _results.append((name, status))
    mark = "OK" if cond else "XX"
    print(f"  [{mark}]  {name}")


# ---------------------------------------------------------------------------
# G1 — Nova Entrada / startProcessingDirect / startProcessingWithConfig
#      processing_config sempre tem engine: readgssi_engine vindo da UI
# ---------------------------------------------------------------------------

print("\nG1 — Processamento novo com engine do processing_config")

check(
    "processing_config com engine=readgssi_engine ->readgssi_engine",
    _get_engine({"engine": "readgssi_engine"}) == "readgssi_engine",
)
check(
    "processing_config com engine + outros campos ->readgssi_engine",
    _get_engine({"engine": "readgssi_engine", "velocity_mns": 0.10, "skip_ia": True})
    == "readgssi_engine",
)
check(
    "processing_config com engine + preset params ->readgssi_engine",
    _get_engine({
        "engine": "readgssi_engine",
        "dewow_window": 5,
        "bandpass_low_mhz": 80,
        "velocity_mns": 0.10,
    }) == "readgssi_engine",
)


# ---------------------------------------------------------------------------
# G2 — Reprocessamento individual com filtros da UI (filtersWithEngine)
# ---------------------------------------------------------------------------

print("\nG2 — Reprocessamento individual com engine injetado pela UI")

filtros_reprocess_ui = {
    "engine": "readgssi_engine",
    "velocity_mns": 0.089929,
    "depth_preview_m": 5.0,
    "bandpass": True,
    "bandpass_low": 80,
    "bandpass_high": 500,
}

check(
    "filtros_customizados com engine=readgssi_engine ->readgssi_engine",
    _get_engine(filtros_reprocess_ui) == "readgssi_engine",
)

# Simula o passthrough do job_gpr.py (8.13D): _filtros_to_pipeline_config descarta engine,
# mas o passthrough loop readiciona antes de _get_engine ser chamado
from job_gpr import _filtros_to_pipeline_config

cfg = _filtros_to_pipeline_config(filtros_reprocess_ui)
# engine foi descartado pelo _filtros_to_pipeline_config
for _k in ("engine", "antenna_freq_mhz", "visual_profile"):
    if _k in filtros_reprocess_ui:
        cfg[_k] = filtros_reprocess_ui[_k]
# agora engine esta de volta

check(
    "apos passthrough 8.13D: engine presente no config",
    cfg.get("engine") == "readgssi_engine",
)
check(
    "_get_engine apos passthrough ->readgssi_engine",
    _get_engine(cfg) == "readgssi_engine",
)


# ---------------------------------------------------------------------------
# G3 — Preflight override (handleReprocessWithOverrides) — nao deve regredir
# ---------------------------------------------------------------------------

print("\nG3 — Preflight override (engine ja presente nos overrides)")

overrides = {
    "engine": "readgssi_engine",
    "antenna_freq_mhz": 350,
    "velocity_mns": 0.089929,
    "visual_profile": "readgssi_reference",
    "depth_preview_m": 5.0,
}

check(
    "overrides de preflight ->readgssi_engine",
    _get_engine(overrides) == "readgssi_engine",
)

# Simula filtersWithEngine quando engine ja vem nos overrides (nao deve ser sobrescrito)
filters_with_engine_from_overrides = {
    **overrides,
    "engine": overrides.get("engine") or "readgssi_engine",
}
check(
    "filtersWithEngine com engine ja definido ->preserva readgssi_engine",
    filters_with_engine_from_overrides.get("engine") == "readgssi_engine",
)


# ---------------------------------------------------------------------------
# G4 — Fallback tecnico (legacy_scansolo permanece disponivel)
# ---------------------------------------------------------------------------

print("\nG4 — Fallback tecnico: legacy_scansolo quando explicitamente passado")

check(
    "engine=legacy_scansolo explicito ->legacy_scansolo",
    _get_engine({"engine": "legacy_scansolo"}) == "legacy_scansolo",
)
check(
    "engine ausente (job antigo sem engine) ->legacy_scansolo",
    _get_engine({}) == "legacy_scansolo",
)
check(
    "engine invalido ->fallback legacy_scansolo",
    _get_engine({"engine": "motor_desconhecido"}) == "legacy_scansolo",
)
check(
    "processing_config None simulado ->legacy_scansolo",
    _get_engine({}) == "legacy_scansolo",
)


# ---------------------------------------------------------------------------
# G5 — Invariantes: engine nao pode ser None nem vazio
# ---------------------------------------------------------------------------

print("\nG5 — Invariantes de engine")

check(
    "engine=None tratado como ausente ->legacy_scansolo",
    _get_engine({"engine": None}) == "legacy_scansolo",
)
# Nota: _get_engine faz str(processing_config.get("engine", "legacy_scansolo"))
# str(None) = "None", que nao esta em _VALID_ENGINES ->fallback legacy_scansolo
check(
    "engine='' (vazio) ->legacy_scansolo",
    _get_engine({"engine": ""}) == "legacy_scansolo",
)


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
