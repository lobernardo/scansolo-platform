export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ProjectStatusPoller } from "../ProjectStatusPoller";
import { CartografiaClient } from "./CartografiaClient";
import { regenerateCartografia } from "./actions";

const ALLOWED = new Set([
  "aguardando_cartografia",
  "cartografia_concluida",
  "cartografia_pendente_dados",
]);

export default async function CartografiaPage({
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
    .select("id, nome, status")
    .eq("id", id)
    .single();
  const project = projectRaw as { id: string; nome: string; status: string } | null;

  if (!project) redirect("/projetos");
  if (!ALLOWED.has(project.status)) redirect(`/projetos/${id}`);

  // Handle ?regenerar=1 via form action
  if (sp.regenerar === "1") {
    await regenerateCartografia(id);
  }

  // Is there a running cartografia job?
  const { data: jobsRaw } = await supabase
    .from("processing_jobs")
    .select("id, status")
    .eq("project_id", id)
    .eq("job_type", "cartografia")
    .order("created_at", { ascending: false })
    .limit(1);
  const latestJob = ((jobsRaw ?? []) as { id: string; status: string }[])[0] ?? null;
  const isJobRunning = latestJob?.status === "aguardando" || latestJob?.status === "processando";

  // Latest cartography output
  const { data: outputRaw } = await supabase
    .from("cartography_outputs")
    .select("*")
    .eq("project_id", id)
    .order("created_at", { ascending: false })
    .limit(1);
  const output = ((outputRaw ?? []) as Record<string, unknown>[])[0] ?? null;

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const downloadBaseUrl = `${supabaseUrl}/storage/v1/object/public`;

  return (
    <div>
      {/* Breadcrumb */}
      <div className="max-w-3xl mx-auto px-4 pt-6 flex items-center gap-2 text-sm text-slate-500">
        <Link href="/projetos" className="hover:text-slate-300 transition-colors">Projetos</Link>
        <span className="text-slate-700">/</span>
        <Link href={`/projetos/${id}`} className="hover:text-slate-300 transition-colors">{project.nome}</Link>
        <span className="text-slate-700">/</span>
        <span className="text-slate-300">Cartografia</span>
      </div>

      {/* Auto-refresh while job is running */}
      {isJobRunning && <ProjectStatusPoller />}

      {/* Header */}
      <div className="max-w-3xl mx-auto px-4 pt-5 pb-2 flex items-center justify-between">
        <h1 className="text-xl font-bold text-slate-100">Arquivos Cartográficos</h1>
        <span className="text-sm text-slate-400">{project.nome}</span>
      </div>

      <CartografiaClient
        project={{ id: project.id, nome: project.nome }}
        output={output as Parameters<typeof CartografiaClient>[0]["output"]}
        downloadBaseUrl={downloadBaseUrl}
        isJobRunning={isJobRunning}
      />
    </div>
  );
}
