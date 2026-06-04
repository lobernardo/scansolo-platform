"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function startRelatorio(projectId: string) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      project_id: projectId,
      job_type: "relatorio",
      status: "aguardando",
    } as unknown as never);

  if (error) throw new Error(error.message);

  await supabase
    .from("projects")
    .update({ status: "aguardando_relatorio" } as unknown as never)
    .eq("id", projectId);

  redirect(`/projetos/${projectId}/relatorio`);
}

export async function approveRelatorio(
  projectId: string,
  reportOutputId: string
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const { error } = await supabase
    .from("report_outputs")
    .update({
      status: "aprovado",
      approved_by: user.id,
      approved_at: new Date().toISOString(),
    } as unknown as never)
    .eq("id", reportOutputId);

  if (error) return { ok: false, error: error.message };

  await supabase
    .from("projects")
    .update({ status: "finalizado" } as unknown as never)
    .eq("id", projectId);

  return { ok: true };
}

export async function generateInferenceReport(projectId: string) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  await supabase
    .from("processing_jobs")
    .insert({
      project_id: projectId,
      job_type: "inferencias",
      status: "aguardando",
    } as unknown as never);

  redirect(`/projetos/${projectId}`);
}

export async function regenerateRelatorio(projectId: string) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  await supabase
    .from("processing_jobs")
    .insert({
      project_id: projectId,
      job_type: "relatorio",
      status: "aguardando",
    } as unknown as never);

  await supabase
    .from("projects")
    .update({ status: "aguardando_relatorio" } as unknown as never)
    .eq("id", projectId);

  redirect(`/projetos/${projectId}/relatorio`);
}
