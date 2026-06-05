"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export type ProjectWithCount = {
  id: string;
  nome: string;
  cliente: string;
  estado: string;
  status: string;
  created_at: string;
  profileCount: number;
};

const STATUS_LABEL: Record<string, string> = {
  criado: "Criado",
  aguardando_arquivos: "Aguardando arquivos",
  aguardando_processamento: "Aguardando processamento",
  processando_gpr: "Processando GPR",
  gpr_concluido: "GPR concluído",
  processando_ia: "Processando IA",
  ia_concluida: "IA concluída",
  revisao_em_andamento: "Revisão em andamento",
  revisao_concluida: "Revisão concluída",
  aguardando_cartografia: "Cartografia em andamento",
  cartografia_concluida: "Cartografia concluída",
  cartografia_pendente_dados: "Cartografia — dados pendentes",
  aguardando_relatorio: "Gerando relatório",
  relatorio_em_andamento: "Relatório em andamento",
  relatorio_gerado: "Relatório gerado",
  aguardando_aprovacao: "Aguardando aprovação",
  finalizado: "Finalizado",
  erro: "Erro",
};

const STATUS_COLOR: Record<string, string> = {
  criado: "bg-slate-700 text-slate-400 border border-slate-600",
  aguardando_arquivos: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  aguardando_processamento: "bg-blue-500/15 text-blue-400 border border-blue-500/30",
  processando_gpr: "bg-blue-500/15 text-blue-400 border border-blue-500/30",
  gpr_concluido: "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30",
  processando_ia: "bg-violet-500/15 text-violet-400 border border-violet-500/30",
  ia_concluida: "bg-violet-500/15 text-violet-400 border border-violet-500/30",
  revisao_em_andamento: "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  revisao_concluida: "bg-orange-500/15 text-orange-400 border border-orange-500/30",
  aguardando_cartografia: "bg-indigo-500/15 text-indigo-400 border border-indigo-500/30",
  cartografia_concluida: "bg-indigo-500/15 text-indigo-400 border border-indigo-500/30",
  cartografia_pendente_dados: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  aguardando_relatorio: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  relatorio_em_andamento: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  relatorio_gerado: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  aguardando_aprovacao: "bg-purple-500/15 text-purple-400 border border-purple-500/30",
  finalizado: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
  erro: "bg-red-500/15 text-red-400 border border-red-500/30",
};

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

function formatDate(iso: string): string {
  const d = new Date(iso);
  return `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
}

function isStale(p: ProjectWithCount): boolean {
  return (
    p.status === "aguardando_arquivos" &&
    Date.now() - new Date(p.created_at).getTime() > SEVEN_DAYS_MS
  );
}

export function ProjetosTable({ projects }: { projects: ProjectWithCount[] }) {
  const [filter, setFilter] = useState("all");
  const router = useRouter();

  const allStatuses = Array.from(new Set(projects.map((p) => p.status))).sort();
  const filtered =
    filter === "all" ? projects : projects.filter((p) => p.status === filter);

  const countByStatus = (s: string) => projects.filter((p) => p.status === s).length;

  return (
    <div className="space-y-4">
      {/* Filter */}
      <div className="flex justify-end">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-md border border-slate-700 bg-slate-800 text-slate-200 text-sm px-3 py-1.5 focus:outline-none focus:ring-1 focus:ring-cyan-500"
        >
          <option value="all">Todos ({projects.length})</option>
          {allStatuses.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABEL[s] ?? s} ({countByStatus(s)})
            </option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-slate-800 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-800/50 border-b border-slate-700 text-left">
                <th className="px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wide">
                  Projeto
                </th>
                <th className="px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wide">
                  Cliente
                </th>
                <th className="px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wide">
                  UF
                </th>
                <th className="px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wide">
                  Status
                </th>
                <th className="px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wide text-right">
                  Arquivos
                </th>
                <th className="px-4 py-3 font-medium text-slate-400 text-xs uppercase tracking-wide text-right">
                  Data
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-sm text-slate-500">
                    Nenhum projeto com este status.
                  </td>
                </tr>
              ) : (
                filtered.map((p) => {
                  const stale = isStale(p);
                  return (
                    <tr
                      key={p.id}
                      onClick={() => router.push(`/projetos/${p.id}`)}
                      className="cursor-pointer hover:bg-slate-800/60 transition-colors"
                    >
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-100">{p.nome}</p>
                        <p className="text-xs text-slate-600 font-mono mt-0.5">
                          {p.id.slice(0, 8)}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-slate-300">{p.cliente}</td>
                      <td className="px-4 py-3">
                        <span className="text-xs bg-slate-800 text-slate-400 border border-slate-700 px-1.5 py-0.5 rounded font-medium">
                          {p.estado}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                            STATUS_COLOR[p.status] ??
                            "bg-slate-700 text-slate-400 border border-slate-600"
                          }`}
                        >
                          {STATUS_LABEL[p.status] ?? p.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <span className="text-slate-400 tabular-nums text-xs">
                          {p.profileCount > 0 ? `${p.profileCount} DZT` : "—"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {stale ? (
                          <span className="text-red-400 text-xs font-medium tabular-nums">
                            ⚠ {formatDate(p.created_at)}
                          </span>
                        ) : (
                          <span className="text-slate-500 text-xs tabular-nums">
                            {formatDate(p.created_at)}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
