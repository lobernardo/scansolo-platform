"use server";

import { createClient } from "@/lib/supabase/server";

export type PipelineMetrics = {
  // Da metrics JSON (pipeline_metrics.json salvo pelo pipeline)
  pipeline_version?: string;
  dzt_filename?: string;
  preset_name?: string;
  modo_processamento?: string;
  modo_coleta?: string;
  n_tracos_json?: number;
  n_amostras_final?: number;
  dist_total_m?: number;
  det_depth_min_m_usado?: number;
  // snr_stages_db: { raw, dewow, bp, bgremoval, tpow, agc } — valores em dB (float)
  snr_stages_db?: Record<string, number>;
  detector_input_mode_json?: string;
  // De gpr_profiles (complementar — disponível mesmo sem metrics JSON)
  snr_raw_db?: number | null;
  snr_raw_ratio?: number | null;
  tipo_solo?: string | null;
  n_tracos?: number | null;
  distancia_max_m?: number | null;
  profundidade_max_m?: number | null;
  // Parâmetros de filtro: de filtros_customizados (reprocessamento) ou n/d
  filtros_customizados?: Record<string, unknown> | null;
  // Bandpass efetivo — lidos do pipeline_metrics.json (cobre primeiro processamento e reprocessamento)
  bandpass_aplicado?: string;        // "desativado" | "80-500 MHz"
  bandpass_low_mhz_usado?: number;   // 0 se desativado
  bandpass_high_mhz_usado?: number;
  bandpass_order_usado?: number;
  bandpass_tipo_usado?: string;
  // Velocity e profundidade técnica
  velocity_mns?: number;             // velocity usada (m/ns)
  velocity_fonte?: string;           // "preset" | "filtros_customizados" | "VELOCITY_POR_SOLO[tipo]"
  depth_tecnica_m?: number;          // profundidade real: twtt_max_ns × velocity / 2 (m)
  // Flags de imagens geradas
  imagem_bruta_ok?: boolean;
  imagem_relatorio_ok?: boolean;
  imagem_anotada_ok?: boolean;
  imagem_migrada_ok?: boolean;
  imagem_preview_ok?: boolean;
  // De detected_targets (contagens)
  n_alvos_alta?: number;
  n_alvos_media?: number;
  n_alvos_baixa?: number;
  n_alvos_score_30?: number;
  // Sinaliza se metrics JSON estava disponível
  metricas_pipeline_url?: string | null;
};

export async function getPipelineMetrics(profileId: string): Promise<PipelineMetrics | null> {
  const supabase = await createClient();

  const { data: profileRaw } = await supabase
    .from("gpr_profiles")
    .select(
      "metricas_pipeline_url, snr_imagem_db, snr_imagem_ratio, modo_processamento, tipo_solo, " +
        "n_tracos, distancia_max_m, profundidade_max_m, filtros_customizados, " +
        "imagem_bruta_url, imagem_processada_url, imagem_anotada_url, " +
        "imagem_migrada_url, imagem_preview_radan_5m_url"
    )
    .eq("id", profileId)
    .single();

  if (!profileRaw) return null;
  const p = profileRaw as Record<string, unknown>;

  // Contagens de alvos
  const { data: targetsRaw } = await supabase
    .from("detected_targets")
    .select("confidence_label_relatorio, confidence_score_0_100")
    .eq("profile_id", profileId);

  const targets = (targetsRaw ?? []) as {
    confidence_label_relatorio: string | null;
    confidence_score_0_100: number | null;
  }[];
  const n_alta = targets.filter((t) => t.confidence_label_relatorio === "alta").length;
  const n_media = targets.filter((t) => t.confidence_label_relatorio === "media").length;
  const n_baixa = targets.filter((t) => t.confidence_label_relatorio === "baixa").length;
  const n_score_30 = targets.filter((t) => (t.confidence_score_0_100 ?? 0) >= 30).length;

  // Busca JSON de métricas do Storage (URL signed de 10 anos)
  let metricsJson: Record<string, unknown> = {};
  const url = p.metricas_pipeline_url as string | null;
  if (url) {
    try {
      const res = await fetch(url, { cache: "no-store" });
      if (res.ok) metricsJson = (await res.json()) as Record<string, unknown>;
    } catch {
      // ignora — campos do JSON ficam undefined → n/d no PipelineLog
    }
  }

  return {
    // Do JSON
    pipeline_version: metricsJson.pipeline_version as string | undefined,
    dzt_filename: metricsJson.dzt_filename as string | undefined,
    preset_name: metricsJson.preset_name as string | undefined,
    modo_processamento: ((metricsJson.modo_processamento ?? p.modo_processamento) as string | undefined),
    modo_coleta: metricsJson.modo_coleta as string | undefined,
    n_tracos_json: metricsJson.n_tracos as number | undefined,
    n_amostras_final: metricsJson.n_amostras_final as number | undefined,
    dist_total_m: metricsJson.dist_total_m as number | undefined,
    det_depth_min_m_usado: metricsJson.det_depth_min_m_usado as number | undefined,
    snr_stages_db: metricsJson.snr_stages_db as Record<string, number> | undefined,
    detector_input_mode_json: metricsJson.detector_input_mode as string | undefined,
    // Do profile
    snr_raw_db: p.snr_imagem_db as number | null,
    snr_raw_ratio: p.snr_imagem_ratio as number | null,
    tipo_solo: p.tipo_solo as string | null,
    n_tracos: p.n_tracos as number | null,
    distancia_max_m: p.distancia_max_m as number | null,
    profundidade_max_m: p.profundidade_max_m as number | null,
    filtros_customizados: p.filtros_customizados as Record<string, unknown> | null,
    bandpass_aplicado: metricsJson.bandpass_aplicado as string | undefined,
    bandpass_low_mhz_usado: metricsJson.bandpass_low_mhz_usado as number | undefined,
    bandpass_high_mhz_usado: metricsJson.bandpass_high_mhz_usado as number | undefined,
    bandpass_order_usado: metricsJson.bandpass_order_usado as number | undefined,
    bandpass_tipo_usado: metricsJson.bandpass_tipo_usado as string | undefined,
    velocity_mns: metricsJson.velocity_mns as number | undefined,
    velocity_fonte: metricsJson.velocity_fonte as string | undefined,
    depth_tecnica_m: metricsJson.depth_tecnica_m as number | undefined,
    imagem_bruta_ok: !!(p.imagem_bruta_url as string),
    imagem_relatorio_ok: !!(p.imagem_processada_url as string),
    imagem_anotada_ok: !!(p.imagem_anotada_url as string),
    imagem_migrada_ok: !!(p.imagem_migrada_url as string),
    imagem_preview_ok: !!(p.imagem_preview_radan_5m_url as string),
    // De detected_targets
    n_alvos_alta: n_alta,
    n_alvos_media: n_media,
    n_alvos_baixa: n_baixa,
    n_alvos_score_30: n_score_30,
    metricas_pipeline_url: url,
  };
}
