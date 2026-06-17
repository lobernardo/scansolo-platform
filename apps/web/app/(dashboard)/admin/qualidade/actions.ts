"use server";

import { createClient } from "@/lib/supabase/server";

export async function dispararRecalibracao(): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  // Busca qualquer project_id para satisfazer a FK (o job não usa o campo)
  const { data: proj } = await supabase
    .from("projects")
    .select("id")
    .limit(1)
    .single();

  const { error } = await supabase.from("processing_jobs").insert({
    job_type: "recalibrar",
    status: "aguardando",
    payload: {},
    ...(proj ? { project_id: proj.id } : {}),
  } as unknown as never);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}
