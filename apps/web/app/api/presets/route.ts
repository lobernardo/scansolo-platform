import { createClient } from "@/lib/supabase/server";
import { NextResponse } from "next/server";

export async function GET() {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json([], { status: 401 });

  const { data } = await supabase
    .from("gpr_presets")
    .select("id, name, description, is_system, parameters")
    .eq("is_active", true)
    .order("is_system", { ascending: false })
    .order("name");

  return NextResponse.json(data ?? []);
}
