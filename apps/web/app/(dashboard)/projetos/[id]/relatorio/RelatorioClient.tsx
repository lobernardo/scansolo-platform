"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { approveRelatorio } from "./actions";

type ReportOutput = {
  id: string;
  version: number;
  status: string;
  docx_storage_url: string | null;
  docx_dropbox_path: string | null;
  pdf_storage_url: string | null;
  created_at: string;
  dados_usados_json: Record<string, unknown> | null;
};

export function RelatorioClient({
  project,
  report,
  isJobRunning,
}: {
  project: { id: string; nome: string; codigo_projeto?: string | null };
  report: ReportOutput | null;
  isJobRunning: boolean;
}) {
  const router = useRouter();
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleApprove() {
    if (!report) return;
    setApproving(true);
    const result = await approveRelatorio(project.id, report.id);
    setApproving(false);
    if (result.ok) {
      router.push(`/projetos/${project.id}`);
    } else {
      setError(result.error ?? "Erro ao aprovar");
    }
  }

  if (isJobRunning) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center space-y-4">
        <div className="w-4 h-4 rounded-full bg-purple-400 animate-pulse mx-auto" />
        <p className="text-sm text-slate-400">
          Gerando relatório… A página atualiza automaticamente.
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-sm text-slate-500">Nenhum relatório gerado ainda.</p>
      </div>
    );
  }

  const isApproved = report.status === "aprovado";
  const dados = report.dados_usados_json ?? {};
  const nTargets = typeof dados.n_targets === "number" ? dados.n_targets : "—";
  const nProfiles = typeof dados.n_profiles === "number" ? dados.n_profiles : "—";

  return (
    <div className="max-w-2xl mx-auto px-4 py-8 space-y-6">
      {error && (
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-400 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-500 hover:text-red-300">✕</button>
        </div>
      )}

      {/* Report card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold text-slate-400">Relatório gerado</h2>
            <p className="text-base font-medium text-slate-100 mt-0.5">
              {project.codigo_projeto ?? project.nome} — v{String(report.version).padStart(2, "0")}
            </p>
          </div>
          <span
            className={`text-xs px-2 py-0.5 rounded-full font-medium ${
              isApproved
                ? "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30"
                : "bg-amber-500/15 text-amber-400 border border-amber-500/30"
            }`}
          >
            {isApproved ? "Aprovado" : "Aguardando aprovação"}
          </span>
        </div>

        <div className="text-xs text-slate-500 grid grid-cols-2 gap-2">
          <span>Alvos no relatório: <strong className="text-slate-300">{nTargets}</strong></span>
          <span>Perfis GPR: <strong className="text-slate-300">{nProfiles}</strong></span>
          <span>
            Gerado em:{" "}
            <strong className="text-slate-300">
              {new Date(report.created_at).toLocaleString("pt-BR")}
            </strong>
          </span>
        </div>

        {/* Download */}
        <div className="border-t border-slate-800 pt-4">
          <p className="text-sm font-medium text-slate-400 mb-3">Arquivos</p>
          <div className="flex flex-col gap-2">
            {report.pdf_storage_url && (
              <a
                href={report.pdf_storage_url}
                download
                className="inline-flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                ↓ Baixar PDF
              </a>
            )}
            {report.docx_storage_url ? (
              <a
                href={report.docx_storage_url}
                download
                className="inline-flex items-center gap-2 text-sm text-cyan-400 hover:text-cyan-300 font-medium transition-colors"
              >
                ↓ Baixar DOCX (Microsoft Word)
              </a>
            ) : (
              <span className="text-sm text-slate-600">DOCX indisponível</span>
            )}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-end pt-2">
        {!isApproved && (
          <>
            <form action={`/projetos/${project.id}/relatorio?regenerar=1`}>
              <button
                type="submit"
                className="rounded-md bg-slate-800 border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
              >
                Regenerar
              </button>
            </form>
            <button
              onClick={handleApprove}
              disabled={approving}
              className="rounded-md bg-cyan-500 px-5 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50 transition-colors"
            >
              {approving ? "Aprovando…" : "Finalizar e aprovar"}
            </button>
          </>
        )}
        {isApproved && (
          <span className="text-sm text-emerald-400 font-medium">✓ Projeto finalizado</span>
        )}
      </div>
    </div>
  );
}
