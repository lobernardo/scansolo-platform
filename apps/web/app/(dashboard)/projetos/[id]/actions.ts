"use server";

import { createClient, createAdminClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export type VisualConfig = {
  visual_base: "raw" | "dewow_bp";
  visual_depth_mode: "real" | "manual";
  visual_depth_m: number | null;
  visual_aspect_ratio: "default" | "panoramic";
  visual_normalization: "linear_percentile" | "symlog";
  visual_contrast: number;
  visual_colormap: string;
  visual_polarity: "normal" | "inverted";
  visual_dewow_enabled: boolean;
  visual_dewow_window: number;
  visual_bandpass_enabled: boolean;
  visual_bandpass_low_mhz: number;
  visual_bandpass_high_mhz: number;
  visual_bandpass_order: number;
  visual_bgremoval_enabled: boolean;
  visual_bgremoval_traces: number;
  visual_tpow_enabled: boolean;
  visual_tpow_power: number;
  visual_agc_enabled: boolean;
  visual_agc_window: number;
};

export type FilterState = {
  dewow: boolean;
  background_removal: boolean;
  bandpass: boolean;
  bandpass_low: number;
  bandpass_high: number;
  gain: boolean;
  gain_type: "linear" | "agc";
  contrast: number;
  velocity_mns: number;
  // Processada 2 (preview RADAN visual) — independent params
  depth_preview_m: number;
  agc_window_preview: number;
  // G3: render config — display-only, never mutate data
  normalization: "linear_percentile" | "symlog" | "linear_minmax";
  polarity: "normal" | "inverted";
  display_depth_m: number | null;
  // G3: preview visual depth mode — how the preview image maps depth
  // "stretch_to_preview_depth" (default): data stretched to fill depth_preview_m frame
  // "axis_limit_no_stretch": physical data preserved; blank space below if depth_preview_m > physical
  preview_visual_depth_mode: "stretch_to_preview_depth" | "axis_limit_no_stretch";
};

export async function reprocessProfile(
  profileId: string,
  filters: FilterState
): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  // Verify the user has access to this profile
  const { data: profileRaw } = await supabase
    .from("gpr_profiles")
    .select("id, project_id")
    .eq("id", profileId)
    .maybeSingle();

  if (!profileRaw) return { ok: false, error: "Perfil não encontrado" };
  const profile = profileRaw as { id: string; project_id: string };

  // Garante que engine está sempre definido (preserva se já vier em overrides de preflight)
  const filtersWithEngine: Record<string, unknown> = {
    ...(filters as Record<string, unknown>),
    engine: (filters as Record<string, unknown>).engine ?? "readgssi_engine",
  };

  // Save custom filters to the profile (column may not exist in DB yet — log and continue)
  const { error: updateError } = await supabase
    .from("gpr_profiles")
    .update({ filtros_customizados: filtersWithEngine } as unknown as never)
    .eq("id", profileId);

  if (updateError) {
    console.log(
      "[reprocessProfile] filtros_customizados column not available yet:",
      updateError.message
    );
  }

  // Generate the job ID client-side so we can return it without a second SELECT
  const jobId = crypto.randomUUID();

  // Insert a GPR reprocessing job with profile_id + filters in payload
  const { error: jobError } = await supabase
    .from("processing_jobs")
    .insert({
      id: jobId,
      project_id: profile.project_id,
      job_type: "gpr",
      status: "aguardando",
      payload: { profile_id: profileId, filtros_customizados: filtersWithEngine },
    } as unknown as never);

  if (jobError) {
    console.log("[reprocessProfile] job insert error:", jobError.message);
    return { ok: false, error: `Erro ao criar job: ${jobError.message}` };
  }

  return { ok: true, jobId };
}

export async function getJobStatus(jobId: string): Promise<string | null> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return null;

  const { data } = await supabase
    .from("processing_jobs")
    .select("status")
    .eq("id", jobId)
    .maybeSingle();

  return (data as { status: string } | null)?.status ?? null;
}

export async function requestIaP2(profileId: string): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const { data: profileRaw } = await supabase
    .from("gpr_profiles")
    .select("id, project_id")
    .eq("id", profileId)
    .maybeSingle();
  if (!profileRaw) return { ok: false, error: "Perfil não encontrado" };
  const profile = profileRaw as { id: string; project_id: string };

  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      project_id: profile.project_id,
      job_type: "ia_p2",
      status: "aguardando",
      payload: { profile_id: profileId },
    } as unknown as never);

  if (error) return { ok: false, error: `Erro ao criar job: ${error.message}` };
  return { ok: true };
}

export async function deleteProject(projectId: string): Promise<{ ok: boolean; error?: string }> {
  // Auth check with user client
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const { data: proj } = await supabase
    .from("projects")
    .select("id")
    .eq("id", projectId)
    .maybeSingle();
  if (!proj) return { ok: false, error: "Projeto não encontrado" };

  // All deletes use service-role client to bypass RLS
  const admin = createAdminClient();

  const profiles = await admin.from("gpr_profiles").select("id").eq("project_id", projectId);
  const profileIds = (profiles.data ?? []).map((p: { id: string }) => p.id);

  if (profileIds.length > 0) {
    const targets = await admin.from("detected_targets").select("id").in("profile_id", profileIds);
    const targetIds = (targets.data ?? []).map((t: { id: string }) => t.id);

    if (targetIds.length > 0) {
      await admin.from("technical_reviews").delete().in("target_id", targetIds);
      await admin.from("ai_interpretations").delete().in("target_id", targetIds);
    }
    await admin.from("ia_training_examples").delete().in("profile_id", profileIds);
    await admin.from("detected_targets").delete().in("profile_id", profileIds);
  }

  await admin.from("ia_training_examples").delete().eq("project_id", projectId);
  await admin.from("project_files").delete().eq("project_id", projectId);
  await admin.from("gpr_profiles").delete().eq("project_id", projectId);
  await admin.from("cartography_outputs").delete().eq("project_id", projectId);
  await admin.from("report_outputs").delete().eq("project_id", projectId);
  await admin.from("processing_jobs").delete().eq("project_id", projectId);

  const { error } = await admin.from("projects").delete().eq("id", projectId);
  if (error) return { ok: false, error: error.message };

  redirect("/projetos");
}

export async function requestRecalibrarVelocity(
  projectId: string,
  velocityMns: number
): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  if (velocityMns < 0.04 || velocityMns > 0.35) {
    return { ok: false, error: "Velocity fora do intervalo válido (0.04–0.35 m/ns)" };
  }

  const jobId = crypto.randomUUID();
  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      id: jobId,
      project_id: projectId,
      job_type: "recalibrar_velocity",
      status: "aguardando",
      payload: { project_id: projectId, velocity_mns: velocityMns },
    } as unknown as never);

  if (error) return { ok: false, error: `Erro ao criar job: ${error.message}` };
  return { ok: true, jobId };
}

export async function generateVisual(
  profileId: string,
  visualConfig: VisualConfig
): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const { data: profileRaw } = await supabase
    .from("gpr_profiles")
    .select("id, project_id")
    .eq("id", profileId)
    .maybeSingle();
  if (!profileRaw) return { ok: false, error: "Perfil não encontrado" };
  const profile = profileRaw as { id: string; project_id: string };

  const jobId = crypto.randomUUID();
  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      id: jobId,
      project_id: profile.project_id,
      job_type: "visual",
      status: "aguardando",
      payload: {
        profile_id: profileId,
        visual_config: { ...visualConfig, generated_by: user.id },
      },
    } as unknown as never);

  if (error) return { ok: false, error: `Erro ao criar job: ${error.message}` };
  return { ok: true, jobId };
}
