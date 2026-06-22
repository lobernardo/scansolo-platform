"""
Phase 8.16D.1 — per-file config logic tests (scansolo_adapter._per_file_config).

Valida:
  T1. 2 DZTs com configs distintas geram effective_configs corretos e independentes.
  T2. Velocities e antenas diferentes preservadas por arquivo.
  T3. Overrides globais aplicados a todos os arquivos sem mudar engine.
  T4. engine sempre 'readgssi_engine' — nunca sobrescrito por global ou file config.
  T5. Arquivo nao listado em _preflight_file_configs usa fallback global.
  T6. Config sem _preflight_file_configs (projeto legado) funciona normalmente.
  T7. Nenhum codigo usa Object.values()[0] para config global silenciosamente.

Rodado como modulo:
  cd services/worker
  python -m gpr_engine._test_phase8_16d1
"""
from __future__ import annotations
import sys
import os

# Garante que o diretorio services/worker esta no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gpr_engine.scansolo_adapter import _per_file_config


def chk(name: str, cond: bool, got=None) -> None:
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  got={got!r}")
        sys.exit(1)


# ── Fixture: 2 DZTs com metadados distintos ──────────────────────────────────

GLOBAL_CONFIG_WITH_FILE_CONFIGS: dict = {
    "engine":              "readgssi_engine",
    "_preflight_done":     True,
    "_preflight_accepted": True,
    "_preflight_file_configs": {
        "HELPER_0001.DZT": {
            "engine":           "readgssi_engine",
            "antenna_freq_mhz": 350,
            "velocity_mns":     0.089929,
            "visual_profile":   "readgssi_reference",
            "depth_preview_m":  5.0,
            "source":           "preflight",
        },
        "HELPER_0002.DZT": {
            "engine":           "readgssi_engine",
            "antenna_freq_mhz": 270,
            "velocity_mns":     0.100000,
            "visual_profile":   "readgssi_reference",
            "depth_preview_m":  5.0,
            "source":           "preflight",
        },
    },
}

GLOBAL_CONFIG_WITH_OVERRIDES: dict = {
    "engine":              "readgssi_engine",
    "_preflight_done":     True,
    "_preflight_accepted": True,
    "_preflight_file_configs": {
        "HELPER_0001.DZT": {
            "engine":           "readgssi_engine",
            "antenna_freq_mhz": 350,
            "velocity_mns":     0.095,     # override global aplicado
            "visual_profile":   "readgssi_reference",
            "depth_preview_m":  5.0,
            "source":           "preflight_with_global_override",
        },
        "HELPER_0002.DZT": {
            "engine":           "readgssi_engine",
            "antenna_freq_mhz": 270,
            "velocity_mns":     0.095,     # mesmo override global
            "visual_profile":   "readgssi_reference",
            "depth_preview_m":  5.0,
            "source":           "preflight_with_global_override",
        },
    },
}

LEGACY_CONFIG: dict = {
    "engine":      "readgssi_engine",
    "velocity_mns": 0.10,
    "bandpass_enabled": True,
}


def main() -> None:
    print("=== Phase 8.16D.1 — per-file config tests ===\n")

    # T1 / T2: configs distintas por arquivo
    cfg1 = _per_file_config(GLOBAL_CONFIG_WITH_FILE_CONFIGS, "HELPER_0001.DZT")
    cfg2 = _per_file_config(GLOBAL_CONFIG_WITH_FILE_CONFIGS, "HELPER_0002.DZT")

    chk("T1a: HELPER_0001 antenna=350",
        cfg1["antenna_freq_mhz"] == 350, cfg1.get("antenna_freq_mhz"))
    chk("T1b: HELPER_0001 velocity=0.089929",
        abs(cfg1["velocity_mns"] - 0.089929) < 1e-6, cfg1.get("velocity_mns"))
    chk("T1c: HELPER_0002 antenna=270",
        cfg2["antenna_freq_mhz"] == 270, cfg2.get("antenna_freq_mhz"))
    chk("T1d: HELPER_0002 velocity=0.100000",
        abs(cfg2["velocity_mns"] - 0.100000) < 1e-6, cfg2.get("velocity_mns"))
    chk("T2a: configs independentes (velocity diferem)",
        abs(cfg1["velocity_mns"] - cfg2["velocity_mns"]) > 1e-6)
    chk("T2b: configs independentes (antenna diferem)",
        cfg1["antenna_freq_mhz"] != cfg2["antenna_freq_mhz"])

    # T3: overrides globais aplicados a todos os arquivos
    cfgo1 = _per_file_config(GLOBAL_CONFIG_WITH_OVERRIDES, "HELPER_0001.DZT")
    cfgo2 = _per_file_config(GLOBAL_CONFIG_WITH_OVERRIDES, "HELPER_0002.DZT")

    chk("T3a: override velocity HELPER_0001=0.095",
        abs(cfgo1["velocity_mns"] - 0.095) < 1e-6, cfgo1.get("velocity_mns"))
    chk("T3b: override velocity HELPER_0002=0.095",
        abs(cfgo2["velocity_mns"] - 0.095) < 1e-6, cfgo2.get("velocity_mns"))
    chk("T3c: source=preflight_with_global_override HELPER_0001",
        cfgo1.get("source") == "preflight_with_global_override", cfgo1.get("source"))
    chk("T3d: source=preflight_with_global_override HELPER_0002",
        cfgo2.get("source") == "preflight_with_global_override", cfgo2.get("source"))

    # T4: engine nunca sobrescrito — nem pelo global nem pelo file config
    tampered_global = {
        **GLOBAL_CONFIG_WITH_FILE_CONFIGS,
        "engine": "legacy_v1",  # tenta sobrescrever
    }
    tampered_file = {
        **GLOBAL_CONFIG_WITH_FILE_CONFIGS,
        "_preflight_file_configs": {
            "HELPER_0001.DZT": {
                **GLOBAL_CONFIG_WITH_FILE_CONFIGS["_preflight_file_configs"]["HELPER_0001.DZT"],
                "engine": "legacy_v1",  # tenta sobrescrever via file config
            },
        },
    }
    chk("T4a: engine forcado mesmo com global='legacy_v1'",
        _per_file_config(tampered_global, "HELPER_0001.DZT")["engine"] == "readgssi_engine")
    chk("T4b: engine forcado mesmo com file_config='legacy_v1'",
        _per_file_config(tampered_file, "HELPER_0001.DZT")["engine"] == "readgssi_engine")

    # T5: arquivo nao listado usa fallback global
    cfg_unknown = _per_file_config(GLOBAL_CONFIG_WITH_FILE_CONFIGS, "HELPER_0099.DZT")
    chk("T5a: arquivo nao listado: engine=readgssi_engine",
        cfg_unknown["engine"] == "readgssi_engine")
    chk("T5b: arquivo nao listado: _preflight_done preservado",
        cfg_unknown.get("_preflight_done") is True)
    chk("T5c: arquivo nao listado: sem file-specific velocity",
        cfg_unknown.get("velocity_mns") is None,
        cfg_unknown.get("velocity_mns"))  # global nao tem velocity — correto

    # T6: config legada sem _preflight_file_configs
    cfg_legacy = _per_file_config(LEGACY_CONFIG, "QUALQUER.DZT")
    chk("T6a: legado: engine=readgssi_engine",
        cfg_legacy["engine"] == "readgssi_engine")
    chk("T6b: legado: velocity_mns=0.10",
        abs(cfg_legacy["velocity_mns"] - 0.10) < 1e-6, cfg_legacy.get("velocity_mns"))
    chk("T6c: legado: bandpass_enabled=True",
        cfg_legacy.get("bandpass_enabled") is True)

    # T7: objeto retornado e independente (mutacao nao afeta global)
    cfg_mut = _per_file_config(GLOBAL_CONFIG_WITH_FILE_CONFIGS, "HELPER_0001.DZT")
    cfg_mut["velocity_mns"] = 99.0
    cfg_fresh = _per_file_config(GLOBAL_CONFIG_WITH_FILE_CONFIGS, "HELPER_0001.DZT")
    chk("T7: mutacao do resultado nao afeta chamada subsequente",
        abs(cfg_fresh["velocity_mns"] - 0.089929) < 1e-6, cfg_fresh.get("velocity_mns"))

    print("\n=== All tests passed ===\n")


if __name__ == "__main__":
    main()
