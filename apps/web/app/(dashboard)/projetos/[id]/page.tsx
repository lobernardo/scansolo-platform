export const dynamic = "force-dynamic";

import { Fragment } from "react";
import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";
import { ProjectStatusPoller } from "./ProjectStatusPoller";
import { acceptAllIaSuggestions } from "./revisao/actions";
import { startCartografia } from "./cartografia/actions";
import { startRelatorio, generateInferenceReport } from "./relatorio/actions";
import { ProjectDetailClient } from "./ProjectDetailClient";
import type { DownloadFile } from "./ProjectDetailClient";
import { DeleteProjectButton } from "./DeleteProjectButton";

type ProjectRow = Database["public"]["Tables"]["projects"]["Row"];
type GprProfileRow = Database["public"]["Tables"]["gpr_profiles"]["Row"];
type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];
type JobRow = Database["public"]["Tables"]["processing_jobs"]["Row"];
type AiInterpretationRow = Database["public"]["Tables"]["ai_interpretations"]["Row"];

const PROCESSING_STATUSES = new Set([
  "aguardando_processamento",
  "processando_gpr",
  "processando_ia",
  "processando_interpretada",
  "aguardando_cartografia",
  "aguardando_relatorio",
  "relatorio_em_andamento",
]);

const STATUS_LABEL: Record<string, string> = {
  criado: "Criado",
  aguardando_arquivos: "Aguardando arquivos",
  aguardando_processamento: "Aguardando processamento",
  processando_gpr: "Processando GPR",
  gpr_concluido: "GPR concluído",
  processando_ia: "Processando IA",
  ia_concluida: "IA concluída",
  revisao_em_andamento: "Revisão em andamento",
  revisao_concluida: "Revisão concluída",
  aguardando_cartografia: "Cartografia em andamento",
  cartografia_concluida: "Cartografia concluída",
  cartografia_pendente_dados: "Cartografia — dados pendentes",
  aguardando_relatorio: "Gerando relatório",
  relatorio_em_andamento: "Relatório em andamento",
  relatorio_gerado: "Relatório gerado",
  processando_interpretada: "Gerando imagem interpretada",
  interpretada_gerada: "Imagem interpretada gerada",
  aguardando_aprovacao: "Aguardando aprovação",
  finalizado: "Finalizado",
  erro: "Erro",
};

const STATUS_COLOR: Record<string, string> = {
  criado: "bg-slate-700 text-slate-400 border border-slate-600",
  aguardando_arquivos: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  aguardando_processamento: "bg-blue-500/15 text-blue-400 border border-blue-500/30",
  processando_gpr: "bg-blue-500/15 text-blue-400 border border-blue-500/30",
  gpr_concluido: "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30",
  processando_ia: "bg-violet-500/15 text-violet-400 border border-violet-500/30",
  ia_concluida: "bg-violet-500/15 text-violet-400 border border-violet-500/30",
  revisao_em_andamento: "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  revisao_concluida: "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  aguardando_cartografia: "bg-indigo-500/15 text-indigo-400 border border-indigo-500/30",
  cartografia_concluida: "bg-indigo-500/15 text-indigo-400 border border-indigo-500/30",
  cartografia_pendente_dados: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  aguardando_relatorio: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  relatorio_em_andamento: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  relatorio_gerado: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  processando_interpretada: "bg-teal-500/15 text-teal-400 border border-teal-500/30",
  interpretada_gerada: "bg-teal-500/15 text-teal-400 border border-teal-500/30",
  aguardando_aprovacao: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  finalizado: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
  erro: "bg-red-500/15 text-red-400 border border-red-500/30",
};

async function trySignedUrl(
  supabase: Awaited<ReturnType<typeof createClient>>,
  bucket: string,
  path: string | null | undefined
): Promise<string | null> {
  if (!path) return null;
  try {
    const { data } = await supabase.storage.from(bucket).createSignedUrl(path, 3600);
    return data?.signedUrl ?? null;
  } catch {
    return null;
  }
}

export default async function ProjetoDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data: projectData } = await supabase
    .from("projects")
    .select("*")
    .eq("id", id)
    .single();

  if (!projectData) redirect("/projetos");
  const project = projectData as ProjectRow;

  const { data: jobsData } = await supabase
    .from("processing_jobs")
    .select("*")
    .eq("project_id", id)
    .order("created_at");
  const jobs = (jobsData ?? []) as JobRow[];

  const { data: profilesData } = await supabase
    .from("gpr_profiles")
    .select("*")
    .eq("project_id", id)
    .order("created_at");
  const profiles = (profilesData ?? []) as GprProfileRow[];

  const profileIds = profiles.map((p) => p.id);
  let targets: DetectedTargetRow[] = [];
  if (profileIds.length > 0) {
    const { data: targetsData } = await supabase
      .from("detected_targets")
      .select("*")
      .in("profile_id", profileIds)
      .order("rank");
    targets = (targetsData ?? []) as DetectedTargetRow[];
  }

  const targetIds = targets.map((t) => t.id);
  let aiInterpretations: AiInterpretationRow[] = [];
  if (targetIds.length > 0) {
    const { data: aiData } = await supabase
      .from("ai_interpretations")
      .select("*")
      .in("target_id", targetIds);
    aiInterpretations = (aiData ?? []) as AiInterpretationRow[];
  }
  const aiByTargetId = Object.fromEntries(aiInterpretations.map((ai) => [ai.target_id, ai]));

  // Cartography and report outputs
  const { data: cartRaw } = await supabase
    .from("cartography_outputs")
    .select("*")
    .eq("project_id", id)
    .order("created_at", { ascending: false })
    .limit(1);
  const cartOutput = ((cartRaw ?? []) as Record<string, unknown>[])[0] ?? null;

  const { data: reportRaw } = await supabase
    .from("report_outputs")
    .select("*")
    .eq("project_id", id)
    .order("created_at", { ascending: false })
    .limit(1);
  const reportOutput = ((reportRaw ?? []) as Record<string, unknown>[])[0] ?? null;

  // Generate signed URLs for downloadable files
  const [dxfUrl, kmlUrl, docxUrl, pdfUrl] = await Promise.all([
    trySignedUrl(supabase, "gpr-tabelas", cartOutput?.dxf_dropbox_path as string | null),
    trySignedUrl(supabase, "gpr-tabelas", cartOutput?.kml_dropbox_path as string | null),
    trySignedUrl(supabase, "gpr-tabelas", reportOutput?.docx_dropbox_path as string | null),
    trySignedUrl(supabase, "gpr-tabelas", reportOutput?.pdf_dropbox_path as string | null),
  ]);

  // Fall back to stored public URL if signed URL failed
  const downloadFiles: DownloadFile[] = [
    {
      label: "Relatório — DOCX (Word)",
      url: docxUrl ?? (reportOutput?.docx_storage_url as string | null) ?? null,
      ext: "docx",
    },
    {
      label: "Relatório — PDF",
      url: pdfUrl ?? (reportOutput?.pdf_storage_url as string | null) ?? null,
      ext: "pdf",
    },
    {
      label: "Cartografia — DXF (AutoCAD)",
      url: dxfUrl ?? (cartOutput?.dxf_storage_url as string | null) ?? null,
      ext: "dxf",
    },
    {
      label: "Cartografia — KML (Google Earth)",
      url: kmlUrl ?? (cartOutput?.kml_storage_url as string | null) ?? null,
      ext: "kml",
    },
  ];

  // Inference report state
  const inferenciasJob = jobs.findLast((j) => j.job_type === "inferencias") ?? null;
  const inferenciasGerada = inferenciasJob?.status === "concluido";
  const inferenciasProcessando =
    inferenciasJob?.status === "aguardando" ||
    (inferenciasJob?.status ?? "").startsWith("processando");
  const inferenciasUrl = inferenciasGerada
    ? await trySignedUrl(supabase, "gpr-tabelas", `${id}/inferencias.txt`)
    : null;
  const gprDone = profiles.length > 0;

  const isProcessing = PROCESSING_STATUSES.has(project.status);
  const gprJob = jobs.find((j) => j.job_type === "gpr");
  const iaJob = jobs.find((j) => j.job_type === "ia");
  const iaDone = project.status === "ia_concluida" || iaJob?.status === "concluido";
  const hasAiResults = aiInterpretations.length > 0;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href="/projetos" className="text-sm text-slate-500 hover:text-slate-300 transition-colors">
              Projetos
            </Link>
            <span className="text-slate-700">/</span>
            <span className="text-sm text-slate-300">{project.nome}</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100">{project.nome}</h1>
          <p className="text-sm text-slate-400 mt-1">
            {project.cliente}
            {project.local ? ` — ${project.local}` : ""} · {project.estado}
            {(project as unknown as Record<string, unknown>).codigo_projeto
              ? ` · ${(project as unknown as Record<string, unknown>).codigo_projeto}`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <StatusBadge status={project.status} />
          <DeleteProjectButton projectId={project.id} />
        </div>
      </div>

      {/* Pipeline progress */}
      <PipelineProgress status={project.status} />

      {/* Auto-refresh while processing */}
      {isProcessing && <ProjectStatusPoller />}

      {/* Upload prompt */}
      {project.status === "aguardando_arquivos" && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4">
          <p className="text-sm text-amber-400 mb-3">
            Projeto criado. Faça o upload dos arquivos .DZT para iniciar o processamento.
          </p>
          <Link
            href={`/projetos/${id}/upload`}
            className="inline-block rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
          >
            Upload de arquivos
          </Link>
        </div>
      )}

      {/* Processing state */}
      {isProcessing && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-4 flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-blue-400 animate-pulse shrink-0" />
          <p className="text-sm text-blue-400">
            Processamento em andamento… Esta página atualiza automaticamente.
          </p>
        </div>
      )}

      {/* GPR error */}
      {project.status === "erro" && gprJob?.job_type === "gpr" && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm font-medium text-red-400 mb-1">Erro no processamento GPR</p>
          {gprJob?.error_message && (
            <p className="text-xs text-red-400 font-mono break-all">{gprJob.error_message}</p>
          )}
        </div>
      )}

      {/* IA done — decision banner */}
      {iaDone && hasAiResults && project.status === "ia_concluida" && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 space-y-3">
          <p className="text-sm text-emerald-400">
            <span className="font-medium">Interpretação IA concluída.</span>{" "}
            {aiInterpretations.length} alvo
            {aiInterpretations.length !== 1 ? "s" : ""} interpretado
            {aiInterpretations.length !== 1 ? "s" : ""} por GPT-4o.
          </p>
          <div className="flex gap-3 flex-wrap">
            <form action={acceptAllIaSuggestions.bind(null, project.id)}>
              <button
                type="submit"
                className="rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition-colors"
              >
                Aceitar todas as sugestões da IA
              </button>
            </form>
            <Link
              href={`/projetos/${id}/revisao`}
              className="rounded-md bg-slate-800 border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 transition-colors"
            >
              Revisar alvos manualmente
            </Link>
          </div>
        </div>
      )}

      {/* Revisão em andamento */}
      {project.status === "revisao_em_andamento" && (
        <div className="rounded-xl border border-orange-500/30 bg-orange-500/10 p-4 flex items-center justify-between">
          <p className="text-sm text-orange-400">
            <span className="font-medium">Revisão técnica em andamento.</span>
          </p>
          <Link
            href={`/projetos/${id}/revisao`}
            className="text-sm font-medium text-orange-400 underline underline-offset-2 hover:text-orange-300"
          >
            Continuar revisão →
          </Link>
        </div>
      )}

      {/* Revisão concluída — iniciar cartografia */}
      {project.status === "revisao_concluida" && (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4 space-y-3">
          <p className="text-sm text-indigo-400">
            <span className="font-medium">Revisão técnica concluída.</span>{" "}
            Pronto para gerar os arquivos cartográficos.
          </p>
          <form action={startCartografia.bind(null, project.id)}>
            <button
              type="submit"
              className="rounded-md bg-indigo-500 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-400 transition-colors"
            >
              Gerar arquivos cartográficos
            </button>
          </form>
        </div>
      )}

      {/* Interpretada em processamento */}
      {project.status === "processando_interpretada" && (
        <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 p-4 flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-teal-400 animate-pulse shrink-0" />
          <p className="text-sm text-teal-400">
            Gerando imagem interpretada… Esta página atualiza automaticamente.
          </p>
        </div>
      )}

      {/* Interpretada gerada — Amilson revisa */}
      {project.status === "interpretada_gerada" && (
        <div className="rounded-xl border border-teal-500/30 bg-teal-500/10 p-4 space-y-3">
          <p className="text-sm text-teal-400">
            <span className="font-medium">Imagem interpretada gerada.</span>{" "}
            Revise e aprove a interpretação antes de gerar a cartografia.
          </p>
          <div className="flex gap-3 flex-wrap">
            <Link
              href={`/projetos/${id}/interpretada`}
              className="rounded-md bg-teal-500 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-400 transition-colors"
            >
              Revisar imagem interpretada →
            </Link>
            <form action={startCartografia.bind(null, project.id)}>
              <button
                type="submit"
                className="rounded-md bg-slate-800 border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 transition-colors"
              >
                Pular e gerar cartografia
              </button>
            </form>
          </div>
        </div>
      )}

      {/* Cartografia em andamento */}
      {project.status === "aguardando_cartografia" && (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-indigo-400 animate-pulse shrink-0" />
            <p className="text-sm text-indigo-400">Gerando arquivos cartográficos…</p>
          </div>
          <Link
            href={`/projetos/${id}/cartografia`}
            className="text-sm font-medium text-indigo-400 underline underline-offset-2 hover:text-indigo-300"
          >
            Ver resultado →
          </Link>
        </div>
      )}

      {/* Cartografia pendente dados */}
      {project.status === "cartografia_pendente_dados" && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 flex items-center justify-between">
          <p className="text-sm text-amber-400">
            <span className="font-medium">Cartografia — dados pendentes.</span>{" "}
            Arquivos de referência necessários.
          </p>
          <Link
            href={`/projetos/${id}/cartografia`}
            className="text-sm font-medium text-amber-400 underline underline-offset-2 hover:text-amber-300"
          >
            Ver detalhes →
          </Link>
        </div>
      )}

      {/* Cartografia concluída — iniciar relatório */}
      {project.status === "cartografia_concluida" && (
        <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/10 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-indigo-400">
              <span className="font-medium">Cartografia concluída.</span>
            </p>
            <Link
              href={`/projetos/${id}/cartografia`}
              className="text-xs font-medium text-indigo-400 underline underline-offset-2 hover:text-indigo-300"
            >
              Ver arquivos
            </Link>
          </div>
          <form action={startRelatorio.bind(null, project.id)}>
            <button
              type="submit"
              className="rounded-md bg-purple-500 px-4 py-2 text-sm font-semibold text-white hover:bg-purple-400 transition-colors"
            >
              Gerar relatório
            </button>
          </form>
        </div>
      )}

      {/* Relatório em andamento */}
      {(project.status === "aguardando_relatorio" ||
        project.status === "relatorio_em_andamento") && (
        <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-purple-400 animate-pulse shrink-0" />
            <p className="text-sm text-purple-400">Gerando relatório…</p>
          </div>
          <Link
            href={`/projetos/${id}/relatorio`}
            className="text-sm font-medium text-purple-400 underline underline-offset-2 hover:text-purple-300"
          >
            Ver status →
          </Link>
        </div>
      )}

      {/* Relatório gerado */}
      {project.status === "relatorio_gerado" && (
        <div className="rounded-xl border border-purple-500/30 bg-purple-500/10 p-4 flex items-center justify-between">
          <p className="text-sm text-purple-400">
            <span className="font-medium">Relatório gerado.</span>{" "}
            Pronto para revisão e aprovação.
          </p>
          <Link
            href={`/projetos/${id}/relatorio`}
            className="text-sm font-medium text-purple-400 underline underline-offset-2 hover:text-purple-300"
          >
            Abrir relatório →
          </Link>
        </div>
      )}

      {/* Finalizado */}
      {project.status === "finalizado" && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 flex items-center justify-between">
          <p className="text-sm text-emerald-400">
            <span className="font-medium">Projeto finalizado.</span> Relatório aprovado.
          </p>
          <Link
            href={`/projetos/${id}/relatorio`}
            className="text-sm font-medium text-emerald-400 underline underline-offset-2 hover:text-emerald-300"
          >
            Ver relatório →
          </Link>
        </div>
      )}

      {/* IA error */}
      {iaJob?.status === "erro" && iaJob.error_message && (
        <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <p className="text-sm font-medium text-red-400 mb-1">Erro na interpretação IA</p>
          <p className="text-xs text-red-400 font-mono break-all">{iaJob.error_message}</p>
        </div>
      )}

      {/* Jobs timeline */}
      {jobs.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {jobs.map((job) => (
            <JobChip key={job.id} job={job} />
          ))}
        </div>
      )}

      {/* Relatório de inferências (sob demanda) */}
      {gprDone && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-slate-100">Relatório de inferências</p>
            <p className="text-xs text-slate-500 mt-0.5">
              Tabela alta + média confiança para revisão técnica (.txt)
            </p>
          </div>
          {inferenciasUrl ? (
            <a
              href={inferenciasUrl}
              download="inferencias.txt"
              className="shrink-0 rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
            >
              ↓ Baixar inferências
            </a>
          ) : inferenciasProcessando ? (
            <span className="shrink-0 text-sm text-slate-400">Gerando…</span>
          ) : (
            <form action={generateInferenceReport.bind(null, project.id)}>
              <button
                type="submit"
                className="shrink-0 rounded-md bg-slate-800 border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 transition-colors"
              >
                Gerar relatório de inferências
              </button>
            </form>
          )}
        </div>
      )}

      {/* Interactive sections: profile cards + targets table + files */}
      {profiles.length > 0 || downloadFiles.some((f) => f.url) ? (
        <ProjectDetailClient
          profiles={profiles}
          targets={targets}
          aiByTargetId={aiByTargetId}
          downloadFiles={downloadFiles}
        />
      ) : (
        !isProcessing && project.status !== "aguardando_arquivos" && (
          <p className="text-sm text-slate-500">Nenhum perfil GPR disponível.</p>
        )
      )}
    </div>
  );
}

// ── Pipeline progress bar ─────────────────────────────────────────────────────

type StageState = "done" | "active" | "pending";

const PIPELINE_STAGES = [
  { id: "gpr", label: "GPR" },
  { id: "ia", label: "IA" },
  { id: "revisao", label: "Revisão" },
  { id: "cartografia", label: "Cartografia" },
  { id: "relatorio", label: "Relatório" },
] as const;

type StageId = (typeof PIPELINE_STAGES)[number]["id"];

function getStageState(stageId: StageId, status: string): StageState {
  const GPR_DONE = new Set(["gpr_concluido","processando_ia","ia_concluida","revisao_em_andamento","revisao_concluida","processando_interpretada","interpretada_gerada","aguardando_cartografia","cartografia_concluida","cartografia_pendente_dados","aguardando_relatorio","relatorio_em_andamento","relatorio_gerado","finalizado"]);
  const IA_DONE  = new Set(["ia_concluida","revisao_em_andamento","revisao_concluida","processando_interpretada","interpretada_gerada","aguardando_cartografia","cartografia_concluida","cartografia_pendente_dados","aguardando_relatorio","relatorio_em_andamento","relatorio_gerado","finalizado"]);
  const REV_DONE = new Set(["revisao_concluida","processando_interpretada","interpretada_gerada","aguardando_cartografia","cartografia_concluida","cartografia_pendente_dados","aguardando_relatorio","relatorio_em_andamento","relatorio_gerado","finalizado"]);
  const CAR_DONE = new Set(["cartografia_concluida","aguardando_relatorio","relatorio_em_andamento","relatorio_gerado","finalizado"]);
  const REL_DONE = new Set(["relatorio_gerado","finalizado"]);

  const GPR_ACT = new Set(["aguardando_processamento","processando_gpr"]);
  const IA_ACT  = new Set(["processando_ia"]);
  const REV_ACT = new Set(["ia_concluida","revisao_em_andamento"]);
  const CAR_ACT = new Set(["revisao_concluida","aguardando_cartografia","cartografia_pendente_dados"]);
  const REL_ACT = new Set(["cartografia_concluida","aguardando_relatorio","relatorio_em_andamento"]);

  const maps: Record<StageId, { done: Set<string>; active: Set<string> }> = {
    gpr:        { done: GPR_DONE, active: GPR_ACT },
    ia:         { done: IA_DONE,  active: IA_ACT  },
    revisao:    { done: REV_DONE, active: REV_ACT  },
    cartografia:{ done: CAR_DONE, active: CAR_ACT  },
    relatorio:  { done: REL_DONE, active: REL_ACT  },
  };

  const { done, active } = maps[stageId];
  if (done.has(status)) return "done";
  if (active.has(status)) return "active";
  return "pending";
}

function PipelineProgress({ status }: { status: string }) {
  if (["criado", "aguardando_arquivos"].includes(status)) return null;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 px-6 py-4">
      <div className="flex items-start">
        {PIPELINE_STAGES.map((stage, idx) => {
          const state = getStageState(stage.id, status);
          return (
            <Fragment key={stage.id}>
              <div className="flex flex-col items-center gap-1.5 shrink-0 w-16">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold transition-colors ${
                    state === "done"
                      ? "bg-emerald-500 text-white"
                      : state === "active"
                      ? "bg-cyan-500 text-slate-950 animate-pulse"
                      : "bg-slate-800 text-slate-600 border border-slate-700"
                  }`}
                >
                  {state === "done" ? "✓" : <span className="w-1.5 h-1.5 rounded-full bg-current" />}
                </div>
                <span
                  className={`text-[10px] font-medium text-center leading-tight ${
                    state === "done"
                      ? "text-emerald-400"
                      : state === "active"
                      ? "text-cyan-400"
                      : "text-slate-600"
                  }`}
                >
                  {stage.label}
                </span>
              </div>
              {idx < PIPELINE_STAGES.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mt-4 mx-0.5 transition-colors ${
                    state === "done" ? "bg-emerald-500/50" : "bg-slate-800"
                  }`}
                />
              )}
            </Fragment>
          );
        })}
      </div>
    </div>
  );
}

// ── Helper components ─────────────────────────────────────────────────────────

function JobChip({ job }: { job: JobRow }) {
  const typeLabel: Record<string, string> = {
    gpr: "GPR", ia: "IA", cartografia: "Cartografia", relatorio: "Relatório", inferencias: "Inferências", interpretada: "Interpretada",
  };
  const statusColor: Record<string, string> = {
    aguardando: "bg-slate-700 text-slate-400",
    processando_gpr: "bg-blue-500/15 text-blue-400",
    processando_ia: "bg-violet-500/15 text-violet-400",
    processando: "bg-blue-500/15 text-blue-400",
    concluido: "bg-emerald-500/15 text-emerald-400",
    erro: "bg-red-500/15 text-red-400",
  };
  const statusLabel: Record<string, string> = {
    aguardando: "aguardando",
    processando_gpr: "processando",
    processando_ia: "processando",
    processando: "processando",
    concluido: "concluído",
    erro: "erro",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${
        statusColor[job.status] ?? "bg-slate-700 text-slate-400"
      }`}
    >
      <span className="font-semibold">{typeLabel[job.job_type] ?? job.job_type}</span>
      <span className="opacity-70">{statusLabel[job.status] ?? job.status}</span>
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-xs font-medium px-2 py-0.5 rounded-full shrink-0 ${
        STATUS_COLOR[status] ?? "bg-slate-700 text-slate-400 border border-slate-600"
      }`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}
