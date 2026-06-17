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

TIPO_OBRA_EN = {
    "utilities":     "underground utilities (water, gas, electricity, telecom)",
    "roads":         "road/pavement investigation",
    "structures":    "structural investigation (floors, walls, slabs)",
    "environmental": "environmental survey",
    "archaeology":   "archaeological survey",
    "other":         "general GPR survey",
}

_SYSTEM_PROMPT_HEAD = """\
You are a GPR (Ground Penetrating Radar) expert geophysicist.

Analyze the detected target from a 270MHz GSSI antenna radargram. The crop image shows the \
hyperbolic reflection centered on the target.

In a radargram:
- Horizontal axis = distance along the survey line
- Vertical axis = depth (increasing downward)
- A hyperbolic signature indicates a buried point or cylindrical object
- Brighter/stronger reflections indicate higher dielectric contrast with surrounding soil"""

_SYSTEM_PROMPT_TAIL = """

Common buried objects in urban/infrastructure surveys:
- tubulacao_agua: water pipe (metal or PVC) — clean strong reflection
- tubulacao_gas: gas pipe (metal) — strong reflection, usually shallow
- tubulacao_esgoto: sewer pipe (concrete/PVC) — larger diameter, moderate reflection
- cabo_eletrico: electrical cable — small diameter, strong metallic reflection
- cabo_telecom: telecom cable — small diameter, may appear in bundles
- galeria_concreto: concrete gallery/culvert — large, double reflection (top+bottom)
- vazio_ar: void/cavity — double reflection surface+bottom
- rocha: rock — irregular shape, variable reflection
- inconclusivo: ambiguous signature

Respond ONLY with a valid JSON object. All description text must be in Brazilian Portuguese:
{
  "ia_tipo_sugerido": "<one of the types listed above>",
  "ia_descricao": "<1-2 sentences describing the detected object in Portuguese>",
  "ia_justificativa_visual": "<visual features in the radargram supporting this interpretation, in Portuguese>",
  "ia_justificativa_tecnica": "<technical reasoning: depth, diameter, signal characteristics, in Portuguese>",
  "ia_confianca": "<alta | media | baixa>",
  "ia_confianca_pct": <integer 0-100>,
  "ia_recomendacao": "<recommended action for field/technical team, in Portuguese>",
  "vai_para_planta_sugerido": true or false,
  "vai_para_relatorio_sugerido": true or false,
  "observacoes": "<additional observations or null>"
}"""


def _build_system_prompt(project: dict) -> str:
    tipo_obra_raw = (project.get("tipo_obra") or "").strip()
    tipo_obra_desc = TIPO_OBRA_EN.get(tipo_obra_raw, tipo_obra_raw or "not informed")
    freq_str = str(project.get("antena_freq_mhz") or 270) + " MHz"
    area_m2 = project.get("area_m2")
    area_str = f"{area_m2:.0f} m²" if area_m2 else "not informed"

    project_context = (
        "\n\nPROJECT CONTEXT:\n"
        f"- Project code: {project.get('codigo_projeto') or 'N/A'}\n"
        f"- Work type: {tipo_obra_desc}\n"
        f"- Site area: {area_str}\n"
        f"- GPR antenna frequency: {freq_str}\n"
        f"- Client contact: {project.get('contato_nome') or 'N/A'}"
    )

    return _SYSTEM_PROMPT_HEAD + project_context + _SYSTEM_PROMPT_TAIL


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

        confianca_cat = parsed.get("ia_confianca", "baixa")
        confianca_pct = int(parsed.get("ia_confianca_pct", 0)) if parsed.get("ia_confianca_pct") else (
            85 if confianca_cat == "alta" else 60 if confianca_cat == "media" else 30
        )

        return {
            "ia_tipo_sugerido": parsed.get("ia_tipo_sugerido", "desconhecido"),
            "ia_descricao": parsed.get("ia_descricao"),
            "ia_justificativa_visual": parsed.get("ia_justificativa_visual"),
            "ia_justificativa_tecnica": parsed.get("ia_justificativa_tecnica"),
            "ia_confianca": confianca_cat,
            "ia_confianca_pct": confianca_pct,
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
        {"role": "system", "content": _build_system_prompt(project_context)},
        {"role": "user", "content": user_content},
    ]


def _user_text(project: dict[str, Any], t: dict[str, Any]) -> str:
    freq = t.get("freq_dominante_mhz")
    freq_str = f"{freq} MHz" if freq else "N/A"
    return (
        f"Survey: {project.get('nome', '?')} | "
        f"Location: {project.get('local', 'N/A')}, {project.get('estado', 'N/A')}\n"
        f"File: {t.get('arquivo_dzt', 'N/A')}\n\n"
        "Automatic detection parameters:\n"
        f"  Rank: #{t.get('rank', '?')}\n"
        f"  Position: {t.get('x_m', '?')} m along profile\n"
        f"  Depth to top (geratriz): {t.get('prof_topo_m', '?')} m\n"
        f"  Center depth: {t.get('depth_m', '?')} m\n"
        f"  Estimated diameter: {t.get('diam_est_m', '?')} m "
        f"(confidence: {t.get('diam_confianca', '?')})\n"
        f"  Hyperbola width: {t.get('largura_hiperbole_m', 'N/A')} m\n"
        f"  Physical classification: {t.get('tipo_material', 'N/A')} "
        f"({t.get('confianca_tipo', 'N/A')})\n"
        f"  Algorithm score: {t.get('confidence_score', '?')}/100 "
        f"({t.get('confidence_label_tecnico', '?')})\n"
        f"  SNR: {t.get('snr_local', 'N/A')}\n"
        f"  Dominant frequency: {freq_str}\n\n"
        "The crop image above is centered on this target's hyperbola apex.\n"
        "Return JSON with all description text in Brazilian Portuguese."
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
