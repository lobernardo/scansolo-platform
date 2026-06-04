import { createClient } from "@/lib/supabase/server";
import { redirect, notFound } from "next/navigation";
import { InterpretadaClient } from "./InterpretadaClient";

export default async function InterpretadaPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id: projectId } = await params;
  const supabase = await createClient();

  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: projectRaw } = await supabase
    .from("projects")
    .select("id, nome, status")
    .eq("id", projectId)
    .single();

  if (!projectRaw) notFound();
  const project = projectRaw as { id: string; nome: string; status: string };

  const { data: profilesRaw } = await supabase
    .from("gpr_profiles")
    .select(
      "id, arquivo_dzt, imagem_processada_url, imagem_interpretada_url, imagem_interpretada_status"
    )
    .eq("project_id", projectId)
    .order("created_at", { ascending: true });

  const profiles = (profilesRaw ?? []) as Array<{
    id: string;
    arquivo_dzt: string | null;
    imagem_processada_url: string | null;
    imagem_interpretada_url: string | null;
    imagem_interpretada_status: string | null;
  }>;

  return (
    <InterpretadaClient
      project={{ id: project.id, nome: project.nome }}
      profiles={profiles}
    />
  );
}
