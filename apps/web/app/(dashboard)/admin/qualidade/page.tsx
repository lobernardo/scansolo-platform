export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import QualidadeClient from "./QualidadeClient";

export type GroundTruthStats = {
  total: number;
  n_vp: number;
  n_fp: number;
  por_modo: Record<string, number>;
  por_preset: Record<string, number>;
};

export type ConfiancaStats = Record<string, number>;

export type CandidatoRecalibracao = {
  gerado_em: string;
  n_amostras: number;
  n_vp: number;
  n_fp: number;
  f1_score: number;
  detalhes_f1?: { threshold_otimo: number; tp: number; fp: number; fn: number };
  thresholds_sugeridos: { det_min_score_csv: number; det_amp_threshold: number; det_depth_min_m: number };
  thresholds_atuais: { det_min_score_csv: number; det_amp_threshold: number; det_depth_min_m: number };
  aprovado: boolean;
  notas: string;
};

export default async function QualidadePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  // ── 1. Ground truth aggregates ─────────────────────────────────────────────
  const { data: gtRows } = await supabase
    .from("gpr_ground_truth")
    .select("e_falso_positivo, modo_processamento, preset_usado");

  const rows = (gtRows ?? []) as {
    e_falso_positivo: boolean | null;
    modo_processamento: string | null;
    preset_usado: string | null;
  }[];

  const gtStats: GroundTruthStats = {
    total: rows.length,
    n_vp: rows.filter((r) => r.e_falso_positivo === false).length,
    n_fp: rows.filter((r) => r.e_falso_positivo === true).length,
    por_modo: {},
    por_preset: {},
  };

  for (const r of rows) {
    const modo = r.modo_processamento ?? "desconhecido";
    gtStats.por_modo[modo] = (gtStats.por_modo[modo] ?? 0) + 1;
    const preset = r.preset_usado ?? "desconhecido";
    gtStats.por_preset[preset] = (gtStats.por_preset[preset] ?? 0) + 1;
  }

  // ── 2. Confiança das revisões ──────────────────────────────────────────────
  const { data: reviewRows } = await supabase
    .from("technical_reviews")
    .select("confianca_revisao")
    .not("vai_para_relatorio", "is", null);

  const confiancaStats: ConfiancaStats = { alta: 0, media: 0, baixa: 0 };
  for (const r of (reviewRows ?? []) as { confianca_revisao: string | null }[]) {
    const c = r.confianca_revisao ?? "alta";
    confiancaStats[c] = (confiancaStats[c] ?? 0) + 1;
  }

  // ── 3. Último candidato de recalibração (Storage) ─────────────────────────
  let candidato: CandidatoRecalibracao | null = null;
  try {
    const { data: files } = await supabase.storage
      .from("gpr-tabelas")
      .list("recalibracao", { limit: 10, sortBy: { column: "name", order: "desc" } });

    const jsonFiles = (files ?? []).filter((f) => f.name.endsWith(".json"));
    if (jsonFiles.length > 0) {
      const { data: blob } = await supabase.storage
        .from("gpr-tabelas")
        .download(`recalibracao/${jsonFiles[0].name}`);
      if (blob) {
        candidato = JSON.parse(await blob.text()) as CandidatoRecalibracao;
      }
    }
  } catch {
    // Storage inacessível no contexto atual — degradar silenciosamente
  }

  return (
    <QualidadeClient
      gtStats={gtStats}
      confiancaStats={confiancaStats}
      candidato={candidato}
    />
  );
}
