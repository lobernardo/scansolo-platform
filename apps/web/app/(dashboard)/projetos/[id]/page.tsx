export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";
import { ProjectStatusPoller } from "./ProjectStatusPoller";

type ProjectRow = Database["public"]["Tables"]["projects"]["Row"];
type GprProfileRow = Database["public"]["Tables"]["gpr_profiles"]["Row"];
type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];

const PROCESSING_STATUSES = new Set([
  "aguardando_processamento",
  "processando_gpr",
  "processando_ia",
]);

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

  const isProcessing = PROCESSING_STATUSES.has(project.status);

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
            {project.cliente} — {project.local ?? project.estado}
          </p>
        </div>
        <StatusBadge status={project.status} />
      </div>

      {/* Auto-refresh while processing */}
      {isProcessing && <ProjectStatusPoller projectId={id} />}

      {/* Upload prompt if waiting for files */}
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
        <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
          <p className="text-sm text-blue-800">
            Processamento em andamento… Esta página atualiza automaticamente.
          </p>
        </div>
      )}

      {/* Error state */}
      {project.status === "erro" && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">
            Ocorreu um erro durante o processamento. Verifique os logs do worker.
          </p>
        </div>
      )}

      {/* GPR Profiles */}
      {profiles.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold mb-4">Perfis GPR</h2>
          <div className="grid gap-6">
            {profiles.map((profile) => (
              <ProfileCard
                key={profile.id}
                profile={profile}
                targets={targets.filter((t) => t.profile_id === profile.id)}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    criado: "bg-gray-100 text-gray-600",
    aguardando_arquivos: "bg-yellow-50 text-yellow-700",
    aguardando_processamento: "bg-blue-50 text-blue-700",
    processando_gpr: "bg-blue-100 text-blue-800",
    gpr_concluido: "bg-green-50 text-green-700",
    processando_ia: "bg-purple-50 text-purple-700",
    ia_concluida: "bg-green-100 text-green-800",
    erro: "bg-red-50 text-red-700",
    finalizado: "bg-green-200 text-green-900",
  };
  const labels: Record<string, string> = {
    criado: "Criado",
    aguardando_arquivos: "Aguardando arquivos",
    aguardando_processamento: "Aguardando processamento",
    processando_gpr: "Processando GPR",
    gpr_concluido: "GPR concluído",
    processando_ia: "Processando IA",
    ia_concluida: "IA concluída",
    erro: "Erro",
    finalizado: "Finalizado",
  };
  return (
    <span
      className={`text-xs font-medium px-3 py-1 rounded-full ${
        colors[status] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {labels[status] ?? status}
    </span>
  );
}

function ProfileCard({
  profile,
  targets,
}: {
  profile: GprProfileRow;
  targets: DetectedTargetRow[];
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
      <div className="p-4 border-b border-gray-100">
        <p className="font-medium">{profile.arquivo_dzt}</p>
        <p className="text-xs text-gray-500 mt-1">
          {profile.n_tracos} traços · {profile.profundidade_max_m?.toFixed(2)} m prof. ·{" "}
          {profile.distancia_max_m?.toFixed(2)} m dist.
        </p>
      </div>

      {/* Images */}
      {(profile.imagem_bruta_url || profile.imagem_processada_url || profile.imagem_anotada_url) && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border-b border-gray-100">
          {[
            { url: profile.imagem_bruta_url, label: "Bruta" },
            { url: profile.imagem_processada_url, label: "Processada" },
            { url: profile.imagem_anotada_url, label: "Anotada" },
          ]
            .filter((img) => img.url)
            .map((img) => (
              <div key={img.label} className="relative">
                <p className="absolute top-2 left-2 text-xs bg-black/50 text-white px-1.5 py-0.5 rounded">
                  {img.label}
                </p>
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
              <tr className="bg-gray-50 text-left">
                <th className="px-3 py-2 font-medium text-gray-500">#</th>
                <th className="px-3 py-2 font-medium text-gray-500">X (m)</th>
                <th className="px-3 py-2 font-medium text-gray-500">Prof (m)</th>
                <th className="px-3 py-2 font-medium text-gray-500">Diâm (m)</th>
                <th className="px-3 py-2 font-medium text-gray-500">Material</th>
                <th className="px-3 py-2 font-medium text-gray-500">Confiança</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {targets.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="px-3 py-2">{t.rank}</td>
                  <td className="px-3 py-2">{t.x_m?.toFixed(2)}</td>
                  <td className="px-3 py-2">{t.depth_m?.toFixed(2)}</td>
                  <td className="px-3 py-2">{t.diam_est_m?.toFixed(3)}</td>
                  <td className="px-3 py-2">{t.tipo_material ?? "—"}</td>
                  <td className="px-3 py-2">
                    <ConfidenceBadge label={t.confidence_label_relatorio} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {targets.length === 0 && profile.imagem_bruta_url && (
        <p className="text-xs text-gray-400 p-4">Nenhum alvo detectado.</p>
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
    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${colors}`}>
      {label}
    </span>
  );
}
