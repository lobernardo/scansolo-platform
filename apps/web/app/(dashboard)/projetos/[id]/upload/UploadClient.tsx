"use client";

import { useEffect, useRef, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  registerUploadedFiles,
  startPreflight,
  getProjectPreflight,
  confirmPreflight,
  startProcessingWithConfig,
  startProcessingDirect,
} from "./actions";
import type {
  FilterConfig,
  PreflightData,
  PreflightOverrides,
  UploadedFileMeta,
} from "./actions";
import { getJobStatus } from "../actions";

// ── Presets de configuração (fallback legado) ─────────────────────────────────

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

const UPLOAD_BATCH_SIZE = 5;
const POLL_MS = 5000;

const CONFIDENCE_COLORS: Record<string, string> = {
  alta:  "text-green-400",
  media: "text-yellow-400",
  baixa: "text-red-400",
};

// ── Tipos locais ──────────────────────────────────────────────────────────────

type Step = "upload" | "preflight" | "configure" | "ready";

// ── Componente principal ──────────────────────────────────────────────────────

// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function UploadClient({ projectId, presetId }: { projectId: string; presetId: string | null }) {
  const [step, setStep]           = useState<Step>("upload");
  const [files, setFiles]         = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress]   = useState(0);
  const [starting, setStarting]   = useState(false);
  const [errorMsg, setErrorMsg]   = useState("");
  const [config, setConfig]       = useState<FilterConfig>(DEFAULT_CONFIG);
  const inputRef = useRef<HTMLInputElement>(null);

  // Preflight job
  const [preflightJobId, setPreflightJobId]   = useState<string | null>(null);
  const [preflightStatus, setPreflightStatus] = useState<string>("aguardando");
  const [preflightError, setPreflightError]   = useState("");
  const [uploadedCount, setUploadedCount]     = useState(0);

  // Preflight data (resultados lidos do banco após job concluir)
  const [preflightData, setPreflightData]     = useState<PreflightData | null>(null);
  const [preflightDataError, setPreflightDataError] = useState("");
  const fetchingPreflight = useRef(false);

  // Confirmação e ajuste
  const [confirming, setConfirming]   = useState(false);
  const [confirmError, setConfirmError] = useState("");
  const [showAdjust, setShowAdjust]   = useState(false);
  const [adjVelocity, setAdjVelocity] = useState("");
  const [adjDepth, setAdjDepth]       = useState("");
  const [adjBandpass, setAdjBandpass] = useState(true);

  // GPR job pesado (após confirmPreflight)
  const [gprJobId, setGprJobId]       = useState<string | null>(null);
  const [gprJobStatus, setGprJobStatus] = useState<string>("aguardando");

  const dztFiles = files.filter((f) => f.name.toLowerCase().endsWith(".dzt"));

  // ── Polling: job preflight ────────────────────────────────────────────────

  useEffect(() => {
    if (step !== "preflight" || !preflightJobId) return;
    if (preflightStatus === "concluido" || preflightStatus === "erro") return;

    const id = setInterval(async () => {
      try {
        const s = await getJobStatus(preflightJobId);
        if (s) setPreflightStatus(s);
      } catch { /* silencioso */ }
    }, POLL_MS);

    return () => clearInterval(id);
  }, [step, preflightJobId, preflightStatus]);

  // ── Fetch preflight data quando job conclui ───────────────────────────────
  // useRef evita múltiplos fetches sem setState síncrono dentro do effect

  useEffect(() => {
    if (preflightStatus !== "concluido" || preflightData || fetchingPreflight.current) return;
    fetchingPreflight.current = true;

    getProjectPreflight(projectId)
      .then((d) => {
        if (d) setPreflightData(d);
        else setPreflightDataError("Resultado do preflight não encontrado no banco.");
      })
      .catch(() => setPreflightDataError("Erro ao carregar resultado do preflight."));
  }, [preflightStatus, preflightData, projectId]);

  // ── Polling: job GPR pesado ───────────────────────────────────────────────

  useEffect(() => {
    if (!gprJobId) return;
    if (gprJobStatus === "concluido" || gprJobStatus === "erro") return;

    const id = setInterval(async () => {
      try {
        const s = await getJobStatus(gprJobId);
        if (s) setGprJobStatus(s);
      } catch { /* silencioso */ }
    }, POLL_MS);

    return () => clearInterval(id);
  }, [gprJobId, gprJobStatus]);

  // ── Upload + preflight ────────────────────────────────────────────────────

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!dztFiles.length) return;
    setUploading(true);
    setProgress(0);
    setErrorMsg("");

    try {
      const supabase = createClient();
      const uploaded: UploadedFileMeta[] = [];

      for (let i = 0; i < dztFiles.length; i += UPLOAD_BATCH_SIZE) {
        const batch = dztFiles.slice(i, i + UPLOAD_BATCH_SIZE);
        const results = await Promise.all(
          batch.map(async (file) => {
            const storagePath = `${projectId}/${file.name}`;
            const { error } = await supabase.storage
              .from("gpr-uploads")
              .upload(storagePath, file, { contentType: "application/octet-stream", upsert: true });
            return { file, storagePath, error };
          })
        );
        for (const r of results) {
          if (r.error) { setErrorMsg(`Erro ao enviar ${r.file.name}: ${r.error.message}`); setUploading(false); return; }
          uploaded.push({ fileName: r.file.name, storagePath: r.storagePath, sizeBytes: r.file.size });
        }
        setProgress(uploaded.length);
      }

      const regResult = await registerUploadedFiles(projectId, uploaded);
      if (!regResult.ok) { setErrorMsg(regResult.error); setUploading(false); return; }

      const pfResult = await startPreflight(projectId);
      if (!pfResult.ok) { setErrorMsg(pfResult.error ?? "Erro ao iniciar preflight"); setUploading(false); return; }

      setUploadedCount(uploaded.length);
      setPreflightJobId(pfResult.jobId ?? null);
      setPreflightStatus("aguardando");
      setPreflightError("");
      setStep("preflight");
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Erro inesperado no upload");
    } finally {
      setUploading(false);
    }
  }

  // ── Confirmar preflight ───────────────────────────────────────────────────

  async function handleConfirm(overrides: PreflightOverrides = {}) {
    setConfirming(true);
    setConfirmError("");
    setShowAdjust(false);
    const result = await confirmPreflight(projectId, overrides);
    if (!result.ok) {
      setConfirmError(result.error ?? "Erro ao confirmar");
      setConfirming(false);
      return;
    }
    setGprJobId(result.jobId ?? null);
    setGprJobStatus("aguardando");
    setConfirming(false);
  }

  function handleOpenAdjust() {
    // Velocity: mediana das recomendações (mais justo para múltiplos arquivos)
    // Depth: maior profundidade física recomendada entre os arquivos (escala uniforme)
    const recs = preflightData ? Object.values(preflightData.files).map((r) => r.recommendation) : [];
    const velocities = recs.map((r) => r.recommended_velocity_mns).sort((a, b) => a - b);
    const medianVelocity = velocities.length > 0 ? velocities[Math.floor(velocities.length / 2)] : 0.10;
    const maxDepth = recs.length > 0 ? Math.max(...recs.map((r) => r.recommended_depth_preview_m)) : 5.0;
    setAdjVelocity(String(medianVelocity));
    setAdjDepth(String(maxDepth));
    setAdjBandpass(true);
    setShowAdjust(true);
  }

  // ── Fallback legado ───────────────────────────────────────────────────────

  async function handleStart() {
    setStarting(true);
    setErrorMsg("");
    try { await startProcessingWithConfig(projectId, config); }
    catch (err: unknown) { setStarting(false); setErrorMsg(err instanceof Error ? err.message : "Erro ao iniciar processamento"); }
  }
  function applyPreset(name: string) { const p = CONFIG_PRESETS[name]; if (p) setConfig(JSON.parse(JSON.stringify(p))); }
  function toggleFiltro(key: keyof FilterConfig["filtros_ativos"]) {
    setConfig((prev) => ({ ...prev, filtros_ativos: { ...prev.filtros_ativos, [key]: !prev.filtros_ativos[key] } }));
  }

  // ── Render: step preflight ────────────────────────────────────────────────

  if (step === "preflight") {
    const isDone    = preflightStatus === "concluido";
    const isError   = preflightStatus === "erro";
    const isPending = !isDone && !isError;

    return (
      <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100">
            {gprJobId
              ? gprJobStatus === "concluido" ? "Processamento concluído" : "Processando GPR…"
              : isDone && preflightData
                ? Object.keys(preflightData.files).length > 1
                  ? `Configurações recomendadas para ${Object.keys(preflightData.files).length} arquivos DZT`
                  : "Configuração recomendada pelo DZT"
              : isDone ? "Preflight concluído"
              : isError ? "Erro no preflight"
              : "Analisando DZTs…"}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            {uploadedCount} arquivo{uploadedCount !== 1 ? "s" : ""} enviado{uploadedCount !== 1 ? "s" : ""} com sucesso.
          </p>
        </div>

        {/* ── Pending: spinner ─────────────────────────────────────────────── */}
        {isPending && (
          <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
              <p className="text-sm font-medium text-cyan-300">Analisando metadados do DZT…</p>
            </div>
            <p className="text-xs text-slate-400">
              Lendo parâmetros de antena, velocity e profundidade para recomendar a
              melhor configuração de processamento.
            </p>
          </div>
        )}

        {/* ── Erro do preflight ────────────────────────────────────────────── */}
        {isError && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 space-y-3">
            <p className="text-sm font-medium text-red-300">Erro ao analisar metadados.</p>
            {preflightError && <p className="text-xs font-mono text-slate-400">{preflightError}</p>}
            <button
              onClick={async () => {
                setPreflightError("");
                const pfResult = await startPreflight(projectId);
                if (!pfResult.ok) { setPreflightError(pfResult.error ?? "Erro ao tentar novamente"); return; }
                setPreflightJobId(pfResult.jobId ?? null);
                setPreflightStatus("aguardando");
              }}
              className="text-sm px-4 py-2 rounded-lg bg-red-500/20 border border-red-500/30 text-red-300 hover:bg-red-500/30 transition-colors"
            >
              Tentar novamente
            </button>
          </div>
        )}

        {/* ── Done: carregando dados do banco ──────────────────────────────── */}
        {isDone && !preflightData && !preflightDataError && !gprJobId && (
          <div className="flex items-center gap-3 text-sm text-slate-400">
            <div className="w-3 h-3 rounded-full border-2 border-slate-500 border-t-transparent animate-spin" />
            Carregando resultado do preflight…
          </div>
        )}

        {/* ── Done: erro ao carregar dados ─────────────────────────────────── */}
        {isDone && preflightDataError && !gprJobId && (
          <div className="rounded-xl border border-yellow-500/30 bg-yellow-500/5 p-4">
            <p className="text-sm text-yellow-300">{preflightDataError}</p>
            <p className="text-xs text-slate-400 mt-1">
              Preflight ainda não disponível. Aguarde alguns segundos e recarregue a página.
            </p>
          </div>
        )}

        {/* ── Done: GPR job rodando ─────────────────────────────────────────── */}
        {isDone && gprJobId && gprJobStatus !== "concluido" && gprJobStatus !== "erro" && (
          <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="w-4 h-4 rounded-full border-2 border-cyan-400 border-t-transparent animate-spin" />
              <p className="text-sm font-medium text-cyan-300">Processamento GPR em andamento…</p>
            </div>
            <p className="text-xs text-slate-400">
              O worker está rodando o pipeline GPR (readgssi engine). Isso pode levar alguns
              minutos. A página do projeto será atualizada automaticamente ao concluir.
            </p>
          </div>
        )}

        {/* ── Done: GPR concluído ───────────────────────────────────────────── */}
        {isDone && gprJobId && gprJobStatus === "concluido" && (
          <div className="rounded-xl border border-green-500/30 bg-green-500/5 p-4 space-y-3">
            <p className="text-sm font-medium text-green-300">Pipeline GPR concluído com sucesso.</p>
            <p className="text-xs text-slate-400">
              Imagens processadas e alvos detectados estão disponíveis na página do projeto.
            </p>
            <a
              href={`/projetos/${projectId}`}
              className="inline-block rounded-lg bg-green-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-green-400 transition-colors"
            >
              Ver resultados
            </a>
          </div>
        )}

        {/* ── Done: GPR erro ────────────────────────────────────────────────── */}
        {isDone && gprJobId && gprJobStatus === "erro" && (
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 space-y-2">
            <p className="text-sm font-medium text-red-300">Erro no processamento GPR.</p>
            <p className="text-xs text-slate-400">Verifique os logs do projeto para mais detalhes.</p>
          </div>
        )}

        {/* ── Confirmation card ─────────────────────────────────────────────── */}
        {isDone && preflightData && !gprJobId && (
          <PreflightConfirmCard
            data={preflightData}
            confirming={confirming}
            confirmError={confirmError}
            showAdjust={showAdjust}
            adjVelocity={adjVelocity}
            adjDepth={adjDepth}
            adjBandpass={adjBandpass}
            onConfirm={() => handleConfirm()}
            onOpenAdjust={handleOpenAdjust}
            onCloseAdjust={() => setShowAdjust(false)}
            onConfirmWithOverrides={() =>
              handleConfirm({
                velocity_mns:    parseFloat(adjVelocity) || undefined,
                depth_preview_m: parseFloat(adjDepth) || undefined,
                bandpass_enabled: adjBandpass,
              })
            }
            onAdjVelocityChange={setAdjVelocity}
            onAdjDepthChange={setAdjDepth}
            onAdjBandpassToggle={() => setAdjBandpass((v) => !v)}
          />
        )}

        {/* Footer link */}
        {!gprJobId && (
          <a
            href={`/projetos/${projectId}`}
            className="block text-center text-sm text-slate-500 hover:text-slate-300 transition-colors"
          >
            Ver projeto sem processar
          </a>
        )}
      </div>
    );
  }

  // ── Render: step ready (fallback — projeto com preset) ────────────────────

  if (step === "ready") {
    return (
      <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Upload concluído</h1>
          <p className="text-sm text-slate-400 mt-1">
            {dztFiles.length} arquivo{dztFiles.length !== 1 ? "s" : ""} enviado{dztFiles.length !== 1 ? "s" : ""} com sucesso.
          </p>
        </div>
        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-1">
          <p className="text-sm font-medium text-cyan-300">Preset configurado via Nova Entrada</p>
          <p className="text-xs text-slate-400">
            Os parâmetros de processamento foram definidos ao criar o projeto.
          </p>
        </div>
        {errorMsg && <p className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">{errorMsg}</p>}
        <button
          onClick={async () => {
            setStarting(true); setErrorMsg("");
            try { await startProcessingDirect(projectId); }
            catch (err: unknown) { setStarting(false); setErrorMsg(err instanceof Error ? err.message : "Erro ao iniciar processamento"); }
          }}
          disabled={starting}
          className="w-full rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50"
        >
          {starting ? "Iniciando…" : "Iniciar processamento com preset selecionado"}
        </button>
      </div>
    );
  }

  // ── Render: step configure (fallback — sem preset) ────────────────────────

  if (step === "configure") {
    return (
      <div className="max-w-xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Configuração de Processamento</h1>
          <p className="text-sm text-slate-400 mt-1">
            {dztFiles.length} arquivo{dztFiles.length !== 1 ? "s" : ""} enviado{dztFiles.length !== 1 ? "s" : ""} com sucesso.
          </p>
        </div>
        <div>
          <p className="text-xs font-medium text-slate-500 mb-2 uppercase tracking-wide">Preset rápido</p>
          <div className="flex flex-wrap gap-2">
            {Object.keys(CONFIG_PRESETS).map((name) => (
              <button key={name} onClick={() => applyPreset(name)}
                className="text-xs px-3 py-1.5 rounded-md border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-slate-100 transition-colors">
                {name}
              </button>
            ))}
          </div>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900 divide-y divide-slate-800">
          {(Object.keys(FILTER_LABELS) as (keyof FilterConfig["filtros_ativos"])[]).map((key) => (
            <div key={key} className="flex items-center justify-between px-4 py-3">
              <span className="text-sm text-slate-300">{FILTER_LABELS[key]}</span>
              <button onClick={() => toggleFiltro(key)}
                className={`relative w-10 h-5 rounded-full transition-colors ${config.filtros_ativos[key] ? "bg-cyan-500" : "bg-slate-700"}`}>
                <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${config.filtros_ativos[key] ? "translate-x-5" : "translate-x-0.5"}`} />
              </button>
            </div>
          ))}
        </div>
        <div className="space-y-4">
          {config.filtros_ativos.background_removal && (
            <Slider label="Background Removal — traços" value={config.bgremoval_traces} min={10} max={100} step={5} onChange={(v) => setConfig((c) => ({ ...c, bgremoval_traces: v }))} />
          )}
          {config.filtros_ativos.tpow_gain && (
            <Slider label="tpow Gain — potência" value={config.tpow_power} min={0.2} max={1.5} step={0.1} onChange={(v) => setConfig((c) => ({ ...c, tpow_power: v }))} />
          )}
          {config.filtros_ativos.agc && (
            <Slider label="AGC — janela" value={config.agc_window} min={50} max={300} step={25} onChange={(v) => setConfig((c) => ({ ...c, agc_window: v }))} />
          )}
          <Slider label="Contraste da imagem" value={config.contrast} min={1.0} max={5.0} step={0.5} onChange={(v) => setConfig((c) => ({ ...c, contrast: v }))} />
        </div>
        {errorMsg && <p className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">{errorMsg}</p>}
        <button onClick={handleStart} disabled={starting}
          className="w-full rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50">
          {starting ? "Iniciando…" : "Iniciar processamento com estas configurações"}
        </button>
      </div>
    );
  }

  // ── Render: step upload ───────────────────────────────────────────────────

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-100 mb-2">Upload de arquivos .DZT</h1>
      <p className="text-sm text-slate-400 mb-6">Projeto: {projectId}</p>
      <form onSubmit={handleUpload} className="space-y-4">
        <div
          className="border-2 border-dashed border-slate-700 rounded-xl p-8 text-center cursor-pointer hover:border-cyan-500/50 hover:bg-slate-800/30 transition-colors"
          onClick={() => !uploading && inputRef.current?.click()}
        >
          <input ref={inputRef} type="file" multiple accept=".dzt" className="hidden"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
          {files.length === 0 ? (
            <p className="text-sm text-slate-500">Clique ou arraste os arquivos .DZT aqui</p>
          ) : (
            <div className="text-sm text-left space-y-1">
              <p className="text-slate-400 mb-2 font-medium">
                {dztFiles.length} arquivo{dztFiles.length !== 1 ? "s" : ""} .DZT selecionado{dztFiles.length !== 1 ? "s" : ""}
              </p>
              <ul className="max-h-48 overflow-y-auto space-y-0.5">
                {dztFiles.map((f) => (
                  <li key={f.name} className="text-slate-300">
                    {f.name} <span className="text-slate-500">({(f.size / 1024 / 1024).toFixed(1)} MB)</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        {uploading && dztFiles.length > 0 && (
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Enviando para o Supabase Storage…</span>
              <span className="tabular-nums font-medium text-slate-300">{progress}/{dztFiles.length}</span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
              <div className="h-full rounded-full bg-cyan-500 transition-all duration-300" style={{ width: `${(progress / dztFiles.length) * 100}%` }} />
            </div>
          </div>
        )}
        {errorMsg && <p className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">{errorMsg}</p>}
        <button type="submit" disabled={!dztFiles.length || uploading}
          className="w-full rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          {uploading ? `Enviando ${progress}/${dztFiles.length}…` : `Enviar ${dztFiles.length > 0 ? dztFiles.length + " arquivo" + (dztFiles.length !== 1 ? "s" : "") : "arquivos"}`}
        </button>
      </form>
    </div>
  );
}

// ── Card de confirmação do preflight ─────────────────────────────────────────

function PreflightConfirmCard({
  data,
  confirming,
  confirmError,
  showAdjust,
  adjVelocity,
  adjDepth,
  adjBandpass,
  onConfirm,
  onOpenAdjust,
  onCloseAdjust,
  onConfirmWithOverrides,
  onAdjVelocityChange,
  onAdjDepthChange,
  onAdjBandpassToggle,
}: {
  data: PreflightData;
  confirming: boolean;
  confirmError: string;
  showAdjust: boolean;
  adjVelocity: string;
  adjDepth: string;
  adjBandpass: boolean;
  onConfirm: () => void;
  onOpenAdjust: () => void;
  onCloseAdjust: () => void;
  onConfirmWithOverrides: () => void;
  onAdjVelocityChange: (v: string) => void;
  onAdjDepthChange: (v: string) => void;
  onAdjBandpassToggle: () => void;
}) {
  const entries = Object.entries(data.files);
  const isMulti = entries.length > 1;

  // Detecta se arquivos têm antena ou velocity distintas
  const uniqueFreqs     = new Set(entries.map(([, r]) => r.recommendation.recommended_antenna_freq_mhz));
  const uniqueVelocities = new Set(entries.map(([, r]) => r.recommendation.recommended_velocity_mns.toFixed(4)));
  const metadataDiffer  = isMulti && (uniqueFreqs.size > 1 || uniqueVelocities.size > 1);

  // Badge de confiança
  const confBadge = (c: string) => {
    const cls = CONFIDENCE_COLORS[c] ?? "text-slate-400";
    return <span className={`text-xs font-medium ${cls}`}>{c}</span>;
  };

  return (
    <div className="space-y-4">
      {/* ── Aviso: metadados diferentes entre arquivos ──────────────────────── */}
      {metadataDiffer && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 px-4 py-3">
          <p className="text-xs font-semibold text-amber-300 mb-0.5">Metadados diferentes entre arquivos</p>
          <p className="text-xs text-slate-400">
            Os arquivos possuem antena ou velocity distintas. Cada DZT será
            processado com sua própria configuração recomendada.
          </p>
        </div>
      )}

      {/* ── Por arquivo ────────────────────────────────────────────────────── */}
      {entries.map(([filename, result]) => {
        const meta = result.dzt_metadata;
        const rec  = result.recommendation;
        const allWarnings = [...(meta.warnings ?? []), ...(rec.warnings ?? [])];

        return (
          <div key={filename} className="rounded-xl border border-slate-700 bg-slate-900 overflow-hidden">
            {/* Cabeçalho do arquivo */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800 bg-slate-800/50">
              <span className="text-sm font-mono font-medium text-slate-200">{filename}</span>
              {confBadge(meta.header_confidence)}
            </div>

            {/* Metadados */}
            <div className="px-4 py-3 grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
              <MetaRow label="Antena detectada"       value={meta.antenna_freq_mhz_detected > 0 ? `${meta.antenna_freq_mhz_detected} MHz` : "—"} />
              <MetaRow label="Velocity header"        value={`${meta.velocity_header_mns.toFixed(6)} m/ns`} />
              <MetaRow label="εr header"              value={meta.epsr_header.toFixed(2)} />
              <MetaRow label="Distância"              value={meta.dist_total_m > 0 ? `${meta.dist_total_m.toFixed(2)} m` : "— (coleta por tempo)"} />
              <MetaRow label="Profundidade (v header)" value={`${meta.depth_real_m_from_header_velocity.toFixed(2)} m`} />
              <MetaRow label="Traços"                 value={String(meta.n_traces)} />
            </div>

            {/* Recomendação por arquivo (só mostra se múltiplos com metadados distintos) */}
            {isMulti && (
              <div className="px-4 pb-3 grid grid-cols-2 gap-x-6 gap-y-1 text-xs border-t border-slate-800 pt-2 bg-slate-800/20">
                <MetaRow label="→ Velocity rec."  value={`${rec.recommended_velocity_mns.toFixed(6)} m/ns${rec.velocity_from_header ? " (header)" : " (padrão)"}`} />
                <MetaRow label="→ Antena rec."    value={rec.recommended_antenna_freq_mhz > 0 ? `${rec.recommended_antenna_freq_mhz} MHz` : "—"} />
              </div>
            )}

            {/* Mismatch de frequência */}
            {rec.frequency_mismatch && (
              <div className="mx-4 mb-3 rounded-lg bg-orange-500/10 border border-orange-500/30 px-3 py-2">
                <p className="text-xs text-orange-300 font-medium">
                  Mismatch de frequência: DZT em {rec.detected_freq_mhz} MHz, preset em {rec.selected_preset_freq_mhz} MHz.
                </p>
                {rec.recommended_preset_family && (
                  <p className="text-xs text-slate-400 mt-0.5">
                    Família recomendada: <span className="font-mono text-slate-300">{rec.recommended_preset_family}</span>
                  </p>
                )}
              </div>
            )}

            {/* Warnings */}
            {allWarnings.length > 0 && (
              <div className="mx-4 mb-3 space-y-1">
                {allWarnings.map((w, i) => (
                  <p key={i} className="text-xs text-yellow-300/80 bg-yellow-500/5 border border-yellow-500/20 rounded px-2 py-1">{w}</p>
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* ── Resumo da recomendação (somente para arquivo único ou arquivos iguais) ─ */}
      {!metadataDiffer && entries[0] && (
        <div className="rounded-xl border border-cyan-500/30 bg-cyan-500/5 p-4 space-y-3">
          <p className="text-xs font-semibold text-cyan-400 uppercase tracking-wide">
            {isMulti ? `Configuração uniforme para ${entries.length} arquivos` : "Configuração recomendada"}
          </p>
          <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
            {(() => {
              const rec = entries[0][1].recommendation;
              return (
                <>
                  <MetaRow label="Antena"                       value={rec.recommended_antenna_freq_mhz > 0 ? `${rec.recommended_antenna_freq_mhz} MHz` : "—"} />
                  <MetaRow label="Velocity"                     value={`${rec.recommended_velocity_mns.toFixed(6)} m/ns${rec.velocity_from_header ? " (do header)" : " (padrão)"}`} />
                  <MetaRow label="Escala inicial de profundidade" value={`${rec.recommended_depth_preview_m} m (profundidade física estimada)`} />
                  <MetaRow label="Perfil visual"                value={rec.recommended_visual_profile} />
                </>
              );
            })()}
          </div>
        </div>
      )}

      {/* ── Painel de ajuste inline ─────────────────────────────────────────── */}
      {showAdjust && (
        <div className="rounded-xl border border-slate-700 bg-slate-900 p-4 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-200">Ajustar antes de processar</p>
              {isMulti && (
                <p className="text-xs text-slate-500 mt-0.5">
                  Estes valores serão aplicados a todos os {entries.length} arquivos.
                </p>
              )}
            </div>
            <button onClick={onCloseAdjust} className="text-xs text-slate-500 hover:text-slate-300">Cancelar</button>
          </div>

          {/* Velocity */}
          <div className="space-y-1">
            <label className="text-xs text-slate-400">
              Velocity (m/ns) — range 0.04–0.35
              {isMulti && <span className="text-slate-600"> · mediana das recomendações usada como ponto de partida</span>}
            </label>
            <input
              type="number" min={0.04} max={0.35} step={0.001}
              value={adjVelocity}
              onChange={(e) => onAdjVelocityChange(e.target.value)}
              className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Profundidade renderizada */}
          <div className="space-y-1">
            <label className="text-xs text-slate-400">
              Escala de profundidade renderizada (m) — ajustável antes ou depois do processamento
            </label>
            <input
              type="number" min={1} max={20} step={0.5}
              value={adjDepth}
              onChange={(e) => onAdjDepthChange(e.target.value)}
              className="w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Bandpass */}
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Bandpass</span>
            <button
              onClick={onAdjBandpassToggle}
              className={`relative w-10 h-5 rounded-full transition-colors ${adjBandpass ? "bg-cyan-500" : "bg-slate-700"}`}
            >
              <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${adjBandpass ? "translate-x-5" : "translate-x-0.5"}`} />
            </button>
          </div>

          <button
            onClick={onConfirmWithOverrides}
            disabled={confirming}
            className="w-full rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50"
          >
            {confirming ? "Iniciando…" : isMulti ? `Processar ${entries.length} arquivos com ajustes` : "Processar com ajustes"}
          </button>
        </div>
      )}

      {/* ── Erro de confirmação ─────────────────────────────────────────────── */}
      {confirmError && (
        <p className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">
          {confirmError}
        </p>
      )}

      {/* ── Botões principais ───────────────────────────────────────────────── */}
      {!showAdjust && (
        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            disabled={confirming}
            className="flex-1 rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50"
          >
            {confirming
              ? "Iniciando…"
              : isMulti
                ? `Processar ${entries.length} arquivos com recomendado`
                : "Processar com recomendado"}
          </button>
          <button
            onClick={onOpenAdjust}
            disabled={confirming}
            className="flex-1 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm font-semibold text-slate-300 hover:bg-slate-700 transition-colors disabled:opacity-50"
          >
            Ajustar antes de processar
          </button>
        </div>
      )}
    </div>
  );
}

// ── Sub-componentes ───────────────────────────────────────────────────────────

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-slate-500">{label}: </span>
      <span className="text-slate-300 font-mono">{value}</span>
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
      <div className="flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className="font-medium tabular-nums text-slate-300">{value}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-cyan-500" />
      <div className="flex justify-between text-[10px] text-slate-600">
        <span>{min}</span><span>{max}</span>
      </div>
    </div>
  );
}
