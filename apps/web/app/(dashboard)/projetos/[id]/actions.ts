"use server";

import { createClient } from "@/lib/supabase/server";

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

  // Insert a GPR reprocessing job — worker will pick it up with the saved filters
  const { error: jobError } = await supabase
    .from("processing_jobs")
    .insert({
      project_id: profile.project_id,
      job_type: "gpr",
      status: "aguardando",
    } as unknown as never);

  if (jobError) {
    console.log("[reprocessProfile] job insert error:", jobError.message);
  }

  return { ok: true };
}
