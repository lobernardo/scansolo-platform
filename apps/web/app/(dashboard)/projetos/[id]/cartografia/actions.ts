"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function startCartografia(projectId: string) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  // Create the cartografia job
  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      project_id: projectId,
      job_type: "cartografia",
      status: "aguardando",
    } as unknown as never);

  if (error) throw new Error(error.message);

  await supabase
    .from("projects")
    .update({ status: "aguardando_cartografia" } as unknown as never)
    .eq("id", projectId);

  redirect(`/projetos/${projectId}/cartografia`);
}

export async function confirmCartografia(
  projectId: string,
  cartographyOutputId: string
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const now = new Date().toISOString();

  const { error: outErr } = await supabase
    .from("cartography_outputs")
    .update({
      status: "concluido",
      confirmed_by: user.id,
      confirmed_at: now,
    } as unknown as never)
    .eq("id", cartographyOutputId);

  if (outErr) return { ok: false, error: outErr.message };

  await supabase
    .from("projects")
    .update({ status: "cartografia_concluida" } as unknown as never)
    .eq("id", projectId);

  return { ok: true };
}

export async function regenerateCartografia(projectId: string) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      project_id: projectId,
      job_type: "cartografia",
      status: "aguardando",
    } as unknown as never);

  if (error) throw new Error(error.message);

  await supabase
    .from("projects")
    .update({ status: "aguardando_cartografia" } as unknown as never)
    .eq("id", projectId);

  redirect(`/projetos/${projectId}/cartografia`);
}
