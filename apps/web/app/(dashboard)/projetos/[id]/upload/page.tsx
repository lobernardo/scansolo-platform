export const dynamic = "force-dynamic";

import { createClient } from "@/lib/supabase/server";
import { UploadClient } from "./UploadClient";

export default async function UploadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const supabase = await createClient();
  const { data: projectRaw } = await supabase
    .from("projects")
    .select("preset_id")
    .eq("id", id)
    .single();
  const project = projectRaw as { preset_id: string | null } | null;

  return <UploadClient projectId={id} presetId={project?.preset_id ?? null} />;
}
