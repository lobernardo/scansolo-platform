export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";

type ProfileRow = Database["public"]["Tables"]["profiles"]["Row"];

type ProjectSummary = {
  id: string;
  status: string;
  created_at: string;
  updated_at: string;
  nome: string;
  cliente: string;
};

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { data } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .single();

  const profile = data as ProfileRow | null;
  const role = profile?.role ?? "operador_campo";

  return (
    <main className="max-w-6xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">
          Bem-vindo, {profile?.name ?? user.email} —{" "}
          <span className="font-medium text-slate-300">{role}</span>
        </p>
      </div>

      {role === "operador_campo" ? <OperadorView /> : <SocioTecnicoView />}
    </main>
  );
}

function OperadorView() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="font-semibold text-lg text-slate-100 mb-2">Nova Entrada</h2>
        <p className="text-slate-400 text-sm mb-4">
          Cadastre um novo projeto e faça upload dos arquivos de campo.
        </p>
        <Link
          href="/nova-entrada"
          className="inline-block rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
        >
          Iniciar nova entrada
        </Link>
      </div>
    </div>
  );
}

async function SocioTecnicoView() {
  const supabase = await createClient();

  const { data: raw } = await supabase
    .from("projects")
    .select("id, status, created_at, updated_at, nome, cliente")
    .order("updated_at", { ascending: false });

  const projects = (raw ?? []) as ProjectSummary[];
  const total = projects.length;

  const EM_PROCESSAMENTO = new Set([
    "aguardando_processamento",
    "processando_gpr",
    "gpr_concluido",
    "processando_ia",
    "ia_concluida",
    "revisao_em_andamento",
  ]);
  const RELATORIO_PENDENTE = new Set([
    "aguardando_cartografia",
    "cartografia_concluida",
    "cartografia_pendente_dados",
    "aguardando_relatorio",
    "relatorio_em_andamento",
    "relatorio_gerado",
    "aguardando_aprovacao",
  ]);

  const kpis = {
    total,
    emProcessamento: projects.filter((p) => EM_PROCESSAMENTO.has(p.status)).length,
    relatorioPendente: projects.filter((p) => RELATORIO_PENDENTE.has(p.status)).length,
    aguardandoArquivos: projects.filter((p) => p.status === "aguardando_arquivos").length,
  };

  const groupCounts = {
    aguardando: projects.filter((p) => p.status === "aguardando_arquivos").length,
    processando: projects.filter((p) =>
      ["aguardando_processamento", "processando_gpr", "gpr_concluido", "processando_ia", "ia_concluida"].includes(
        p.status
      )
    ).length,
    revisao: projects.filter((p) =>
      ["revisao_em_andamento", "revisao_concluida"].includes(p.status)
    ).length,
    relatorio: projects.filter((p) =>
      [
        "aguardando_cartografia",
        "cartografia_concluida",
        "cartografia_pendente_dados",
        "aguardando_relatorio",
        "relatorio_em_andamento",
        "relatorio_gerado",
        "aguardando_aprovacao",
      ].includes(p.status)
    ).length,
    finalizado: projects.filter((p) => p.status === "finalizado").length,
  };

  const recent = projects.slice(0, 6);

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <KpiCard
          label="Total de projetos"
          value={kpis.total}
          sub="todos os status"
          accentClass="bg-cyan-500"
        />
        <KpiCard
          label="Em processamento"
          value={kpis.emProcessamento}
          sub="GPR · IA · Revisão"
          accentClass="bg-violet-500"
        />
        <KpiCard
          label="Relatórios pendentes"
          value={kpis.relatorioPendente}
          sub="aguardando ou em andamento"
          accentClass="bg-amber-500"
        />
        <KpiCard
          label="Aguardando arquivos"
          value={kpis.aguardandoArquivos}
          sub="campo não entregou ainda"
          accentClass="bg-red-500"
        />
      </div>

      {/* Pipeline distribution */}
      {total > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 p-5">
          <h2 className="text-xs font-semibold text-slate-400 mb-4 uppercase tracking-wider">
            Distribuição do pipeline
          </h2>
          <div className="space-y-2.5">
            {[
              { label: "Aguardando arquivos", count: groupCounts.aguardando, color: "bg-red-500/70" },
              { label: "GPR / IA em processamento", count: groupCounts.processando, color: "bg-violet-500/70" },
              { label: "Revisão técnica", count: groupCounts.revisao, color: "bg-orange-500/70" },
              { label: "Relatório / Cartografia", count: groupCounts.relatorio, color: "bg-amber-500/70" },
              { label: "Finalizado", count: groupCounts.finalizado, color: "bg-emerald-500/70" },
            ].map((g) => (
              <div key={g.label} className="flex items-center gap-3">
                <span className="text-xs text-slate-400 w-48 shrink-0">{g.label}</span>
                <div className="flex-1 bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${g.color}`}
                    style={{
                      width: `${
                        total > 0
                          ? Math.max((g.count / total) * 100, g.count > 0 ? 2 : 0)
                          : 0
                      }%`,
                    }}
                  />
                </div>
                <span className="text-xs text-slate-500 w-5 text-right tabular-nums">{g.count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent activity */}
      {recent.length > 0 && (
        <div className="rounded-xl border border-slate-800 bg-slate-900 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <h2 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Atividade recente
            </h2>
            <Link
              href="/projetos"
              className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors"
            >
              Ver todos →
            </Link>
          </div>
          <div className="divide-y divide-slate-800/60">
            {recent.map((p) => (
              <Link
                key={p.id}
                href={`/projetos/${p.id}`}
                className="flex items-center gap-3 px-5 py-3 hover:bg-slate-800/50 transition-colors"
              >
                <StatusDot status={p.status} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-slate-200 truncate">{p.nome}</p>
                  <p className="text-xs text-slate-500 truncate">
                    {p.cliente} · {statusLabel(p.status)}
                  </p>
                </div>
                <span className="text-xs text-slate-600 shrink-0 tabular-nums">
                  {relativeTime(p.updated_at)}
                </span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {total === 0 && (
        <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/50 p-10 text-center">
          <p className="text-slate-500 text-sm mb-4">Nenhum projeto cadastrado.</p>
          <Link
            href="/nova-entrada"
            className="inline-block rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
          >
            Criar primeiro projeto
          </Link>
        </div>
      )}
    </div>
  );
}

function KpiCard({
  label,
  value,
  sub,
  accentClass,
}: {
  label: string;
  value: number;
  sub: string;
  accentClass: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4 relative overflow-hidden">
      <div className={`absolute top-0 left-0 right-0 h-0.5 ${accentClass}`} />
      <p className="text-xs text-slate-500 mb-1.5">{label}</p>
      <p className="text-3xl font-bold text-slate-100 tabular-nums">{value}</p>
      <p className="text-xs text-slate-600 mt-1">{sub}</p>
    </div>
  );
}

const STATUS_DOT: Record<string, string> = {
  aguardando_arquivos: "bg-amber-500",
  aguardando_processamento: "bg-blue-500",
  processando_gpr: "bg-blue-500",
  gpr_concluido: "bg-cyan-500",
  processando_ia: "bg-violet-500",
  ia_concluida: "bg-violet-400",
  revisao_em_andamento: "bg-orange-500",
  revisao_concluida: "bg-orange-400",
  aguardando_cartografia: "bg-indigo-500",
  cartografia_concluida: "bg-indigo-400",
  aguardando_relatorio: "bg-purple-500",
  relatorio_em_andamento: "bg-purple-500",
  relatorio_gerado: "bg-purple-400",
  finalizado: "bg-emerald-500",
  erro: "bg-red-500",
};

function StatusDot({ status }: { status: string }) {
  const color = STATUS_DOT[status] ?? "bg-slate-600";
  return <span className={`inline-block w-2 h-2 rounded-full shrink-0 ${color}`} />;
}

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    aguardando_arquivos: "Aguardando arquivos",
    aguardando_processamento: "Aguardando processamento",
    processando_gpr: "Processando GPR",
    gpr_concluido: "GPR concluído",
    processando_ia: "Processando IA",
    ia_concluida: "IA concluída",
    revisao_em_andamento: "Em revisão",
    revisao_concluida: "Revisão concluída",
    aguardando_cartografia: "Cartografia",
    cartografia_concluida: "Cartografia concluída",
    aguardando_relatorio: "Gerando relatório",
    relatorio_em_andamento: "Relatório em andamento",
    relatorio_gerado: "Relatório gerado",
    finalizado: "Finalizado",
    erro: "Erro",
  };
  return labels[status] ?? status;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "agora";
  if (m < 60) return `${m}min`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d}d`;
  return `${Math.floor(d / 30)}m`;
}
