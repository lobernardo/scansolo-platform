"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function uploadDztFiles(
  projectId: string,
  formData: FormData
): Promise<{ ok: true } | { ok: false; error: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const files = formData.getAll("files") as File[];
  if (!files.length || !files[0].size)
    return { ok: false, error: "Nenhum arquivo selecionado" };

  const dztFiles = files.filter((f) => f.name.toLowerCase().endsWith(".dzt"));
  if (!dztFiles.length)
    return { ok: false, error: "Apenas arquivos .DZT são aceitos" };

  for (const file of dztFiles) {
    const bytes = await file.arrayBuffer();
    const storagePath = `${projectId}/${file.name}`;

    const { error: storageError } = await supabase.storage
      .from("gpr-uploads")
      .upload(storagePath, bytes, { contentType: "application/octet-stream", upsert: true });
    if (storageError) return { ok: false, error: storageError.message };

    const { error: dbError } = await supabase.from("project_files").insert({
      project_id: projectId,
      file_name: file.name,
      extension: "dzt",
      supabase_storage_path: storagePath,
      size_bytes: file.size,
      uploaded_by: user.id,
      status: "confirmado",
    } as unknown as never);
    if (dbError) return { ok: false, error: dbError.message };
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
