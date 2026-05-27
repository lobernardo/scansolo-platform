"""
Dropbox client stub for the worker — Phase 0.

Phase 1: implement actual Dropbox API calls using OAuth2 refresh token flow.
Credentials stay in environment variables only — never in DB or frontend.
"""

from __future__ import annotations

import os
import hashlib
import structlog
from pathlib import Path

log = structlog.get_logger()

DROPBOX_ROOT = "/ScanSOLO_Projetos"


class DropboxClient:
    def __init__(self) -> None:
        # Phase 1: initialize dropbox.Dropbox with refresh token
        self._app_key = os.environ.get("DROPBOX_APP_KEY", "")
        self._app_secret = os.environ.get("DROPBOX_APP_SECRET", "")
        self._refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN", "")
        log.info("dropbox_client_init_stub", note="Phase 0 — no real connection")

    def create_project_folder(self, project_name: str) -> str:
        """Create standard folder structure for a new project. Returns Dropbox path."""
        from datetime import date
        year = date.today().year
        project_path = f"{DROPBOX_ROOT}/{year}/{project_name}"

        subfolders = [
            "00_Entrada/DZT",
            "00_Entrada/DZG",
            "00_Entrada/KML_KMZ",
            "00_Entrada/DWG_DXF",
            "00_Entrada/Fotos_Campo",
            "00_Entrada/PipeLocator",
            "00_Entrada/Observacoes",
            "01_Processamento_GPR",
            "02_IA_Interpretacao",
            "03_Revisao_Tecnica",
            "04_Cartografia",
            "05_Relatorio",
            "06_Entrega_Cliente",
            "99_Logs",
        ]
        log.info("dropbox_create_folder_stub", project_path=project_path, subfolders=len(subfolders))
        return project_path

    def upload_file(self, local_path: Path, dropbox_path: str) -> str:
        """Upload file to Dropbox. Returns Dropbox file path."""
        log.info("dropbox_upload_stub", local=str(local_path), remote=dropbox_path)
        return dropbox_path

    def download_file(self, dropbox_path: str, local_path: Path) -> None:
        """Download file from Dropbox to local path."""
        log.info("dropbox_download_stub", remote=dropbox_path, local=str(local_path))

    def list_folder(self, dropbox_path: str) -> list[dict]:
        """List files in a Dropbox folder."""
        log.info("dropbox_list_stub", path=dropbox_path)
        return []

    def upload_manifest(self, project_path: str, manifest: dict) -> None:
        """Write project_manifest.json to Dropbox project root."""
        import json
        log.info("dropbox_manifest_stub", project_path=project_path, manifest_keys=list(manifest.keys()))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
