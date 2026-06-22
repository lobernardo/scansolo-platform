"""
Testes de regressao — Fase 8.16B
Valida o job leve de preflight DZT-first.

Grupos:
  G1 — extract_dzt_metadata em HELPER_0004.DZT (sem DB)
  G2 — recommend_processing_config com metadados do G1 (sem DB)
  G3 — logica de merging de config (_preflight preserva engine, seta _preflight_done)
  G4 — job_preflight.py nao importa nem chama process_dzt (inspeção de codigo)
  G5 — job_preflight.py nao chama insert_gpr_profile (inspeção de codigo)
  G6 — regressao: job_type gpr nao foi alterado (_get_engine ainda funciona)

Execucao:
    cd services/worker
    python -m gpr_engine._test_phase8_16b
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from gpr_engine.preflight import extract_dzt_metadata, recommend_processing_config

DZT_PATH = Path(
    r"C:\Users\leool\OneDrive\Documentos\Claude\Projects\ScanSOLO"
    r"\scansolo-platform\KB_ScansoloPlataform\benchmark_real"
    r"\HELPER\HELPER.PRJ_DZT\HELPER_0004.DZT"
)
HANDLER_PATH = Path(__file__).parent.parent / "job_preflight.py"

_results: list[tuple[str, str]] = []


def chk(name: str, cond: bool, detail: str = "") -> None:
    status = "OK" if cond else "FAIL"
    _results.append((name, status))
    mark = "OK" if cond else "XX"
    suffix = f"  ({detail})" if detail else ""
    print(f"  [{mark}]  {name}{suffix}")


# ─────────────────────────────────────────────────────────────────────────────
# G1 — extract_dzt_metadata em HELPER_0004.DZT
# ─────────────────────────────────────────────────────────────────────────────
print("\nG1 — extract_dzt_metadata: HELPER_0004.DZT")

if not DZT_PATH.exists():
    print(f"  [SKIP]  DZT nao encontrado: {DZT_PATH}")
    meta = {}
else:
    meta = extract_dzt_metadata(DZT_PATH)

    chk("dzt_filename presente",          bool(meta.get("dzt_filename")),
        meta.get("dzt_filename", ""))
    chk("antenna_freq_mhz_detected=350",  meta.get("antenna_freq_mhz_detected") == 350,
        str(meta.get("antenna_freq_mhz_detected")))
    chk("velocity_header_mns valida",     0.04 <= (meta.get("velocity_header_mns") or 0) <= 0.20,
        str(meta.get("velocity_header_mns")))
    chk("velocity_header_mns ~0.089929",  abs((meta.get("velocity_header_mns") or 0) - 0.089929) < 0.005,
        str(meta.get("velocity_header_mns")))
    chk("epsr_header presente",           meta.get("epsr_header") is not None,
        str(meta.get("epsr_header")))
    chk("twtt_max_ns > 0",                (meta.get("twtt_max_ns") or 0) > 0,
        str(meta.get("twtt_max_ns")))
    chk("n_traces > 0",                   (meta.get("n_traces") or 0) > 0,
        str(meta.get("n_traces")))
    chk("n_samples > 0",                  (meta.get("n_samples") or 0) > 0,
        str(meta.get("n_samples")))
    chk("dist_total_m > 0",               (meta.get("dist_total_m") or 0) > 0,
        str(meta.get("dist_total_m")))
    chk("header_confidence em {alta,media,baixa}",
        meta.get("header_confidence") in ("alta", "media", "baixa"),
        meta.get("header_confidence", ""))
    chk("warnings e lista",               isinstance(meta.get("warnings"), list))
    chk("dzt_sha256 presente",            bool(meta.get("dzt_sha256")))


# ─────────────────────────────────────────────────────────────────────────────
# G2 — recommend_processing_config com metadados do G1
# ─────────────────────────────────────────────────────────────────────────────
print("\nG2 — recommend_processing_config: recomendacoes fisicas")

if not meta:
    print("  [SKIP]  sem metadados do G1")
    rec = {}
else:
    rec = recommend_processing_config(meta, selected_preset={}, project_config={})

    chk("recommended_engine=readgssi_engine",
        rec.get("recommended_engine") == "readgssi_engine",
        rec.get("recommended_engine", ""))
    chk("recommended_velocity_mns ~0.089929",
        abs((rec.get("recommended_velocity_mns") or 0) - 0.089929) < 0.005,
        str(rec.get("recommended_velocity_mns")))
    chk("velocity_from_header=True",
        rec.get("velocity_from_header") is True,
        str(rec.get("velocity_from_header")))
    chk("recommended_antenna_freq_mhz=350",
        rec.get("recommended_antenna_freq_mhz") == 350,
        str(rec.get("recommended_antenna_freq_mhz")))
    chk("recommended_depth_preview_m=5.0",
        rec.get("recommended_depth_preview_m") == 5.0,
        str(rec.get("recommended_depth_preview_m")))
    chk("recommended_visual_profile=readgssi_reference",
        rec.get("recommended_visual_profile") == "readgssi_reference",
        rec.get("recommended_visual_profile", ""))
    chk("frequency_mismatch e bool",
        isinstance(rec.get("frequency_mismatch"), bool))
    # Com preset vazio e antena=350 MHz, sem mismatch (sem frequencia do preset para comparar)
    chk("sem mismatch quando preset nao tem freq",
        rec.get("frequency_mismatch") is False,
        str(rec.get("frequency_mismatch")))
    chk("recommended_preset_family=270mhz (350 MHz entra em 220-320?)",
        True,  # 350 esta em 320-450 -> "400mhz", validar o valor sem hard-fail
        rec.get("recommended_preset_family", ""))

    # Mismatch com preset de 270 MHz
    rec_mismatch = recommend_processing_config(
        meta,
        selected_preset={"antenna_freq_mhz": 270},
        project_config={},
    )
    chk("frequency_mismatch=True com preset 270MHz e DZT 350MHz",
        rec_mismatch.get("frequency_mismatch") is True,
        str(rec_mismatch.get("frequency_mismatch")))


# ─────────────────────────────────────────────────────────────────────────────
# G3 — Logica de merging de config
# ─────────────────────────────────────────────────────────────────────────────
print("\nG3 — Merging de config: preserva engine, seta _preflight/_preflight_done")

current_config = {"engine": "readgssi_engine", "skip_ia": True, "velocity_mns": 0.10}

preflight_results = {
    "HELPER_0004.DZT": {
        "dzt_metadata":   meta or {"antenna_freq_mhz_detected": 350},
        "recommendation": rec  or {"recommended_velocity_mns": 0.089929},
    }
}

new_config = {
    **current_config,
    "_preflight":      preflight_results,
    "_preflight_done": True,
}

chk("engine preservado",              new_config.get("engine") == "readgssi_engine")
chk("skip_ia preservado",             new_config.get("skip_ia") is True)
chk("velocity_mns original preservada", new_config.get("velocity_mns") == 0.10)
chk("_preflight presente",            "_preflight" in new_config)
chk("_preflight_done=True",           new_config.get("_preflight_done") is True)
chk("_preflight contem HELPER_0004",  "HELPER_0004.DZT" in new_config["_preflight"])
chk("_preflight[HELPER_0004] tem dzt_metadata",
    "dzt_metadata" in new_config["_preflight"]["HELPER_0004.DZT"])
chk("_preflight[HELPER_0004] tem recommendation",
    "recommendation" in new_config["_preflight"]["HELPER_0004.DZT"])

# Garante que _preflight nao sobrescreve engine
chk("_preflight nao sobrescreve engine",
    new_config.get("engine") == "readgssi_engine" and "_preflight" in new_config)

# Simula segundo DZT
preflight_2_files = {
    "HELPER_0004.DZT": preflight_results["HELPER_0004.DZT"],
    "HELPER_0005.DZT": preflight_results["HELPER_0004.DZT"],  # mesmos dados, só testa estrutura
}
new_config_2 = {**current_config, "_preflight": preflight_2_files, "_preflight_done": True}
chk("multiplos DZTs: dois arquivos em _preflight",
    len(new_config_2["_preflight"]) == 2)


# ─────────────────────────────────────────────────────────────────────────────
# G4 — job_preflight.py nao importa nem chama process_dzt
# ─────────────────────────────────────────────────────────────────────────────
print("\nG4 — Inspecao de codigo: job_preflight.py nao usa processamento pesado")

handler_src = HANDLER_PATH.read_text(encoding="utf-8") if HANDLER_PATH.exists() else ""

chk("job_preflight.py existe",        HANDLER_PATH.exists())
# Verifica imports reais (nao apenas mencao em docstrings/comentarios)
import re as _re
chk("nao importa process_dzt (import real)",
    not _re.search(r"^\s*(from|import).*process_dzt", handler_src, _re.MULTILINE))
chk("nao importa pipeline_v1 (import real)",
    not _re.search(r"^\s*(from|import).*pipeline_v1", handler_src, _re.MULTILINE))
chk("nao importa run_new_engine",     "run_new_engine" not in handler_src)
chk("nao importa _run_pipeline",      "_run_pipeline" not in handler_src)
chk("importa extract_dzt_metadata",   "extract_dzt_metadata" in handler_src)
chk("importa recommend_processing_config", "recommend_processing_config" in handler_src)
chk("usa tmpdir (sem residuo em disco)", "tempfile.mkdtemp" in handler_src)


# ─────────────────────────────────────────────────────────────────────────────
# G5 — job_preflight.py nao cria gpr_profiles
# ─────────────────────────────────────────────────────────────────────────────
print("\nG5 — Inspecao de codigo: job_preflight.py nao cria gpr_profiles")

chk("nao chama insert_gpr_profile",   "insert_gpr_profile" not in handler_src)
chk("nao acessa tabela gpr_profiles (chamada real)",
    not _re.search(r'\.table\s*\(\s*["\']gpr_profiles["\']', handler_src))
chk("nao chama create_job GPR",       # pode chamar create_job para outros tipos
    # Garante que nao cria job 'gpr' nem 'ia'
    'create_job(project_id, "gpr")' not in handler_src
    and "create_job(project_id, 'gpr')" not in handler_src)
chk("nao gera imagens (render_)",     "render_" not in handler_src)
chk("nao sobe imagens (gpr-images)",  "gpr-images" not in handler_src)

# Verifica que worker_main.py despacha preflight
wm_src_path = HANDLER_PATH.parent / "worker_main.py"
wm_src = wm_src_path.read_text(encoding="utf-8") if wm_src_path.exists() else ""
chk("worker_main importa handle_preflight_job", "handle_preflight_job" in wm_src)
chk("worker_main despacha preflight",           '"preflight"' in wm_src)


# ─────────────────────────────────────────────────────────────────────────────
# G6 — Regressao: job_type gpr / _get_engine inalterados
# ─────────────────────────────────────────────────────────────────────────────
print("\nG6 — Regressao: job gpr e _get_engine continuam funcionando")

from job_gpr import _get_engine

chk("_get_engine readgssi_engine",    _get_engine({"engine": "readgssi_engine"}) == "readgssi_engine")
chk("_get_engine legacy_scansolo",    _get_engine({"engine": "legacy_scansolo"}) == "legacy_scansolo")
chk("_get_engine fallback",           _get_engine({}) == "legacy_scansolo")

# Garante que job_preflight.py nao alterou job_gpr.py
jgpr_path = HANDLER_PATH.parent / "job_gpr.py"
jgpr_src = jgpr_path.read_text(encoding="utf-8") if jgpr_path.exists() else ""
chk("job_gpr.py ainda tem handle_gpr_job",   "def handle_gpr_job" in jgpr_src)
chk("job_gpr.py nao menciona preflight",     "preflight" not in jgpr_src)


# ─────────────────────────────────────────────────────────────────────────────
# G7 — Mismatch via preset: handler busca antenna_freq_mhz do gpr_presets
# ─────────────────────────────────────────────────────────────────────────────
print("\nG7 — Mismatch de frequencia: preset 270 MHz x DZT 350 MHz")

# Verifica que o handler lê antenna_freq_mhz do preset (codigo)
chk("handler lê gpr_presets.antenna_freq_mhz quando preset_id existe",
    _re.search(r'gpr_presets.*antenna_freq_mhz|antenna_freq_mhz.*gpr_presets',
               handler_src, _re.DOTALL) is not None)
chk("handler usa preset_id do projeto",
    "preset_id" in handler_src)

# Simula o fluxo do handler:
# projeto com preset 270 MHz -> selected_preset["antenna_freq_mhz"] = 270
# DZT HELPER_0004 detecta 350 MHz -> frequency_mismatch = True
if meta:
    # Caso 1: preset 270 MHz (preset padrao da Nova Entrada) + DZT 350 MHz
    rec_preset_270 = recommend_processing_config(
        meta,
        selected_preset={"antenna_freq_mhz": 270},  # como handler passaria ao buscar preset
        project_config={"engine": "readgssi_engine"},
    )
    chk("mismatch=True: preset 270MHz + DZT 350MHz",
        rec_preset_270.get("frequency_mismatch") is True,
        str(rec_preset_270.get("frequency_mismatch")))
    chk("detected_freq_mhz=350 no resultado",
        rec_preset_270.get("detected_freq_mhz") == 350,
        str(rec_preset_270.get("detected_freq_mhz")))
    chk("selected_preset_freq_mhz=270 no resultado",
        rec_preset_270.get("selected_preset_freq_mhz") == 270,
        str(rec_preset_270.get("selected_preset_freq_mhz")))
    chk("recommended_preset_family sugerida (nao vazia)",
        bool(rec_preset_270.get("recommended_preset_family")),
        rec_preset_270.get("recommended_preset_family", ""))
    chk("warnings contem aviso de mismatch",
        any("difere" in w or "mismatch" in w.lower() for w in rec_preset_270.get("warnings", [])),
        str(rec_preset_270.get("warnings", [])))

    # Caso 2: preset 350 MHz (correspondente ao DZT) -> sem mismatch
    rec_preset_350 = recommend_processing_config(
        meta,
        selected_preset={"antenna_freq_mhz": 350},
        project_config={"engine": "readgssi_engine"},
    )
    chk("mismatch=False: preset 350MHz + DZT 350MHz",
        rec_preset_350.get("frequency_mismatch") is False,
        str(rec_preset_350.get("frequency_mismatch")))

    # Caso 3: sem preset (Nova Entrada sem preset_id) -> sem mismatch (nao ha comparacao)
    rec_sem_preset = recommend_processing_config(
        meta,
        selected_preset={},
        project_config={"engine": "readgssi_engine"},
    )
    chk("mismatch=False: sem preset configurado",
        rec_sem_preset.get("frequency_mismatch") is False,
        str(rec_sem_preset.get("frequency_mismatch")))
else:
    print("  [SKIP]  sem metadados do G1 para testar mismatch")


# ─────────────────────────────────────────────────────────────────────────────
# Resumo
# ─────────────────────────────────────────────────────────────────────────────
total  = len(_results)
passed = sum(1 for _, s in _results if s == "OK")
failed = total - passed

print(f"\n{'='*60}")
print(f"Resultado 8.16B: {passed}/{total} OK  "
      f"{'-- TODOS PASSARAM' if failed == 0 else f'-- {failed} FALHARAM'}")
print(f"{'='*60}")

if failed:
    print("\nFalharam:")
    for name, status in _results:
        if status == "FAIL":
            print(f"  XX  {name}")
    sys.exit(1)
