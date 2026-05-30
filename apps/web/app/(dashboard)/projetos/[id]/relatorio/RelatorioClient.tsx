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
        <div className="w-4 h-4 rounded-full bg-blue-400 animate-pulse mx-auto" />
        <p className="text-sm text-gray-600">
          Gerando relatório… A página atualiza automaticamente.
        </p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-sm text-gray-500">Nenhum relatório gerado ainda.</p>
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
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {/* Report card */}
      <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Relatório gerado</h2>
            <p className="text-base font-medium mt-0.5">
              {project.codigo_projeto ?? project.nome} — v{String(report.version).padStart(2, "0")}
            </p>
          </div>
          <span
            className={`text-xs px-2 py-1 rounded font-medium ${
              isApproved
                ? "bg-green-100 text-green-700"
                : "bg-yellow-100 text-yellow-700"
            }`}
          >
            {isApproved ? "Aprovado" : "Aguardando aprovação"}
          </span>
        </div>

        <div className="text-xs text-gray-500 grid grid-cols-2 gap-2">
          <span>Alvos no relatório: <strong className="text-gray-700">{nTargets}</strong></span>
          <span>Perfis GPR: <strong className="text-gray-700">{nProfiles}</strong></span>
          <span>
            Gerado em:{" "}
            <strong className="text-gray-700">
              {new Date(report.created_at).toLocaleString("pt-BR")}
            </strong>
          </span>
        </div>

        {/* Download */}
        <div className="border-t border-gray-100 pt-4">
          <p className="text-sm font-medium text-gray-700 mb-3">Arquivos</p>
          <div className="flex flex-col gap-2">
            {report.docx_storage_url ? (
              <a
                href={report.docx_storage_url}
                download
                className="inline-flex items-center gap-2 text-sm text-blue-600 hover:text-blue-800 font-medium"
              >
                ↓ Baixar DOCX (Microsoft Word)
              </a>
            ) : (
              <span className="text-sm text-gray-400">DOCX indisponível</span>
            )}
            <span className="text-xs text-gray-400">
              PDF: conversão automática disponível em versão futura.
            </span>
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
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Regenerar
              </button>
            </form>
            <button
              onClick={handleApprove}
              disabled={approving}
              className="rounded-md bg-gray-900 px-5 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 transition-colors"
            >
              {approving ? "Aprovando…" : "Finalizar e aprovar"}
            </button>
          </>
        )}
        {isApproved && (
          <span className="text-sm text-green-700 font-medium">✓ Projeto finalizado</span>
        )}
      </div>
    </div>
  );
}
