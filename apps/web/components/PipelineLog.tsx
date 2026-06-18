"use client";

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

// ── Full log ─────────────────────────────────────────────────────────────────

function FullLog({ m }: { m: PipelineMetrics }) {
  const snr = m.snr_stages_db ?? {};
  const snrRaw = m.snr_raw_db ?? (snr.raw != null && snr.raw > -998 ? snr.raw : null);
  const snrRawRatio = m.snr_raw_ratio;
  const modo = m.modo_processamento;
  const filtros = m.filtros_customizados ?? {};

  // Parâmetros de filtro: filtros_customizados (reprocessamento) ou pipeline_metrics.json (primeiro processamento)
  const dewowW = filtros.dewow_window;
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
  const bgTraces = filtros.bgremoval_traces;
  const tpowPow = filtros.tpow_power;
  const agcW = filtros.agc_window;

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
}: {
  metrics: PipelineMetrics | null;
  compact?: boolean;
}) {
  if (!metrics) {
    return (
      <p className="text-xs text-slate-500">
        Log não disponível — perfil não encontrado.
      </p>
    );
  }

  if (compact) return <CompactLog m={metrics} />;
  return <FullLog m={metrics} />;
}
