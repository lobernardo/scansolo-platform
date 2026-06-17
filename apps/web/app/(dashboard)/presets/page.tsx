import { createClient } from "@/lib/supabase/server";
import { getPresets } from "@/app/actions/preset-actions";
import { PresetsClient } from "./PresetsClient";

export const dynamic = "force-dynamic";

export default async function PresetsPage() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();

  let isAdmin = false;
  if (user) {
    const { data } = await supabase
      .from("profiles")
      .select("role")
      .eq("id", user.id)
      .single();
    const role = (data as { role?: string } | null)?.role ?? "";
    isAdmin = role === "admin" || role === "socio";
  }

  const presets = await getPresets();

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <PresetsClient presets={presets} isAdmin={isAdmin} />
    </div>
  );
}
