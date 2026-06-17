"use client";

import { Fragment, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { reviewTarget, finalizeReview } from "./actions";
import type { Database } from "@/lib/types/database";

type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];
type AiInterpretationRow = Database["public"]["Tables"]["ai_interpretations"]["Row"];
type TechnicalReviewRow = Database["public"]["Tables"]["technical_reviews"]["Row"];

type ProfileSlim = {
  id: string;
  arquivo_dzt: string | null;
  imagem_bruta_url: string | null;
  imagem_processada_url: string | null;
  imagem_anotada_url: string | null;
};

type LightboxState = { images: { url: string; label: string }[]; index: number };

type ReviewStatus = "pendente" | "aprovado" | "ajustado" | "descartado";

type AdjustForm = {
  tipoFinal: string;
  vaiParaPlanta: boolean;
  vaiParaRelatorio: boolean;
  observacao: string;
  confiancaRevisao: "alta" | "media" | "baixa";
  profundidadeReal: string;
  eReferencia: boolean;
};

const TIPOS = [
  { value: "tubulacao_agua", label: "Tubulação de água" },
  { value: "tubulacao_gas", label: "Tubulação de gás" },
  { value: "cabo_eletrico", label: "Cabo elétrico" },
  { value: "cabo_telecom", label: "Cabo telecom" },
  { value: "vazio", label: "Vazio / Cavidade" },
  { value: "raiz", label: "Raiz" },
  { value: "rocha", label: "Rocha" },
  { value: "desconhecido", label: "Desconhecido" },
];

const STATUS_STYLE: Record<ReviewStatus, string> = {
  pendente: "bg-slate-700 text-slate-400",
  aprovado: "bg-emerald-500/15 text-emerald-400",
  ajustado: "bg-blue-500/15 text-blue-400",
  descartado: "bg-red-500/15 text-red-400",
};

const STATUS_LABEL: Record<ReviewStatus, string> = {
  pendente: "pendente",
  aprovado: "aprovado",
  ajustado: "ajustado",
  descartado: "descartado",
};

export function ReviewClient({
  project,
  targets,
  profiles = [],
  aiByTargetId,
  existingReviews,
}: {
  project: { id: string; nome: string };
  targets: DetectedTargetRow[];
  profiles?: ProfileSlim[];
  aiByTargetId: Record<string, AiInterpretationRow>;
  existingReviews: Record<string, TechnicalReviewRow>;
}) {
  const router = useRouter();

  const [lightbox, setLightbox] = useState<LightboxState | null>(null);

  const closeLightbox = useCallback(() => setLightbox(null), []);

  const prevImage = useCallback(() => {
    setLightbox((lb) => lb ? { ...lb, index: (lb.index - 1 + lb.images.length) % lb.images.length } : null);
  }, []);

  const nextImage = useCallback(() => {
    setLightbox((lb) => lb ? { ...lb, index: (lb.index + 1) % lb.images.length } : null);
  }, []);

  useEffect(() => {
    if (!lightbox) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") closeLightbox();
      else if (e.key === "ArrowLeft") prevImage();
      else if (e.key === "ArrowRight") nextImage();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [lightbox, closeLightbox, prevImage, nextImage]);

  function openLightbox(profile: ProfileSlim, startIndex: number) {
    const imgs: { url: string; label: string }[] = [
      { url: profile.imagem_bruta_url ?? "", label: "Bruta" },
      { url: profile.imagem_processada_url ?? "", label: "Processada" },
      { url: profile.imagem_anotada_url ?? "", label: "Anotada" },
    ].filter((i) => i.url);
    if (imgs.length === 0) return;
    const safeIndex = Math.min(startIndex, imgs.length - 1);
    setLightbox({ images: imgs, index: safeIndex });
  }

  const [statuses, setStatuses] = useState<Record<string, ReviewStatus>>(() => {
    const init: Record<string, ReviewStatus> = {};
    for (const t of targets) {
      init[t.id] = (existingReviews[t.id]?.status_review as ReviewStatus) ?? "pendente";
    }
    return init;
  });

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [forms, setForms] = useState<Record<string, AdjustForm>>({});
  const [saving, setSaving] = useState<Set<string>>(new Set());
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function getForm(targetId: string): AdjustForm {
    if (forms[targetId]) return forms[targetId];
    const existing = existingReviews[targetId];
    const ai = aiByTargetId[targetId];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const ex = existing as any;
    return {
      tipoFinal: existing?.tipo_final ?? ai?.ia_tipo_sugerido ?? "desconhecido",
      vaiParaPlanta: existing?.vai_para_planta ?? ai?.vai_para_planta_sugerido ?? false,
      vaiParaRelatorio: existing?.vai_para_relatorio ?? ai?.vai_para_relatorio_sugerido ?? true,
      observacao: existing?.observacao ?? "",
      confiancaRevisao: (ex?.confianca_revisao ?? "alta") as "alta" | "media" | "baixa",
      profundidadeReal: ex?.profundidade_real_m != null ? String(ex.profundidade_real_m) : "",
      eReferencia: ex?.e_referencia ?? false,
    };
  }

  function updateForm(targetId: string, patch: Partial<AdjustForm>) {
    setForms((prev) => ({ ...prev, [targetId]: { ...getForm(targetId), ...patch } }));
  }

  function startSaving(id: string) {
    setSaving((prev) => new Set(prev).add(id));
  }
  function stopSaving(id: string) {
    setSaving((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  async function handleAccept(targetId: string) {
    const ai = aiByTargetId[targetId];
    setStatuses((prev) => ({ ...prev, [targetId]: "aprovado" }));
    startSaving(targetId);

    const result = await reviewTarget({
      targetId,
      projectId: project.id,
      statusReview: "aprovado",
      tipoFinal: ai?.ia_tipo_sugerido ?? null,
      vaiParaPlanta: ai?.vai_para_planta_sugerido ?? false,
      vaiParaRelatorio: ai?.vai_para_relatorio_sugerido ?? true,
    });

    stopSaving(targetId);
    if (!result.ok) {
      setStatuses((prev) => ({ ...prev, [targetId]: "pendente" }));
      setError(result.error ?? "Erro ao salvar");
    }
  }

  async function handleDiscard(targetId: string) {
    setStatuses((prev) => ({ ...prev, [targetId]: "descartado" }));
    startSaving(targetId);

    const result = await reviewTarget({
      targetId,
      projectId: project.id,
      statusReview: "descartado",
      vaiParaPlanta: false,
      vaiParaRelatorio: false,
    });

    stopSaving(targetId);
    if (!result.ok) {
      setStatuses((prev) => ({ ...prev, [targetId]: "pendente" }));
      setError(result.error ?? "Erro ao salvar");
    }
  }

  async function handleSaveAdjust(targetId: string) {
    const form = getForm(targetId);
    setStatuses((prev) => ({ ...prev, [targetId]: "ajustado" }));
    setExpandedId(null);
    startSaving(targetId);

    const result = await reviewTarget({
      targetId,
      projectId: project.id,
      statusReview: "ajustado",
      tipoFinal: form.tipoFinal,
      vaiParaPlanta: form.vaiParaPlanta,
      vaiParaRelatorio: form.vaiParaRelatorio,
      observacao: form.observacao || null,
      confiancaRevisao: form.vaiParaRelatorio ? form.confiancaRevisao : null,
      profundidadeReal: form.eReferencia && form.profundidadeReal !== ""
        ? parseFloat(form.profundidadeReal)
        : null,
      eReferencia: form.eReferencia,
    });

    stopSaving(targetId);
    if (!result.ok) {
      setStatuses((prev) => ({ ...prev, [targetId]: "pendente" }));
      setExpandedId(targetId);
      setError(result.error ?? "Erro ao salvar");
    }
  }

  async function handleFinalize() {
    setFinalizing(true);
    const result = await finalizeReview(project.id);
    setFinalizing(false);
    if (result.ok) {
      router.push(`/projetos/${project.id}`);
    } else {
      setError(result.error ?? "Erro ao finalizar");
    }
  }

  const reviewed = Object.values(statuses).filter((s) => s !== "pendente").length;
  const total = targets.length;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-slate-100">Revisão Técnica</h1>
          <p className="text-sm text-slate-400 mt-0.5">{project.nome}</p>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <span className="text-sm text-slate-400">
            {reviewed} / {total} revisados
          </span>
          <button
            onClick={handleFinalize}
            disabled={finalizing}
            className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50 transition-colors"
          >
            {finalizing ? "Finalizando…" : "Finalizar revisão"}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-slate-800 rounded-full h-1.5">
        <div
          className="bg-cyan-500 h-1.5 rounded-full transition-all duration-300"
          style={{ width: `${total > 0 ? (reviewed / total) * 100 : 0}%` }}
        />
      </div>

      {/* Profile image thumbnails */}
      {profiles.length > 0 && (
        <div className="space-y-3">
          {profiles.map((prof) => {
            const imgs = [
              { url: prof.imagem_bruta_url, label: "Bruta" },
              { url: prof.imagem_processada_url, label: "Processada" },
              { url: prof.imagem_anotada_url, label: "Anotada" },
            ].filter((i): i is { url: string; label: string } => !!i.url);
            if (imgs.length === 0) return null;
            return (
              <div key={prof.id} className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
                <p className="text-xs font-medium text-slate-500 px-3 py-1.5 border-b border-slate-800">
                  {prof.arquivo_dzt ?? prof.id}
                </p>
                <div className="flex gap-2 p-2">
                  {imgs.map((img, idx) => (
                    <button
                      key={img.label}
                      onClick={() => openLightbox(prof, idx)}
                      className="relative group rounded overflow-hidden border border-slate-700 hover:border-cyan-500/50 transition-colors"
                      title={`Abrir ${img.label}`}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={img.url} alt={img.label} className="h-20 w-auto object-cover" />
                      <span className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[10px] text-center py-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
                        {img.label}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Lightbox overlay */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
          onClick={closeLightbox}
        >
          <button
            onClick={closeLightbox}
            className="absolute top-4 right-4 text-white text-2xl leading-none hover:text-slate-300"
            aria-label="Fechar"
          >
            ✕
          </button>

          {lightbox.images.length > 1 && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); prevImage(); }}
                className="absolute left-4 text-white text-3xl leading-none hover:text-slate-300 px-2"
                aria-label="Anterior"
              >
                ←
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); nextImage(); }}
                className="absolute right-12 text-white text-3xl leading-none hover:text-slate-300 px-2"
                aria-label="Próxima"
              >
                →
              </button>
            </>
          )}

          <div className="flex flex-col items-center gap-3 max-w-[90vw] max-h-[90vh]" onClick={(e) => e.stopPropagation()}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={lightbox.images[lightbox.index].url}
              alt={lightbox.images[lightbox.index].label}
              className="max-w-full max-h-[80vh] object-contain rounded"
            />
            <div className="flex gap-3 items-center">
              <span className="text-white text-sm">{lightbox.images[lightbox.index].label}</span>
              <span className="text-slate-400 text-xs">{lightbox.index + 1} / {lightbox.images.length}</span>
            </div>
          </div>
        </div>
      )}

      {/* Error banner */}
      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-400 flex justify-between items-center">
          {error}
          <button
            onClick={() => setError(null)}
            className="text-red-500 hover:text-red-300 ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-xl border border-slate-800 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-slate-800/50 border-b border-slate-700 text-left">
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">#</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">X (m)</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Prof (m)</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Diâm (m)</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">IA — Tipo</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">IA — Conf.</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Status</th>
              <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {targets.map((t) => {
              const ai = aiByTargetId[t.id];
              const status = statuses[t.id] ?? "pendente";
              const isSaving = saving.has(t.id);
              const isExpanded = expandedId === t.id;
              const form = getForm(t.id);

              return (
                <Fragment key={t.id}>
                  <tr className={status === "descartado" ? "opacity-40" : "hover:bg-slate-800/60"}>
                    <td className="px-3 py-2 text-slate-400">{t.rank}</td>
                    <td className="px-3 py-2 text-slate-300">{t.x_m?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2 text-slate-300">{t.depth_m?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2 text-slate-300">{t.diam_est_m?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-2 text-slate-400">{ai?.ia_tipo_sugerido ?? "—"}</td>
                    <td className="px-3 py-2">
                      <ConfBadge label={ai?.ia_confianca ?? null} />
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`inline-block px-1.5 py-0.5 rounded text-xs font-medium ${STATUS_STYLE[status]}`}
                      >
                        {STATUS_LABEL[status]}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      {isSaving ? (
                        <span className="text-slate-500 italic">salvando…</span>
                      ) : (
                        <div className="flex gap-1.5">
                          <button
                            disabled={status === "aprovado"}
                            onClick={() => handleAccept(t.id)}
                            className="px-2 py-0.5 rounded text-xs bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 disabled:opacity-30 disabled:cursor-default transition-colors"
                          >
                            Aceitar
                          </button>
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : t.id)}
                            className={`px-2 py-0.5 rounded text-xs transition-colors ${
                              isExpanded
                                ? "bg-cyan-500 text-slate-950"
                                : "bg-blue-500/15 text-blue-400 hover:bg-blue-500/25"
                            }`}
                          >
                            Ajustar
                          </button>
                          <button
                            disabled={status === "descartado"}
                            onClick={() => handleDiscard(t.id)}
                            className="px-2 py-0.5 rounded text-xs bg-red-500/15 text-red-400 hover:bg-red-500/25 disabled:opacity-30 disabled:cursor-default transition-colors"
                          >
                            Descartar
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>

                  {isExpanded && (
                    <tr className="bg-slate-800/50 border-b border-slate-700">
                      <td colSpan={8} className="px-4 py-3">
                        <div className="flex flex-wrap gap-4 items-end">
                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">
                              Tipo final
                            </label>
                            <select
                              value={form.tipoFinal}
                              onChange={(e) => updateForm(t.id, { tipoFinal: e.target.value })}
                              className="text-xs bg-slate-800 border border-slate-700 text-slate-100 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                            >
                              {TIPOS.map((tp) => (
                                <option key={tp.value} value={tp.value}>
                                  {tp.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="flex gap-4">
                            <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={form.vaiParaPlanta}
                                onChange={(e) =>
                                  updateForm(t.id, { vaiParaPlanta: e.target.checked })
                                }
                                className="rounded border-slate-600 bg-slate-800"
                              />
                              Vai para planta
                            </label>
                            <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={form.vaiParaRelatorio}
                                onChange={(e) =>
                                  updateForm(t.id, { vaiParaRelatorio: e.target.checked })
                                }
                                className="rounded border-slate-600 bg-slate-800"
                              />
                              Vai para relatório
                            </label>
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-slate-400 mb-1">
                              Observação
                            </label>
                            <input
                              type="text"
                              value={form.observacao}
                              onChange={(e) => updateForm(t.id, { observacao: e.target.value })}
                              placeholder="Opcional"
                              className="text-xs bg-slate-800 border border-slate-700 text-slate-100 rounded px-2 py-1.5 w-52 focus:outline-none focus:ring-1 focus:ring-cyan-500 placeholder:text-slate-500"
                            />
                          </div>

                          {form.vaiParaRelatorio && (
                            <div>
                              <label className="block text-xs font-medium text-slate-400 mb-1">
                                Confiança
                              </label>
                              <select
                                value={form.confiancaRevisao}
                                onChange={(e) =>
                                  updateForm(t.id, {
                                    confiancaRevisao: e.target.value as "alta" | "media" | "baixa",
                                  })
                                }
                                className="text-xs bg-slate-800 border border-slate-700 text-slate-100 rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500"
                              >
                                <option value="alta">Alta</option>
                                <option value="media">Média</option>
                                <option value="baixa">Baixa</option>
                              </select>
                            </div>
                          )}

                          <label
                            className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer self-end pb-1.5"
                            title="Marque se a profundidade real deste alvo foi medida em campo. Usado para calibrar a velocity."
                          >
                            <input
                              type="checkbox"
                              checked={form.eReferencia}
                              onChange={(e) => updateForm(t.id, { eReferencia: e.target.checked })}
                              className="rounded border-slate-600 bg-slate-800"
                            />
                            Alvo de referência (depth known)
                          </label>

                          {form.eReferencia && (
                            <div>
                              <label className="block text-xs font-medium text-slate-400 mb-1">
                                Prof. medida in-field
                              </label>
                              <input
                                type="number"
                                step="0.01"
                                min="0"
                                max="10"
                                value={form.profundidadeReal}
                                onChange={(e) =>
                                  updateForm(t.id, { profundidadeReal: e.target.value })
                                }
                                placeholder="Prof. real (m)"
                                className="text-xs bg-slate-800 border border-slate-700 text-slate-100 rounded px-2 py-1.5 w-32 focus:outline-none focus:ring-1 focus:ring-cyan-500 placeholder:text-slate-500"
                              />
                            </div>
                          )}

                          <div className="flex gap-2">
                            <button
                              onClick={() => handleSaveAdjust(t.id)}
                              className="text-xs bg-cyan-500 text-slate-950 px-3 py-1.5 rounded hover:bg-cyan-400 transition-colors font-semibold"
                            >
                              Salvar ajuste
                            </button>
                            <button
                              onClick={() => setExpandedId(null)}
                              className="text-xs text-slate-500 px-2 py-1.5 hover:text-slate-300 transition-colors"
                            >
                              Cancelar
                            </button>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Bottom finalize */}
      {total > 0 && (
        <div className="flex justify-end pt-2">
          <button
            onClick={handleFinalize}
            disabled={finalizing}
            className="rounded-md bg-cyan-500 px-5 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50 transition-colors"
          >
            {finalizing
              ? "Finalizando…"
              : `Finalizar revisão${reviewed < total ? ` (${total - reviewed} pendentes serão aceitos)` : ""}`}
          </button>
        </div>
      )}
    </div>
  );
}

function ConfBadge({ label }: { label: string | null }) {
  if (!label) return <span className="text-slate-600">—</span>;
  const colors =
    label === "alta"
      ? "bg-emerald-500/15 text-emerald-400"
      : label === "media"
        ? "bg-amber-500/15 text-amber-400"
        : "bg-red-500/15 text-red-400";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded font-medium ${colors}`}>
      {label}
    </span>
  );
}
