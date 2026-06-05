export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";
import { ProjetosTable } from "./ProjetosTable";
import type { ProjectWithCount } from "./ProjetosTable";

type ProjectRow = Database["public"]["Tables"]["projects"]["Row"];

export default async function ProjetosPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const [{ data: projectsRaw }, { data: profilesRaw }] = await Promise.all([
    supabase
      .from("projects")
      .select("id, nome, cliente, estado, status, created_at")
      .order("created_at", { ascending: false }),
    supabase.from("gpr_profiles").select("project_id"),
  ]);

  // Count profiles per project
  const countMap: Record<string, number> = {};
  for (const p of profilesRaw ?? []) {
    const row = p as { project_id: string };
    countMap[row.project_id] = (countMap[row.project_id] ?? 0) + 1;
  }

  const projects: ProjectWithCount[] = (
    (projectsRaw ?? []) as Array<
      Pick<ProjectRow, "id" | "nome" | "cliente" | "estado" | "created_at"> & {
        status: string;
      }
    >
  ).map((p) => ({
    id: p.id,
    nome: p.nome,
    cliente: p.cliente,
    estado: p.estado,
    status: p.status,
    created_at: p.created_at,
    profileCount: countMap[p.id] ?? 0,
  }));

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-100">Projetos</h1>
        <Link
          href="/nova-entrada"
          className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
        >
          Nova entrada
        </Link>
      </div>

      {projects.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum projeto ainda.</p>
      ) : (
        <ProjetosTable projects={projects} />
      )}
    </div>
  );
}
