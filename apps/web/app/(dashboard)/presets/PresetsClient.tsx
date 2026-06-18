"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { GprPreset, PresetUpsertData } from "@/app/actions/preset-actions";
import {
  createPreset,
  updatePreset,
  deletePreset,
  duplicatePreset,
} from "@/app/actions/preset-actions";

// ── Default parameter values for new presets ──────────────────────────────────
const DEFAULT_PARAMS: Record<string, unknown> = {
  dewow_window: 5,
  bandpass_low_mhz: 80,
  bandpass_high_mhz: 500,
  bandpass_order: 5,
  bgremoval_traces: 30,
  tpow_power: 0.5,
  agc_window: 150,
  velocity_mns: 0.10,
  contrast: 2.5,
  colormap: "gray",
  dpi: 150,
  det_amp_threshold: 0.50,
  det_h_min_m: 0.10,
  det_h_max_m: 3.00,
  det_top_n: 25,
  det_min_score_csv: 30,
  det_depth_min_m: 0.30,
  detector_input_mode: "raw",
  tipo_solo: "standard",
  fis_ativo: true,
  fis_amp_metal_thr: 0.75,
  fis_amp_nao_metal_thr: 0.40,
};

type ModalState = {
  mode: "create" | "edit";
  preset?: GprPreset;
};

// ── Main component ─────────────────────────────────────────────────────────────

export function PresetsClient({
  presets,
  isAdmin,
}: {
  presets: GprPreset[];
  isAdmin: boolean;
}) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [modal, setModal] = useState<ModalState | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  function toggleExpand(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function openCreate() {
    setModal({ mode: "create" });
  }

  function openEdit(preset: GprPreset) {
    setModal({ mode: "edit", preset });
  }

  function openDuplicate(preset: GprPreset) {
    setModal({ mode: "create", preset });
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Desativar o preset "${name}"? Esta ação pode ser revertida pelo suporte.`)) return;
    const result = await deletePreset(id);
    if (result.ok) {
      startTransition(() => router.refresh());
    } else {
      alert(`Erro: ${result.error}`);
    }
  }

  const systemPresets = presets.filter((p) => p.is_system);
  const userPresets = presets.filter((p) => !p.is_system);

  return (
    <>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Presets de Processamento</h1>
          <p className="text-sm text-slate-500 mt-1">
            Configurações técnicas de processamento GPR com base científica.
          </p>
        </div>
        {isAdmin && (
          <button
            onClick={openCreate}
            className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
          >
            + Novo preset
          </button>
        )}
      </div>

      {/* System presets */}
      <section className="mb-8">
        <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
          Presets do sistema ({systemPresets.length})
        </h2>
        <div className="grid gap-3">
          {systemPresets.map((p) => (
            <PresetCard
              key={p.id}
              preset={p}
              isAdmin={isAdmin}
              expanded={expanded.has(p.id)}
              onToggleExpand={() => toggleExpand(p.id)}
              onDuplicate={() => openDuplicate(p)}
              onEdit={() => {}}
              onDelete={() => {}}
              isSystem
            />
          ))}
        </div>
      </section>

      {/* User presets */}
      {(userPresets.length > 0 || isAdmin) && (
        <section>
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">
            Presets personalizados ({userPresets.length})
          </h2>
          {userPresets.length === 0 ? (
            <p className="text-sm text-slate-600">
              Nenhum preset personalizado. Clique em &ldquo;+ Novo preset&rdquo; ou duplique um do sistema.
            </p>
          ) : (
            <div className="grid gap-3">
              {userPresets.map((p) => (
                <PresetCard
                  key={p.id}
                  preset={p}
                  isAdmin={isAdmin}
                  expanded={expanded.has(p.id)}
                  onToggleExpand={() => toggleExpand(p.id)}
                  onDuplicate={() => openDuplicate(p)}
                  onEdit={() => openEdit(p)}
                  onDelete={() => handleDelete(p.id, p.name)}
                  isSystem={false}
                />
              ))}
            </div>
          )}
        </section>
      )}

      {/* Modal */}
      {modal && (
        <PresetModal
          mode={modal.mode}
          base={modal.preset}
          onClose={() => setModal(null)}
          onSaved={() => {
            setModal(null);
            startTransition(() => router.refresh());
          }}
        />
      )}
    </>
  );
}

// ── Preset card ───────────────────────────────────────────────────────────────

function PresetCard({
  preset,
  isAdmin,
  expanded,
  onToggleExpand,
  onDuplicate,
  onEdit,
  onDelete,
  isSystem,
}: {
  preset: GprPreset;
  isAdmin: boolean;
  expanded: boolean;
  onToggleExpand: () => void;
  onDuplicate: () => void;
  onEdit: () => void;
  onDelete: () => void;
  isSystem: boolean;
}) {
  const p = preset.parameters;
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/40 overflow-hidden">
      <div className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-semibold text-slate-100 text-sm">{preset.name}</span>
              {isSystem && (
                <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-blue-500/20 text-blue-400 border border-blue-500/30">
                  Sistema
                </span>
              )}
            </div>
            {preset.description && (
              <p className="text-xs text-slate-400 mt-1">{preset.description}</p>
            )}
            {preset.target_scenario && (
              <p className="text-xs text-slate-500 mt-0.5 italic">{preset.target_scenario}</p>
            )}
            {/* Key params summary */}
            <div className="flex items-center gap-3 mt-2 flex-wrap">
              <ParamChip label="v" value={`${p.velocity_mns} m/ns`} />
              <ParamChip label="BP" value={
                Number(p.bandpass_low_mhz ?? 80) > 0
                  ? `${p.bandpass_low_mhz}–${p.bandpass_high_mhz} MHz`
                  : "desativado"
              } />
              <ParamChip label="solo" value={String(p.tipo_solo ?? "standard")} />
              <ParamChip label="prof." value={`até ${p.det_h_max_m}m`} />
              {p.fis_ativo === false && (
                <span className="text-[10px] text-amber-400 border border-amber-400/30 px-1.5 py-0.5 rounded">
                  sem física
                </span>
              )}
            </div>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button
              onClick={onToggleExpand}
              className="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded transition-colors"
            >
              {expanded ? "▲ Fechar" : "▼ Parâmetros"}
            </button>
            {isAdmin && (
              <>
                <button
                  onClick={onDuplicate}
                  className="px-2 py-1 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-700 rounded transition-colors"
                >
                  Duplicar
                </button>
                {!isSystem && (
                  <>
                    <button
                      onClick={onEdit}
                      className="px-2 py-1 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-slate-700 rounded transition-colors"
                    >
                      Editar
                    </button>
                    <button
                      onClick={onDelete}
                      className="px-2 py-1 text-xs text-red-400 hover:text-red-300 hover:bg-slate-700 rounded transition-colors"
                    >
                      Deletar
                    </button>
                  </>
                )}
              </>
            )}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-slate-700 bg-slate-900/50 p-4 space-y-4">
          {preset.scientific_basis && (
            <div>
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
                Base científica
              </span>
              <p className="text-xs text-slate-400 mt-0.5">{preset.scientific_basis}</p>
            </div>
          )}
          <ParamGroup label="Filtragem de Sinal" params={[
            ["dewow_window", p.dewow_window],
            ["bandpass_low_mhz", p.bandpass_low_mhz],
            ["bandpass_high_mhz", p.bandpass_high_mhz],
            ["bandpass_order", p.bandpass_order],
            ["bgremoval_traces", p.bgremoval_traces],
          ]} />
          <ParamGroup label="Ganho e Contraste" params={[
            ["tpow_power", p.tpow_power],
            ["agc_window", p.agc_window],
            ["contrast", p.contrast],
          ]} />
          <ParamGroup label="Escala e Geometry" params={[
            ["velocity_mns", p.velocity_mns],
            ["colormap", p.colormap],
            ["dpi", p.dpi],
          ]} />
          <ParamGroup label="Detector" params={[
            ["det_amp_threshold", p.det_amp_threshold],
            ["det_h_min_m", p.det_h_min_m],
            ["det_h_max_m", p.det_h_max_m],
            ["det_top_n", p.det_top_n],
            ["det_min_score_csv", p.det_min_score_csv],
            ["det_depth_min_m", p.det_depth_min_m],
            ["detector_input_mode", p.detector_input_mode],
          ]} />
          <ParamGroup label="Física" params={[
            ["fis_ativo", p.fis_ativo],
            ["fis_amp_metal_thr", p.fis_amp_metal_thr],
            ["fis_amp_nao_metal_thr", p.fis_amp_nao_metal_thr],
          ]} />
        </div>
      )}
    </div>
  );
}

function ParamChip({ label, value }: { label: string; value: string }) {
  return (
    <span className="text-[10px] text-slate-400">
      <span className="text-slate-600">{label}:</span> {value}
    </span>
  );
}

function ParamGroup({ label, params }: { label: string; params: [string, unknown][] }) {
  return (
    <div>
      <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</span>
      <div className="mt-1 grid grid-cols-2 sm:grid-cols-3 gap-x-6 gap-y-0.5">
        {params.map(([k, v]) => (
          <div key={k} className="flex items-center gap-1.5 text-xs">
            <span className="text-slate-500 font-mono">{k}:</span>
            <span className="text-slate-300">{String(v ?? "—")}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Preset modal (create / edit) ──────────────────────────────────────────────

type ParamForm = {
  bandpass_enabled: boolean;
  dewow_window: number;
  bandpass_low_mhz: number;
  bandpass_high_mhz: number;
  bandpass_order: number;
  bgremoval_traces: number;
  tpow_power: number;
  agc_window: number;
  contrast: number;
  velocity_mns: number;
  colormap: string;
  dpi: number;
  det_amp_threshold: number;
  det_h_min_m: number;
  det_h_max_m: number;
  det_top_n: number;
  det_min_score_csv: number;
  det_depth_min_m: number;
  detector_input_mode: string;
  fis_ativo: boolean;
  fis_amp_metal_thr: number;
  fis_amp_nao_metal_thr: number;
};

function paramsToForm(p: Record<string, unknown>): ParamForm {
  return {
    bandpass_enabled:   Number(p.bandpass_low_mhz ?? 80) > 0,
    dewow_window:        Number(p.dewow_window ?? 5),
    bandpass_low_mhz:   Number(p.bandpass_low_mhz ?? 80),
    bandpass_high_mhz:  Number(p.bandpass_high_mhz ?? 500),
    bandpass_order:     Number(p.bandpass_order ?? 5),
    bgremoval_traces:   Number(p.bgremoval_traces ?? 30),
    tpow_power:         Number(p.tpow_power ?? 0.5),
    agc_window:         Number(p.agc_window ?? 150),
    contrast:           Number(p.contrast ?? 2.5),
    velocity_mns:       Number(p.velocity_mns ?? 0.10),
    colormap:           String(p.colormap ?? "gray"),
    dpi:                Number(p.dpi ?? 150),
    det_amp_threshold:  Number(p.det_amp_threshold ?? 0.50),
    det_h_min_m:        Number(p.det_h_min_m ?? 0.10),
    det_h_max_m:        Number(p.det_h_max_m ?? 3.00),
    det_top_n:          Number(p.det_top_n ?? 25),
    det_min_score_csv:  Number(p.det_min_score_csv ?? 30),
    det_depth_min_m:    Number(p.det_depth_min_m ?? 0.30),
    detector_input_mode: String(p.detector_input_mode ?? "raw"),
    fis_ativo:          Boolean(p.fis_ativo ?? true),
    fis_amp_metal_thr:  Number(p.fis_amp_metal_thr ?? 0.75),
    fis_amp_nao_metal_thr: Number(p.fis_amp_nao_metal_thr ?? 0.40),
  };
}

function PresetModal({
  mode,
  base,
  onClose,
  onSaved,
}: {
  mode: "create" | "edit";
  base?: GprPreset;
  onClose: () => void;
  onSaved: () => void;
}) {
  const isEdit = mode === "edit" && base && !base.is_system;
  const title = isEdit ? "Editar preset" : base ? `Duplicar: ${base.name}` : "Novo preset";

  const [name, setName] = useState(isEdit ? (base?.name ?? "") : (base ? `Cópia de ${base.name}` : ""));
  const [description, setDescription] = useState(base?.description ?? "");
  const [targetScenario, setTargetScenario] = useState(base?.target_scenario ?? "");
  const [scientificBasis, setScientificBasis] = useState(base?.scientific_basis ?? "");
  const [antennaFreq, setAntennaFreq] = useState(base?.antenna_freq_mhz ?? 270);
  const [params, setParams] = useState<ParamForm>(
    paramsToForm(base?.parameters ?? DEFAULT_PARAMS)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function setP<K extends keyof ParamForm>(key: K, value: ParamForm[K]) {
    setParams((prev) => ({ ...prev, [key]: value }));
  }

  async function handleSave() {
    if (!name.trim()) { setError("Nome é obrigatório."); return; }
    setSaving(true);
    setError(null);

    // bandpass_enabled is a UI helper — excluded from saved parameters
    const { bandpass_enabled: _ignored, ...paramData } = params;
    const data: PresetUpsertData = {
      name: name.trim(),
      description: description.trim() || undefined,
      target_scenario: targetScenario.trim() || undefined,
      scientific_basis: scientificBasis.trim() || undefined,
      antenna_freq_mhz: antennaFreq || undefined,
      parameters: { ...paramData },
    };

    let result: { ok: boolean; error?: string };
    if (isEdit && base) {
      result = await updatePreset(base.id, data);
    } else {
      result = await createPreset(data);
    }

    setSaving(false);
    if (result.ok) {
      onSaved();
    } else {
      setError(result.error ?? "Erro desconhecido.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-slate-900 border-b border-slate-700 px-6 py-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200 text-xl leading-none">×</button>
        </div>

        <div className="p-6 space-y-5">
          {/* Meta */}
          <ModalInput label="Nome *" value={name} onChange={setName} placeholder="Solo argiloso — projeto XYZ" />
          <ModalTextarea label="Descrição" value={description} onChange={setDescription} placeholder="Uso recomendado…" />
          <ModalInput label="Cenário alvo" value={targetScenario} onChange={setTargetScenario} placeholder="Detecção de utilidades em solo argiloso…" />
          <ModalTextarea label="Referência científica" value={scientificBasis} onChange={setScientificBasis} placeholder="Cassidy (2009) GPR Theory…" rows={2} />
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">Frequência da antena (MHz)</label>
            <input
              type="number"
              value={antennaFreq}
              onChange={(e) => setAntennaFreq(parseInt(e.target.value) || 270)}
              className={inputCls}
            />
          </div>

          {/* Filtragem */}
          <ParamSection label="Filtragem de Sinal">
            <IntField label="dewow_window (3–15)" hint="Janela de remoção de deriva DC (samples)"
              value={params.dewow_window} min={3} max={15} onChange={(v) => setP("dewow_window", v)} />
            <div className="col-span-2 border-t border-slate-800 pt-2">
              <label className="flex items-center gap-2 cursor-pointer mb-2">
                <input
                  type="checkbox"
                  checked={params.bandpass_enabled}
                  onChange={(e) => {
                    const on = e.target.checked;
                    setP("bandpass_enabled", on);
                    if (!on) {
                      setP("bandpass_low_mhz", 0);
                    } else if (params.bandpass_low_mhz === 0) {
                      setP("bandpass_low_mhz", 80);
                    }
                  }}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500"
                />
                <span className="text-xs text-slate-300">
                  Bandpass ligado
                  {!params.bandpass_enabled && (
                    <span className="ml-2 text-amber-400 font-semibold">— desativado (bandpass_low_mhz=0)</span>
                  )}
                </span>
              </label>
              <p className="text-[10px] text-slate-600 mb-2">
                Desativar melhora imagens em dados com SNR muito alto (onda direta forte). Usar com cautela — DZTs ruidosos precisam do filtro.
              </p>
            </div>
            {params.bandpass_enabled && (
              <>
                <IntField label="bandpass_low_mhz (30–200)" hint="Frequência de corte inferior (MHz)"
                  value={params.bandpass_low_mhz} min={30} max={200} onChange={(v) => setP("bandpass_low_mhz", v)} />
                <IntField label="bandpass_high_mhz (200–900)" hint="Frequência de corte superior (MHz)"
                  value={params.bandpass_high_mhz} min={200} max={900} onChange={(v) => setP("bandpass_high_mhz", v)} />
                <IntField label="bandpass_order (2–8)" hint="Ordem do filtro Butterworth (curva de corte)"
                  value={params.bandpass_order} min={2} max={8} onChange={(v) => setP("bandpass_order", v)} />
              </>
            )}
            <IntField label="bgremoval_traces (5–60)" hint="Traços para remoção de fundo horizontal"
              value={params.bgremoval_traces} min={5} max={60} onChange={(v) => setP("bgremoval_traces", v)} />
          </ParamSection>

          {/* Ganho */}
          <ParamSection label="Ganho e Contraste">
            <FloatField label="tpow_power (0.1–2.0)" hint="Potência do ganho temporal (compensa atenuação)"
              value={params.tpow_power} min={0.1} max={2.0} step={0.05} onChange={(v) => setP("tpow_power", v)} />
            <IntField label="agc_window (50–300)" hint="Janela AGC em samples (menor = mais agressivo)"
              value={params.agc_window} min={50} max={300} onChange={(v) => setP("agc_window", v)} />
            <FloatField label="contrast (1.0–5.0)" hint="Contraste da imagem final"
              value={params.contrast} min={1.0} max={5.0} step={0.1} onChange={(v) => setP("contrast", v)} />
          </ParamSection>

          {/* Escala */}
          <ParamSection label="Escala e Geometry">
            <FloatField label="velocity_mns (0.04–0.30)" hint="Velocity EM no solo (m/ns). ε_r = (0.3/v)²"
              value={params.velocity_mns} min={0.04} max={0.30} step={0.01} onChange={(v) => setP("velocity_mns", v)} />
            <div>
              <label className="block text-xs text-slate-400 mb-1">colormap</label>
              <p className="text-[10px] text-slate-600 mb-1">Paleta de cores do radargrama</p>
              <select value={params.colormap} onChange={(e) => setP("colormap", e.target.value)} className={inputCls}>
                <option value="gray">gray</option>
                <option value="seismic">seismic</option>
                <option value="bwr">bwr</option>
              </select>
            </div>
            <IntField label="dpi (72–300)" hint="Resolução da imagem de saída"
              value={params.dpi} min={72} max={300} onChange={(v) => setP("dpi", v)} />
          </ParamSection>

          {/* Detector */}
          <ParamSection label="Detector de Hipérboles">
            <FloatField label="det_amp_threshold (0.10–0.90)" hint="Amplitude mínima normalizada para candidato"
              value={params.det_amp_threshold} min={0.10} max={0.90} step={0.01} onChange={(v) => setP("det_amp_threshold", v)} />
            <FloatField label="det_h_min_m (0.05–1.0)" hint="Profundidade mínima dos alvos (m)"
              value={params.det_h_min_m} min={0.05} max={1.0} step={0.05} onChange={(v) => setP("det_h_min_m", v)} />
            <FloatField label="det_h_max_m (0.5–6.0)" hint="Profundidade máxima dos alvos (m)"
              value={params.det_h_max_m} min={0.5} max={6.0} step={0.25} onChange={(v) => setP("det_h_max_m", v)} />
            <IntField label="det_top_n (5–50)" hint="Máximo de candidatos antes do filtro de score"
              value={params.det_top_n} min={5} max={50} onChange={(v) => setP("det_top_n", v)} />
            <IntField label="det_min_score_csv (10–80)" hint="Score mínimo para exportar alvo (0–100)"
              value={params.det_min_score_csv} min={10} max={80} onChange={(v) => setP("det_min_score_csv", v)} />
            <FloatField label="det_depth_min_m (0.10–1.00)" hint="Profundidade mínima — elimina airwave/onda direta"
              value={params.det_depth_min_m} min={0.10} max={1.00} step={0.05} onChange={(v) => setP("det_depth_min_m", v)} />
            <div>
              <label className="block text-xs text-slate-400 mb-1">detector_input_mode</label>
              <p className="text-[10px] text-slate-600 mb-1">Array de entrada do detector. &apos;raw&apos; recomendado (v2.0.0)</p>
              <select value={params.detector_input_mode} onChange={(e) => setP("detector_input_mode", e.target.value)} className={inputCls}>
                <option value="raw">raw</option>
                <option value="raw_dewow_bandpass">raw_dewow_bandpass</option>
                <option value="sem_agc">sem_agc</option>
                <option value="proc_agc_atual">proc_agc_atual</option>
              </select>
            </div>
          </ParamSection>

          {/* Física */}
          <ParamSection label="Análise Física">
            <div className="col-span-2">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={params.fis_ativo}
                  onChange={(e) => setP("fis_ativo", e.target.checked)}
                  className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500"
                />
                <span className="text-xs text-slate-300">fis_ativo — Habilita classificação de material (metal/não-metal)</span>
              </label>
            </div>
            {params.fis_ativo && (
              <>
                <FloatField label="fis_amp_metal_thr" hint="Amplitude mínima para classificar como metal"
                  value={params.fis_amp_metal_thr} min={0.1} max={1.0} step={0.05} onChange={(v) => setP("fis_amp_metal_thr", v)} />
                <FloatField label="fis_amp_nao_metal_thr" hint="Amplitude máxima para classificar como não-metal"
                  value={params.fis_amp_nao_metal_thr} min={0.1} max={1.0} step={0.05} onChange={(v) => setP("fis_amp_nao_metal_thr", v)} />
              </>
            )}
          </ParamSection>

          {error && (
            <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
        </div>

        <div className="sticky bottom-0 bg-slate-900 border-t border-slate-700 px-6 py-4 flex gap-3 justify-end">
          <button onClick={onClose} className="px-4 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors">
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 text-sm font-semibold bg-cyan-500 text-slate-950 hover:bg-cyan-400 rounded-lg transition-colors disabled:opacity-50"
          >
            {saving ? "Salvando…" : "Salvar"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Field helpers ─────────────────────────────────────────────────────────────

const inputCls = "w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500";

function ModalInput({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1">{label}</label>
      <input type="text" value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className={inputCls} />
    </div>
  );
}

function ModalTextarea({ label, value, onChange, placeholder, rows = 3 }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string; rows?: number }) {
  return (
    <div>
      <label className="block text-xs font-medium text-slate-400 mb-1">{label}</label>
      <textarea value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} rows={rows}
        className={`${inputCls} resize-none`} />
    </div>
  );
}

function ParamSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h4 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 border-b border-slate-800 pb-1">
        {label}
      </h4>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {children}
      </div>
    </div>
  );
}

function IntField({ label, hint, value, min, max, onChange }: { label: string; hint: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-0.5">{label}</label>
      <p className="text-[10px] text-slate-600 mb-1">{hint}</p>
      <input type="number" value={value} min={min} max={max} step={1}
        onChange={(e) => onChange(parseInt(e.target.value) || min)}
        className={inputCls} />
    </div>
  );
}

function FloatField({ label, hint, value, min, max, step, onChange }: { label: string; hint: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-0.5">{label}</label>
      <p className="text-[10px] text-slate-600 mb-1">{hint}</p>
      <input type="number" value={value} min={min} max={max} step={step}
        onChange={(e) => onChange(parseFloat(e.target.value) || min)}
        className={inputCls} />
    </div>
  );
}
