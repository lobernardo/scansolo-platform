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
  created_by: string | null;
  parameters: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type PresetUpsertData = {
  name: string;
  description?: string;
  scientific_basis?: string;
  target_scenario?: string;
  antenna_freq_mhz?: number;
  parameters: Record<string, unknown>;
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
  return (data as GprPreset) ?? null;
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
    } as never)
    .select("id")
    .single();

  if (error) return { ok: false, error: error.message };
  return { ok: true, id: (data as { id: string }).id };
}
