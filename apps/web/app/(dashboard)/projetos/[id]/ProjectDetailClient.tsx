"use client";

import { Fragment, useState, useEffect, useCallback } from "react";
import type { Database } from "@/lib/types/database";

type GprProfileRow = Database["public"]["Tables"]["gpr_profiles"]["Row"];
type DetectedTargetRow = Database["public"]["Tables"]["detected_targets"]["Row"];
type AiInterpretationRow = Database["public"]["Tables"]["ai_interpretations"]["Row"];

type LightboxState = { images: { url: string; label: string }[]; index: number };
type FilterTab = "all" | "alta" | "media" | "baixa";

export type DownloadFile = {
  label: string;
  url: string | null;
  ext: string;
};

export function ProjectDetailClient({
  profiles,
  targets,
  aiByTargetId,
  downloadFiles,
}: {
  profiles: GprProfileRow[];
  targets: DetectedTargetRow[];
  aiByTargetId: Record<string, AiInterpretationRow>;
  downloadFiles: DownloadFile[];
}) {
  const [lightbox, setLightbox] = useState<LightboxState | null>(null);
  const [filterTab, setFilterTab] = useState<FilterTab>("all");

  const closeLightbox = useCallback(() => setLightbox(null), []);
  const prevImage = useCallback(() =>
    setLightbox((lb) =>
      lb ? { ...lb, index: (lb.index - 1 + lb.images.length) % lb.images.length } : null
    ), []);
  const nextImage = useCallback(() =>
    setLightbox((lb) =>
      lb ? { ...lb, index: (lb.index + 1) % lb.images.length } : null
    ), []);

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

  function openLightbox(profile: GprProfileRow, startIndex: number) {
    const imgs: { url: string; label: string }[] = [
      { url: profile.imagem_bruta_url ?? "", label: "Bruta" },
      { url: profile.imagem_processada_url ?? "", label: "Processada" },
      { url: profile.imagem_anotada_url ?? "", label: "Anotada (IA)" },
    ].filter((i) => i.url);
    if (!imgs.length) return;
    setLightbox({ images: imgs, index: Math.min(startIndex, imgs.length - 1) });
  }

  // Build profile map for targets table
  const profileMap: Record<string, GprProfileRow> = {};
  for (const p of profiles) profileMap[p.id] = p;

  // Target counts
  const nAlta = targets.filter((t) => t.confidence_label_relatorio === "alta").length;
  const nMedia = targets.filter((t) => t.confidence_label_relatorio === "media").length;
  const nBaixa = targets.filter((t) => t.confidence_label_relatorio === "baixa").length;

  const filteredTargets =
    filterTab === "all"
      ? targets
      : targets.filter((t) => t.confidence_label_relatorio === filterTab);

  const visibleFiles = downloadFiles.filter((f) => f.url);

  return (
    <div className="space-y-8">
      {/* ── Profile cards ── */}
      {profiles.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-slate-100 mb-4">
            Perfis GPR{" "}
            <span className="text-sm font-normal text-slate-500">
              ({profiles.length} perfil{profiles.length !== 1 ? "s" : ""} ·{" "}
              {targets.length} alvo{targets.length !== 1 ? "s" : ""} total)
            </span>
          </h2>
          <div className="grid gap-4">
            {profiles.map((profile) => {
              const pTargets = targets.filter((t) => t.profile_id === profile.id);
              const pAlta = pTargets.filter((t) => t.confidence_label_relatorio === "alta").length;
              const pMedia = pTargets.filter((t) => t.confidence_label_relatorio === "media").length;
              const pBaixa = pTargets.filter((t) => t.confidence_label_relatorio === "baixa").length;
              const imgs = [
                { url: profile.imagem_bruta_url, label: "Bruta" },
                { url: profile.imagem_processada_url, label: "Processada" },
                { url: profile.imagem_anotada_url, label: "Anotada IA" },
              ].filter((i): i is { url: string; label: string } => !!i.url);

              return (
                <div key={profile.id} className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
                  {/* Header */}
                  <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-slate-100">{profile.arquivo_dzt ?? profile.id}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {profile.n_tracos != null ? `${profile.n_tracos} traços` : "—"}
                        {profile.distancia_max_m != null
                          ? ` · ${profile.distancia_max_m.toFixed(2)} m dist.`
                          : ""}
                        {profile.profundidade_max_m != null
                          ? ` · ${profile.profundidade_max_m.toFixed(2)} m prof.`
                          : ""}
                      </p>
                    </div>
                    {pTargets.length > 0 && (
                      <div className="flex gap-1.5 shrink-0 text-xs">
                        {pAlta > 0 && (
                          <span className="bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 px-2 py-0.5 rounded-full font-medium">
                            {pAlta} alta
                          </span>
                        )}
                        {pMedia > 0 && (
                          <span className="bg-amber-500/15 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full font-medium">
                            {pMedia} média
                          </span>
                        )}
                        {pBaixa > 0 && (
                          <span className="bg-slate-700 text-slate-400 border border-slate-600 px-2 py-0.5 rounded-full font-medium">
                            {pBaixa} baixa
                          </span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Thumbnails + download */}
                  {imgs.length > 0 && (
                    <div className="p-3 bg-slate-800/50 border-b border-slate-800 space-y-2">
                      <div className="flex gap-2">
                        {imgs.map((img, idx) => (
                          <button
                            key={img.label}
                            onClick={() => openLightbox(profile, idx)}
                            className="relative group rounded overflow-hidden border border-slate-700 hover:border-cyan-500/50 transition-colors flex-1"
                            title={`Abrir ${img.label} em tamanho real`}
                          >
                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                              src={img.url}
                              alt={img.label}
                              className="w-full h-36 object-cover"
                            />
                            <div className="absolute inset-0 bg-black/0 group-hover:bg-black/15 transition-colors" />
                            <span className="absolute bottom-0 left-0 right-0 bg-black/65 text-white text-[10px] text-center py-1 font-medium">
                              {img.label}
                            </span>
                          </button>
                        ))}
                      </div>
                      {/* Botões de download por imagem */}
                      <div className="flex gap-2 flex-wrap">
                        {imgs.map((img) => (
                          <a
                            key={img.label}
                            href={img.url}
                            download={`${profile.arquivo_dzt ?? profile.id}_${img.label.toLowerCase().replace(/\s/g, "_")}.png`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-700 bg-slate-800 text-[11px] font-medium text-slate-300 hover:bg-slate-700 transition"
                          >
                            ⬇ {img.label}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* No images, no targets */}
                  {imgs.length === 0 && pTargets.length === 0 && (
                    <p className="text-xs text-slate-500 p-4">Aguardando resultados…</p>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Lightbox overlay ── */}
      {lightbox && (
        <div
          className="fixed inset-0 z-50 bg-black/92 flex items-center justify-center"
          onClick={closeLightbox}
        >
          <button
            onClick={closeLightbox}
            className="absolute top-4 right-5 text-white text-3xl leading-none hover:text-slate-300 z-10"
            aria-label="Fechar"
          >
            ✕
          </button>

          {lightbox.images.length > 1 && (
            <>
              <button
                onClick={(e) => { e.stopPropagation(); prevImage(); }}
                className="absolute left-4 top-1/2 -translate-y-1/2 text-white text-4xl leading-none hover:text-slate-300 px-3 py-4 z-10"
                aria-label="Anterior"
              >
                ←
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); nextImage(); }}
                className="absolute right-4 top-1/2 -translate-y-1/2 text-white text-4xl leading-none hover:text-slate-300 px-3 py-4 z-10"
                aria-label="Próxima"
              >
                →
              </button>
            </>
          )}

          <div
            className="flex flex-col items-center gap-3 max-w-[90vw] max-h-[90vh] z-10"
            onClick={(e) => e.stopPropagation()}
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={lightbox.images[lightbox.index].url}
              alt={lightbox.images[lightbox.index].label}
              className="max-w-full max-h-[82vh] object-contain rounded"
            />
            <div className="flex items-center gap-4">
              <span className="text-white text-sm font-medium">
                {lightbox.images[lightbox.index].label}
              </span>
              <span className="text-slate-400 text-xs">
                {lightbox.index + 1} / {lightbox.images.length}
              </span>
              {lightbox.images.length > 1 && (
                <span className="text-slate-500 text-xs">← → ou setas do teclado</span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Targets table ── */}
      {targets.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-3 gap-4">
            <h2 className="text-lg font-semibold text-slate-100 shrink-0">
              Alvos detectados{" "}
              <span className="text-sm font-normal text-slate-500">
                ({targets.length} total)
              </span>
            </h2>
            <div className="flex gap-1 flex-wrap">
              {(
                [
                  { id: "all" as FilterTab, label: `Todos (${targets.length})` },
                  { id: "alta" as FilterTab, label: `Alta (${nAlta})` },
                  { id: "media" as FilterTab, label: `Média (${nMedia})` },
                  { id: "baixa" as FilterTab, label: `Baixa (${nBaixa})` },
                ] as { id: FilterTab; label: string }[]
              ).map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setFilterTab(tab.id)}
                  className={`text-xs px-3 py-1 rounded-full font-medium transition-colors ${
                    filterTab === tab.id
                      ? tab.id === "all"
                        ? "bg-cyan-500 text-slate-950"
                        : tab.id === "alta"
                        ? "bg-emerald-500 text-white"
                        : tab.id === "media"
                        ? "bg-amber-500 text-slate-950"
                        : "bg-slate-600 text-white"
                      : "bg-slate-800 text-slate-400 hover:bg-slate-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-slate-800 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-800/50 border-b border-slate-700 text-left">
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Arquivo</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">#</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">X (m)</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Prof (m)</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Diâm (m)</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Material</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Score</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">Confiança</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">IA — Tipo</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">IA — Conf.</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px] text-center">Planta</th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px] text-center">Relatório</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {filteredTargets.map((t) => {
                    const ai = aiByTargetId[t.id] ?? null;
                    const prof = profileMap[t.profile_id ?? ""];
                    const score =
                      (t as unknown as Record<string, unknown>)["confidence_score_0_100"] ??
                      (t as unknown as Record<string, unknown>)["confidence_score"];
                    return (
                      <tr
                        key={t.id}
                        className="hover:bg-slate-800/60"
                        title={ai?.ia_descricao ?? undefined}
                      >
                        <td className="px-3 py-2 text-slate-500 max-w-[110px] truncate">
                          {prof?.arquivo_dzt ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-400">{t.rank}</td>
                        <td className="px-3 py-2 text-slate-300">{t.x_m?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-300">{t.depth_m?.toFixed(2) ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-300">{t.diam_est_m?.toFixed(3) ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-400">{t.tipo_material ?? "—"}</td>
                        <td className="px-3 py-2 text-slate-300">{score != null ? String(score) : "—"}</td>
                        <td className="px-3 py-2">
                          <ConfBadge label={t.confidence_label_relatorio} />
                        </td>
                        <td className="px-3 py-2 text-slate-400">
                          {ai?.ia_tipo_sugerido ?? "—"}
                        </td>
                        <td className="px-3 py-2">
                          <ConfBadge label={ai?.ia_confianca ?? null} />
                        </td>
                        <td className="px-3 py-2 text-center">
                          {ai?.vai_para_planta_sugerido ? (
                            <span className="text-emerald-400 font-bold">✓</span>
                          ) : (
                            <span className="text-slate-700">✗</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-center">
                          {ai?.vai_para_relatorio_sugerido ? (
                            <span className="text-emerald-400 font-bold">✓</span>
                          ) : (
                            <span className="text-slate-700">✗</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {filteredTargets.length === 0 && (
                    <tr>
                      <td colSpan={12} className="px-3 py-6 text-center text-slate-500 text-xs">
                        Nenhum alvo com confiança &quot;{filterTab}&quot;
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </section>
      )}

      {/* ── Files section ── */}
      {visibleFiles.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-slate-100 mb-3">Arquivos gerados</h2>
          <div className="rounded-xl border border-slate-800 bg-slate-900 divide-y divide-slate-800">
            {visibleFiles.map((f) => (
              <a
                key={f.label}
                href={f.url!}
                download
                className="flex items-center gap-3 px-4 py-3 hover:bg-slate-800/60 transition-colors group"
              >
                <span className="text-xl shrink-0">{fileIcon(f.ext)}</span>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-slate-100 truncate">{f.label}</p>
                  <p className="text-xs text-slate-500 uppercase">{f.ext}</p>
                </div>
                <span className="ml-auto text-xs text-cyan-400 font-medium shrink-0 group-hover:underline">
                  ↓ Baixar
                </span>
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function ConfBadge({ label }: { label: string | null | undefined }) {
  if (!label) return <span className="text-slate-600">—</span>;
  const cls =
    label === "alta"
      ? "bg-emerald-500/15 text-emerald-400"
      : label === "media"
      ? "bg-amber-500/15 text-amber-400"
      : "bg-slate-700 text-slate-400";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded font-medium ${cls}`}>{label}</span>
  );
}

function fileIcon(ext: string): string {
  if (ext === "docx") return "📄";
  if (ext === "pdf") return "📕";
  if (ext === "dxf") return "📐";
  if (ext === "kml") return "🗺️";
  if (ext === "csv") return "📊";
  return "📁";
}
