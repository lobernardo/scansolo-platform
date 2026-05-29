"use client";

import { Fragment, useState } from "react";
import { useRouter } from "next/navigation";
import { reviewTarget, finalizeReview } from "./actions";
import type { Database } from "@/lib/types/database";

type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];
type AiInterpretationRow = Database["public"]["Tables"]["ai_interpretations"]["Row"];
type TechnicalReviewRow = Database["public"]["Tables"]["technical_reviews"]["Row"];

type ReviewStatus = "pendente" | "aprovado" | "ajustado" | "descartado";

type AdjustForm = {
  tipoFinal: string;
  vaiParaPlanta: boolean;
  vaiParaRelatorio: boolean;
  observacao: string;
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
  pendente: "bg-gray-100 text-gray-500",
  aprovado: "bg-green-100 text-green-700",
  ajustado: "bg-blue-100 text-blue-700",
  descartado: "bg-red-50 text-red-500",
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
  aiByTargetId,
  existingReviews,
}: {
  project: { id: string; nome: string };
  targets: DetectedTargetRow[];
  aiByTargetId: Record<string, AiInterpretationRow>;
  existingReviews: Record<string, TechnicalReviewRow>;
}) {
  const router = useRouter();

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
    return {
      tipoFinal: existing?.tipo_final ?? ai?.ia_tipo_sugerido ?? "desconhecido",
      vaiParaPlanta: existing?.vai_para_planta ?? ai?.vai_para_planta_sugerido ?? false,
      vaiParaRelatorio: existing?.vai_para_relatorio ?? ai?.vai_para_relatorio_sugerido ?? true,
      observacao: existing?.observacao ?? "",
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
          <h1 className="text-xl font-bold">Revisão Técnica</h1>
          <p className="text-sm text-gray-500 mt-0.5">{project.nome}</p>
        </div>
        <div className="flex items-center gap-4 shrink-0">
          <span className="text-sm text-gray-500">
            {reviewed} / {total} revisados
          </span>
          <button
            onClick={handleFinalize}
            disabled={finalizing}
            className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 transition-colors"
          >
            {finalizing ? "Finalizando…" : "Finalizar revisão"}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div
          className="bg-green-500 h-1.5 rounded-full transition-all duration-300"
          style={{ width: `${total > 0 ? (reviewed / total) * 100 : 0}%` }}
        />
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 flex justify-between items-center">
          {error}
          <button
            onClick={() => setError(null)}
            className="text-red-400 hover:text-red-600 ml-4"
          >
            ✕
          </button>
        </div>
      )}

      {/* Table */}
      <div className="rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-100 text-left">
              <th className="px-3 py-2.5 font-medium text-gray-500">#</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">X (m)</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">Prof (m)</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">Diâm (m)</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">IA — Tipo</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">IA — Conf.</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">Status</th>
              <th className="px-3 py-2.5 font-medium text-gray-500">Ações</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {targets.map((t) => {
              const ai = aiByTargetId[t.id];
              const status = statuses[t.id] ?? "pendente";
              const isSaving = saving.has(t.id);
              const isExpanded = expandedId === t.id;
              const form = getForm(t.id);

              return (
                <Fragment key={t.id}>
                  <tr className={status === "descartado" ? "opacity-40" : "hover:bg-gray-50"}>
                    <td className="px-3 py-2 text-gray-500">{t.rank}</td>
                    <td className="px-3 py-2">{t.x_m?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{t.depth_m?.toFixed(2) ?? "—"}</td>
                    <td className="px-3 py-2">{t.diam_est_m?.toFixed(3) ?? "—"}</td>
                    <td className="px-3 py-2 text-gray-700">{ai?.ia_tipo_sugerido ?? "—"}</td>
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
                        <span className="text-gray-400 italic">salvando…</span>
                      ) : (
                        <div className="flex gap-1.5">
                          <button
                            disabled={status === "aprovado"}
                            onClick={() => handleAccept(t.id)}
                            className="px-2 py-0.5 rounded text-xs bg-green-50 text-green-700 hover:bg-green-100 disabled:opacity-30 disabled:cursor-default"
                          >
                            Aceitar
                          </button>
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : t.id)}
                            className={`px-2 py-0.5 rounded text-xs ${
                              isExpanded
                                ? "bg-blue-600 text-white"
                                : "bg-blue-50 text-blue-700 hover:bg-blue-100"
                            }`}
                          >
                            Ajustar
                          </button>
                          <button
                            disabled={status === "descartado"}
                            onClick={() => handleDiscard(t.id)}
                            className="px-2 py-0.5 rounded text-xs bg-red-50 text-red-600 hover:bg-red-100 disabled:opacity-30 disabled:cursor-default"
                          >
                            Descartar
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>

                  {isExpanded && (
                    <tr className="bg-blue-50 border-b border-blue-100">
                      <td colSpan={8} className="px-4 py-3">
                        <div className="flex flex-wrap gap-4 items-end">
                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">
                              Tipo final
                            </label>
                            <select
                              value={form.tipoFinal}
                              onChange={(e) => updateForm(t.id, { tipoFinal: e.target.value })}
                              className="text-xs border border-gray-300 rounded px-2 py-1.5 bg-white focus:outline-none focus:ring-1 focus:ring-blue-400"
                            >
                              {TIPOS.map((tp) => (
                                <option key={tp.value} value={tp.value}>
                                  {tp.label}
                                </option>
                              ))}
                            </select>
                          </div>

                          <div className="flex gap-4">
                            <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={form.vaiParaPlanta}
                                onChange={(e) =>
                                  updateForm(t.id, { vaiParaPlanta: e.target.checked })
                                }
                                className="rounded"
                              />
                              Vai para planta
                            </label>
                            <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                              <input
                                type="checkbox"
                                checked={form.vaiParaRelatorio}
                                onChange={(e) =>
                                  updateForm(t.id, { vaiParaRelatorio: e.target.checked })
                                }
                                className="rounded"
                              />
                              Vai para relatório
                            </label>
                          </div>

                          <div>
                            <label className="block text-xs font-medium text-gray-600 mb-1">
                              Observação
                            </label>
                            <input
                              type="text"
                              value={form.observacao}
                              onChange={(e) => updateForm(t.id, { observacao: e.target.value })}
                              placeholder="Opcional"
                              className="text-xs border border-gray-300 rounded px-2 py-1.5 w-52 focus:outline-none focus:ring-1 focus:ring-blue-400"
                            />
                          </div>

                          <div className="flex gap-2">
                            <button
                              onClick={() => handleSaveAdjust(t.id)}
                              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded hover:bg-blue-700 transition-colors"
                            >
                              Salvar ajuste
                            </button>
                            <button
                              onClick={() => setExpandedId(null)}
                              className="text-xs text-gray-500 px-2 py-1.5 hover:text-gray-700"
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
            className="rounded-md bg-gray-900 px-5 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 transition-colors"
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
  if (!label) return <span className="text-gray-300">—</span>;
  const colors =
    label === "alta"
      ? "bg-green-100 text-green-700"
      : label === "media"
        ? "bg-yellow-100 text-yellow-700"
        : "bg-red-50 text-red-600";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded font-medium ${colors}`}>
      {label}
    </span>
  );
}
