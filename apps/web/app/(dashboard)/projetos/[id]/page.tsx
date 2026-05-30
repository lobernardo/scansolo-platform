export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";
import { ProjectStatusPoller } from "./ProjectStatusPoller";
import { acceptAllIaSuggestions } from "./revisao/actions";
import { startCartografia } from "./cartografia/actions";
import { startRelatorio } from "./relatorio/actions";

type ProjectRow = Database["public"]["Tables"]["projects"]["Row"];
type GprProfileRow = Database["public"]["Tables"]["gpr_profiles"]["Row"];
type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];
type JobRow = Database["public"]["Tables"]["processing_jobs"]["Row"];
type AiInterpretationRow = Database["public"]["Tables"]["ai_interpretations"]["Row"];

const PROCESSING_STATUSES = new Set([
  "aguardando_processamento",
  "processando_gpr",
  "processando_ia",
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
  aguardando_aprovacao: "Aguardando aprovação",
  finalizado: "Finalizado",
  erro: "Erro",
};

const STATUS_COLOR: Record<string, string> = {
  criado: "bg-gray-100 text-gray-600",
  aguardando_arquivos: "bg-yellow-50 text-yellow-700",
  aguardando_processamento: "bg-blue-50 text-blue-700",
  processando_gpr: "bg-blue-100 text-blue-800",
  gpr_concluido: "bg-green-100 text-green-700",
  processando_ia: "bg-purple-50 text-purple-700",
  ia_concluida: "bg-green-200 text-green-800",
  revisao_em_andamento: "bg-orange-100 text-orange-700",
  revisao_concluida: "bg-teal-100 text-teal-700",
  aguardando_cartografia: "bg-indigo-100 text-indigo-700",
  cartografia_concluida: "bg-indigo-200 text-indigo-800",
  cartografia_pendente_dados: "bg-yellow-100 text-yellow-700",
  aguardando_relatorio: "bg-violet-100 text-violet-700",
  relatorio_em_andamento: "bg-violet-100 text-violet-700",
  relatorio_gerado: "bg-violet-200 text-violet-800",
  aguardando_aprovacao: "bg-violet-200 text-violet-800",
  finalizado: "bg-green-300 text-green-900",
  erro: "bg-red-50 text-red-700",
};

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

  // Fetch all jobs for this project (for IA status display)
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

  const isProcessing = PROCESSING_STATUSES.has(project.status);
  const gprJob = jobs.find((j) => j.job_type === "gpr");
  const iaJob = jobs.find((j) => j.job_type === "ia");
  const iaDone = project.status === "ia_concluida" || iaJob?.status === "concluido";
  const hasAiResults = aiInterpretations.length > 0;

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link href="/projetos" className="text-sm text-gray-500 hover:text-gray-700">
              Projetos
            </Link>
            <span className="text-gray-300">/</span>
            <span className="text-sm text-gray-700">{project.nome}</span>
          </div>
          <h1 className="text-2xl font-bold">{project.nome}</h1>
          <p className="text-sm text-gray-500 mt-1">
            {project.cliente}{project.local ? ` — ${project.local}` : ""} · {project.estado}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>

      {/* Auto-refresh while processing */}
      {isProcessing && <ProjectStatusPoller />}

      {/* Upload prompt */}
      {project.status === "aguardando_arquivos" && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4">
          <p className="text-sm text-yellow-800 mb-3">
            Projeto criado. Faça o upload dos arquivos .DZT para iniciar o processamento.
          </p>
          <Link
            href={`/projetos/${id}/upload`}
            className="inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors"
          >
            Upload de arquivos
          </Link>
        </div>
      )}

      {/* Processing state */}
      {isProcessing && (
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4 flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-blue-400 animate-pulse shrink-0" />
          <p className="text-sm text-blue-800">
            Processamento em andamento… Esta página atualiza automaticamente.
          </p>
        </div>
      )}

      {/* GPR error */}
      {project.status === "erro" && gprJob?.job_type === "gpr" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-700 mb-1">Erro no processamento GPR</p>
          {gprJob?.error_message && (
            <p className="text-xs text-red-600 font-mono break-all">{gprJob.error_message}</p>
          )}
        </div>
      )}

      {/* IA done — decision banner */}
      {iaDone && hasAiResults && project.status === "ia_concluida" && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-4 space-y-3">
          <p className="text-sm text-green-800">
            <span className="font-medium">Interpretação IA concluída.</span>{" "}
            {aiInterpretations.length} alvo{aiInterpretations.length !== 1 ? "s" : ""} interpretado{aiInterpretations.length !== 1 ? "s" : ""} por GPT-4o. Escolha como prosseguir:
          </p>
          <div className="flex gap-3 flex-wrap">
            <form action={acceptAllIaSuggestions.bind(null, project.id)}>
              <button
                type="submit"
                className="rounded-md bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800 transition-colors"
              >
                Aceitar todas as sugestões da IA
              </button>
            </form>
            <Link
              href={`/projetos/${id}/revisao`}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Revisar alvos manualmente
            </Link>
          </div>
        </div>
      )}

      {/* Revisão em andamento */}
      {project.status === "revisao_em_andamento" && (
        <div className="rounded-lg border border-orange-200 bg-orange-50 p-4 flex items-center justify-between">
          <p className="text-sm text-orange-800">
            <span className="font-medium">Revisão técnica em andamento.</span>
          </p>
          <Link
            href={`/projetos/${id}/revisao`}
            className="text-sm font-medium text-orange-700 underline underline-offset-2 hover:text-orange-900"
          >
            Continuar revisão →
          </Link>
        </div>
      )}

      {/* Revisão concluída — iniciar cartografia */}
      {project.status === "revisao_concluida" && (
        <div className="rounded-lg border border-teal-200 bg-teal-50 p-4 space-y-3">
          <p className="text-sm text-teal-800">
            <span className="font-medium">Revisão técnica concluída.</span>{" "}
            Pronto para gerar os arquivos cartográficos.
          </p>
          <form action={startCartografia.bind(null, project.id)}>
            <button
              type="submit"
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 transition-colors"
            >
              Gerar arquivos cartográficos
            </button>
          </form>
        </div>
      )}

      {/* Cartografia em andamento */}
      {project.status === "aguardando_cartografia" && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-indigo-400 animate-pulse shrink-0" />
            <p className="text-sm text-indigo-800">
              Gerando arquivos cartográficos…
            </p>
          </div>
          <Link
            href={`/projetos/${id}/cartografia`}
            className="text-sm font-medium text-indigo-700 underline underline-offset-2 hover:text-indigo-900"
          >
            Ver resultado →
          </Link>
        </div>
      )}

      {/* Cartografia pendente dados */}
      {project.status === "cartografia_pendente_dados" && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 flex items-center justify-between">
          <p className="text-sm text-yellow-800">
            <span className="font-medium">Cartografia — dados pendentes.</span>{" "}
            Arquivos de referência necessários.
          </p>
          <Link
            href={`/projetos/${id}/cartografia`}
            className="text-sm font-medium text-yellow-700 underline underline-offset-2 hover:text-yellow-900"
          >
            Ver detalhes →
          </Link>
        </div>
      )}

      {/* Cartografia concluída — iniciar relatório */}
      {project.status === "cartografia_concluida" && (
        <div className="rounded-lg border border-indigo-200 bg-indigo-50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm text-indigo-800">
              <span className="font-medium">Cartografia concluída.</span>
            </p>
            <Link
              href={`/projetos/${id}/cartografia`}
              className="text-xs font-medium text-indigo-600 underline underline-offset-2 hover:text-indigo-800"
            >
              Ver arquivos
            </Link>
          </div>
          <form action={startRelatorio.bind(null, project.id)}>
            <button
              type="submit"
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 transition-colors"
            >
              Gerar relatório
            </button>
          </form>
        </div>
      )}

      {/* Relatório em andamento */}
      {(project.status === "aguardando_relatorio" || project.status === "relatorio_em_andamento") && (
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-violet-400 animate-pulse shrink-0" />
            <p className="text-sm text-violet-800">Gerando relatório…</p>
          </div>
          <Link
            href={`/projetos/${id}/relatorio`}
            className="text-sm font-medium text-violet-700 underline underline-offset-2 hover:text-violet-900"
          >
            Ver status →
          </Link>
        </div>
      )}

      {/* Relatório gerado */}
      {project.status === "relatorio_gerado" && (
        <div className="rounded-lg border border-violet-200 bg-violet-50 p-4 flex items-center justify-between">
          <p className="text-sm text-violet-800">
            <span className="font-medium">Relatório gerado.</span>{" "}
            Pronto para revisão e aprovação.
          </p>
          <Link
            href={`/projetos/${id}/relatorio`}
            className="text-sm font-medium text-violet-700 underline underline-offset-2 hover:text-violet-900"
          >
            Abrir relatório →
          </Link>
        </div>
      )}

      {/* Finalizado */}
      {project.status === "finalizado" && (
        <div className="rounded-lg border border-green-300 bg-green-50 p-4 flex items-center justify-between">
          <p className="text-sm text-green-800">
            <span className="font-medium">Projeto finalizado.</span>{" "}
            Relatório aprovado.
          </p>
          <Link
            href={`/projetos/${id}/relatorio`}
            className="text-sm font-medium text-green-700 underline underline-offset-2 hover:text-green-900"
          >
            Ver relatório →
          </Link>
        </div>
      )}

      {/* IA error */}
      {iaJob?.status === "erro" && iaJob.error_message && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-700 mb-1">Erro na interpretação IA</p>
          <p className="text-xs text-red-600 font-mono break-all">{iaJob.error_message}</p>
        </div>
      )}

      {/* Jobs timeline (compact) */}
      {jobs.length > 0 && (
        <div className="flex gap-3 flex-wrap">
          {jobs.map((job) => (
            <JobChip key={job.id} job={job} />
          ))}
        </div>
      )}

      {/* GPR Profiles */}
      {profiles.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-4">
            Perfis GPR{" "}
            <span className="text-sm font-normal text-gray-400">
              ({profiles.length} perfil{profiles.length !== 1 ? "s" : ""} ·{" "}
              {targets.length} alvo{targets.length !== 1 ? "s" : ""} total)
            </span>
          </h2>
          <div className="grid gap-6">
            {profiles.map((profile) => (
              <ProfileCard
                key={profile.id}
                profile={profile}
                targets={targets.filter((t) => t.profile_id === profile.id)}
                aiByTargetId={aiByTargetId}
              />
            ))}
          </div>
        </section>
      )}

      {/* Empty state after processing */}
      {!isProcessing && profiles.length === 0 && project.status !== "aguardando_arquivos" && (
        <p className="text-sm text-gray-400">Nenhum perfil GPR disponível.</p>
      )}
    </div>
  );
}

function JobChip({ job }: { job: JobRow }) {
  const typeLabel: Record<string, string> = {
    gpr: "GPR",
    ia: "IA",
    cartografia: "Cartografia",
    relatorio: "Relatório",
  };
  const statusColor: Record<string, string> = {
    aguardando: "bg-gray-100 text-gray-500",
    processando_gpr: "bg-blue-100 text-blue-700",
    processando_ia: "bg-purple-100 text-purple-700",
    processando: "bg-blue-100 text-blue-700",
    concluido: "bg-green-100 text-green-700",
    erro: "bg-red-50 text-red-600",
  };
  const statusLabel: Record<string, string> = {
    aguardando: "aguardando",
    processando_gpr: "processando",
    processando_ia: "processando",
    processando: "processando",
    concluido: "concluído",
    erro: job.job_type === "ia" ? "pendente (Fase 2)" : "erro",
  };
  return (
    <span
      className={`inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
        statusColor[job.status] ?? "bg-gray-100 text-gray-500"
      }`}
    >
      <span className="font-medium">{typeLabel[job.job_type] ?? job.job_type}</span>
      <span className="opacity-70">{statusLabel[job.status] ?? job.status}</span>
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`text-xs font-medium px-3 py-1 rounded-full ${
        STATUS_COLOR[status] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

function ProfileCard({
  profile,
  targets,
  aiByTargetId,
}: {
  profile: GprProfileRow;
  targets: DetectedTargetRow[];
  aiByTargetId: Record<string, AiInterpretationRow>;
}) {
  const hasImages =
    profile.imagem_bruta_url || profile.imagem_processada_url || profile.imagem_anotada_url;

  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Profile header */}
      <div className="p-4 border-b border-gray-100 flex items-center justify-between">
        <div>
          <p className="font-medium text-gray-900">{profile.arquivo_dzt}</p>
          <p className="text-xs text-gray-500 mt-0.5">
            {profile.n_tracos != null ? `${profile.n_tracos} traços` : "—"} ·{" "}
            {profile.profundidade_max_m != null
              ? `${profile.profundidade_max_m.toFixed(2)} m prof.`
              : "—"}{" "}
            ·{" "}
            {profile.distancia_max_m != null
              ? `${profile.distancia_max_m.toFixed(2)} m dist.`
              : "—"}
          </p>
        </div>
        <span className="text-xs text-gray-400 bg-gray-50 px-2 py-1 rounded">
          {targets.length} alvo{targets.length !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Images */}
      {hasImages && (
        <div className="grid grid-cols-1 md:grid-cols-3 border-b border-gray-100">
          {[
            { url: profile.imagem_bruta_url, label: "Bruta" },
            { url: profile.imagem_processada_url, label: "Processada" },
            { url: profile.imagem_anotada_url, label: "Anotada" },
          ]
            .filter((img) => img.url)
            .map((img, i) => (
              <div key={img.label} className={`relative ${i > 0 ? "md:border-l border-gray-100" : ""}`}>
                <span className="absolute top-2 left-2 text-xs bg-black/50 text-white px-1.5 py-0.5 rounded z-10">
                  {img.label}
                </span>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={img.url!}
                  alt={img.label}
                  className="w-full h-48 object-cover"
                />
              </div>
            ))}
        </div>
      )}

      {/* Targets table */}
      {targets.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-100 text-left">
                <th className="px-3 py-2 font-medium text-gray-500">#</th>
                <th className="px-3 py-2 font-medium text-gray-500">X (m)</th>
                <th className="px-3 py-2 font-medium text-gray-500">Prof (m)</th>
                <th className="px-3 py-2 font-medium text-gray-500">Diâm (m)</th>
                <th className="px-3 py-2 font-medium text-gray-500">Material</th>
                <th className="px-3 py-2 font-medium text-gray-500">Score</th>
                <th className="px-3 py-2 font-medium text-gray-500">Confiança</th>
                <th className="px-3 py-2 font-medium text-gray-500">IA — Tipo</th>
                <th className="px-3 py-2 font-medium text-gray-500">IA — Conf.</th>
                <th className="px-3 py-2 font-medium text-gray-500">Planta</th>
                <th className="px-3 py-2 font-medium text-gray-500">Relatório</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {targets.map((t) => {
                const ai = aiByTargetId[t.id] ?? null;
                return (
                  <tr key={t.id} className="hover:bg-gray-50" title={ai?.ia_descricao ?? undefined}>
                    <td className="px-3 py-2 text-gray-500">{t.rank}</td>
                    <td className="px-3 py-2">{t.x_m?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{t.depth_m?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{t.diam_est_m?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-2">{t.tipo_material ?? "—"}</td>
                    <td className="px-3 py-2">{t.confidence_score ?? "—"}</td>
                    <td className="px-3 py-2">
                      <ConfidenceBadge label={t.confidence_label_relatorio} />
                    </td>
                    <td className="px-3 py-2 text-gray-700">
                      {ai ? (ai.ia_tipo_sugerido ?? "—") : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-3 py-2">
                      {ai ? <ConfidenceBadge label={ai.ia_confianca} /> : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {ai
                        ? (ai.vai_para_planta_sugerido ? <span className="text-green-600 font-bold">✓</span> : <span className="text-gray-300">✗</span>)
                        : <span className="text-gray-300">—</span>}
                    </td>
                    <td className="px-3 py-2 text-center">
                      {ai
                        ? (ai.vai_para_relatorio_sugerido ? <span className="text-green-600 font-bold">✓</span> : <span className="text-gray-300">✗</span>)
                        : <span className="text-gray-300">—</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {targets.length === 0 && !hasImages && (
        <p className="text-xs text-gray-400 p-4">Aguardando resultados…</p>
      )}
      {targets.length === 0 && hasImages && (
        <p className="text-xs text-gray-400 p-4">Nenhum alvo detectado neste perfil.</p>
      )}
    </div>
  );
}

function ConfidenceBadge({ label }: { label: string | null }) {
  if (!label) return <span className="text-gray-400">—</span>;
  const colors =
    label === "alta"
      ? "bg-green-100 text-green-700"
      : "bg-yellow-100 text-yellow-700";
  return (
    <span className={`px-1.5 py-0.5 rounded font-medium ${colors}`}>{label}</span>
  );
}
