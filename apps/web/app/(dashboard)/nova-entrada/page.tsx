"use client";

import { Fragment, useActionState, useState, useEffect } from "react";
import { createProject, type CreateProjectState } from "./actions";
import { createPreset } from "@/app/actions/preset-actions";
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
  function addPreset(p: PresetSummary) {
    setPresets((prev) => [...prev, p]);
  }
  return { presets, addPreset };
}

export default function NovaEntradaPage() {
  const [state, formAction, pending] = useActionState<CreateProjectState, FormData>(
    createProject,
    null
  );
  const { presets, addPreset } = usePresets();

  const [selectedPresetId, setSelectedPresetId] = useState<string>("");
  const [showCustom, setShowCustom] = useState(false);
  const [overrides, setOverrides] = useState<Record<string, unknown>>({});

  // Create preset inline modal
  const [showCreatePreset, setShowCreatePreset] = useState(false);
  const [newPresetName, setNewPresetName] = useState("");
  const [newPresetDesc, setNewPresetDesc] = useState("");
  const [createStatus, setCreateStatus] = useState<"idle" | "saving" | "error">("idle");
  const [createError, setCreateError] = useState("");

  const selectedPreset = presets.find((p) => p.id === selectedPresetId) ?? null;
  const baseParams = selectedPreset?.parameters ?? {};

  function getParam(key: string, fallback: unknown) {
    return key in overrides ? overrides[key] : (baseParams[key] ?? fallback);
  }

  function setOverride(key: string, value: unknown) {
    setOverrides((prev) => ({ ...prev, [key]: value }));
  }

  const bandpassEnabled = Number(getParam("bandpass_low_mhz", 80)) > 0;

  function toggleBandpass(enabled: boolean) {
    if (!enabled) {
      setOverride("bandpass_low_mhz", 0);
    } else {
      setOverrides((prev) => {
        const next = { ...prev };
        if (next.bandpass_low_mhz === 0) delete next.bandpass_low_mhz;
        return next;
      });
    }
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

          {/* Criar preset a partir das configurações atuais */}
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => { setShowCreatePreset(true); setCreateStatus("idle"); setNewPresetName(""); setNewPresetDesc(""); }}
              className="text-xs text-cyan-400 hover:text-cyan-300 underline disabled:opacity-40"
              disabled={!selectedPresetId}
              title={!selectedPresetId ? "Selecione um preset base primeiro" : "Salvar configuração atual como novo preset"}
            >
              + Salvar como novo preset
            </button>
          </div>

          {/* Modal inline de criação de preset */}
          {showCreatePreset && (
            <div className="rounded-lg border border-cyan-700 bg-slate-900 p-3 space-y-2">
              <p className="text-xs font-semibold text-cyan-300">Novo preset — baseado em &ldquo;{selectedPreset?.name}&rdquo;</p>
              <p className="text-xs text-slate-500">Parâmetros atuais (base + personalizações) serão salvos.</p>
              <input
                type="text"
                placeholder="Nome do preset *"
                value={newPresetName}
                onChange={(e) => setNewPresetName(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-cyan-500"
                autoFocus
              />
              <input
                type="text"
                placeholder="Descrição (opcional)"
                value={newPresetDesc}
                onChange={(e) => setNewPresetDesc(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-cyan-500"
              />
              {createStatus === "error" && (
                <p className="text-xs text-red-400">{createError}</p>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={!newPresetName.trim() || createStatus === "saving"}
                  onClick={async () => {
                    setCreateStatus("saving");
                    const mergedParams = { ...(selectedPreset?.parameters ?? {}), ...overrides };
                    const res = await createPreset({
                      name: newPresetName.trim(),
                      description: newPresetDesc.trim() || undefined,
                      parameters: mergedParams,
                    });
                    if (res.ok && res.id) {
                      addPreset({ id: res.id, name: newPresetName.trim(), description: newPresetDesc.trim() || null, is_system: false, parameters: mergedParams });
                      handlePresetChange(res.id);
                      setShowCreatePreset(false);
                    } else {
                      setCreateStatus("error");
                      setCreateError(res.error ?? "Erro ao criar preset.");
                    }
                  }}
                  className="rounded bg-cyan-500 px-3 py-1 text-xs font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50 transition-colors"
                >
                  {createStatus === "saving" ? "Salvando…" : "Salvar preset"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowCreatePreset(false)}
                  className="rounded bg-slate-700 px-3 py-1 text-xs text-slate-300 hover:bg-slate-600 transition-colors"
                >
                  Cancelar
                </button>
              </div>
            </div>
          )}

          {selectedPreset && (
            <>
              {selectedPreset.description && (
                <p className="text-xs text-slate-500">{selectedPreset.description}</p>
              )}
              {/* Key params summary */}
              <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                <SumRow label="Velocity" value={`${getParam("velocity_mns", baseParams.velocity_mns ?? "—")} m/ns`} />
                <SumRow label="Bandpass" value={
                  bandpassEnabled
                    ? `${getParam("bandpass_low_mhz", 80)}–${getParam("bandpass_high_mhz", 500)} MHz`
                    : "desativado"
                } />
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

                  {/* Mini pipeline visual */}
                  <div className="flex items-center flex-wrap gap-0.5">
                    {(["Filtros", "SNR Gate", "Detector", "Imagens"] as const).map(
                      (label, i, arr) => (
                        <Fragment key={label}>
                          <span className="px-2 py-0.5 rounded border border-slate-700 bg-slate-900 text-[10px] text-slate-400">
                            {label}
                          </span>
                          {i < arr.length - 1 && (
                            <span className="text-slate-700 text-[10px] mx-0.5">→</span>
                          )}
                        </Fragment>
                      )
                    )}
                    <span className="ml-2 text-[10px] text-slate-600">
                      Hover ⓘ em cada parâmetro para detalhes
                    </span>
                  </div>

                  <CustomGroup label="Filtragem de Sinal">
                    <CInt label="dewow_window" value={Number(getParam("dewow_window", 5))} min={3} max={15} onChange={(v) => setOverride("dewow_window", v)}
                      tooltip="Filtra deriva de baixa frequência (saturação do receptor). Raramente precisa ser alterado. Recomendado: 3–7." />
                    <div className="col-span-2">
                      <div className="flex items-center gap-2 py-1 border-t border-slate-800 mt-1">
                        <input
                          type="checkbox"
                          id="nova_bandpass_enabled"
                          checked={bandpassEnabled}
                          onChange={(e) => toggleBandpass(e.target.checked)}
                          className="h-3.5 w-3.5 rounded border-slate-600 bg-slate-800 text-cyan-500"
                        />
                        <label htmlFor="nova_bandpass_enabled" className="text-[10px] text-slate-300 flex items-center gap-0.5">
                          Bandpass ligado
                          <ParamTooltip text="Filtro passa-banda. Desligar melhora imagens em dados com SNR muito alto (onda direta forte, como HELPER). O bandpass pode distorcer hipérboles quando o sinal já está limpo. Use 'desligado' com cautela — DZTs ruidosos precisam do filtro." />
                        </label>
                        {!bandpassEnabled && (
                          <span className="ml-1 text-[10px] text-amber-400 font-semibold">DESATIVADO — bandpass_low_mhz=0</span>
                        )}
                      </div>
                    </div>
                    {bandpassEnabled && (
                      <>
                        <CInt label="bandpass_low_mhz" value={Number(getParam("bandpass_low_mhz", 80))} min={30} max={200} onChange={(v) => setOverride("bandpass_low_mhz", v)}
                          tooltip="Frequência de corte inferior do filtro passa-banda. Elimina componentes DC e ruído abaixo do espectro da antena. Recomendado: 60–100 MHz para antena 270 MHz." />
                        <CInt label="bandpass_high_mhz" value={Number(getParam("bandpass_high_mhz", 500))} min={200} max={900} onChange={(v) => setOverride("bandpass_high_mhz", v)}
                          tooltip="Frequência de corte superior do filtro passa-banda. Elimina ruído de alta frequência. Recomendado: 400–600 MHz para antena 270 MHz." />
                      </>
                    )}
                    <CInt label="bgremoval_traces" value={Number(getParam("bgremoval_traces", 30))} min={5} max={60} onChange={(v) => setOverride("bgremoval_traces", v)}
                      tooltip="Remove padrões horizontais (solo homogêneo, interferências). Maior = remoção mais agressiva. Muito alto apaga hipérboles rasas. Recomendado: 15–40 traços." />
                  </CustomGroup>

                  <CustomGroup label="Ganho e Contraste">
                    <CFloat label="tpow_power" value={Number(getParam("tpow_power", 0.5))} min={0.1} max={2.0} step={0.05} onChange={(v) => setOverride("tpow_power", v)}
                      tooltip="Ganho por potência do tempo — compensa atenuação com profundidade. Maior = mais amplificação de reflexões profundas. Recomendado: 0.3–0.8." />
                    <CInt label="agc_window" value={Number(getParam("agc_window", 150))} min={50} max={300} onChange={(v) => setOverride("agc_window", v)}
                      tooltip="Controle automático de ganho. Janela menor = mais agressivo (amplifica sinais fracos, pode saturar sinais fortes). Ideal para solos úmidos/argilosos. Recomendado: 80–200 samples." />
                    <CFloat label="contrast" value={Number(getParam("contrast", 2.5))} min={1.0} max={5.0} step={0.1} onChange={(v) => setOverride("contrast", v)}
                      tooltip="Multiplicador de contraste da imagem final. Não afeta o processamento — só a visualização. Recomendado: 1.5–3.0." />
                  </CustomGroup>

                  <CustomGroup label="Escala e Profundidade">
                    <CFloat label="velocity_mns" value={Number(getParam("velocity_mns", 0.10))} min={0.04} max={0.30} step={0.01} onChange={(v) => setOverride("velocity_mns", v)}
                      tooltip="Converte eixo de tempo (ns) em profundidade (m). NÃO afeta filtros de sinal. ε_r = (0.3/v)². Recomendado: 0.06 (argila saturada) a 0.20 (areia seca)." />
                    <CFloat label="depth_preview_m" value={Number(getParam("depth_preview_m", 5.0))} min={1.0} max={10.0} step={0.5} onChange={(v) => setOverride("depth_preview_m", v)}
                      tooltip="Controla o eixo Y da imagem Visual (Processada 2). Não altera profundidade técnica, detector ou CSV — apenas a escala exibida na imagem de comparação." />
                    <CInt label="agc_window_preview" value={Number(getParam("agc_window_preview", 80))} min={40} max={200} onChange={(v) => setOverride("agc_window_preview", v)}
                      tooltip="Ganho visual da imagem Visual. Valores menores aumentam contraste; maiores suavizam. Não afeta processamento técnico." />
                  </CustomGroup>

                  <CustomGroup label="Detector">
                    <CFloat label="det_amp_threshold" value={Number(getParam("det_amp_threshold", 0.50))} min={0.10} max={0.90} step={0.01} onChange={(v) => setOverride("det_amp_threshold", v)}
                      tooltip="Amplitude mínima relativa para candidato a alvo. Maior = menos candidatos, menos falsos positivos. Recomendado: 0.40–0.60." />
                    <CFloat label="det_h_max_m" value={Number(getParam("det_h_max_m", 3.0))} min={0.5} max={6.0} step={0.25} onChange={(v) => setOverride("det_h_max_m", v)}
                      tooltip="Profundidade máxima de busca de hipérboles. Definida pelo contexto do projeto. Recomendado: 2–5 m." />
                    <CInt label="det_min_score_csv" value={Number(getParam("det_min_score_csv", 30))} min={10} max={80} onChange={(v) => setOverride("det_min_score_csv", v)}
                      tooltip="Score mínimo para incluir alvo no CSV (combina geometria CurveFit + análise física). Recomendado: 25–40." />
                    <CFloat label="det_depth_min_m" value={Number(getParam("det_depth_min_m", 0.30))} min={0.10} max={1.00} step={0.05} onChange={(v) => setOverride("det_depth_min_m", v)}
                      tooltip="Alvos acima deste limiar são descartados. Elimina reflexão de superfície (airwave). Aumentar em modo MINIMO se houver muitos falsos positivos rasos. Recomendado: 0.30–0.50m." />
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

function ParamTooltip({ text }: { text: string }) {
  return (
    <span className="relative group inline-block ml-0.5 cursor-help align-middle">
      <span className="text-slate-600 group-hover:text-cyan-500 text-[9px] leading-none transition-colors">ⓘ</span>
      <span className="pointer-events-none invisible group-hover:visible absolute z-50 w-60 p-2.5 rounded-lg bg-slate-800 border border-slate-600/60 text-[10px] text-slate-300 leading-relaxed shadow-xl left-4 top-0 whitespace-normal">
        {text}
      </span>
    </span>
  );
}

function CInt({ label, value, min, max, onChange, tooltip }: { label: string; value: number; min: number; max: number; onChange: (v: number) => void; tooltip?: string }) {
  return (
    <div>
      <label className="flex items-center text-[10px] text-slate-400 mb-0.5">
        {label}{tooltip && <ParamTooltip text={tooltip} />}
      </label>
      <input type="number" value={value} min={min} max={max} step={1}
        onChange={(e) => onChange(parseInt(e.target.value) || min)} className={inputCls} />
    </div>
  );
}

function CFloat({ label, value, min, max, step, onChange, tooltip }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; tooltip?: string }) {
  return (
    <div>
      <label className="flex items-center text-[10px] text-slate-400 mb-0.5">
        {label}{tooltip && <ParamTooltip text={tooltip} />}
      </label>
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
