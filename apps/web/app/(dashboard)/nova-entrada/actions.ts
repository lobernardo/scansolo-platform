"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import type { Database } from "@/lib/types/database";

type ProjectInsert = Database["public"]["Tables"]["projects"]["Insert"];

export type CreateProjectState = { error: string } | null;

export async function createProject(
  _prev: CreateProjectState,
  formData: FormData
): Promise<CreateProjectState> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const nome = (formData.get("nome") as string)?.trim();
  const cliente = (formData.get("cliente") as string)?.trim();
  const local = (formData.get("local") as string)?.trim() || null;
  const estado = (formData.get("estado") as string)?.trim().toUpperCase().slice(0, 2);
  const data_levantamento = formData.get("data_levantamento") as string;
  const codigo_projeto = (formData.get("codigo_projeto") as string)?.trim() || null;
  const contato_nome = (formData.get("contato_nome") as string)?.trim() || null;
  const area_m2_raw = formData.get("area_m2") as string;
  const area_m2 = area_m2_raw ? parseFloat(area_m2_raw) : null;
  const antena_freq_mhz = 270;
  const tem_pipe_locator = formData.get("tem_pipe_locator") === "true";
  const auto_accept_ia = formData.get("auto_accept_ia") === "true";
  const skip_ia = formData.get("skip_ia") === "true";

  if (!nome || !cliente || !estado || !data_levantamento) {
    return { error: "Preencha todos os campos obrigatórios (nome, cliente, estado, data)." };
  }

  const payload: ProjectInsert = {
    nome,
    cliente,
    local,
    estado,
    data_levantamento,
    codigo_projeto,
    contato_nome,
    area_m2,
    antena_freq_mhz,
    tem_pipe_locator,
    auto_accept_ia,
    processing_config: skip_ia ? { skip_ia: true } : null,
    created_by: user.id,
    status: "aguardando_arquivos",
  };

  const { data, error } = await supabase
    .from("projects")
    .insert(payload as unknown as never)
    .select("id")
    .single();

  if (error) return { error: `Erro ao criar projeto: ${error.message}` };

  const row = data as { id: string };
  redirect(`/projetos/${row.id}/upload`);
}
