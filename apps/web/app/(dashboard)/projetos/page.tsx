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
  criado: "bg-gray-100 text-gray-600",
  aguardando_arquivos: "bg-yellow-50 text-yellow-700",
  aguardando_processamento: "bg-blue-50 text-blue-700",
  processando_gpr: "bg-blue-100 text-blue-800",
  gpr_concluido: "bg-green-50 text-green-700",
  processando_ia: "bg-purple-50 text-purple-700",
  ia_concluida: "bg-green-100 text-green-800",
  revisao_em_andamento: "bg-orange-100 text-orange-700",
  revisao_concluida: "bg-teal-100 text-teal-700",
  aguardando_cartografia: "bg-indigo-100 text-indigo-700",
  cartografia_concluida: "bg-indigo-200 text-indigo-800",
  cartografia_pendente_dados: "bg-yellow-100 text-yellow-700",
  aguardando_relatorio: "bg-violet-100 text-violet-700",
  relatorio_em_andamento: "bg-violet-100 text-violet-700",
  relatorio_gerado: "bg-violet-200 text-violet-800",
  aguardando_aprovacao: "bg-violet-200 text-violet-800",
  finalizado: "bg-green-300 text-green-900",
  erro: "bg-red-50 text-red-700",
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
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Projetos</h1>
        <Link
          href="/nova-entrada"
          className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors"
        >
          Nova entrada
        </Link>
      </div>

      {projects.length === 0 ? (
        <p className="text-sm text-gray-500">Nenhum projeto ainda.</p>
      ) : (
        <div className="space-y-2">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/projetos/${p.id}`}
              className="block rounded-lg border border-gray-200 bg-white p-4 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-gray-900">{p.nome}</p>
                  <p className="text-sm text-gray-500">
                    {p.cliente} — {p.local ?? p.estado}
                  </p>
                </div>
                <span
                  className={`text-xs font-medium px-2 py-1 rounded-full ${
                    STATUS_COLOR[p.status] ?? "bg-gray-100 text-gray-600"
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
