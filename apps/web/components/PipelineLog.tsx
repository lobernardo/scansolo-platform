"use client";

import { useState } from "react";
import type { PipelineMetrics } from "@/app/actions/gpr-actions";

const ND = "n/d";

function safe(v: number | null | undefined, suffix = ""): string {
  if (v == null || v <= -998) return ND;
  return `${v}${suffix}`;
}

function db(v: number | null | undefined): string {
  if (v == null || v <= -998) return ND;
  return `${v.toFixed(1)} dB`;
}

function ratio(v: number | null | undefined): string {
  if (v == null || v <= 0) return ND;
  return `${v.toFixed(0)}×`;
}

function StageIcon({ s }: { s: "ok" | "warn" | "skip" | "na" }) {
  if (s === "ok") return <span className="text-emerald-400 select-none">✓</span>;
  if (s === "warn") return <span className="text-amber-400 select-none">⚠</span>;
  if (s === "skip") return <span className="text-slate-600 select-none">✗</span>;
  return <span className="text-slate-600 select-none">—</span>;
}

function Row({
  s,
  label,
  value,
}: {
  s: "ok" | "warn" | "skip" | "na";
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-1.5">
      <StageIcon s={s} />
      <span className="text-slate-500 shrink-0">{label}:</span>
      <span className="text-slate-300 break-all">{value}</span>
    </div>
  );
}

function SectionHead({ title }: { title: string }) {
  return (
    <p className="text-[10px] font-bold uppercase tracking-widest text-slate-600 pt-1">
      {title}
    </p>
  );
}

function ModeBadge({ mode }: { mode: string | null | undefined }) {
  if (!mode) return <span className="text-slate-500">{ND}</span>;
  const cls =
    mode === "PADRAO"
      ? "bg-emerald-500/15 text-emerald-400"
      : mode === "MINIMO"
      ? "bg-amber-500/15 text-amber-400"
      : mode === "AGRESSIVO"
      ? "bg-red-500/15 text-red-400"
      : "bg-slate-700/50 text-slate-400";
  return (
    <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${cls}`}>
      {mode}
    </span>
  );
}

// ── Compact: only SNR gate + detector summary ────────────────────────────────

function CompactLog({ m }: { m: PipelineMetrics }) {
  const nScore30 = m.n_alvos_score_30 ?? 0;
  const nAlta = m.n_alvos_alta ?? 0;
  const nMedia = m.n_alvos_media ?? 0;
  const modo = m.modo_processamento;

  return (
    <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs font-mono">
      <span className="flex items-center gap-1.5">
        <span className="text-slate-500">Modo:</span>
        <ModeBadge mode={modo} />
      </span>
      {m.snr_raw_ratio != null && (
        <span className="flex items-center gap-1">
          <span className="text-slate-500">SNR ratio:</span>
          <span className="text-slate-300">{ratio(m.snr_raw_ratio)}</span>
        </span>
      )}
      {m.snr_raw_db != null && (
        <span className="flex items-center gap-1">
          <span className="text-slate-500">SNR raw:</span>
          <span className="text-slate-300">{db(m.snr_raw_db)}</span>
        </span>
      )}
      <span className="flex items-center gap-1">
        <span className="text-slate-500">Alvos ≥30:</span>
        <span className="text-slate-300">{nScore30}</span>
        <span className="text-slate-600">
          ({nAlta} alta, {nMedia} média)
        </span>
      </span>
    </div>
  );
}

// ── Preflight DZT section ─────────────────────────────────────────────────────

function formatPresetFamily(
  family: string | null | undefined,
  detectedFreq: number | null | undefined
): string {
  if (family == null) return ND;
  if (family === "400mhz") {
    if (detectedFreq != null && detectedFreq > 0) return `${detectedFreq}–400 MHz`;
    return "350–400 MHz";
  }
  if (family === "270mhz") return "270 MHz";
  if (family === "900mhz") return "900 MHz";
  return family;
}

function PreflightSection({
  m,
  profileId,
  onReprocessWithOverrides,
}: {
  m: PipelineMetrics;
  profileId?: string;
  onReprocessWithOverrides?: (overrides: Record<string, unknown>) => Promise<void>;
}) {
  const [confirming, setConfirming] = useState(false);
  const [applying, setApplying] = useState(false);

  const hasPreflight =
    (m.antenna_freq_mhz_detected != null && m.antenna_freq_mhz_detected > 0) ||
    m.velocity_header_mns != null ||
    m.frequency_mismatch === true ||
    (m.preflight_warnings?.length ?? 0) > 0;

  if (!hasPreflight) return null;

  const confStatus =
    m.preflight_header_confidence === "alta"
      ? "ok"
      : m.preflight_header_confidence === "media"
      ? "warn"
      : m.preflight_header_confidence === "baixa"
      ? "skip"
      : "na";

  const headerWarnings =
    (m.preflight?.dzt_metadata?.warnings as string[] | undefined) ?? [];

  const canReprocess =
    !!profileId &&
    !!onReprocessWithOverrides &&
    (m.frequency_mismatch === true || m.recommended_velocity_mns != null);

  function buildOverrides(): Record<string, unknown> {
    const overrides: Record<string, unknown> = { engine: "readgssi_engine" };
    if (m.antenna_freq_mhz_detected != null && m.antenna_freq_mhz_detected > 0)
      overrides.antenna_freq_mhz = m.antenna_freq_mhz_detected;
    if (m.recommended_velocity_mns != null)
      overrides.velocity_mns = m.recommended_velocity_mns;
    if (m.recommended_visual_profile != null)
      overrides.visual_profile = m.recommended_visual_profile;
    if (m.recommended_depth_preview_m != null)
      overrides.depth_preview_m = m.recommended_depth_preview_m;
    return overrides;
  }

  async function handleApply() {
    setApplying(true);
    try {
      await onReprocessWithOverrides!(buildOverrides());
    } finally {
      setApplying(false);
      setConfirming(false);
    }
  }

  return (
    <>
      <SectionHead title="Preflight DZT" />
      <div className="pl-2 space-y-0.5">
        {m.frequency_mismatch && (
          <div className="rounded border border-amber-600/40 bg-amber-900/20 px-2 py-1 text-amber-400 text-[11px] mb-1 leading-snug">
            ⚠ Preset/frequência possivelmente incompatível com o DZT. Arquivo detectado como{" "}
            {m.antenna_freq_mhz_detected != null ? `${m.antenna_freq_mhz_detected} MHz` : "frequência diferente"}.
          </div>
        )}
        {m.antenna_freq_mhz_detected != null && m.antenna_freq_mhz_detected > 0 && (
          <Row
            s={m.frequency_mismatch ? "warn" : "ok"}
            label="Antena detectada"
            value={`${m.antenna_freq_mhz_detected} MHz`}
          />
        )}
        {m.velocity_header_mns != null && (
          <Row
            s="ok"
            label="Velocity header"
            value={`${m.velocity_header_mns.toFixed(4)} m/ns${
              m.epsr_header != null ? ` (εr = ${m.epsr_header.toFixed(2)})` : ""
            }`}
          />
        )}
        {m.preflight_header_confidence != null && (
          <Row
            s={confStatus}
            label="Confiança header"
            value={m.preflight_header_confidence}
          />
        )}
        {m.recommended_preset_family != null && (
          <Row
            s="ok"
            label="Família recomendada"
            value={formatPresetFamily(m.recommended_preset_family, m.antenna_freq_mhz_detected)}
          />
        )}
        {m.recommended_velocity_mns != null && (
          <Row
            s="ok"
            label="Velocity recomendada"
            value={`${m.recommended_velocity_mns.toFixed(4)} m/ns`}
          />
        )}
        {m.recommended_visual_profile != null && (
          <Row s="ok" label="Perfil visual rec." value={m.recommended_visual_profile} />
        )}
        {headerWarnings.map((w, i) => (
          <div key={i} className="text-[10px] text-amber-600/80 pl-4 leading-snug break-words">
            • {w.length > 90 ? w.slice(0, 90) + "…" : w}
          </div>
        ))}

        {/* Botão "Usar configuração recomendada" — só aparece quando há profileId + handler + dados de preflight */}
        {canReprocess && !confirming && (
          <button
            onClick={() => setConfirming(true)}
            className="mt-1.5 text-[11px] px-2.5 py-1 rounded border border-cyan-700/60 bg-cyan-900/20 text-cyan-400 hover:bg-cyan-900/40 hover:text-cyan-300 transition-colors"
          >
            Usar configuração recomendada
          </button>
        )}

        {confirming && (
          <div className="mt-1.5 rounded border border-slate-600/60 bg-slate-900/60 px-2.5 py-2 space-y-1.5">
            <p className="text-[11px] text-slate-300 font-medium">
              Aplicar configuração recomendada e reprocessar este DZT?
            </p>
            <div className="space-y-0.5 text-[11px]">
              {m.antenna_freq_mhz_detected != null && m.antenna_freq_mhz_detected > 0 && (
                <div>
                  <span className="text-slate-500">Antena:</span>{" "}
                  <span className="text-slate-300">{m.antenna_freq_mhz_detected} MHz</span>
                </div>
              )}
              {m.recommended_velocity_mns != null && (
                <div>
                  <span className="text-slate-500">Velocity:</span>{" "}
                  <span className="text-slate-300">{m.recommended_velocity_mns.toFixed(4)} m/ns</span>
                </div>
              )}
              {m.recommended_visual_profile != null && (
                <div>
                  <span className="text-slate-500">Perfil visual:</span>{" "}
                  <span className="text-slate-300">{m.recommended_visual_profile}</span>
                </div>
              )}
              {m.recommended_preset_family != null && (
                <div>
                  <span className="text-slate-500">Família recomendada:</span>{" "}
                  <span className="text-slate-300">
                    {formatPresetFamily(m.recommended_preset_family, m.antenna_freq_mhz_detected)}
                  </span>
                </div>
              )}
              {m.recommended_depth_preview_m != null && (
                <div>
                  <span className="text-slate-500">Profundidade visual:</span>{" "}
                  <span className="text-slate-300">{m.recommended_depth_preview_m.toFixed(1)} m</span>
                </div>
              )}
            </div>
            <div className="flex gap-2 pt-0.5">
              <button
                onClick={handleApply}
                disabled={applying}
                className="text-[11px] px-3 py-1 rounded bg-cyan-700 text-white hover:bg-cyan-600 disabled:opacity-50 transition-colors"
              >
                {applying ? "Enviando…" : "Confirmar"}
              </button>
              <button
                onClick={() => setConfirming(false)}
                disabled={applying}
                className="text-[11px] px-3 py-1 rounded border border-slate-600 text-slate-400 hover:text-slate-200 disabled:opacity-50 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ── Full log ─────────────────────────────────────────────────────────────────

function FullLog({
  m,
  profileId,
  onReprocessWithOverrides,
}: {
  m: PipelineMetrics;
  profileId?: string;
  onReprocessWithOverrides?: (overrides: Record<string, unknown>) => Promise<void>;
}) {
  const snr = m.snr_stages_db ?? {};
  const snrRaw = m.snr_raw_db ?? (snr.raw != null && snr.raw > -998 ? snr.raw : null);
  const snrRawRatio = m.snr_raw_ratio;
  const modo = m.modo_processamento;
  const filtros = m.filtros_customizados ?? {};

  // Parâmetros de filtro: filtros_customizados (reprocessamento) > pipeline_metrics.json (primeiro processamento)
  const dewowW = (filtros.dewow_window as number | undefined) ?? m.dewow_window;
  // bandpass: checa JSON primeiro (cobre primeiro processamento), depois filtros_customizados (reprocessamento)
  const bandpassDesativado =
    m.bandpass_aplicado === "desativado" ||
    m.bandpass_low_mhz_usado === 0 ||
    filtros.bandpass === false;
  const bpLow =
    filtros.bandpass_low_mhz ??
    (m.bandpass_low_mhz_usado != null && m.bandpass_low_mhz_usado > 0 ? m.bandpass_low_mhz_usado : null);
  const bpHigh =
    filtros.bandpass_high_mhz ??
    (m.bandpass_high_mhz_usado != null && m.bandpass_high_mhz_usado > 0 ? m.bandpass_high_mhz_usado : null);
  const bpOrder = filtros.bandpass_order ?? m.bandpass_order_usado;
  const bgTraces = (filtros.bgremoval_traces as number | undefined) ?? m.bgremoval_traces;
  const tpowPow = (filtros.tpow_power as number | undefined) ?? m.tpow_power;
  const agcW = (filtros.agc_window as number | undefined) ?? m.agc_window;

  // SNR pós-filtros (aproximações via snr_stages_db)
  const snrBp = snr.bp != null && snr.bp > -998 ? snr.bp : null;   // ≈ científico (dewow+bp)
  const snrTpow = snr.tpow != null && snr.tpow > -998 ? snr.tpow : null; // ≈ relatório (bgremoval+tpow)

  function delta(a: number | null, b: number | null): string {
    if (a == null || b == null) return "";
    const d = a - b;
    return ` (${d >= 0 ? "+" : ""}${d.toFixed(1)} dB vs raw)`;
  }

  const nAlvos =
    (m.n_alvos_alta ?? 0) + (m.n_alvos_media ?? 0) + (m.n_alvos_baixa ?? 0);
  const nScore30 = m.n_alvos_score_30 ?? 0;

  return (
    <div className="space-y-2 text-xs font-mono">
      {/* LEITURA */}
      <SectionHead title="Leitura do DZT" />
      <div className="pl-2 space-y-0.5">
        <Row
          s={m.dzt_filename ? "ok" : "na"}
          label="Arquivo"
          value={m.dzt_filename ?? ND}
        />
        <Row
          s={(m.n_tracos ?? m.n_tracos_json) != null ? "ok" : "na"}
          label="Traços × amostras"
          value={`${safe(m.n_tracos ?? m.n_tracos_json)} × ${safe(m.n_amostras_final)}`}
        />
        {(m.distancia_max_m ?? m.dist_total_m) != null && (
          <Row
            s="ok"
            label="Dist. total"
            value={`${(m.distancia_max_m ?? m.dist_total_m)!.toFixed(2)} m`}
          />
        )}
        {m.profundidade_max_m != null && (
          <Row
            s="ok"
            label="Prof. máx."
            value={`${m.profundidade_max_m.toFixed(2)} m`}
          />
        )}
      </div>

      {/* PREFLIGHT DZT */}
      <PreflightSection
        m={m}
        profileId={profileId}
        onReprocessWithOverrides={onReprocessWithOverrides}
      />

      {/* ESCALA E PROFUNDIDADE */}
      <SectionHead title="Escala e Profundidade" />
      <div className="pl-2 space-y-0.5">
        {m.velocity_mns != null ? (
          <Row
            s="ok"
            label="Velocity"
            value={`${m.velocity_mns.toFixed(4)} m/ns (εr ≈ ${Math.round(
              Math.pow(0.3 / m.velocity_mns, 2)
            )})`}
          />
        ) : (filtros.velocity_mns as number | undefined) != null ? (
          <Row
            s="ok"
            label="Velocity"
            value={`${filtros.velocity_mns} m/ns (εr ≈ ${Math.round(
              Math.pow(0.3 / Number(filtros.velocity_mns), 2)
            )})`}
          />
        ) : null}
        {m.velocity_fonte != null && (
          <div className="text-[10px] text-slate-600 pl-4">fonte: {m.velocity_fonte}</div>
        )}
        {m.depth_tecnica_m != null && (
          <Row s="ok" label="Prof. técnica" value={`${m.depth_tecnica_m.toFixed(2)} m`} />
        )}
        {m.depth_preview_m != null && (
          <Row
            s="ok"
            label="Visual — eixo Y"
            value={`${m.depth_preview_m.toFixed(2)} m${m.preview_visual_depth_configurado ? " (configurado)" : " (padrão 5 m)"}`}
          />
        )}
        {m.preview_velocity_mns != null && m.preview_velocity_mns !== m.velocity_mns && (
          <Row s="ok" label="Visual — velocity" value={`${m.preview_velocity_mns.toFixed(4)} m/ns`} />
        )}
        {m.preview_depth_real_m != null && (
          <Row s="ok" label="Visual — prof. física" value={`${m.preview_depth_real_m.toFixed(2)} m`} />
        )}
        {(m.agc_window_preview ?? (filtros.agc_window_preview as number | undefined)) != null && (
          <Row
            s="ok"
            label="Visual — AGC window"
            value={`window=${m.agc_window_preview ?? (filtros.agc_window_preview as number)}`}
          />
        )}
        {m.profundidade_max_m == null && m.depth_tecnica_m == null && (
          <Row s="na" label="Velocity" value={ND} />
        )}
      </div>

      {/* SNR GATE */}
      <SectionHead title="SNR Gate" />
      <div className="pl-2 space-y-0.5">
        <Row
          s={snrRaw != null ? "ok" : "na"}
          label="SNR raw"
          value={`${db(snrRaw)}  ratio ${ratio(snrRawRatio)}`}
        />
        <div className="flex items-center gap-1.5 pl-4">
          <span className="text-slate-500">Modo:</span>
          <ModeBadge mode={modo} />
        </div>
        {m.tipo_solo && (
          <div className="text-[10px] text-slate-600 pl-4">
            solo: {m.tipo_solo}
          </div>
        )}
      </div>

      {/* FILTROS */}
      <SectionHead title="Filtros de Sinal" />
      <div className="pl-2 space-y-0.5">
        <Row
          s={snr.dewow != null && snr.dewow > -998 ? "ok" : "na"}
          label="Dewow"
          value={
            dewowW != null
              ? `window=${dewowW}`
              : snr.dewow != null && snr.dewow > -998
              ? "aplicado"
              : ND
          }
        />
        <Row
          s={bandpassDesativado ? "skip" : snr.bp != null && snr.bp > -998 ? "ok" : "na"}
          label="Bandpass"
          value={
            bandpassDesativado
              ? "desativado"
              : bpLow != null && bpHigh != null
              ? `${bpLow}–${bpHigh} MHz, ordem ${bpOrder ?? "?"}`
              : snr.bp != null && snr.bp > -998
              ? "aplicado"
              : ND
          }
        />
        <Row
          s={snr.bgremoval != null && snr.bgremoval > -998 ? "ok" : "na"}
          label="BGRemoval"
          value={
            bgTraces != null
              ? `${bgTraces} traços`
              : snr.bgremoval != null && snr.bgremoval > -998
              ? "aplicado"
              : ND
          }
        />
        <Row
          s={snr.tpow != null && snr.tpow > -998 ? "ok" : "na"}
          label="TPow"
          value={
            tpowPow != null
              ? `power=${tpowPow}`
              : snr.tpow != null && snr.tpow > -998
              ? "aplicado"
              : ND
          }
        />
        <Row
          s={snr.agc != null && snr.agc > -998 ? "ok" : "na"}
          label="AGC"
          value={
            agcW != null
              ? `window=${agcW}`
              : snr.agc != null && snr.agc > -998
              ? "aplicado"
              : ND
          }
        />
      </div>

      {/* SNR PÓS-FILTROS */}
      <SectionHead title="SNR Pós-Filtros" />
      <div className="pl-2 space-y-0.5">
        <Row
          s={snrBp != null ? "ok" : "na"}
          label="Científico (≈ pós-bp)"
          value={snrBp != null ? `${snrBp.toFixed(1)} dB${delta(snrBp, snrRaw)}` : ND}
        />
        <Row
          s={snrTpow != null ? "ok" : "na"}
          label="Relatório (≈ pós-tpow)"
          value={snrTpow != null ? `${snrTpow.toFixed(1)} dB${delta(snrTpow, snrRaw)}` : ND}
        />
      </div>

      {/* MIGRAÇÃO */}
      <SectionHead title="Migração F-K" />
      <div className="pl-2">
        <Row
          s={m.imagem_migrada_ok ? "ok" : "skip"}
          label="Status"
          value={m.imagem_migrada_ok ? "concluída" : "não gerada"}
        />
      </div>

      {/* DETECTOR */}
      <SectionHead title="Detector" />
      <div className="pl-2 space-y-0.5">
        <Row
          s={nAlvos > 0 ? "ok" : "warn"}
          label="Total detectados"
          value={String(nAlvos)}
        />
        <Row
          s={nScore30 > 0 ? "ok" : "warn"}
          label="Score ≥ 30"
          value={String(nScore30)}
        />
        <Row
          s="ok"
          label="Alta / Média / Baixa"
          value={`${m.n_alvos_alta ?? 0} / ${m.n_alvos_media ?? 0} / ${m.n_alvos_baixa ?? 0}`}
        />
        {m.det_depth_min_m_usado != null && (
          <Row s="ok" label="Prof. mín. filtro" value={`${m.det_depth_min_m_usado} m`} />
        )}
        {m.detector_input_mode_json && (
          <Row s="ok" label="Input mode" value={m.detector_input_mode_json} />
        )}
      </div>

      {/* IMAGENS */}
      <SectionHead title="Imagens Geradas" />
      <div className="pl-2 space-y-0.5">
        {(
          [
            ["Bruta", m.imagem_bruta_ok],
            ["Relatório", m.imagem_relatorio_ok],
            ["Anotada", m.imagem_anotada_ok],
            ["Migrada", m.imagem_migrada_ok],
            ["Preview RADAN", m.imagem_preview_ok],
          ] as [string, boolean | undefined][]
        ).map(([label, ok]) => (
          <Row
            key={label}
            s={ok ? "ok" : "skip"}
            label={label}
            value={ok ? "gerada" : "não disponível"}
          />
        ))}
      </div>

      {m.pipeline_version && (
        <p className="text-[9px] text-slate-700 pt-1">
          pipeline v{m.pipeline_version} · preset: {m.preset_name ?? ND}
        </p>
      )}
      {!m.metricas_pipeline_url && (
        <p className="text-[9px] text-amber-700/80 italic pt-0.5">
          JSON de métricas ausente — dados parciais (perfil processado antes da Fase 11)
        </p>
      )}
    </div>
  );
}

// ── Diff (antes → depois de um reprocessamento) ───────────────────────────────

type DiffValue = string | number | null | undefined;

function DiffRow({
  label,
  prev,
  curr,
}: {
  label: string;
  prev: DiffValue;
  curr: DiffValue;
}) {
  const pStr = prev == null ? ND : String(prev);
  const cStr = curr == null ? ND : String(curr);
  const changed = pStr !== cStr;

  const numericDiff =
    typeof prev === "number" && typeof curr === "number"
      ? curr - prev
      : null;

  return (
    <div className="flex items-center gap-1.5 text-xs font-mono">
      <span className="text-slate-500 w-32 shrink-0 truncate">{label}</span>
      <span className="text-slate-500">{pStr}</span>
      {changed ? (
        <>
          <span className="text-slate-600">→</span>
          <span
            className={
              numericDiff != null
                ? numericDiff > 0
                  ? "text-emerald-400"
                  : "text-red-400"
                : "text-cyan-400"
            }
          >
            {cStr}
            {numericDiff != null &&
              ` (${numericDiff > 0 ? "+" : ""}${typeof numericDiff === "number" && !Number.isInteger(numericDiff)
                ? numericDiff.toFixed(1)
                : numericDiff})`}
          </span>
        </>
      ) : (
        <span className="text-slate-600 text-[10px]">(sem mudança)</span>
      )}
    </div>
  );
}

export function MetricsDiff({
  prev,
  curr,
}: {
  prev: PipelineMetrics;
  curr: PipelineMetrics;
}) {
  return (
    <div className="mt-2 rounded-lg border border-slate-700/60 bg-slate-900/50 p-3 space-y-1">
      <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 mb-2">
        Comparação antes → depois
      </p>
      <DiffRow
        label="Modo"
        prev={prev.modo_processamento}
        curr={curr.modo_processamento}
      />
      <DiffRow
        label="Alvos ≥30"
        prev={prev.n_alvos_score_30}
        curr={curr.n_alvos_score_30}
      />
      <DiffRow
        label="Alta confiança"
        prev={prev.n_alvos_alta}
        curr={curr.n_alvos_alta}
      />
      <DiffRow
        label="SNR raw (dB)"
        prev={prev.snr_raw_db != null ? parseFloat(prev.snr_raw_db.toFixed(1)) : null}
        curr={curr.snr_raw_db != null ? parseFloat(curr.snr_raw_db.toFixed(1)) : null}
      />
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function PipelineLog({
  metrics,
  compact = false,
  profileId,
  onReprocessWithOverrides,
}: {
  metrics: PipelineMetrics | null;
  compact?: boolean;
  profileId?: string;
  onReprocessWithOverrides?: (overrides: Record<string, unknown>) => Promise<void>;
}) {
  if (!metrics) {
    return (
      <p className="text-xs text-slate-500">
        Log não disponível — perfil sem métricas ou processado antes da Fase 11.
      </p>
    );
  }

  if (compact) return <CompactLog m={metrics} />;
  return (
    <FullLog
      m={metrics}
      profileId={profileId}
      onReprocessWithOverrides={onReprocessWithOverrides}
    />
  );
}
