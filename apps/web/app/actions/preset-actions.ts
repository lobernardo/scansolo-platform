"use server";

import { createClient, createAdminClient } from "@/lib/supabase/server";

export type GprPreset = {
  id: string;
  name: string;
  description: string | null;
  scientific_basis: string | null;
  target_scenario: string | null;
  antenna_freq_mhz: number | null;
  is_system: boolean;
  is_active: boolean;
  is_hidden_for_client: boolean;
  created_by: string | null;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  // Versionamento e validação (Fase D)
  version: number;
  parent_id: string | null;
  validated_by: string | null;
  validated_at: string | null;
  notes: string | null;
  dataset_validation: string | null;
  priority_order: number | null;
};

export type PresetUpsertData = {
  name: string;
  description?: string;
  scientific_basis?: string;
  target_scenario?: string;
  antenna_freq_mhz?: number;
  parameters: Record<string, unknown>;
  notes?: string;
  dataset_validation?: string;
  priority_order?: number;
  is_hidden_for_client?: boolean;
};

async function getRole(): Promise<string | null> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return null;
  const { data } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();
  return (data as { role?: string } | null)?.role ?? null;
}

export async function getPresets(): Promise<GprPreset[]> {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("gpr_presets")
    .select("*")
    .eq("is_active", true)
    .order("is_system", { ascending: false })
    .order("name");
  if (error) return [];
  return (data ?? []) as GprPreset[];
}

export async function getPresetById(id: string): Promise<GprPreset | null> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("gpr_presets")
    .select("*")
    .eq("id", id)
    .single();
  return (data as unknown as GprPreset) ?? null;
}

export async function createPreset(
  input: PresetUpsertData
): Promise<{ ok: boolean; id?: string; error?: string }> {
  const role = await getRole();
  if (!role || !["admin", "socio"].includes(role)) {
    return { ok: false, error: "Sem permissão." };
  }

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { data, error } = await supabase
    .from("gpr_presets")
    .insert({
      ...input,
      is_system: false,
      is_active: true,
      created_by: user!.id,
    } as never)
    .select("id")
    .single();

  if (error) return { ok: false, error: error.message };
  return { ok: true, id: (data as { id: string }).id };
}

export async function updatePreset(
  id: string,
  input: Partial<PresetUpsertData>
): Promise<{ ok: boolean; error?: string }> {
  const role = await getRole();
  if (!role || !["admin", "socio"].includes(role)) {
    return { ok: false, error: "Sem permissão." };
  }

  const supabase = await createClient();
  const { error } = await supabase
    .from("gpr_presets")
    .update({ ...input, updated_at: new Date().toISOString() } as never)
    .eq("id", id)
    .eq("is_system", false);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

export async function deletePreset(
  id: string
): Promise<{ ok: boolean; error?: string }> {
  const role = await getRole();
  if (!role || !["admin", "socio"].includes(role)) {
    return { ok: false, error: "Sem permissão." };
  }

  // Soft delete — preserva referências históricas em projects.preset_id
  const supabase = await createClient();
  const { error } = await supabase
    .from("gpr_presets")
    .update({ is_active: false } as never)
    .eq("id", id)
    .eq("is_system", false);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

export async function duplicatePreset(
  id: string,
  newName: string
): Promise<{ ok: boolean; id?: string; error?: string }> {
  const role = await getRole();
  if (!role || !["admin", "socio"].includes(role)) {
    return { ok: false, error: "Sem permissão." };
  }

  const original = await getPresetById(id);
  if (!original) return { ok: false, error: "Preset não encontrado." };

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { data, error } = await supabase
    .from("gpr_presets")
    .insert({
      name: newName,
      description: original.description,
      scientific_basis: original.scientific_basis,
      target_scenario: original.target_scenario,
      antenna_freq_mhz: original.antenna_freq_mhz,
      is_system: false,
      is_active: true,
      created_by: user!.id,
      parameters: original.parameters,
      parent_id: original.id,
      version: 1,
    } as never)
    .select("id")
    .single();

  if (error) return { ok: false, error: error.message };
  return { ok: true, id: (data as { id: string }).id };
}

export async function saveCurrentFiltersAsPreset(
  profileId: string,
  name: string,
  description?: string
): Promise<{ ok: boolean; id?: string; error?: string }> {
  const role = await getRole();
  if (!role || !["admin", "socio"].includes(role)) {
    return { ok: false, error: "Sem permissão." };
  }

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  // Busca o perfil e o projeto para obter filtros + preset base
  const profileRes = await supabase
    .from("gpr_profiles")
    .select("filtros_customizados, project_id")
    .eq("id", profileId)
    .single();
  const profile = profileRes.data as { filtros_customizados: unknown; project_id: string } | null;

  if (!profile) return { ok: false, error: "Perfil não encontrado." };

  const projectRes = await supabase
    .from("projects")
    .select("preset_id")
    .eq("id", profile.project_id)
    .single();
  const project = projectRes.data as { preset_id: string | null } | null;

  // Carrega parâmetros do preset base (se existir)
  let baseParams: Record<string, unknown> = {};
  if (project?.preset_id) {
    const presetRes = await supabase
      .from("gpr_presets")
      .select("parameters")
      .eq("id", project.preset_id)
      .single();
    const presetData = presetRes.data as { parameters: unknown } | null;
    if (presetData?.parameters) baseParams = presetData.parameters as Record<string, unknown>;
  }

  // Converte FilterState → pipeline parameter format
  const f = (profile.filtros_customizados ?? {}) as Record<string, unknown>;
  const overrides: Record<string, unknown> = {};
  if (f.bandpass === false) {
    overrides.bandpass_low_mhz = 0;
  } else {
    if (f.bandpass_low != null) overrides.bandpass_low_mhz = f.bandpass_low;
    if (f.bandpass_high != null) overrides.bandpass_high_mhz = f.bandpass_high;
  }
  if (f.velocity_mns != null) overrides.velocity_mns = f.velocity_mns;
  if (f.contrast != null) overrides.contrast = f.contrast;
  if (f.depth_preview_m != null) overrides.depth_preview_m = f.depth_preview_m;
  if (f.agc_window_preview != null) overrides.agc_window_preview = f.agc_window_preview;
  if (f.det_amp_threshold != null) overrides.det_amp_threshold = f.det_amp_threshold;
  if (f.det_h_max_m != null) overrides.det_h_max_m = f.det_h_max_m;
  if (f.det_min_score_csv != null) overrides.det_min_score_csv = f.det_min_score_csv;
  if (f.det_depth_min_m != null) overrides.det_depth_min_m = f.det_depth_min_m;

  const mergedParams = { ...baseParams, ...overrides };

  const { data, error } = await supabase
    .from("gpr_presets")
    .insert({
      name: name.trim(),
      description: description?.trim() || undefined,
      is_system: false,
      is_active: true,
      created_by: user!.id,
      parameters: mergedParams,
      parent_id: project?.preset_id ?? null,
      version: 1,
    } as never)
    .select("id")
    .single();

  if (error) return { ok: false, error: error.message };
  return { ok: true, id: (data as { id: string }).id };
}

export async function validatePreset(
  id: string,
  datasetValidation: string
): Promise<{ ok: boolean; error?: string }> {
  const role = await getRole();
  if (!role || !["admin", "socio"].includes(role)) {
    return { ok: false, error: "Sem permissão." };
  }

  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  const { error } = await supabase
    .from("gpr_presets")
    .update({
      validated_by: user!.id,
      validated_at: new Date().toISOString(),
      dataset_validation: datasetValidation,
      updated_at: new Date().toISOString(),
    } as never)
    .eq("id", id)
    .eq("is_system", false);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}
