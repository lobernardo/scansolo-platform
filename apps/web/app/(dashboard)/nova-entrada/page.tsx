"use client";

import { useActionState, useState, useEffect } from "react";
import { createProject, type CreateProjectState } from "./actions";
import type { GprPreset } from "@/app/actions/preset-actions";

type PresetSummary = Pick<GprPreset, "id" | "name" | "description" | "is_system" | "parameters">;

// Fetched client-side to avoid making this page async (uses useActionState)
function usePresets() {
  const [presets, setPresets] = useState<PresetSummary[]>([]);
  useEffect(() => {
    fetch("/api/presets")
      .then((r) => r.json())
      .then((data) => Array.isArray(data) ? setPresets(data) : setPresets([]))
      .catch(() => setPresets([]));
  }, []);
  return presets;
}

export default function NovaEntradaPage() {
  const [state, formAction, pending] = useActionState<CreateProjectState, FormData>(
    createProject,
    null
  );
  const presets = usePresets();

  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
  const [showCustom, setShowCustom] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, unknown>>({});

  const selectedPreset = presets.find((p) => p.id === selectedPresetId) ?? null;
  const baseParams = selectedPreset?.parameters ?? {};

  function getParam(key: string, fallback: unknown) {
    return key in overrides ? overrides[key] : (baseParams[key] ?? fallback);
  }

  function setOverride(key: string, value: unknown) {
    setOverrides((prev) => ({ ...prev, [key]: value }));
  }

  // When preset changes, reset overrides
  function handlePresetChange(id: string) {
    setSelectedPresetId(id);
    setOverrides({});
    setShowCustom(false);
  }

  const systemPresets = presets.filter((p) => p.is_system);
  const userPresets = presets.filter((p) => !p.is_system);

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-100 mb-6">Nova entrada</h1>
      <form action={formAction} className="space-y-4">

        {/* Preset id hidden */}
        {selectedPresetId && (
          <input type="hidden" name="preset_id" value={selectedPresetId} />
        )}
        {/* Overrides as JSON hidden */}
        {Object.keys(overrides).length > 0 && (
          <input type="hidden" name="param_overrides" value={JSON.stringify(overrides)} />
        )}

        {/* Project info */}
        <div className="grid grid-cols-2 gap-4">
          <Field label="Nome do projeto *" name="nome" required placeholder="PATIO_001" />
          <Field label="Código interno" name="codigo_projeto" placeholder="PT-GPR-SOL-036" />
        </div>

        <Field label="Cliente *" name="cliente" required placeholder="Empresa XYZ Ltda" />

        <div className="grid grid-cols-2 gap-4">
          <Field label="A/C (contato)" name="contato_nome" placeholder="João Silva" />
          <Field label="Local" name="local" placeholder="Rua das Flores, 100" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Estado *" name="estado" required placeholder="SP" maxLength={2} />
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Data levantamento *
            </label>
            <input
              type="date"
              name="data_levantamento"
              required
              className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">Área levantada (m²)</label>
          <input
            type="number" name="area_m2" min="1" step="1" placeholder="500"
            className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 placeholder:text-slate-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <input type="checkbox" name="tem_pipe_locator" id="tem_pipe_locator" value="true"
            className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500" />
          <label htmlFor="tem_pipe_locator" className="text-sm text-slate-300">
            Levantamento inclui Pipe Locator
          </label>
        </div>

        {/* ── Preset selector ── */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-4 space-y-3">
          <label className="block text-sm font-semibold text-slate-200">
            Preset de processamento
          </label>

          <select
            value={selectedPresetId}
            onChange={(e) => handlePresetChange(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500"
          >
            <option value="">— Selecione um preset —</option>
            {systemPresets.length > 0 && (
              <optgroup label="Sistema">
                {systemPresets.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </optgroup>
            )}
            {userPresets.length > 0 && (
              <optgroup label="Personalizados">
                {userPresets.map((p) => (
                  <option key={p.id} value={p.id}>{p.name}</option>
                ))}
              </optgroup>
            )}
          </select>

          {selectedPreset && (
            <>
              {selectedPreset.description && (
                <p className="text-xs text-slate-500">{selectedPreset.description}</p>
              )}
              {/* Key params summary */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <SumRow label="Velocity" value={`${baseParams.velocity_mns ?? "—"} m/ns`} />
                <SumRow label="Bandpass" value={`${baseParams.bandpass_low_mhz ?? "—"}–${baseParams.bandpass_high_mhz ?? "—"} MHz`} />
                <SumRow label="Solo" value={String(baseParams.tipo_solo ?? "—")} />
                <SumRow label="Prof. máx." value={`${baseParams.det_h_max_m ?? "—"} m`} />
                <SumRow label="Análise física" value={(baseParams.fis_ativo as boolean) ? "sim" : "não"} />
              </div>

              <button
                type="button"
                onClick={() => setShowCustom((v) => !v)}
                className="text-xs text-cyan-400 hover:text-cyan-300 underline"
              >
                {showCustom ? "▲ Ocultar parâmetros" : "▼ Personalizar parâmetros"}
              </button>

              {showCustom && (
                <div className="space-y-4 pt-2 border-t border-slate-700">
                  <p className="text-xs text-slate-500">
                    Alterações aqui sobrescrevem apenas este projeto — o preset original não é modificado.
                  </p>

                  <CustomGroup label="Filtragem de Sinal">
                    <CInt label="dewow_window" value={Number(getParam("dewow_window", 5))} min={3} max={15} onChange={(v) => setOverride("dewow_window", v)} />
                    <CInt label="bandpass_low_mhz" value={Number(getParam("bandpass_low_mhz", 80))} min={30} max={200} onChange={(v) => setOverride("bandpass_low_mhz", v)} />
                    <CInt label="bandpass_high_mhz" value={Number(getParam("bandpass_high_mhz", 500))} min={200} max={900} onChange={(v) => setOverride("bandpass_high_mhz", v)} />
                    <CInt label="bgremoval_traces" value={Number(getParam("bgremoval_traces", 30))} min={5} max={60} onChange={(v) => setOverride("bgremoval_traces", v)} />
                  </CustomGroup>

                  <CustomGroup label="Ganho e Contraste">
                    <CFloat label="tpow_power" value={Number(getParam("tpow_power", 0.5))} min={0.1} max={2.0} step={0.05} onChange={(v) => setOverride("tpow_power", v)} />
                    <CInt label="agc_window" value={Number(getParam("agc_window", 150))} min={50} max={300} onChange={(v) => setOverride("agc_window", v)} />
                    <CFloat label="contrast" value={Number(getParam("contrast", 2.5))} min={1.0} max={5.0} step={0.1} onChange={(v) => setOverride("contrast", v)} />
                  </CustomGroup>

                  <CustomGroup label="Escala">
                    <CFloat label="velocity_mns" value={Number(getParam("velocity_mns", 0.10))} min={0.04} max={0.30} step={0.01} onChange={(v) => setOverride("velocity_mns", v)} />
                  </CustomGroup>

                  <CustomGroup label="Detector">
                    <CFloat label="det_amp_threshold" value={Number(getParam("det_amp_threshold", 0.50))} min={0.10} max={0.90} step={0.01} onChange={(v) => setOverride("det_amp_threshold", v)} />
                    <CFloat label="det_h_max_m" value={Number(getParam("det_h_max_m", 3.0))} min={0.5} max={6.0} step={0.25} onChange={(v) => setOverride("det_h_max_m", v)} />
                    <CInt label="det_min_score_csv" value={Number(getParam("det_min_score_csv", 30))} min={10} max={80} onChange={(v) => setOverride("det_min_score_csv", v)} />
                    <CFloat label="det_depth_min_m" value={Number(getParam("det_depth_min_m", 0.30))} min={0.10} max={1.00} step={0.05} onChange={(v) => setOverride("det_depth_min_m", v)} />
                  </CustomGroup>
                </div>
              )}
            </>
          )}
        </div>

        {/* IA options */}
        <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <input type="checkbox" name="auto_accept_ia" id="auto_accept_ia" value="true"
              className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500" />
            <label htmlFor="auto_accept_ia" className="text-sm font-medium text-slate-200">
              Aprovação automática da interpretação IA (GPT-4o por alvo)
            </label>
          </div>
          <p className="text-xs text-slate-500 pl-6">
            Alta confiança → planta + relatório. Média → só planta. Baixa → descartado.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <input type="checkbox" name="skip_ia" id="skip_ia" value="true"
              className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500" />
            <label htmlFor="skip_ia" className="text-sm font-medium text-slate-200">
              Pular interpretação IA dos alvos (GPT-4o)
            </label>
          </div>
          <p className="text-xs text-slate-500 pl-6">
            Para validações locais. Pipeline GPR e detector rodam normalmente.
          </p>
        </div>

        {state?.error && (
          <p className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">
            {state.error}
          </p>
        )}

        <div className="pt-2">
          <button
            type="submit"
            disabled={pending || !selectedPresetId}
            className="w-full rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50"
          >
            {pending ? "Criando projeto…" : "Criar projeto e fazer upload"}
          </button>
          {!selectedPresetId && (
            <p className="text-xs text-slate-500 text-center mt-1">Selecione um preset para continuar.</p>
          )}
        </div>
      </form>
    </div>
  );
}

function SumRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-1 text-xs">
      <span className="text-slate-500">{label}:</span>
      <span className="text-slate-300">{value}</span>
    </div>
  );
}

function CustomGroup({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">{label}</p>
      <div className="grid grid-cols-2 gap-2">{children}</div>
    </div>
  );
}

const inputCls = "w-full bg-slate-900 border border-slate-700 text-slate-100 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-cyan-500";

function CInt({ label, value, min, max, onChange }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-[10px] text-slate-400 mb-0.5">{label}</label>
      <input type="number" value={value} min={min} max={max} step={1}
        onChange={(e) => onChange(parseInt(e.target.value) || min)} className={inputCls} />
    </div>
  );
}

function CFloat({ label, value, min, max, step, onChange }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void }) {
  return (
    <div>
      <label className="block text-[10px] text-slate-400 mb-0.5">{label}</label>
      <input type="number" value={value} min={min} max={max} step={step}
        onChange={(e) => onChange(parseFloat(e.target.value) || min)} className={inputCls} />
    </div>
  );
}

function Field({ label, name, required, placeholder, maxLength }: {
  label: string; name: string; required?: boolean; placeholder?: string; maxLength?: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1">{label}</label>
      <input type="text" name={name} required={required} placeholder={placeholder} maxLength={maxLength}
        className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 placeholder:text-slate-500" />
    </div>
  );
}
