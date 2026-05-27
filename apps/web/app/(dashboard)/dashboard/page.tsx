export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";

export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profile } = await supabase
    .from("profiles")
    .select("name, role")
    .eq("id", user.id)
    .single();

  const role = profile?.role ?? "operador_campo";

  return (
    <main className="max-w-5xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-gray-500 text-sm mt-1">
          Bem-vindo, {profile?.name ?? user.email} — perfil:{" "}
          <span className="font-medium">{role}</span>
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
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="font-semibold text-lg mb-2">Nova Entrada</h2>
        <p className="text-gray-500 text-sm mb-4">
          Cadastre um novo projeto e faça upload dos arquivos de campo.
        </p>
        <a
          href="/nova-entrada"
          className="inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors"
        >
          Iniciar nova entrada
        </a>
      </div>
    </div>
  );
}

function SocioTecnicoView() {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="font-semibold text-lg mb-2">Projetos</h2>
        <p className="text-gray-500 text-sm mb-4">
          Visão geral de todos os projetos em andamento.
        </p>
        <a
          href="/projetos"
          className="inline-block rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors"
        >
          Ver projetos
        </a>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-6">
        <h2 className="font-semibold text-lg mb-2">Nova Entrada</h2>
        <p className="text-gray-500 text-sm mb-4">
          Cadastrar novo projeto.
        </p>
        <a
          href="/nova-entrada"
          className="inline-block rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
        >
          Nova entrada
        </a>
      </div>
    </div>
  );
}
