import { createClient } from "@/lib/supabase/server";
import { redirect } from "next/navigation";
import Link from "next/link";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const { data: profileRaw } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .single();
  const role = (profileRaw as { role?: string } | null)?.role ?? "operador_campo";
  const isAdmin = role === "socio" || role === "admin";

  return (
    <div className="min-h-screen bg-slate-950">
      <nav className="sticky top-0 z-50 border-b border-slate-800 bg-slate-900/95 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/dashboard" className="font-bold tracking-tight text-base">
              <span className="text-cyan-400">SCAN</span>
              <span className="text-slate-100">SOLO</span>
            </Link>
            <div className="flex items-center gap-1">
              <Link
                href="/dashboard"
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-md transition-colors"
              >
                Dashboard
              </Link>
              <Link
                href="/projetos"
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-md transition-colors"
              >
                Projetos
              </Link>
              <Link
                href="/nova-entrada"
                className="px-3 py-1.5 text-sm bg-cyan-500/10 text-cyan-400 hover:bg-cyan-500/20 rounded-md transition-colors font-medium"
              >
                + Nova entrada
              </Link>
              <Link
                href="/presets"
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-md transition-colors"
              >
                Presets
              </Link>
              <Link
                href="/treinamento"
                className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-md transition-colors"
              >
                Treinamento
              </Link>
              {isAdmin && (
                <Link
                  href="/admin/qualidade"
                  className="px-3 py-1.5 text-sm text-slate-400 hover:text-slate-100 hover:bg-slate-800 rounded-md transition-colors"
                >
                  Qualidade
                </Link>
              )}
            </div>
          </div>
          <span className="text-xs text-slate-500 font-mono">{user.email}</span>
        </div>
      </nav>
      <main className="bg-slate-950 min-h-[calc(100vh-3.5rem)]">{children}</main>
    </div>
  );
}
