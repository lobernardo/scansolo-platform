"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export async function uploadDztFiles(projectId: string, formData: FormData) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const files = formData.getAll("files") as File[];
  if (!files.length || !files[0].size) {
    throw new Error("Nenhum arquivo selecionado");
  }

  const dztFiles = files.filter((f) =>
    f.name.toLowerCase().endsWith(".dzt")
  );
  if (!dztFiles.length) {
    throw new Error("Apenas arquivos .DZT são aceitos");
  }

  for (const file of dztFiles) {
    const bytes = await file.arrayBuffer();
    const storagePath = `${projectId}/${file.name}`;

    const { error: storageError } = await supabase.storage
      .from("gpr-uploads")
      .upload(storagePath, bytes, {
        contentType: "application/octet-stream",
        upsert: true,
      });

    if (storageError) throw new Error(storageError.message);

    const { error: dbError } = await supabase.from("project_files").insert({
      project_id: projectId,
      file_name: file.name,
      extension: "dzt",
      supabase_storage_path: storagePath,
      size_bytes: file.size,
      uploaded_by: user.id,
      status: "confirmado",
    } as unknown as never);

    if (dbError) throw new Error(dbError.message);
  }

  await supabase
    .from("projects")
    .update({ status: "aguardando_processamento" } as unknown as never)
    .eq("id", projectId);

  const { error: jobError } = await supabase
    .from("processing_jobs")
    .insert({ project_id: projectId, job_type: "gpr", status: "aguardando" } as unknown as never);

  if (jobError) throw new Error(jobError.message);

  redirect(`/projetos/${projectId}`);
}
