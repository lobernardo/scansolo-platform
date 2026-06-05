export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";
import type { Database } from "@/lib/types/database";

type ProfileRow = Database["public"]["Tables"]["profiles"]["Row"];

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
          Bem-vindo, {profile?.name ?? user.email} — perfil:{" "}
          <span className="font-medium text-slate-300">{role}</span>
        </p>
      </div>

      {role === "operador_campo" ? (
        <OperadorView />
      ) : (
        <SocioTecnicoView />
      )}
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

function SocioTecnicoView() {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="font-semibold text-lg text-slate-100 mb-2">Projetos</h2>
        <p className="text-slate-400 text-sm mb-4">
          Visão geral de todos os projetos em andamento.
        </p>
        <Link
          href="/projetos"
          className="inline-block rounded-md bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
        >
          Ver projetos
        </Link>
      </div>

      <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
        <h2 className="font-semibold text-lg text-slate-100 mb-2">Nova Entrada</h2>
        <p className="text-slate-400 text-sm mb-4">
          Cadastrar novo projeto.
        </p>
        <Link
          href="/nova-entrada"
          className="inline-block rounded-md bg-slate-800 border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:bg-slate-700 transition-colors"
        >
          Nova entrada
        </Link>
      </div>
    </div>
  );
}
