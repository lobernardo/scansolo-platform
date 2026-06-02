"use client";

import { useParams } from "next/navigation";
import { useRef, useState } from "react";
import { uploadDztFiles, startProcessingWithConfig } from "./actions";
import type { FilterConfig } from "./actions";

// ── Presets de configuração ───────────────────────────────────────────────────

const CONFIG_PRESETS: Record<string, FilterConfig> = {
  "Padrão ScanSOLO": {
    filtros_ativos: { dewow: true, bandpass: true, background_removal: true, tpow_gain: true, agc: true, ia_imagem: false },
    bgremoval_traces: 30, tpow_power: 0.5, contrast: 2.5, agc_window: 150,
  },
  "Solo argiloso": {
    filtros_ativos: { dewow: true, bandpass: true, background_removal: true, tpow_gain: true, agc: true, ia_imagem: false },
    bgremoval_traces: 50, tpow_power: 0.8, contrast: 3.5, agc_window: 150,
  },
  "Solo arenoso": {
    filtros_ativos: { dewow: true, bandpass: true, background_removal: true, tpow_gain: true, agc: true, ia_imagem: false },
    bgremoval_traces: 20, tpow_power: 0.3, contrast: 2.0, agc_window: 100,
  },
  "Mínimo": {
    filtros_ativos: { dewow: true, bandpass: false, background_removal: false, tpow_gain: false, agc: true, ia_imagem: false },
    bgremoval_traces: 30, tpow_power: 0.5, contrast: 2.0, agc_window: 150,
  },
};

const DEFAULT_CONFIG = CONFIG_PRESETS["Padrão ScanSOLO"];

const FILTER_LABELS: Record<keyof FilterConfig["filtros_ativos"], string> = {
  dewow:              "Dewow",
  bandpass:           "Bandpass (80–500 MHz)",
  background_removal: "Background Removal",
  tpow_gain:          "tpow Gain",
  agc:                "AGC",
  ia_imagem:          "Melhoria IA (gpt-image-1) — consome créditos OpenAI",
};

// ── Componente ────────────────────────────────────────────────────────────────

type Step = "upload" | "configure";

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const [step, setStep] = useState<Step>("upload");
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [config, setConfig] = useState<FilterConfig>(DEFAULT_CONFIG);
  const inputRef = useRef<HTMLInputElement>(null);

  // ── Step 1: upload ──────────────────────────────────────────────────────────

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!files.length) return;
    setUploading(true);
    setErrorMsg("");
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    const result = await uploadDztFiles(id, fd);
    setUploading(false);
    if (!result.ok) {
      setErrorMsg(result.error);
    } else {
      setStep("configure");
    }
  }

  // ── Step 2: configure + start ───────────────────────────────────────────────

  async function handleStart() {
    setStarting(true);
    setErrorMsg("");
    try {
      await startProcessingWithConfig(id, config);
    } catch (err: unknown) {
      setStarting(false);
      setErrorMsg(err instanceof Error ? err.message : "Erro ao iniciar processamento");
    }
  }

  function applyPreset(name: string) {
    const p = CONFIG_PRESETS[name];
    if (p) setConfig(JSON.parse(JSON.stringify(p)));
  }

  function toggleFiltro(key: keyof FilterConfig["filtros_ativos"]) {
    setConfig((prev) => ({
      ...prev,
      filtros_ativos: { ...prev.filtros_ativos, [key]: !prev.filtros_ativos[key] },
    }));
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  if (step === "configure") {
    return (
      <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Configuração de Processamento</h1>
          <p className="text-sm text-gray-500 mt-1">
            {files.length} arquivo{files.length !== 1 ? "s" : ""} enviado{files.length !== 1 ? "s" : ""} com sucesso.
            Escolha os filtros e inicie o processamento.
          </p>
        </div>

        {/* Presets rápidos */}
        <div>
          <p className="text-xs font-medium text-gray-500 mb-2 uppercase tracking-wide">Preset rápido</p>
          <div className="flex flex-wrap gap-2">
            {Object.keys(CONFIG_PRESETS).map((name) => (
              <button
                key={name}
                onClick={() => applyPreset(name)}
                className="text-xs px-3 py-1.5 rounded-md border border-gray-300 hover:bg-gray-50 transition-colors"
              >
                {name}
              </button>
            ))}
          </div>
        </div>

        {/* Filtros — toggles */}
        <div className="rounded-lg border border-gray-200 bg-white divide-y divide-gray-100">
          {(Object.keys(FILTER_LABELS) as (keyof FilterConfig["filtros_ativos"])[]).map((key) => (
            <div key={key} className="flex items-center justify-between px-4 py-3">
              <span className="text-sm text-gray-700">{FILTER_LABELS[key]}</span>
              <button
                onClick={() => toggleFiltro(key)}
                className={`relative w-10 h-5 rounded-full transition-colors ${
                  config.filtros_ativos[key] ? "bg-gray-900" : "bg-gray-200"
                }`}
              >
                <span
                  className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${
                    config.filtros_ativos[key] ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          ))}
        </div>

        {/* Sliders — só mostra filtros ativos */}
        <div className="space-y-4">
          {config.filtros_ativos.background_removal && (
            <Slider
              label="Background Removal — traços"
              value={config.bgremoval_traces}
              min={10} max={100} step={5}
              onChange={(v) => setConfig((c) => ({ ...c, bgremoval_traces: v }))}
            />
          )}
          {config.filtros_ativos.tpow_gain && (
            <Slider
              label="tpow Gain — potência"
              value={config.tpow_power}
              min={0.2} max={1.5} step={0.1}
              onChange={(v) => setConfig((c) => ({ ...c, tpow_power: v }))}
            />
          )}
          {config.filtros_ativos.agc && (
            <Slider
              label="AGC — janela"
              value={config.agc_window}
              min={50} max={300} step={25}
              onChange={(v) => setConfig((c) => ({ ...c, agc_window: v }))}
            />
          )}
          <Slider
            label="Contraste da imagem"
            value={config.contrast}
            min={1.0} max={5.0} step={0.5}
            onChange={(v) => setConfig((c) => ({ ...c, contrast: v }))}
          />
        </div>

        {errorMsg && (
          <p className="text-sm text-red-600 rounded-md bg-red-50 px-3 py-2">{errorMsg}</p>
        )}

        <button
          onClick={handleStart}
          disabled={starting}
          className="w-full rounded-md bg-gray-900 px-4 py-2.5 text-sm font-medium text-white hover:bg-gray-700 transition-colors disabled:opacity-50"
        >
          {starting ? "Iniciando…" : "Iniciar processamento com estas configurações"}
        </button>
      </div>
    );
  }

  // Step: upload
  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">Upload de arquivos .DZT</h1>
      <p className="text-sm text-gray-500 mb-6">Projeto: {id}</p>

      <form onSubmit={handleUpload} className="space-y-4">
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 transition-colors"
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".dzt"
            className="hidden"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
          {files.length === 0 ? (
            <p className="text-sm text-gray-500">Clique ou arraste os arquivos .DZT aqui</p>
          ) : (
            <ul className="text-sm text-left space-y-1">
              {files.map((f) => (
                <li key={f.name} className="text-gray-700">
                  {f.name}{" "}
                  <span className="text-gray-400">({(f.size / 1024 / 1024).toFixed(1)} MB)</span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {errorMsg && (
          <p className="text-sm text-red-600 rounded-md bg-red-50 px-3 py-2">{errorMsg}</p>
        )}

        <button
          type="submit"
          disabled={!files.length || uploading}
          className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {uploading ? "Enviando…" : "Enviar arquivos"}
        </button>
      </form>
    </div>
  );
}

function Slider({
  label, value, min, max, step, onChange,
}: {
  label: string; value: number; min: number; max: number; step: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-gray-600">
        <span>{label}</span>
        <span className="font-medium tabular-nums">{value}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full accent-gray-900"
      />
      <div className="flex justify-between text-[10px] text-gray-400">
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  );
}
