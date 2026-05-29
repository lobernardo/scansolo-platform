"""OpenAI GPT-4o client for GPR target interpretation."""

from __future__ import annotations

import json
import os
from typing import Any

import structlog
from openai import OpenAI

log = structlog.get_logger()

AI_MODEL = "gpt-4o"
AI_TEMPERATURE = 0.2

# Approximate cost per token for gpt-4o (2024)
_COST_INPUT = 2.50 / 1_000_000
_COST_OUTPUT = 10.00 / 1_000_000

_SYSTEM_PROMPT = """\
You are an expert geophysicist specializing in Ground Penetrating Radar (GPR) interpretation.

You will analyze a crop of a GPR radargram showing a hyperbolic reflection from a buried object, \
along with numerical data from an automated detection algorithm.

In a radargram:
- Horizontal axis = distance along the survey line
- Vertical axis = depth (increasing downward)
- A hyperbolic signature indicates a point-like or cylindrical buried object
- Brighter/stronger reflections indicate higher dielectric contrast with surrounding soil

Common buried objects in urban/infrastructure surveys:
- tubulacao_agua: water pipe (metallic or PVC), strong clean reflection
- tubulacao_gas: gas pipe (metallic), strong reflection, often shallow
- cabo_eletrico: electric cable, small diameter, strong metallic reflection
- cabo_telecom: telecom cable, small diameter, may appear in bundles
- vazio: void/cavity, double reflection (top and bottom surface)
- raiz: tree root, irregular hyperbola, organic material
- rocha: rock, irregular shape, variable reflection
- desconhecido: ambiguous signature

Respond ONLY with a valid JSON object using these exact fields:
{
  "ia_tipo_sugerido": "<one of the types listed above>",
  "ia_descricao": "<1-2 sentences describing the detected object>",
  "ia_justificativa_visual": "<what visual features in the radargram indicate this interpretation>",
  "ia_justificativa_tecnica": "<technical reasoning: depth, diameter, signal characteristics>",
  "ia_confianca": "<alta | media | baixa>",
  "ia_recomendacao": "<action recommendation for the field/technical team>",
  "vai_para_planta_sugerido": true or false,
  "vai_para_relatorio_sugerido": true or false,
  "observacoes": "<additional observations or null>"
}"""


class OpenAIClient:
    def __init__(self) -> None:
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            log.warning("openai_api_key_missing")
        self._client = OpenAI(api_key=api_key)

    def interpret_target(
        self,
        *,
        project_context: dict[str, Any],
        target_data: dict[str, Any],
        radargram_image_b64: str | None = None,
        crop_image_b64: str | None = None,
    ) -> dict[str, Any]:
        messages = _build_messages(project_context, target_data, radargram_image_b64, crop_image_b64)

        try:
            response = self._client.chat.completions.create(
                model=AI_MODEL,
                temperature=AI_TEMPERATURE,
                response_format={"type": "json_object"},
                messages=messages,
            )
        except Exception as exc:
            log.error("openai_call_failed", error=str(exc))
            return _error_result(str(exc))

        usage = response.usage
        tokens_in = usage.prompt_tokens if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost = round(tokens_in * _COST_INPUT + tokens_out * _COST_OUTPUT, 6)

        raw_text = response.choices[0].message.content or "{}"
        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            log.error("openai_invalid_json", raw=raw_text[:500])
            return _error_result("JSON inválido retornado pelo modelo")

        log.info(
            "openai_interpret_done",
            target_rank=target_data.get("rank"),
            tipo=parsed.get("ia_tipo_sugerido"),
            confianca=parsed.get("ia_confianca"),
            tokens=tokens_in + tokens_out,
            cost_usd=cost,
        )

        return {
            "ia_tipo_sugerido": parsed.get("ia_tipo_sugerido", "desconhecido"),
            "ia_descricao": parsed.get("ia_descricao"),
            "ia_justificativa_visual": parsed.get("ia_justificativa_visual"),
            "ia_justificativa_tecnica": parsed.get("ia_justificativa_tecnica"),
            "ia_confianca": parsed.get("ia_confianca", "baixa"),
            "ia_recomendacao": parsed.get("ia_recomendacao"),
            "vai_para_planta_sugerido": bool(parsed.get("vai_para_planta_sugerido", False)),
            "vai_para_relatorio_sugerido": bool(parsed.get("vai_para_relatorio_sugerido", True)),
            "observacoes": parsed.get("observacoes"),
            "raw_response_json": parsed,
            "model_usado": AI_MODEL,
            "tokens_usados": tokens_in + tokens_out,
            "custo_usd": cost,
        }


def _build_messages(
    project_context: dict[str, Any],
    target_data: dict[str, Any],
    radargram_image_b64: str | None,
    crop_image_b64: str | None,
) -> list[dict]:
    user_content: list[Any] = [{"type": "text", "text": _user_text(project_context, target_data)}]

    if crop_image_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{crop_image_b64}", "detail": "high"},
        })

    if radargram_image_b64:
        user_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{radargram_image_b64}", "detail": "low"},
        })

    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _user_text(project: dict[str, Any], t: dict[str, Any]) -> str:
    return (
        f"Survey: {project.get('nome', '?')} | "
        f"Local: {project.get('local', 'N/A')}, {project.get('estado', 'N/A')}\n"
        f"File: {t.get('arquivo_dzt', 'N/A')}\n\n"
        "Automated detection data:\n"
        f"  Rank: #{t.get('rank', '?')}\n"
        f"  Position: {t.get('x_m', '?')} m along profile\n"
        f"  Depth: {t.get('depth_m', '?')} m\n"
        f"  Estimated diameter: {t.get('diam_est_m', '?')} m "
        f"(confidence: {t.get('diam_confianca', '?')})\n"
        f"  Material type (algorithm): {t.get('tipo_material', 'N/A')} "
        f"({t.get('confianca_tipo', 'N/A')})\n"
        f"  Algorithm score: {t.get('confidence_score', '?')}/100 "
        f"({t.get('confidence_label_tecnico', '?')})\n"
        f"  SNR local: {t.get('snr_local', 'N/A')}\n\n"
        "Image above: crop of the radargram centered on this target.\n"
        "Return JSON interpretation."
    )


def _error_result(error_msg: str) -> dict[str, Any]:
    return {
        "ia_tipo_sugerido": "desconhecido",
        "ia_descricao": f"Interpretação falhou: {error_msg[:200]}",
        "ia_justificativa_visual": None,
        "ia_justificativa_tecnica": None,
        "ia_confianca": "baixa",
        "ia_recomendacao": None,
        "vai_para_planta_sugerido": False,
        "vai_para_relatorio_sugerido": False,
        "observacoes": f"Erro OpenAI: {error_msg[:200]}",
        "raw_response_json": {"error": error_msg[:500]},
        "model_usado": AI_MODEL,
        "tokens_usados": 0,
        "custo_usd": 0.0,
    }
