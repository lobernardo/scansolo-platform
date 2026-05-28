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

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b border-gray-200 bg-white">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-6">
            <span className="font-bold text-gray-900">ScanSOLO</span>
            <Link
              href="/dashboard"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Dashboard
            </Link>
            <Link
              href="/projetos"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Projetos
            </Link>
            <Link
              href="/nova-entrada"
              className="text-sm text-gray-600 hover:text-gray-900"
            >
              Nova entrada
            </Link>
          </div>
          <span className="text-xs text-gray-400">{user.email}</span>
        </div>
      </nav>
      <main>{children}</main>
    </div>
  );
}
