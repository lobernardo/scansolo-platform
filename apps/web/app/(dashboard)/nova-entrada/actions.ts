"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import type { Database } from "@/lib/types/database";

type ProjectInsert = Database["public"]["Tables"]["projects"]["Insert"];

export async function createProject(formData: FormData) {
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

  if (!nome || !cliente || !estado || !data_levantamento) {
    throw new Error("Campos obrigatórios ausentes");
  }

  const payload: ProjectInsert = {
    nome,
    cliente,
    local,
    estado,
    data_levantamento,
    created_by: user.id,
    status: "aguardando_arquivos",
  };

  const { data, error } = await supabase
    .from("projects")
    .insert(payload as unknown as never)
    .select("id")
    .single();

  if (error) throw new Error(error.message);

  const row = data as { id: string };
  redirect(`/projetos/${row.id}/upload`);
}
