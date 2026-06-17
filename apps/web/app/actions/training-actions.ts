"use server";

import { createClient, createAdminClient } from "@/lib/supabase/server";

// ── Types ─────────────────────────────────────────────────────────────────────

export type GroundTruthEntryInput = {
  session_id: string;
  project_id: string;
  profile_id: string;
  detected_target_id?: string | null;
  e_verdadeiro_positivo: boolean;
  e_falso_negativo?: boolean;
  x_real_m?: number | null;
  depth_real_m?: number | null;
  tipo_alvo_confirmado?: string | null;
  material_alvo?: string | null;
  diametro_real_mm?: number | null;
  fonte_confirmacao: string;
  confianca_fonte: number;
  tipo_solo: string;
  umidade_solo: string;
  tipo_superficie: string;
  dias_sem_chuva?: number | null;
  profundidade_lencol_m?: number | null;
  observacoes?: string | null;
};

export type GroundTruthStats = {
  total_entries: number;
  total_vp: number;
  total_fp: number;
  total_fn: number;
  f1_estimado: number;
  por_tipo_solo: Record<string, number>;
  por_tipo_alvo: Record<string, number>;
};

export type TrainingSession = {
  id: string;
  project_id: string;
  profile_id: string;
  descricao: string | null;
  total_vp: number;
  total_fp: number;
  total_fn: number;
  status: string;
  created_at: string;
  projects?: { nome: string } | null;
  gpr_profiles?: { arquivo_dzt: string } | null;
};

export type ProjectForTraining = {
  id: string;
  nome: string;
  cliente: string;
  status: string;
};

export type ProfileForTraining = {
  id: string;
  arquivo_dzt: string;
  imagem_anotada_url: string | null;
  imagem_bruta_url: string | null;
  run_id: string;
};

export type DetectedTargetForTraining = {
  id: string;
  rank: number;
  x_m: number | null;
  depth_m: number | null;
  diam_est_m: number | null;
  confidence_score_0_100: number | null;
  confidence_label_tecnico: string | null;
  tipo_material: string | null;
  amplitude_relativa_max: number | null;
};

export type RecalibracaoResult = {
  name: string;
  created_at: string;
  signed_url: string;
};

export type RecalibracaoContent = {
  gerado_em: string;
  n_amostras: number;
  n_vp: number;
  n_fp: number;
  f1_score: number;
  detalhes_f1: { threshold_otimo: number; tp: number; fp: number; fn: number };
  thresholds_sugeridos: { det_min_score_csv: number; det_amp_threshold: number; det_depth_min_m: number };
  thresholds_atuais: { det_min_score_csv: number; det_amp_threshold: number; det_depth_min_m: number };
  aprovado: boolean;
  notas: string;
};

// ── Helpers ───────────────────────────────────────────────────────────────────

const STATUSES_GPR_DONE = [
  "gpr_concluido", "processando_ia", "ia_concluida", "revisao_em_andamento",
  "revisao_concluida", "processando_interpretada", "interpretada_gerada",
  "aguardando_cartografia", "cartografia_concluida", "cartografia_pendente_dados",
  "aguardando_relatorio", "relatorio_em_andamento", "relatorio_gerado", "finalizado",
];

// ── Project / Profile / Target fetches ───────────────────────────────────────

export async function getProjectsForTraining(): Promise<ProjectForTraining[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("projects")
    .select("id, nome, cliente, status")
    .in("status", STATUSES_GPR_DONE)
    .order("created_at", { ascending: false })
    .limit(100);
  return (data ?? []) as ProjectForTraining[];
}

export async function getProfilesForProject(projectId: string): Promise<ProfileForTraining[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("gpr_profiles")
    .select("id, arquivo_dzt, imagem_anotada_url, imagem_bruta_url, run_id")
    .eq("project_id", projectId)
    .order("arquivo_dzt");
  return (data ?? []) as ProfileForTraining[];
}

export async function getTargetsForProfile(profileId: string): Promise<DetectedTargetForTraining[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("detected_targets")
    .select("id, rank, x_m, depth_m, diam_est_m, confidence_score_0_100, confidence_label_tecnico, tipo_material, amplitude_relativa_max")
    .eq("profile_id", profileId)
    .order("rank");
  return (data ?? []) as DetectedTargetForTraining[];
}

// ── Session management ────────────────────────────────────────────────────────

export async function createTrainingSession(
  projectId: string,
  profileId: string,
  descricao: string
): Promise<{ ok: boolean; session_id?: string; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  const { data, error } = await supabase
    .from("gpr_training_sessions")
    .insert({
      project_id: projectId,
      profile_id: profileId,
      created_by: user.id,
      descricao: descricao.trim() || null,
      status: "rascunho",
    } as never)
    .select("id")
    .single();

  if (error) return { ok: false, error: error.message };
  return { ok: true, session_id: (data as { id: string }).id };
}

export async function saveGroundTruthEntry(
  entry: GroundTruthEntryInput
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  // Copia métricas do detected_targets
  let score_detector: number | null = null;
  let amplitude_relativa_max: number | null = null;
  let depth_detector_m: number | null = null;
  let diam_est_m: number | null = null;

  if (entry.detected_target_id) {
    const { data: tgt } = await supabase
      .from("detected_targets")
      .select("confidence_score_0_100, amplitude_relativa_max, depth_m, diam_est_m")
      .eq("id", entry.detected_target_id)
      .single();
    if (tgt) {
      const t = tgt as Record<string, unknown>;
      score_detector = (t.confidence_score_0_100 as number) ?? null;
      amplitude_relativa_max = (t.amplitude_relativa_max as number) ?? null;
      depth_detector_m = (t.depth_m as number) ?? null;
      diam_est_m = (t.diam_est_m as number) ?? null;
    }
  }

  const { error } = await supabase
    .from("gpr_ground_truth")
    .insert({
      session_id: entry.session_id,
      project_id: entry.project_id,
      profile_id: entry.profile_id,
      detected_target_id: entry.detected_target_id ?? null,
      created_by: user.id,
      tipo_solo: entry.tipo_solo,
      umidade_solo: entry.umidade_solo,
      tipo_superficie: entry.tipo_superficie,
      dias_sem_chuva: entry.dias_sem_chuva ?? null,
      profundidade_lencol_m: entry.profundidade_lencol_m ?? null,
      e_verdadeiro_positivo: entry.e_verdadeiro_positivo,
      e_falso_negativo: entry.e_falso_negativo ?? false,
      x_real_m: entry.x_real_m ?? null,
      depth_real_m: entry.depth_real_m ?? null,
      tipo_alvo_confirmado: entry.tipo_alvo_confirmado ?? null,
      material_alvo: entry.material_alvo ?? null,
      diametro_real_mm: entry.diametro_real_mm ?? null,
      fonte_confirmacao: entry.fonte_confirmacao,
      confianca_fonte: entry.confianca_fonte,
      observacoes: entry.observacoes ?? null,
      score_detector,
      amplitude_relativa_max,
      depth_detector_m,
      diam_est_m,
    } as never);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

export async function finalizeTrainingSession(
  sessionId: string
): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();

  const { data: entries } = await supabase
    .from("gpr_ground_truth")
    .select("e_verdadeiro_positivo, e_falso_negativo")
    .eq("session_id", sessionId);

  const rows = (entries ?? []) as { e_verdadeiro_positivo: boolean; e_falso_negativo: boolean }[];
  const total_vp = rows.filter(r => r.e_verdadeiro_positivo && !r.e_falso_negativo).length;
  const total_fp = rows.filter(r => !r.e_verdadeiro_positivo).length;
  const total_fn = rows.filter(r => r.e_falso_negativo).length;

  const { error } = await supabase
    .from("gpr_training_sessions")
    .update({ total_vp, total_fp, total_fn, status: "concluida" } as never)
    .eq("id", sessionId);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

// ── Stats ─────────────────────────────────────────────────────────────────────

export async function getGroundTruthStats(): Promise<GroundTruthStats> {
  const supabase = await createClient();

  const { data: rows } = await supabase
    .from("gpr_ground_truth")
    .select("e_verdadeiro_positivo, e_falso_negativo, tipo_solo, tipo_alvo_confirmado");

  const all = (rows ?? []) as {
    e_verdadeiro_positivo: boolean;
    e_falso_negativo: boolean;
    tipo_solo: string | null;
    tipo_alvo_confirmado: string | null;
  }[];

  const total_vp = all.filter(r => r.e_verdadeiro_positivo && !r.e_falso_negativo).length;
  const total_fp = all.filter(r => !r.e_verdadeiro_positivo).length;
  const total_fn = all.filter(r => r.e_falso_negativo).length;
  const denom = 2 * total_vp + total_fp + total_fn;
  const f1_estimado = denom > 0 ? Math.round((2 * total_vp / denom) * 1000) / 1000 : 0;

  const por_tipo_solo: Record<string, number> = {};
  const por_tipo_alvo: Record<string, number> = {};
  for (const r of all) {
    const solo = r.tipo_solo ?? "outro";
    por_tipo_solo[solo] = (por_tipo_solo[solo] ?? 0) + 1;
    if (r.e_verdadeiro_positivo && !r.e_falso_negativo && r.tipo_alvo_confirmado) {
      const alvo = r.tipo_alvo_confirmado;
      por_tipo_alvo[alvo] = (por_tipo_alvo[alvo] ?? 0) + 1;
    }
  }

  return {
    total_entries: all.length,
    total_vp,
    total_fp,
    total_fn,
    f1_estimado,
    por_tipo_solo,
    por_tipo_alvo,
  };
}

// ── History ───────────────────────────────────────────────────────────────────

export async function getTrainingSessions(): Promise<TrainingSession[]> {
  const supabase = await createClient();
  const { data } = await supabase
    .from("gpr_training_sessions")
    .select("*, projects(nome), gpr_profiles(arquivo_dzt)")
    .order("created_at", { ascending: false })
    .limit(50);
  return (data ?? []) as unknown as TrainingSession[];
}

// ── Recalibração ──────────────────────────────────────────────────────────────

export async function triggerRecalibracao(): Promise<{ ok: boolean; error?: string }> {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return { ok: false, error: "Não autenticado" };

  // Qualquer project_id para satisfazer a FK
  const { data: proj } = await supabase
    .from("projects").select("id").limit(1).single();

  const { error } = await supabase
    .from("processing_jobs")
    .insert({
      job_type: "recalibrar",
      status: "aguardando",
      payload: {},
      ...(proj ? { project_id: (proj as { id: string }).id } : {}),
    } as never);

  if (error) return { ok: false, error: error.message };
  return { ok: true };
}

export async function getRecalibracaoResults(): Promise<RecalibracaoResult[]> {
  try {
    const admin = await createAdminClient();
    const { data: files } = await admin.storage
      .from("gpr-tabelas")
      .list("recalibracao", { sortBy: { column: "created_at", order: "desc" } });

    if (!files) return [];

    const results: RecalibracaoResult[] = [];
    for (const f of files) {
      if (!f.name.endsWith(".json")) continue;
      const { data: urlData } = await admin.storage
        .from("gpr-tabelas")
        .createSignedUrl(`recalibracao/${f.name}`, 3600);
      results.push({
        name: f.name,
        created_at: f.created_at ?? f.name,
        signed_url: urlData?.signedUrl ?? "",
      });
    }
    return results;
  } catch {
    return [];
  }
}

export async function getRecalibracaoContent(
  signedUrl: string
): Promise<{ ok: boolean; content?: RecalibracaoContent; error?: string }> {
  try {
    const res = await fetch(signedUrl);
    if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
    const content = (await res.json()) as RecalibracaoContent;
    return { ok: true, content };
  } catch (e) {
    return { ok: false, error: String(e) };
  }
}

export async function applyRecalibracao(
  thresholds: RecalibracaoContent["thresholds_sugeridos"]
): Promise<{ ok: boolean; error?: string }> {
  // Importa server action de presets inline para evitar ciclo
  const { createPreset, getPresets } = await import("@/app/actions/preset-actions");

  const presets = await getPresets();
  const base = presets.find(p => p.name === "270mhz" && p.is_system);
  if (!base) return { ok: false, error: "Preset base '270mhz' não encontrado." };

  const newParams = {
    ...base.parameters,
    det_min_score_csv: thresholds.det_min_score_csv,
    det_min_score_plot: thresholds.det_min_score_csv + 10,
    det_amp_threshold: thresholds.det_amp_threshold,
    det_depth_min_m: thresholds.det_depth_min_m,
  };

  const ts = new Date().toISOString().slice(0, 16).replace("T", " ");
  const result = await createPreset({
    name: `270mhz recalibrado ${ts}`,
    description: `Recalibrado automaticamente via ground truth. Score≥${thresholds.det_min_score_csv}, amp≥${thresholds.det_amp_threshold}, depth_min=${thresholds.det_depth_min_m}m`,
    scientific_basis: "Otimização F1 via gpr_ground_truth (job_recalibrar)",
    parameters: newParams,
  });

  return result;
}
