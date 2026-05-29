"use server";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export type ReviewTargetParams = {
  targetId: string;
  projectId: string;
  statusReview: "aprovado" | "descartado" | "ajustado";
  tipoFinal?: string | null;
  profundidadeAjustada?: number | null;
  diametroAjustado?: number | null;
  vaiParaPlanta: boolean;
  vaiParaRelatorio: boolean;
  observacao?: string | null;
};

export async function reviewTarget(
  params: ReviewTargetParams
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const payload = {
    target_id: params.targetId,
    status_review: params.statusReview,
    tipo_final: params.tipoFinal ?? null,
    profundidade_ajustada: params.profundidadeAjustada ?? null,
    diametro_ajustado: params.diametroAjustado ?? null,
    vai_para_planta: params.vaiParaPlanta,
    vai_para_relatorio: params.vaiParaRelatorio,
    observacao: params.observacao ?? null,
    reviewed_by: user.id,
    reviewed_at: new Date().toISOString(),
  };

  // Check if review already exists for this target
  const { data: existingRaw } = await supabase
    .from("technical_reviews")
    .select("id")
    .eq("target_id", params.targetId)
    .maybeSingle();
  const existing = existingRaw as { id: string } | null;

  if (existing) {
    const { error } = await supabase
      .from("technical_reviews")
      .update(payload as unknown as never)
      .eq("id", existing.id);
    if (error) return { ok: false, error: error.message };
  } else {
    const { error } = await supabase
      .from("technical_reviews")
      .insert(payload as unknown as never);
    if (error) return { ok: false, error: error.message };
  }

  // Advance project to revisao_em_andamento if not already further along
  const { data: projectRaw } = await supabase
    .from("projects")
    .select("status")
    .eq("id", params.projectId)
    .single();
  const project = projectRaw as { status: string } | null;

  const advanceFrom = new Set(["ia_concluida", "gpr_concluido"]);
  if (project && advanceFrom.has(project.status)) {
    await supabase
      .from("projects")
      .update({ status: "revisao_em_andamento" } as unknown as never)
      .eq("id", params.projectId);
  }

  return { ok: true };
}

export async function finalizeReview(
  projectId: string
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  type Row = { id: string };
  type ReviewRow = { target_id: string };
  type AiRow = { target_id: string; ia_tipo_sugerido: string | null; vai_para_planta_sugerido: boolean | null; vai_para_relatorio_sugerido: boolean | null };

  // Get all targets for this project (latest run via latest profiles)
  const { data: profilesRaw } = await supabase
    .from("gpr_profiles")
    .select("id")
    .eq("project_id", projectId)
    .order("created_at", { ascending: false });
  const profiles = (profilesRaw ?? []) as Row[];

  const profileIds = profiles.map((p) => p.id);
  if (!profileIds.length) return { ok: false, error: "Nenhum perfil encontrado" };

  const { data: targetsRaw } = await supabase
    .from("detected_targets")
    .select("id")
    .in("profile_id", profileIds);
  const targetsData = (targetsRaw ?? []) as Row[];

  const targetIds = targetsData.map((t) => t.id);
  if (!targetIds.length) return { ok: false, error: "Nenhum alvo encontrado" };

  // Find targets without a review yet
  const { data: existingReviewsRaw } = await supabase
    .from("technical_reviews")
    .select("target_id")
    .in("target_id", targetIds);
  const existingReviews = (existingReviewsRaw ?? []) as ReviewRow[];

  const reviewedIds = new Set(existingReviews.map((r) => r.target_id));
  const pendingIds = targetIds.filter((id) => !reviewedIds.has(id));

  if (pendingIds.length > 0) {
    // Auto-accept remaining pending targets using IA suggestions
    const { data: aiInterpsRaw } = await supabase
      .from("ai_interpretations")
      .select("target_id, ia_tipo_sugerido, vai_para_planta_sugerido, vai_para_relatorio_sugerido")
      .in("target_id", pendingIds);
    const aiInterps = (aiInterpsRaw ?? []) as AiRow[];

    const aiByTarget: Record<string, AiRow> = {};
    for (const ai of aiInterps) {
      aiByTarget[ai.target_id] = ai;
    }

    const toInsert = pendingIds.map((targetId) => ({
      target_id: targetId,
      status_review: "aprovado",
      tipo_final: aiByTarget[targetId]?.ia_tipo_sugerido ?? null,
      vai_para_planta: aiByTarget[targetId]?.vai_para_planta_sugerido ?? false,
      vai_para_relatorio: aiByTarget[targetId]?.vai_para_relatorio_sugerido ?? true,
      reviewed_by: user.id,
      reviewed_at: new Date().toISOString(),
    }));

    const { error } = await supabase
      .from("technical_reviews")
      .insert(toInsert as unknown as never);
    if (error) return { ok: false, error: error.message };
  }

  await supabase
    .from("projects")
    .update({ status: "revisao_concluida" } as unknown as never)
    .eq("id", projectId);

  return { ok: true };
}

// Called as form action from project detail page (Server Component)
export async function acceptAllIaSuggestions(projectId: string) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  type Row = { id: string };
  type ReviewRow = { target_id: string };
  type AiRow = { target_id: string; ia_tipo_sugerido: string | null; vai_para_planta_sugerido: boolean | null; vai_para_relatorio_sugerido: boolean | null };

  const { data: profilesRaw } = await supabase
    .from("gpr_profiles")
    .select("id")
    .eq("project_id", projectId)
    .order("created_at", { ascending: false });
  const profiles = (profilesRaw ?? []) as Row[];

  const profileIds = profiles.map((p) => p.id);
  if (!profileIds.length) redirect(`/projetos/${projectId}`);

  const { data: targetsRaw } = await supabase
    .from("detected_targets")
    .select("id")
    .in("profile_id", profileIds);
  const targetsData = (targetsRaw ?? []) as Row[];

  const targetIds = targetsData.map((t) => t.id);
  if (!targetIds.length) redirect(`/projetos/${projectId}`);

  // Skip targets that already have a review
  const { data: existingReviewsRaw } = await supabase
    .from("technical_reviews")
    .select("target_id")
    .in("target_id", targetIds);
  const existingReviews = (existingReviewsRaw ?? []) as ReviewRow[];

  const reviewedIds = new Set(existingReviews.map((r) => r.target_id));
  const pendingIds = targetIds.filter((id) => !reviewedIds.has(id));

  if (pendingIds.length > 0) {
    const { data: aiInterpsRaw } = await supabase
      .from("ai_interpretations")
      .select("target_id, ia_tipo_sugerido, vai_para_planta_sugerido, vai_para_relatorio_sugerido")
      .in("target_id", pendingIds);
    const aiInterps = (aiInterpsRaw ?? []) as AiRow[];

    const aiByTarget: Record<string, AiRow> = {};
    for (const ai of aiInterps) {
      aiByTarget[ai.target_id] = ai;
    }

    const toInsert = pendingIds.map((targetId) => ({
      target_id: targetId,
      status_review: "aprovado",
      tipo_final: aiByTarget[targetId]?.ia_tipo_sugerido ?? null,
      vai_para_planta: aiByTarget[targetId]?.vai_para_planta_sugerido ?? false,
      vai_para_relatorio: aiByTarget[targetId]?.vai_para_relatorio_sugerido ?? true,
      reviewed_by: user!.id,
      reviewed_at: new Date().toISOString(),
    }));

    await supabase
      .from("technical_reviews")
      .insert(toInsert as unknown as never);
  }

  await supabase
    .from("projects")
    .update({ status: "revisao_concluida" } as unknown as never)
    .eq("id", projectId);

  redirect(`/projetos/${projectId}`);
}
