"""
OpenAI client stub for the worker — Phase 0.

Phase 2: implement GPT-4o calls for automatic GPR interpretation.
API key stays in environment variables only — never in DB or frontend.
"""

from __future__ import annotations

import os
import structlog
from typing import Any

log = structlog.get_logger()

AI_MODEL = "gpt-4o"
AI_TEMPERATURE = 0.2


class OpenAIClient:
    def __init__(self) -> None:
        # Phase 2: initialize openai.OpenAI(api_key=...)
        self._api_key = os.environ.get("OPENAI_API_KEY", "")
        log.info("openai_client_init_stub", model=AI_MODEL, note="Phase 0 — no real connection")

    def interpret_target(
        self,
        *,
        project_context: dict[str, Any],
        target_data: dict[str, Any],
        radargram_image_b64: str | None = None,
        crop_image_b64: str | None = None,
    ) -> dict[str, Any]:
        """
        Call GPT-4o to interpret a single detected target.

        Returns structured dict with:
          ia_tipo_sugerido, ia_descricao, ia_justificativa_visual,
          ia_justificativa_tecnica, ia_confianca, ia_recomendacao,
          vai_para_planta_sugerido, vai_para_relatorio_sugerido,
          observacoes, raw_response_json, model_usado, tokens_usados, custo_usd
        """
        log.info(
            "openai_interpret_stub",
            target_rank=target_data.get("rank"),
            note="Phase 0 — returning placeholder",
        )
        return {
            "ia_tipo_sugerido": "nao_interpretado",
            "ia_descricao": "Interpretação IA não executada — Phase 0 stub",
            "ia_justificativa_visual": None,
            "ia_justificativa_tecnica": None,
            "ia_confianca": "baixa",
            "ia_recomendacao": None,
            "vai_para_planta_sugerido": False,
            "vai_para_relatorio_sugerido": False,
            "observacoes": "Phase 0: OpenAI client not yet connected",
            "raw_response_json": {},
            "model_usado": AI_MODEL,
            "tokens_usados": 0,
            "custo_usd": 0.0,
        }
