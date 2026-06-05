export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";

type ProjectRow = Database["public"]["Tables"]["projects"]["Row"];

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

export default async function ProjetosPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data } = await supabase
    .from("projects")
    .select("*")
    .order("created_at", { ascending: false });

  const projects = (data ?? []) as ProjectRow[];

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-slate-100">Projetos</h1>
        <Link
          href="/nova-entrada"
          className="rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
        >
          Nova entrada
        </Link>
      </div>

      {projects.length === 0 ? (
        <p className="text-sm text-slate-500">Nenhum projeto ainda.</p>
      ) : (
        <div className="space-y-2">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projetos/${p.id}`}
              className="block rounded-xl border border-slate-800 bg-slate-900 p-4 hover:bg-slate-800/60 hover:border-slate-700 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-slate-100">{p.nome}</p>
                  <p className="text-sm text-slate-400">
                    {p.cliente} — {p.local ?? p.estado}
                  </p>
                </div>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    STATUS_COLOR[p.status] ?? "bg-slate-700 text-slate-400 border border-slate-600"
                  }`}
                >
                  {STATUS_LABEL[p.status] ?? p.status}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
