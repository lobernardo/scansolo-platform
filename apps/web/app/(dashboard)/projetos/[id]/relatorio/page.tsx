export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ProjectStatusPoller } from "../ProjectStatusPoller";
import { RelatorioClient } from "./RelatorioClient";
import { regenerateRelatorio } from "./actions";

const ALLOWED = new Set([
  "aguardando_relatorio",
  "relatorio_em_andamento",
  "relatorio_gerado",
  "aguardando_aprovacao",
  "finalizado",
]);

export default async function RelatorioPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ regenerar?: string }>;
}) {
  const { id } = await params;
  const sp = await searchParams;
  const supabase = await createClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: projectRaw } = await supabase
    .from("projects")
    .select("id, nome, status, codigo_projeto")
    .eq("id", id)
    .single();
  const project = projectRaw as {
    id: string;
    nome: string;
    status: string;
    codigo_projeto: string | null;
  } | null;

  if (!project) redirect("/projetos");
  if (!ALLOWED.has(project.status)) redirect(`/projetos/${id}`);

  if (sp.regenerar === "1") {
    await regenerateRelatorio(id);
  }

  // Running job?
  const { data: jobsRaw } = await supabase
    .from("processing_jobs")
    .select("id, status")
    .eq("project_id", id)
    .eq("job_type", "relatorio")
    .order("created_at", { ascending: false })
    .limit(1);
  const latestJob = ((jobsRaw ?? []) as { id: string; status: string }[])[0] ?? null;
  const isJobRunning = latestJob?.status === "aguardando" || latestJob?.status === "processando";

  // Latest report output
  const { data: outputRaw } = await supabase
    .from("report_outputs")
    .select("*")
    .eq("project_id", id)
    .order("created_at", { ascending: false })
    .limit(1);
  const report = ((outputRaw ?? []) as Record<string, unknown>[])[0] ?? null;

  return (
    <div>
      <div className="max-w-2xl mx-auto px-4 pt-6 flex items-center gap-2 text-sm text-gray-500">
        <Link href="/projetos" className="hover:text-gray-700">Projetos</Link>
        <span className="text-gray-300">/</span>
        <Link href={`/projetos/${id}`} className="hover:text-gray-700">{project.nome}</Link>
        <span className="text-gray-300">/</span>
        <span className="text-gray-700">Relatório</span>
      </div>

      {isJobRunning && <ProjectStatusPoller />}

      <div className="max-w-2xl mx-auto px-4 pt-5 pb-2 flex items-center justify-between">
        <h1 className="text-xl font-bold">Relatório Técnico</h1>
        <span className="text-sm text-gray-500">{project.nome}</span>
      </div>

      <RelatorioClient
        project={project}
        report={report as Parameters<typeof RelatorioClient>[0]["report"]}
        isJobRunning={isJobRunning}
      />
    </div>
  );
}
