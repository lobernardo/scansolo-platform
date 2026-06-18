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
      processing_config: config,
    } as unknown as never)
    .eq("id", projectId);

  const { error } = await supabase
    .from("processing_jobs")
    .insert({ project_id: projectId, job_type: "gpr", status: "aguardando" } as unknown as never);

  if (error) throw new Error(error.message);

  redirect(`/projetos/${projectId}`);
}

/**
 * Inicia o processamento SEM alterar processing_config.
 * Usado quando o projeto já tem preset_id configurado via Nova Entrada.
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
