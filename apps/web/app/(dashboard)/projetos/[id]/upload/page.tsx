export const dynamic = "force-dynamic";

import { UploadClient } from "./UploadClient";

export default async function UploadPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <UploadClient projectId={id} />;
}
