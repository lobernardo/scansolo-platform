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
Você é um geofísico especialista em interpretação de Radar de Penetração no Solo (GPR).

Analise o recorte do radarograma GPR fornecido, que mostra uma reflexão hiperbólica de um objeto enterrado, \
juntamente com os dados numéricos do algoritmo de detecção automática.

Em um radarograma:
- Eixo horizontal = distância ao longo da linha de levantamento
- Eixo vertical = profundidade (crescente para baixo)
- Uma assinatura hiperbólica indica um objeto enterrado pontual ou cilíndrico
- Reflexões mais brilhantes/fortes indicam maior contraste dielétrico com o solo circundante

Objetos enterrados comuns em levantamentos urbanos/de infraestrutura:
- tubulacao_agua: tubulação de água (metálica ou PVC), reflexão limpa e forte
- tubulacao_gas: tubulação de gás (metálica), reflexão forte, geralmente rasa
- cabo_eletrico: cabo elétrico, diâmetro pequeno, reflexão metálica forte
- cabo_telecom: cabo de telecomunicações, diâmetro pequeno, pode aparecer em feixes
- vazio: vazio/cavidade, dupla reflexão (superfície superior e inferior)
- raiz: raiz de árvore, hipérbole irregular, material orgânico
- rocha: rocha, forma irregular, reflexão variável
- desconhecido: assinatura ambígua

Responda APENAS com um objeto JSON válido usando exatamente estes campos. \
Todos os textos devem estar em português do Brasil:
{
  "ia_tipo_sugerido": "<um dos tipos listados acima>",
  "ia_descricao": "<1-2 frases descrevendo o objeto detectado>",
  "ia_justificativa_visual": "<quais características visuais no radarograma indicam esta interpretação>",
  "ia_justificativa_tecnica": "<raciocínio técnico: profundidade, diâmetro, características do sinal>",
  "ia_confianca": "<alta | media | baixa>",
  "ia_recomendacao": "<recomendação de ação para a equipe de campo/técnica>",
  "vai_para_planta_sugerido": true ou false,
  "vai_para_relatorio_sugerido": true ou false,
  "observacoes": "<observações adicionais ou null>"
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
        f"Levantamento: {project.get('nome', '?')} | "
        f"Local: {project.get('local', 'N/A')}, {project.get('estado', 'N/A')}\n"
        f"Arquivo: {t.get('arquivo_dzt', 'N/A')}\n\n"
        "Dados da detecção automática:\n"
        f"  Rank: #{t.get('rank', '?')}\n"
        f"  Posição: {t.get('x_m', '?')} m ao longo do perfil\n"
        f"  Profundidade: {t.get('depth_m', '?')} m\n"
        f"  Diâmetro estimado: {t.get('diam_est_m', '?')} m "
        f"(confiança: {t.get('diam_confianca', '?')})\n"
        f"  Tipo de material (algoritmo): {t.get('tipo_material', 'N/A')} "
        f"({t.get('confianca_tipo', 'N/A')})\n"
        f"  Score do algoritmo: {t.get('confidence_score', '?')}/100 "
        f"({t.get('confidence_label_tecnico', '?')})\n"
        f"  SNR local: {t.get('snr_local', 'N/A')}\n\n"
        "Imagem acima: recorte do radarograma centralizado neste alvo.\n"
        "Retorne a interpretação em JSON com todos os textos em português do Brasil."
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
