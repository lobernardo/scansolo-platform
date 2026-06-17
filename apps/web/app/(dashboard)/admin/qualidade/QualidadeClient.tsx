"use client";

import { useState } from "react";
import type { GroundTruthStats, ConfiancaStats, CandidatoRecalibracao } from "./page";
import { dispararRecalibracao } from "./actions";

type Props = {
  gtStats: GroundTruthStats;
  confiancaStats: ConfiancaStats;
  candidato: CandidatoRecalibracao | null;
};

// ── Barra horizontal simples ──────────────────────────────────────────────────
function Bar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="flex-1 bg-slate-800 rounded-full h-2 overflow-hidden">
      <div
        className={`h-full rounded-full ${color}`}
        style={{ width: `${Math.max(pct, pct > 0 ? 2 : 0)}%` }}
      />
    </div>
  );
}

// ── Card wrapper ──────────────────────────────────────────────────────────────
function Card({ title, accent, children }: { title: string; accent: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
      <div className={`h-0.5 ${accent}`} />
      <div className="p-5">
        <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">{title}</h2>
        {children}
      </div>
    </div>
  );
}

export default function QualidadeClient({ gtStats, confiancaStats, candidato }: Props) {
  const [disparando, setDisparando] = useState(false);
  const [dispatchMsg, setDispatchMsg] = useState<string | null>(null);

  const precisao = gtStats.total > 0 ? Math.round((gtStats.n_vp / gtStats.total) * 100) : 0;
  const vpPct = gtStats.total > 0 ? (gtStats.n_vp / gtStats.total) * 100 : 0;
  const fpPct = gtStats.total > 0 ? (gtStats.n_fp / gtStats.total) * 100 : 0;

  const modos = ["minimo", "padrao", "agressivo"];
  const modoMax = Math.max(...modos.map((m) => gtStats.por_modo[m] ?? 0), 1);

  const totalConfianca = Object.values(confiancaStats).reduce((a, b) => a + b, 0);
  const confMax = Math.max(...Object.values(confiancaStats), 1);

  async function handleDisparar() {
    if (!window.confirm("Disparar recalibração?\n\nO worker calculará novos thresholds candidatos a partir do ground truth atual. O preset de produção NÃO será alterado automaticamente.")) return;
    setDisparando(true);
    setDispatchMsg(null);
    const res = await dispararRecalibracao();
    setDisparando(false);
    setDispatchMsg(res.ok ? "Job criado — worker processará em breve." : `Erro: ${res.error}`);
  }

  return (
    <main className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Dashboard de Qualidade</h1>
        <p className="text-slate-400 text-sm mt-1">
          Loop de aprendizado —{" "}
          {new Date().toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" })}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* ── CARD 1: Ground Truth ─────────────────────────────────────────── */}
        <Card title="Ground Truth" accent="bg-emerald-500">
          <p className="text-3xl font-bold text-slate-100 tabular-nums mb-1">
            {gtStats.total}
          </p>
          <p className="text-xs text-slate-500 mb-4">amostras validadas</p>

          {gtStats.total > 0 ? (
            <>
              {/* Barra VP/FP composta */}
              <div className="flex h-3 rounded-full overflow-hidden mb-2">
                <div
                  className="bg-emerald-500 transition-all"
                  style={{ width: `${vpPct}%` }}
                />
                <div
                  className="bg-red-500 transition-all"
                  style={{ width: `${fpPct}%` }}
                />
              </div>
              <div className="flex justify-between text-xs text-slate-400">
                <span>
                  <span className="inline-block w-2 h-2 rounded-full bg-emerald-500 mr-1" />
                  {gtStats.n_vp} VP
                </span>
                <span className="font-semibold text-slate-200">{precisao}% precisão</span>
                <span>
                  {gtStats.n_fp} FP{" "}
                  <span className="inline-block w-2 h-2 rounded-full bg-red-500 ml-1" />
                </span>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">Nenhuma amostra ainda. Conclua revisões técnicas para alimentar o ground truth.</p>
          )}
        </Card>

        {/* ── CARD 2: Distribuição por Modo ───────────────────────────────── */}
        <Card title="Distribuição por Modo" accent="bg-violet-500">
          <div className="space-y-3">
            {modos.map((modo) => {
              const count = gtStats.por_modo[modo] ?? 0;
              const pct = (count / modoMax) * 100;
              const labelColor: Record<string, string> = {
                minimo:    "text-red-400",
                padrao:    "text-emerald-400",
                agressivo: "text-amber-400",
              };
              return (
                <div key={modo} className="flex items-center gap-3">
                  <span className={`text-xs w-18 shrink-0 ${labelColor[modo] ?? "text-slate-400"}`}>
                    {modo}
                  </span>
                  <Bar pct={pct} color="bg-violet-500/70" />
                  <span className="text-xs text-slate-500 w-6 text-right tabular-nums">{count}</span>
                </div>
              );
            })}
          </div>
        </Card>

        {/* ── CARD 3: Confiança das Revisões ──────────────────────────────── */}
        <Card title="Confiança das Revisões" accent="bg-cyan-500">
          {totalConfianca === 0 ? (
            <p className="text-sm text-slate-500">Nenhuma revisão registrada ainda.</p>
          ) : (
            <div className="space-y-3">
              {(
                [
                  { key: "alta",  label: "Alta",  color: "bg-emerald-500/70" },
                  { key: "media", label: "Média", color: "bg-amber-500/70" },
                  { key: "baixa", label: "Baixa", color: "bg-red-500/70" },
                ] as const
              ).map(({ key, label, color }) => {
                const count = confiancaStats[key] ?? 0;
                const pct = (count / confMax) * 100;
                const pctTotal = totalConfianca > 0 ? Math.round((count / totalConfianca) * 100) : 0;
                return (
                  <div key={key} className="flex items-center gap-3">
                    <span className="text-xs text-slate-400 w-10 shrink-0">{label}</span>
                    <Bar pct={pct} color={color} />
                    <span className="text-xs text-slate-500 w-14 text-right tabular-nums">
                      {count} ({pctTotal}%)
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* ── CARD 4: Candidato de Recalibração ───────────────────────────── */}
        <Card title="Último Candidato de Recalibração" accent="bg-amber-500">
          {candidato ? (
            <>
              <div className="flex items-baseline gap-3 mb-4">
                <span className="text-3xl font-bold text-slate-100 tabular-nums">
                  {(candidato.f1_score * 100).toFixed(1)}%
                </span>
                <span className="text-xs text-slate-500">F1 score</span>
                <span className="ml-auto text-xs text-slate-600">
                  {new Date(candidato.gerado_em).toLocaleDateString("pt-BR")}
                </span>
              </div>

              <table className="w-full text-xs mb-4">
                <thead>
                  <tr className="text-slate-500 border-b border-slate-800">
                    <th className="text-left pb-1.5 font-medium">Parâmetro</th>
                    <th className="text-right pb-1.5 font-medium">Atual</th>
                    <th className="text-right pb-1.5 font-medium">Sugerido</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {(
                    [
                      { key: "det_min_score_csv",  label: "Score mín. CSV" },
                      { key: "det_amp_threshold",  label: "Amp. threshold" },
                      { key: "det_depth_min_m",    label: "Depth mín. (m)" },
                    ] as const
                  ).map(({ key, label }) => {
                    const atual    = candidato.thresholds_atuais[key];
                    const sugerido = candidato.thresholds_sugeridos[key];
                    const changed  = String(atual) !== String(sugerido);
                    return (
                      <tr key={key}>
                        <td className="py-1.5 text-slate-400">{label}</td>
                        <td className="py-1.5 text-right text-slate-500 tabular-nums">{atual}</td>
                        <td className={`py-1.5 text-right tabular-nums font-medium ${changed ? "text-amber-400" : "text-slate-400"}`}>
                          {sugerido}
                          {changed && <span className="ml-1 text-amber-500">↑</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>

              <p className="text-xs text-slate-500 mb-4 leading-relaxed">{candidato.notas}</p>
            </>
          ) : (
            <p className="text-sm text-slate-500 mb-4">Nenhum candidato gerado ainda.</p>
          )}

          <div className="space-y-2">
            <button
              onClick={handleDisparar}
              disabled={disparando}
              className="w-full rounded-md bg-amber-500/10 border border-amber-500/30 px-3 py-2 text-xs font-medium text-amber-400 hover:bg-amber-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {disparando ? "Criando job…" : "Disparar Recalibração"}
            </button>
            {dispatchMsg && (
              <p className={`text-xs text-center ${dispatchMsg.startsWith("Erro") ? "text-red-400" : "text-emerald-400"}`}>
                {dispatchMsg}
              </p>
            )}
          </div>
        </Card>
      </div>
    </main>
  );
}
