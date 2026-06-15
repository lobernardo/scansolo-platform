"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export type FilterState = {
  dewow: boolean;
  background_removal: boolean;
  bandpass: boolean;
  bandpass_low: number;
  bandpass_high: number;
  gain: boolean;
  gain_type: "linear" | "exponential" | "agc";
  contrast: number;
};

export async function reprocessProfile(
  profileId: string,
  filters: FilterState
): Promise<{ ok: boolean; error?: string }> {
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

  // Save custom filters to the profile (column may not exist in DB yet — log and continue)
  const { error: updateError } = await supabase
    .from("gpr_profiles")
    .update({ filtros_customizados: filters } as unknown as never)
    .eq("id", profileId);

  if (updateError) {
    console.log(
      "[reprocessProfile] filtros_customizados column not available yet:",
      updateError.message
    );
  }

  // Insert a GPR reprocessing job with profile_id + filters in payload
  const { error: jobError } = await supabase
    .from("processing_jobs")
    .insert({
      project_id: profile.project_id,
      job_type: "gpr",
      status: "aguardando",
      payload: { profile_id: profileId, filtros_customizados: filters },
    } as unknown as never);

  if (jobError) {
    console.log("[reprocessProfile] job insert error:", jobError.message);
  }

  return { ok: true };
}

export async function deleteProject(projectId: string): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  // Verify ownership / access
  const { data: proj } = await supabase
    .from("projects")
    .select("id")
    .eq("id", projectId)
    .maybeSingle();
  if (!proj) return { ok: false, error: "Projeto não encontrado" };

  // Delete in FK order
  const profiles = await supabase.from("gpr_profiles").select("id").eq("project_id", projectId);
  const profileIds = (profiles.data ?? []).map((p: { id: string }) => p.id);

  if (profileIds.length > 0) {
    const targets = await supabase.from("detected_targets").select("id").in("profile_id", profileIds);
    const targetIds = (targets.data ?? []).map((t: { id: string }) => t.id);

    if (targetIds.length > 0) {
      await supabase.from("technical_reviews").delete().in("target_id", targetIds);
      await supabase.from("ai_interpretations").delete().in("target_id", targetIds);
    }
    await supabase.from("ia_training_examples").delete().in("profile_id", profileIds);
    await supabase.from("detected_targets").delete().in("profile_id", profileIds);
  }

  await supabase.from("ia_training_examples").delete().eq("project_id", projectId);
  await supabase.from("project_files").delete().eq("project_id", projectId);
  await supabase.from("gpr_profiles").delete().eq("project_id", projectId);
  await supabase.from("cartography_outputs").delete().eq("project_id", projectId);
  await supabase.from("report_outputs").delete().eq("project_id", projectId);
  await supabase.from("processing_jobs").delete().eq("project_id", projectId);

  const { error } = await supabase.from("projects").delete().eq("id", projectId);
  if (error) return { ok: false, error: error.message };

  redirect("/projetos");
}
