"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export type UploadedFileMeta = {
  fileName: string;
  storagePath: string;
  sizeBytes: number;
};

export async function registerUploadedFiles(
  projectId: string,
  uploadedFiles: UploadedFileMeta[]
): Promise<{ ok: true } | { ok: false; error: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  if (!uploadedFiles.length)
    return { ok: false, error: "Nenhum arquivo para registrar" };

  for (const f of uploadedFiles) {
    const { error } = await supabase.from("project_files").insert({
      project_id: projectId,
      file_name: f.fileName,
      extension: "dzt",
      supabase_storage_path: f.storagePath,
      size_bytes: f.sizeBytes,
      uploaded_by: user.id,
      status: "confirmado",
    } as unknown as never);
    if (error) return { ok: false, error: error.message };
  }

  return { ok: true };
}

export type FilterConfig = {
  filtros_ativos: {
    dewow: boolean;
    bandpass: boolean;
    background_removal: boolean;
    tpow_gain: boolean;
    agc: boolean;
    ia_imagem: boolean;
  };
  bgremoval_traces: number;
  tpow_power: number;
  contrast: number;
  agc_window: number;
};

// ── Tipos do preflight ────────────────────────────────────────────────────────

export type DztMetadata = {
  dzt_filename: string;
  antenna_freq_mhz_detected: number;
  velocity_header_mns: number;
  epsr_header: number;
  dist_total_m: number;
  depth_real_m_from_header_velocity: number;
  depth_real_m_from_standard_velocity: number;
  header_confidence: "alta" | "media" | "baixa";
  warnings: string[];
  modo_coleta: string;
  n_traces: number;
};

export type PreflightRecommendation = {
  frequency_mismatch: boolean;
  selected_preset_freq_mhz: number;
  detected_freq_mhz: number;
  recommended_antenna_freq_mhz: number;
  recommended_preset_family: string | null;
  recommended_velocity_mns: number;
  velocity_from_header: boolean;
  recommended_engine: string;
  recommended_visual_profile: string;
  recommended_depth_preview_m: number;
  header_confidence: "alta" | "media" | "baixa";
  warnings: string[];
};

export type PreflightFileResult = {
  dzt_metadata: DztMetadata;
  recommendation: PreflightRecommendation;
};

export type PreflightData = {
  files: Record<string, PreflightFileResult>;
  projectStatus: string;
  currentConfig: Record<string, unknown>;
};

export type PreflightOverrides = {
  velocity_mns?: number;
  depth_preview_m?: number;
  bandpass_enabled?: boolean;
};

// ── Server actions ────────────────────────────────────────────────────────────

export async function startProcessingWithConfig(
  projectId: string,
  config: FilterConfig
): Promise<void> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  await supabase
    .from("projects")
    .update({
      status: "aguardando_processamento",
      processing_config: { engine: "readgssi_engine", ...config },
    } as unknown as never)
    .eq("id", projectId);

  const { error } = await supabase
    .from("processing_jobs")
    .insert({ project_id: projectId, job_type: "gpr", status: "aguardando" } as unknown as never);

  if (error) throw new Error(error.message);

  redirect(`/projetos/${projectId}`);
}

/**
 * Inicia job leve de preflight: lê metadados dos DZTs e gera recomendação
 * de configuração antes do processamento pesado GPR.
 */
export async function startPreflight(
  projectId: string
): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  await supabase
    .from("projects")
    .update({ status: "aguardando_preflight" } as unknown as never)
    .eq("id", projectId);

  const jobId = crypto.randomUUID();
  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      id: jobId,
      project_id: projectId,
      job_type: "preflight",
      status: "aguardando",
    } as unknown as never);

  if (error) return { ok: false, error: `Erro ao criar job preflight: ${error.message}` };
  return { ok: true, jobId };
}

/**
 * Busca o resultado do preflight salvo em projects.processing_config._preflight.
 */
export async function getProjectPreflight(
  projectId: string
): Promise<PreflightData | null> {
  const supabase = await createClient();
  const { data: rawData } = await supabase
    .from("projects")
    .select("processing_config, status")
    .eq("id", projectId)
    .single();

  const data = rawData as { processing_config: unknown; status: string } | null;
  if (!data) return null;

  const config = (data.processing_config as Record<string, unknown>) ?? {};
  const preflight = config._preflight as Record<string, PreflightFileResult> | undefined;

  if (!preflight || typeof preflight !== "object") return null;

  return {
    files: preflight,
    projectStatus: data.status,
    currentConfig: config,
  };
}

/**
 * Confirma o preflight e cria o job GPR pesado.
 *
 * Lê o _preflight salvo, monta a config recomendada com overrides opcionais,
 * atualiza projects.processing_config, e insere processing_jobs (job_type="gpr").
 * Nunca permite engine diferente de readgssi_engine.
 */
export async function confirmPreflight(
  projectId: string,
  overrides: PreflightOverrides = {}
): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const { data: projRaw } = await supabase
    .from("projects")
    .select("processing_config")
    .eq("id", projectId)
    .single();

  const proj = projRaw as { processing_config: unknown } | null;
  const currentConfig = (proj?.processing_config as Record<string, unknown>) ?? {};
  const preflight = currentConfig._preflight as
    | Record<string, { recommendation: PreflightRecommendation }>
    | undefined;

  // Usa recomendação do primeiro arquivo como base
  const firstRec = preflight ? Object.values(preflight)[0]?.recommendation : null;

  const recommended: Record<string, unknown> = {
    engine:           "readgssi_engine",
    antenna_freq_mhz: firstRec?.recommended_antenna_freq_mhz ?? 270,
    velocity_mns:     firstRec?.recommended_velocity_mns ?? 0.10,
    visual_profile:   firstRec?.recommended_visual_profile ?? "readgssi_reference",
    depth_preview_m:  firstRec?.recommended_depth_preview_m ?? 5.0,
  };

  // Aplica overrides (engine sempre forçado para readgssi_engine)
  if (overrides.velocity_mns !== undefined) recommended.velocity_mns = overrides.velocity_mns;
  if (overrides.depth_preview_m !== undefined) recommended.depth_preview_m = overrides.depth_preview_m;
  if (overrides.bandpass_enabled !== undefined) recommended.bandpass_enabled = overrides.bandpass_enabled;

  const finalConfig: Record<string, unknown> = {
    ...currentConfig,
    ...recommended,
    engine:              "readgssi_engine",  // nunca sobrescrito por override
    _preflight:          currentConfig._preflight,
    _preflight_done:     true,
    _preflight_accepted: true,
  };

  const { error: updateErr } = await supabase
    .from("projects")
    .update({
      processing_config: finalConfig,
      status: "aguardando_processamento",
    } as unknown as never)
    .eq("id", projectId);

  if (updateErr)
    return { ok: false, error: `Erro ao atualizar config: ${updateErr.message}` };

  const jobId = crypto.randomUUID();
  const { error: jobErr } = await supabase
    .from("processing_jobs")
    .insert({
      id: jobId,
      project_id: projectId,
      job_type: "gpr",
      status: "aguardando",
    } as unknown as never);

  if (jobErr)
    return { ok: false, error: `Erro ao criar job GPR: ${jobErr.message}` };

  return { ok: true, jobId };
}

/**
 * Inicia o processamento SEM alterar processing_config.
 * Mantido como fallback para projetos sem preflight.
 */
export async function startProcessingDirect(projectId: string): Promise<void> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  await supabase
    .from("projects")
    .update({ status: "aguardando_processamento" } as unknown as never)
    .eq("id", projectId);

  const { error } = await supabase
    .from("processing_jobs")
    .insert({ project_id: projectId, job_type: "gpr", status: "aguardando" } as unknown as never);

  if (error) throw new Error(error.message);

  redirect(`/projetos/${projectId}`);
}
