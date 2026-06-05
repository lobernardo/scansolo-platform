export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import { ReviewClient } from "./ReviewClient";
import type { Database } from "@/lib/types/database";

type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];
type AiInterpretationRow = Database["public"]["Tables"]["ai_interpretations"]["Row"];
type TechnicalReviewRow = Database["public"]["Tables"]["technical_reviews"]["Row"];

const ALLOWED_STATUSES = new Set([
  "ia_concluida",
  "gpr_concluido",
  "revisao_em_andamento",
  "revisao_concluida",
]);

export default async function RevisaoPage({
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

  const { data: projectRaw } = await supabase
    .from("projects")
    .select("id, nome, status")
    .eq("id", id)
    .single();
  const projectData = projectRaw as { id: string; nome: string; status: string } | null;

  if (!projectData) redirect("/projetos");
  if (!ALLOWED_STATUSES.has(projectData.status)) redirect(`/projetos/${id}`);

  // Mark as in-progress when user opens the review screen
  if (projectData.status === "ia_concluida" || projectData.status === "gpr_concluido") {
    await supabase
      .from("projects")
      .update({ status: "revisao_em_andamento" } as unknown as never)
      .eq("id", id);
  }

  const { data: profilesRaw } = await supabase
    .from("gpr_profiles")
    .select("id, arquivo_dzt, imagem_bruta_url, imagem_processada_url, imagem_anotada_url")
    .eq("project_id", id)
    .order("created_at", { ascending: false });
  type ProfileSlim = { id: string; arquivo_dzt: string | null; imagem_bruta_url: string | null; imagem_processada_url: string | null; imagem_anotada_url: string | null };
  const profiles = (profilesRaw ?? []) as ProfileSlim[];
  const profileIds = profiles.map((p) => p.id);

  let targets: DetectedTargetRow[] = [];
  if (profileIds.length > 0) {
    const { data } = await supabase
      .from("detected_targets")
      .select("*")
      .in("profile_id", profileIds)
      .order("rank");
    targets = (data ?? []) as DetectedTargetRow[];
  }

  const targetIds = targets.map((t) => t.id);

  let aiInterpretations: AiInterpretationRow[] = [];
  let existingReviews: TechnicalReviewRow[] = [];

  if (targetIds.length > 0) {
    const [{ data: aiData }, { data: reviewData }] = await Promise.all([
      supabase.from("ai_interpretations").select("*").in("target_id", targetIds),
      supabase.from("technical_reviews").select("*").in("target_id", targetIds),
    ]);
    aiInterpretations = (aiData ?? []) as AiInterpretationRow[];
    existingReviews = (reviewData ?? []) as TechnicalReviewRow[];
  }

  const aiByTargetId = Object.fromEntries(aiInterpretations.map((ai) => [ai.target_id, ai]));
  const existingReviewsByTargetId = Object.fromEntries(existingReviews.map((r) => [r.target_id, r]));

  return (
    <div>
      {/* Breadcrumb */}
      <div className="max-w-6xl mx-auto px-4 pt-6 flex items-center gap-2 text-sm text-slate-500">
        <Link href="/projetos" className="hover:text-slate-300 transition-colors">Projetos</Link>
        <span className="text-slate-700">/</span>
        <Link href={`/projetos/${id}`} className="hover:text-slate-300 transition-colors">{projectData.nome}</Link>
        <span className="text-slate-700">/</span>
        <span className="text-slate-300">Revisão técnica</span>
      </div>

      <ReviewClient
        project={{ id: projectData.id, nome: projectData.nome }}
        targets={targets}
        profiles={profiles}
        aiByTargetId={aiByTargetId}
        existingReviews={existingReviewsByTargetId}
      />
    </div>
  );
}
