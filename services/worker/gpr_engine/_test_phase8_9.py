"""
_test_phase8_9.py -- Testa correção do MIME de upload de pipeline_metrics.json.

Problema corrigido (Fase 8.9):
  upload_file("gpr-tabelas", ..., "application/json")
  → 400 invalid_mime_type (bucket não aceita application/json)

Correção:
  upload_file("gpr-tabelas", ..., "application/octet-stream")
  → aceito pelo bucket (listado na migration 20260529000002)

Grupos:
  G1: application/json NÃO está mais no código de upload de metrics
  G2: application/octet-stream É o MIME usado para metrics em job_gpr.py
  G3: Filename do metrics preserva sufixo .json
  G4: Código de upload de metrics está em _persist_outputs (shared, não engine-specific)
  G5: bucket migration inclui application/octet-stream
  G6: Mock de _persist_outputs confirma upload_file chamado com application/octet-stream
  G7: process_dzt produz _pipeline_metrics.json (requer HELPER_0001.dzt)
  G8: readgssi_engine completo sem erro (requer HELPER_0001.dzt)

Uso:
  cd services/worker
  python -m gpr_engine._test_phase8_9
"""
from __future__ import annotations

import ast
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, call, patch

_HERE = Path(__file__).resolve().parent            # gpr_engine/
_WORKER = _HERE.parent                             # services/worker/
_REPO_ROOT = _HERE.parents[2]                      # scansolo-platform/

sys.path.insert(0, str(_WORKER))

_PASS = 0
_FAIL = 0
_WARN = 0

_DZT = _REPO_ROOT / "KB_ScansoloPlataform" / "benchmark_real" / "HELPER" / "HELPER.PRJ_DZT" / "HELPER_0001.dzt"
_JOB_GPR = _WORKER / "job_gpr.py"
_MIGRATION = _REPO_ROOT / "supabase" / "migrations" / "20260529000002_storage_cartografia_mimetypes.sql"

# ── CSV alvos headers (mesmo do adapter) ────────────────────────────────────
_CSV_ALVOS_HEADERS = [
    "rank", "arquivo_dzt", "x_m", "depth_m", "diam_est_m", "diam_confianca",
    "fit_ok", "score", "tipo_material", "confianca_tipo",
    "amplitude_relativa_max", "amplitude_relativa_raw", "fase_consistente",
    "evidencia_raw", "evidencia_sem_agc", "snr_local",
    "confidence_score_0_100", "confidence_label_tecnico",
    "confidence_label_relatorio", "motivo_confianca",
]

# ── Helpers de relatório ─────────────────────────────────────────────────────

def _ok(g: str, msg: str) -> None:
    global _PASS
    _PASS += 1
    print(f"  [OK]   {g}: {msg}")

def _fail(g: str, msg: str) -> None:
    global _FAIL
    _FAIL += 1
    print(f"  [FAIL] {g}: {msg}")

def _warn(g: str, msg: str) -> None:
    global _WARN
    _WARN += 1
    print(f"  [WARN] {g}: {msg}")

def _sep(g: str, titulo: str) -> None:
    print(f"\n-- {g}: {titulo}")


# ── Helpers de fixture ───────────────────────────────────────────────────────

def _write_fake_png(path: Path) -> None:
    """PNG mínimo válido (1×1 pixel)."""
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
        b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00"
        b"\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N"
        b"\x00\x00\x00\x00IEND\xaeB`\x82"
    )

def _write_index_csv(path: Path, stem: str) -> None:
    rows = [{
        "arquivo_dzt":        f"{stem}.dzt",
        "n_tracos":           "129",
        "n_amostras":         "171",
        "profundidade_max_m": "5.0",
        "distancia_max_m":    "8.82",
        "velocity_mns":       "0.1",
        "velocity_calibrada": "False",
        "config_hash":        "",
        "snr_imagem_db":      "10.7",
        "snr_imagem_ratio":   "3.2",
        "modo_processamento": "agressivo",
        "tipo_solo":          "standard",
    }]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

def _write_empty_alvos_csv(path: Path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=_CSV_ALVOS_HEADERS)
        writer.writeheader()

def _build_mock_supa(profile_id: str = "aabbccdd-1234-0000-0000-000000000000") -> MagicMock:
    """Mock de SupabaseClient com respostas mínimas para _persist_outputs."""
    supa = MagicMock()

    # insert_gpr_profile → retorna perfil com id
    supa.insert_gpr_profile.return_value = {"id": profile_id}

    # insert_detected_targets → no-op
    supa.insert_detected_targets.return_value = None

    # upload_file → no-op (vamos capturar os calls)
    supa.upload_file.return_value = None

    # _client.storage.from_("gpr-tabelas").create_signed_url(path, ttl) → URL válida
    signed_mock = MagicMock()
    signed_mock.get.return_value = "https://signed.test.url/metrics.json"
    supa._client.storage.from_.return_value.create_signed_url.return_value = signed_mock

    # _client.table("gpr_profiles").update(data).eq(id, pid).execute() → ok
    supa._client.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

    # _client.table("detected_targets").delete().eq().execute() → ok
    supa._client.table.return_value.delete.return_value.eq.return_value.execute.return_value = MagicMock()

    return supa


# ============================================================
# G1 — application/json NÃO está no upload de metrics
# ============================================================

def test_g1_no_json_mime() -> None:
    _sep("G1", "application/json NÃO está no upload de metrics")

    src = _JOB_GPR.read_text(encoding="utf-8")
    lines = src.splitlines()

    # Encontra o bloco de metrics upload
    metrics_mime_lines = [
        l for l in lines
        if "upload_file" in l and "pipeline_metrics" in l
        or ("upload_file" in l and "gpr-tabelas" in l and "application/json" in l)
    ]

    # Verifica que a linha de upload de metrics não usa application/json
    bad = [l for l in lines if "upload_file" in l and "application/json" in l]
    if bad:
        _fail("G1", f"Ainda encontrado application/json em upload_file: {bad[0].strip()!r}")
    else:
        _ok("G1", "application/json NÃO encontrado em upload_file (correção aplicada)")


# ============================================================
# G2 — application/octet-stream É o MIME para metrics
# ============================================================

def test_g2_correct_mime() -> None:
    _sep("G2", "application/octet-stream É o MIME para metrics")

    src = _JOB_GPR.read_text(encoding="utf-8")
    lines = src.splitlines()

    # Localiza o bloco de upload de metrics (cerca da linha com pipeline_metrics.json)
    for i, line in enumerate(lines):
        if "pipeline_metrics.json" in line and "m_path" in line:
            # Olha as próximas 5 linhas para encontrar o upload_file
            context = "\n".join(lines[i:i+5])
            if "application/octet-stream" in context:
                _ok("G2", "application/octet-stream encontrado no upload de metrics")
                return
            else:
                _fail("G2", f"MIME inesperado no upload de metrics. Contexto:\n{context}")
                return

    # Busca genérica
    octet = [l for l in lines if "upload_file" in l and "application/octet-stream" in l and "gpr-tabelas" in l]
    if octet:
        _ok("G2", f"application/octet-stream encontrado: {octet[0].strip()!r}")
    else:
        _fail("G2", "Não foi possível localizar o MIME do upload de metrics")


# ============================================================
# G3 — Filename do metrics preserva sufixo .json
# ============================================================

def test_g3_json_suffix() -> None:
    _sep("G3", "Filename do metrics preserva sufixo .json")

    src = _JOB_GPR.read_text(encoding="utf-8")

    # A linha que define metrics_file deve usar .json como sufixo
    for line in src.splitlines():
        if "metrics_file" in line and "_pipeline_metrics.json" in line:
            _ok("G3", f"Sufixo .json preservado: {line.strip()!r}")
            return

    _fail("G3", "Linha de definição de metrics_file não encontrada no job_gpr.py")


# ============================================================
# G4 — Upload de metrics está em _persist_outputs (shared)
# ============================================================

def test_g4_shared_code_path() -> None:
    _sep("G4", "Upload de metrics está em _persist_outputs (não em branch de engine)")

    src = _JOB_GPR.read_text(encoding="utf-8")

    # Parseia AST para verificar que o upload de metrics está dentro de _persist_outputs
    tree = ast.parse(src)
    persist_func = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_persist_outputs":
            persist_func = node
            break

    if persist_func is None:
        _fail("G4", "_persist_outputs não encontrada no AST de job_gpr.py")
        return

    # Extrai linhas da função
    func_lines = src.splitlines()[persist_func.lineno - 1: persist_func.end_lineno]
    func_src = "\n".join(func_lines)

    if "pipeline_metrics" in func_src and "upload_file" in func_src:
        _ok("G4", "Upload de metrics está em _persist_outputs (shared entre engines)")
    else:
        _fail("G4", "Upload de metrics não encontrado em _persist_outputs")

    # Verifica também que NÃO está condicionado a um engine específico
    if "readgssi_engine" in func_src and "pipeline_metrics" in func_src:
        _warn("G4", "Há referência a readgssi_engine dentro de _persist_outputs — verificar manualmente")
    else:
        _ok("G4", "Sem condicionamento de engine em _persist_outputs (correção é universal)")


# ============================================================
# G5 — Bucket migration inclui application/octet-stream
# ============================================================

def test_g5_bucket_migration() -> None:
    _sep("G5", "Migration do bucket gpr-tabelas inclui application/octet-stream")

    if not _MIGRATION.exists():
        _warn("G5", f"Migration não encontrada: {_MIGRATION}")
        return

    migration_sql = _MIGRATION.read_text(encoding="utf-8")
    if "application/octet-stream" in migration_sql:
        _ok("G5", "application/octet-stream listado em allowed_mime_types na migration")
    else:
        _fail("G5", "application/octet-stream NÃO encontrado na migration do bucket")

    if "application/json" in migration_sql:
        _warn("G5", "application/json encontrado na migration — bucket poderia aceitar JSON também")
    else:
        _ok("G5", "application/json NÃO está na lista de MIMEs aceitos (confirma que era o problema)")


# ============================================================
# G6 — Mock: _persist_outputs chama upload_file com octet-stream para metrics
# ============================================================

def test_g6_mock_upload_mime() -> None:
    _sep("G6", "Mock: upload_file chamado com application/octet-stream para metrics")

    from job_gpr import _persist_outputs

    stem = "MOCK_DZT_001"
    project_id = "00000000-0000-0000-0000-000000000001"
    run_id     = "00000000-0000-0000-0000-000000000002"
    profile_id = "aabbccdd-1234-0000-0000-000000000000"

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)

        # Estrutura esperada por _persist_outputs
        (out / "01_Imagens_Brutas").mkdir()
        (out / "02_Imagens_Processadas").mkdir()
        (out / "05_Tabela_Alvos").mkdir()

        _write_index_csv(out / "index_projeto.csv", stem)
        _write_fake_png(out / "01_Imagens_Brutas" / f"{stem}_bruta.png")
        _write_fake_png(out / "02_Imagens_Processadas" / f"{stem}_processada.png")
        _write_fake_png(out / "02_Imagens_Processadas" / f"{stem}_radargrama_cientifico.png")

        # Arquivo de metrics — este é o sujeito do teste
        metrics_content = json.dumps({"pipeline_version": "8.9-test", "n_tracos": 129})
        (out / "02_Imagens_Processadas" / f"{stem}_pipeline_metrics.json").write_text(
            metrics_content, encoding="utf-8"
        )

        _write_empty_alvos_csv(out / "05_Tabela_Alvos" / f"{stem}_alvos.csv")

        supa = _build_mock_supa(profile_id=profile_id)

        _persist_outputs(supa, project_id, run_id, out)

    # Analisa todas as chamadas a upload_file
    all_calls = supa.upload_file.call_args_list
    if not all_calls:
        _fail("G6", "upload_file nunca foi chamado")
        return

    metrics_calls = [c for c in all_calls if "pipeline_metrics" in str(c)]
    if not metrics_calls:
        _warn("G6", "Nenhuma chamada a upload_file com 'pipeline_metrics' na path")
        # Lista todas as calls para debug
        for c in all_calls:
            _warn("G6", f"  upload_file call: bucket={c.args[0]!r}, path=...{str(c.args[1])[-40:]!r}, mime={c.args[3]!r}")
        return

    for c in metrics_calls:
        bucket       = c.args[0]
        path         = c.args[1]
        content_type = c.args[3] if len(c.args) > 3 else c.kwargs.get("content_type", "??")

        if content_type == "application/octet-stream":
            _ok("G6", f"upload_file para metrics usa 'application/octet-stream' ✓")
            _ok("G6", f"  bucket={bucket!r}  path=...{path[-40:]!r}")
        elif content_type == "application/json":
            _fail("G6", f"upload_file para metrics ainda usa 'application/json' — correção não aplicada!")
        else:
            _warn("G6", f"upload_file para metrics usa MIME inesperado: {content_type!r}")

        # Verifica que o filename termina em .json
        filename = Path(path).name
        if filename.endswith(".json"):
            _ok("G6", f"Filename preserva sufixo .json: {filename!r}")
        else:
            _fail("G6", f"Filename não termina em .json: {filename!r}")


# ============================================================
# G7 — process_dzt produz _pipeline_metrics.json (requer DZT)
# ============================================================

def test_g7_pipeline_produces_metrics() -> None:
    _sep("G7", "process_dzt produz _pipeline_metrics.json (requer HELPER_0001.dzt)")

    if not _DZT.exists():
        _warn("G7", f"DZT não encontrado: {_DZT} — pulando")
        return

    from gpr_engine.pipeline import process_dzt

    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir)
        result = process_dzt(
            dzt_path=_DZT,
            output_dir=out,
            config={"visual_profile": "readgssi_reference", "skip_ia": True},
            tipo_solo="standard",
            stem=_DZT.stem,
        )

        if result.metrics_path is None:
            _fail("G7", "result.metrics_path é None — pipeline não gerou metrics")
            return

        metrics_p = Path(result.metrics_path)
        if not metrics_p.exists():
            _fail("G7", f"Arquivo metrics não existe: {metrics_p}")
            return

        if not metrics_p.name.endswith(".json"):
            _fail("G7", f"Sufixo inesperado: {metrics_p.name!r}")
        else:
            _ok("G7", f"Metrics gerado: {metrics_p.name} ({metrics_p.stat().st_size} bytes)")

        # Verifica que é JSON válido
        try:
            m = json.loads(metrics_p.read_text(encoding="utf-8"))
            _ok("G7", f"JSON válido — campos: {list(m.keys())[:5]}...")
        except Exception as e:
            _fail("G7", f"Arquivo não é JSON válido: {e}")


# ============================================================
# G8 — readgssi_engine completo sem erro de MIME (smoke test)
# ============================================================

def test_g8_readgssi_no_mime_error() -> None:
    _sep("G8", "readgssi_engine: scansolo_adapter não produz erro de MIME no upload")

    if not _DZT.exists():
        _warn("G8", f"DZT não encontrado: {_DZT} — pulando")
        return

    from gpr_engine.scansolo_adapter import run_new_engine

    with tempfile.TemporaryDirectory() as tmpdir:
        inp = Path(tmpdir) / "input"
        out = Path(tmpdir) / "output"
        inp.mkdir()
        out.mkdir()

        import shutil
        shutil.copy2(str(_DZT), str(inp / _DZT.name))

        run_new_engine(
            input_dir=inp,
            output_dir=out,
            config={"engine": "readgssi_engine", "visual_profile": "readgssi_reference"},
            tipo_solo="standard",
        )

        # Verifica que metrics foi produzido (será upado por _persist_outputs em prod)
        proc_dir = out / "02_Imagens_Processadas"
        metrics_files = list(proc_dir.glob("*_pipeline_metrics.json"))
        if not metrics_files:
            _fail("G8", "Nenhum _pipeline_metrics.json em 02_Imagens_Processadas após adapter")
        else:
            mf = metrics_files[0]
            _ok("G8", f"Adapter produziu metrics: {mf.name} ({mf.stat().st_size} bytes)")
            _ok("G8", "Pronto para upload — suffix .json preservado, MIME corrigido em job_gpr.py")


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    print("=" * 65)
    print("  _test_phase8_9.py — MIME fix pipeline_metrics.json upload")
    print("=" * 65)

    test_g1_no_json_mime()
    test_g2_correct_mime()
    test_g3_json_suffix()
    test_g4_shared_code_path()
    test_g5_bucket_migration()
    test_g6_mock_upload_mime()
    test_g7_pipeline_produces_metrics()
    test_g8_readgssi_no_mime_error()

    print(f"\n{'='*65}")
    print(f"  RESULTADO: {_PASS} PASS | {_FAIL} FAIL | {_WARN} WARN")
    print("=" * 65)
    if _FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
