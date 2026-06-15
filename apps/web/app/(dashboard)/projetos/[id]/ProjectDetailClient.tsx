"use client";

import { Fragment, useState, useEffect, useCallback } from "react";
import type { Database } from "@/lib/types/database";
import { reprocessProfile } from "./actions";
import type { FilterState } from "./actions";

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

// ── Filter state ──────────────────────────────────────────────────────────────

const DEFAULT_FILTERS: FilterState = {
  dewow: true,
  background_removal: true,
  bandpass: true,
  bandpass_low: 80,
  bandpass_high: 500,
  gain: true,
  gain_type: "linear",
  contrast: 1.0,
  depth_preview_m: 5.0,
  agc_window_preview: 80,
};

// ── Main component ────────────────────────────────────────────────────────────

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

  // Per-profile filter state
  const [filterStates, setFilterStates] = useState<Record<string, FilterState>>({});
  const [filterTargets, setFilterTargets] = useState<Record<string, "processada" | "processada2">>({});
  const [expandedFilters, setExpandedFilters] = useState<Record<string, boolean>>({});
  const [reprocessStatus, setReprocessStatus] = useState<
    Record<string, "idle" | "loading" | "queued" | "error">
  >({});

  const closeLightbox = useCallback(() => setLightbox(null), []);
  const prevImage = useCallback(
    () =>
      setLightbox((lb) =>
        lb ? { ...lb, index: (lb.index - 1 + lb.images.length) % lb.images.length } : null
      ),
    []
  );
  const nextImage = useCallback(
    () =>
      setLightbox((lb) =>
        lb ? { ...lb, index: (lb.index + 1) % lb.images.length } : null
      ),
    []
  );

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
      { url: profile.imagem_anotada_url ?? "", label: "Anotada IA" },
      { url: profile.imagem_preview_radan_5m_url ?? "", label: "Processada 2" },
    ].filter((i) => i.url);
    if (!imgs.length) return;
    setLightbox({ images: imgs, index: Math.min(startIndex, imgs.length - 1) });
  }

  // ── Filter helpers ──────────────────────────────────────────────────────────

  function getFilters(profileId: string): FilterState {
    return filterStates[profileId] ?? DEFAULT_FILTERS;
  }

  function isCustomized(profileId: string): boolean {
    const fs = filterStates[profileId];
    if (!fs) return false;
    return JSON.stringify(fs) !== JSON.stringify(DEFAULT_FILTERS);
  }

  function updateFilter(profileId: string, patch: Partial<FilterState>) {
    setFilterStates((prev) => ({
      ...prev,
      [profileId]: { ...(prev[profileId] ?? DEFAULT_FILTERS), ...patch },
    }));
  }

  function resetFilters(profileId: string) {
    setFilterStates((prev) => ({ ...prev, [profileId]: DEFAULT_FILTERS }));
  }

  function toggleFilterPanel(profileId: string) {
    setExpandedFilters((prev) => ({ ...prev, [profileId]: !prev[profileId] }));
  }

  async function handleReprocess(profileId: string) {
    setReprocessStatus((prev) => ({ ...prev, [profileId]: "loading" }));
    try {
      const result = await reprocessProfile(profileId, getFilters(profileId));
      setReprocessStatus((prev) => ({
        ...prev,
        [profileId]: result.ok ? "queued" : "error",
      }));
    } catch {
      setReprocessStatus((prev) => ({ ...prev, [profileId]: "error" }));
    }
  }

  // ── Build profile / target maps ─────────────────────────────────────────────

  const profileMap: Record<string, GprProfileRow> = {};
  for (const p of profiles) profileMap[p.id] = p;

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
              const pAlta = pTargets.filter(
                (t) => t.confidence_label_relatorio === "alta"
              ).length;
              const pMedia = pTargets.filter(
                (t) => t.confidence_label_relatorio === "media"
              ).length;
              const pBaixa = pTargets.filter(
                (t) => t.confidence_label_relatorio === "baixa"
              ).length;
              const imgs = [
                { url: profile.imagem_bruta_url, label: "Bruta" },
                { url: profile.imagem_processada_url, label: "Processada" },
                { url: profile.imagem_anotada_url, label: "Anotada IA" },
                { url: profile.imagem_preview_radan_5m_url, label: "Processada 2" },
              ].filter((i): i is { url: string; label: string } => !!i.url);

              const customized = isCustomized(profile.id);
              const expanded = expandedFilters[profile.id] ?? false;
              const rpStatus = reprocessStatus[profile.id] ?? "idle";

              return (
                <div
                  key={profile.id}
                  className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden"
                >
                  {/* Header */}
                  <div className="px-4 py-3 border-b border-slate-800 flex items-center justify-between gap-4">
                    <div>
                      <p className="font-medium text-slate-100">
                        {profile.arquivo_dzt ?? profile.id}
                      </p>
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
                    <div className="flex gap-1.5 shrink-0 text-xs items-center flex-wrap justify-end">
                      {customized && (
                        <span className="bg-amber-500/15 text-amber-400 border border-amber-500/30 px-2 py-0.5 rounded-full font-medium">
                          Customizado
                        </span>
                      )}
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
                      {/* Download buttons */}
                      <div className="flex gap-2 flex-wrap">
                        {imgs.map((img) => (
                          <a
                            key={img.label}
                            href={img.url}
                            download={`${profile.arquivo_dzt ?? profile.id}_${img.label
                              .toLowerCase()
                              .replace(/\s/g, "_")}.png`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-slate-700 bg-slate-800 text-[11px] font-medium text-slate-300 hover:bg-slate-700 transition"
                          >
                            ⬇ {img.label}
                          </a>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* No images / no targets */}
                  {imgs.length === 0 && pTargets.length === 0 && (
                    <p className="text-xs text-slate-500 p-4">Aguardando resultados…</p>
                  )}

                  {/* Filter panel */}
                  <div className="px-4 py-3 border-t border-slate-800/60">
                    <button
                      onClick={() => toggleFilterPanel(profile.id)}
                      className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                    >
                      <span className="text-[10px]">{expanded ? "▾" : "▸"}</span>
                      <span>Ajustar filtros</span>
                    </button>

                    {expanded && (
                      <FilterPanel
                        filters={getFilters(profile.id)}
                        filterTarget={filterTargets[profile.id] ?? "processada"}
                        onTargetChange={(t) =>
                          setFilterTargets((prev) => ({ ...prev, [profile.id]: t }))
                        }
                        onChange={(patch) => updateFilter(profile.id, patch)}
                        onReprocess={() => handleReprocess(profile.id)}
                        onReset={() => resetFilters(profile.id)}
                        status={rpStatus}
                      />
                    )}
                  </div>
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
          {/* Close button — fixed acima do overlay (z-50) */}
          <button
            onClick={(e) => { e.stopPropagation(); closeLightbox(); }}
            className="fixed top-4 right-4 z-[9999] flex items-center justify-center w-10 h-10 rounded-lg bg-black/70 border border-white/20 text-white text-lg hover:bg-red-500/40 transition-colors"
            aria-label="Fechar"
          >
            ✕
          </button>

          {lightbox.images.length > 1 && (
            <>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  prevImage();
                }}
                className="absolute left-4 top-1/2 -translate-y-1/2 text-white text-4xl leading-none hover:text-slate-300 px-3 py-4 z-10"
                aria-label="Anterior"
              >
                ←
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  nextImage();
                }}
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
              className="max-w-full max-h-[75vh] object-contain rounded"
            />

            {/* Tabs — 3b */}
            {lightbox.images.length > 1 && (
              <div className="flex gap-2">
                {lightbox.images.map((img, idx) => (
                  <button
                    key={img.label}
                    onClick={() =>
                      setLightbox((lb) => (lb ? { ...lb, index: idx } : null))
                    }
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      lightbox.index === idx
                        ? "bg-cyan-500 text-slate-950"
                        : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-200"
                    }`}
                  >
                    {img.label}
                  </button>
                ))}
              </div>
            )}

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
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      Arquivo
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      #
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      X (m)
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      Prof (m)
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      Diâm (m)
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      Material
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      Score
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      Confiança
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      IA — Tipo
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px]">
                      IA — Conf.
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px] text-center">
                      Planta
                    </th>
                    <th className="px-3 py-2.5 font-medium text-slate-400 uppercase tracking-wide text-[10px] text-center">
                      Relatório
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {filteredTargets.map((t) => {
                    const ai = aiByTargetId[t.id] ?? null;
                    const prof = profileMap[t.profile_id ?? ""];
                    const score =
                      (t as unknown as Record<string, unknown>)[
                        "confidence_score_0_100"
                      ] ??
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
                        <td className="px-3 py-2 text-slate-300">
                          {t.x_m?.toFixed(2) ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-300">
                          {t.depth_m?.toFixed(2) ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-300">
                          {t.diam_est_m?.toFixed(3) ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-400">
                          {t.tipo_material ?? "—"}
                        </td>
                        <td className="px-3 py-2 text-slate-300">
                          {score != null ? String(score) : "—"}
                        </td>
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
                      <td
                        colSpan={12}
                        className="px-3 py-6 text-center text-slate-500 text-xs"
                      >
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

// ── Filter panel sub-components ───────────────────────────────────────────────

function FilterPanel({
  filters,
  filterTarget,
  onTargetChange,
  onChange,
  onReprocess,
  onReset,
  status,
}: {
  filters: FilterState;
  filterTarget: "processada" | "processada2";
  onTargetChange: (t: "processada" | "processada2") => void;
  onChange: (patch: Partial<FilterState>) => void;
  onReprocess: () => void;
  onReset: () => void;
  status: "idle" | "loading" | "queued" | "error";
}) {
  return (
    <div className="mt-3 rounded-lg border border-slate-700 bg-slate-800/50 p-3 space-y-3">
      {/* Output target tabs */}
      <div className="flex gap-1 rounded-md bg-slate-900 p-0.5 w-fit">
        {(["processada", "processada2"] as const).map((t) => (
          <button
            key={t}
            onClick={() => onTargetChange(t)}
            className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
              filterTarget === t
                ? "bg-cyan-500 text-slate-950"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {t === "processada" ? "Processada" : "Processada 2"}
          </button>
        ))}
      </div>

      {filterTarget === "processada" && (
        <>
          {/* Toggles */}
          <div className="grid grid-cols-2 gap-2">
            <Toggle
              label="Dewow"
              checked={filters.dewow}
              onChange={(v) => onChange({ dewow: v })}
            />
            <Toggle
              label="Background removal"
              checked={filters.background_removal}
              onChange={(v) => onChange({ background_removal: v })}
            />
            <Toggle
              label="Bandpass"
              checked={filters.bandpass}
              onChange={(v) => onChange({ bandpass: v })}
            />
            <Toggle
              label="Gain"
              checked={filters.gain}
              onChange={(v) => onChange({ gain: v })}
            />
          </div>

          {/* Bandpass sliders */}
          {filters.bandpass && (
            <div className="space-y-2">
              <SliderRow
                label={`Bandpass low — ${filters.bandpass_low} MHz`}
                value={filters.bandpass_low}
                min={10}
                max={200}
                step={10}
                onChange={(v) => onChange({ bandpass_low: v })}
              />
              <SliderRow
                label={`Bandpass high — ${filters.bandpass_high} MHz`}
                value={filters.bandpass_high}
                min={100}
                max={600}
                step={10}
                onChange={(v) => onChange({ bandpass_high: v })}
              />
            </div>
          )}

          {/* Gain type */}
          {filters.gain && (
            <div className="flex items-center gap-2">
              <label className="text-xs text-slate-400 w-20 shrink-0">Tipo de gain</label>
              <select
                value={filters.gain_type}
                onChange={(e) =>
                  onChange({ gain_type: e.target.value as FilterState["gain_type"] })
                }
                className="flex-1 rounded border border-slate-600 bg-slate-800 text-slate-200 text-xs px-2 py-1 focus:outline-none focus:ring-1 focus:ring-cyan-500"
              >
                <option value="linear">Linear</option>
                <option value="exponential">Exponencial</option>
                <option value="agc">AGC</option>
              </select>
            </div>
          )}

          {/* Contrast */}
          <SliderRow
            label={`Contraste — ${filters.contrast.toFixed(1)}×`}
            value={filters.contrast}
            min={0.5}
            max={2.0}
            step={0.1}
            onChange={(v) => onChange({ contrast: parseFloat(v.toFixed(1)) })}
          />
        </>
      )}

      {filterTarget === "processada2" && (
        <>
          <p className="text-[10px] text-slate-500 leading-relaxed">
            Imagem visual comparativa (escala RADAN ~5 m). Parâmetros independentes do fluxo científico.
          </p>
          <SliderRow
            label={`Profundidade máxima — ${filters.depth_preview_m.toFixed(1)} m`}
            value={filters.depth_preview_m}
            min={2.0}
            max={8.0}
            step={0.5}
            onChange={(v) => onChange({ depth_preview_m: parseFloat(v.toFixed(1)) })}
          />
          <SliderRow
            label={`Janela AGC visual — ${filters.agc_window_preview} traços`}
            value={filters.agc_window_preview}
            min={40}
            max={200}
            step={10}
            onChange={(v) => onChange({ agc_window_preview: v })}
          />
        </>
      )}

      {/* Actions */}
      <div className="flex gap-2 pt-1">
        <button
          onClick={onReprocess}
          disabled={status === "loading"}
          className="flex-1 rounded-md bg-cyan-500 px-3 py-1.5 text-xs font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {status === "loading" ? "Solicitando…" : "Reaplicar filtros"}
        </button>
        <button
          onClick={onReset}
          className="rounded-md border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 transition-colors"
        >
          Restaurar preset
        </button>
      </div>

      {status === "queued" && (
        <p className="text-xs text-cyan-400">
          ✓ Em fila — reprocessamento em background. Recarregue a página em ~1-2 min.
        </p>
      )}
      {status === "error" && (
        <p className="text-xs text-red-400">
          Erro ao criar job. Verifique a conexão e tente novamente.
        </p>
      )}
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex w-8 h-4 rounded-full transition-colors shrink-0 focus:outline-none focus:ring-1 focus:ring-cyan-500 ${
          checked ? "bg-cyan-500" : "bg-slate-700"
        }`}
      >
        <span
          className={`inline-block w-3 h-3 bg-white rounded-full shadow transition-transform mt-0.5 ${
            checked ? "translate-x-4" : "translate-x-0.5"
          }`}
        />
      </button>
      <span className="text-xs text-slate-300">{label}</span>
    </label>
  );
}

function SliderRow({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <span className="text-xs text-slate-400">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-1.5 bg-slate-700 rounded-full accent-cyan-500 cursor-pointer"
      />
      <div className="flex justify-between text-[10px] text-slate-600">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

// ── Shared helpers ────────────────────────────────────────────────────────────

function ConfBadge({ label }: { label: string | null | undefined }) {
  if (!label) return <span className="text-slate-600">—</span>;
  const cls =
    label === "alta"
      ? "bg-emerald-500/15 text-emerald-400"
      : label === "media"
      ? "bg-amber-500/15 text-amber-400"
      : "bg-slate-700 text-slate-400";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded font-medium ${cls}`}>
      {label}
    </span>
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

// Suppress unused import warning — Fragment kept for future use
void Fragment;
