"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { confirmCartografia } from "./actions";

type CartographyOutput = {
  id: string;
  cartography_mode: string | null;
  cartography_confidence: string | null;
  cartography_source: string | null;
  cartography_notes: string | null;
  csv_path: string | null;
  geojson_path: string | null;
  dxf_dropbox_path: string | null;
  kml_dropbox_path: string | null;
  status: string;
};

const MODE_LABEL: Record<string, string> = {
  georeferenced: "Georreferenciado",
  profile_local: "Perfil Local (seção transversal)",
  cad_local: "CAD Local / Desconhecido",
  mixed: "Misto",
  unknown: "Desconhecido",
};

const CONFIDENCE_STYLE: Record<string, string> = {
  alta: "bg-green-100 text-green-700",
  media: "bg-yellow-100 text-yellow-700",
  baixa: "bg-red-50 text-red-600",
};

const SOURCE_LABEL: Record<string, string> = {
  kml: "KML/KMZ",
  kmz: "KMZ",
  dzg: "DZG (GPS)",
  dxf: "DXF/DWG",
  dwg: "DWG",
  manual: "Manual",
  inferred: "Inferido (somente DZT)",
};

export function CartografiaClient({
  project,
  output,
  downloadBaseUrl,
  isJobRunning,
}: {
  project: { id: string; nome: string };
  output: CartographyOutput | null;
  downloadBaseUrl: string;
  isJobRunning: boolean;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleConfirm() {
    if (!output) return;
    setConfirming(true);
    const result = await confirmCartografia(project.id, output.id);
    setConfirming(false);
    if (result.ok) {
      router.push(`/projetos/${project.id}`);
    } else {
      setError(result.error ?? "Erro ao confirmar");
    }
  }

  function downloadUrl(path: string | null) {
    if (!path) return null;
    return `${downloadBaseUrl}/gpr-tabelas/${path}`;
  }

  // Job running state
  if (isJobRunning) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center space-y-4">
        <div className="w-4 h-4 rounded-full bg-blue-400 animate-pulse mx-auto" />
        <p className="text-sm text-gray-600">
          Gerando arquivos cartográficos… A página atualiza automaticamente.
        </p>
      </div>
    );
  }

  // No output yet
  if (!output) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center">
        <p className="text-sm text-gray-500">Nenhum resultado disponível ainda.</p>
      </div>
    );
  }

  const mode = output.cartography_mode ?? "unknown";
  const confidence = output.cartography_confidence ?? "baixa";
  const source = output.cartography_source ?? "inferred";
  const isAlreadyConfirmed = output.status === "concluido";

  const files: { label: string; path: string | null; ext: string }[] = [
    { label: "CSV (tabela de alvos)", path: output.csv_path, ext: "CSV" },
    { label: "GeoJSON", path: output.geojson_path, ext: "GeoJSON" },
    { label: "DXF (seção transversal)", path: output.dxf_dropbox_path, ext: "DXF" },
    { label: "KML (Google Earth)", path: output.kml_dropbox_path, ext: "KML" },
  ].filter((f) => f.path);

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-6">
      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-3 text-sm text-red-700 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-400 hover:text-red-600">✕</button>
        </div>
      )}

      {/* Detection result card */}
      <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-900">Modo cartográfico detectado</h2>
            <p className="text-lg font-bold mt-0.5">{MODE_LABEL[mode] ?? mode}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <span className={`text-xs px-2 py-1 rounded font-medium ${CONFIDENCE_STYLE[confidence] ?? "bg-gray-100 text-gray-600"}`}>
              Confiança: {confidence}
            </span>
            <span className="text-xs px-2 py-1 rounded bg-gray-100 text-gray-600">
              Fonte: {SOURCE_LABEL[source] ?? source}
            </span>
          </div>
        </div>

        {output.cartography_notes && (
          <div className="rounded bg-gray-50 border border-gray-200 p-3 text-xs text-gray-700 leading-relaxed">
            {output.cartography_notes}
          </div>
        )}
      </div>

      {/* Files */}
      <div className="rounded-lg border border-gray-200 bg-white p-5 space-y-3">
        <h2 className="text-sm font-semibold text-gray-900">Arquivos gerados</h2>
        {files.length === 0 && (
          <p className="text-sm text-gray-400">Nenhum arquivo gerado.</p>
        )}
        <div className="divide-y divide-gray-100">
          {files.map((f) => {
            const url = downloadUrl(f.path);
            return (
              <div key={f.label} className="flex items-center justify-between py-2.5">
                <span className="text-sm text-gray-700">{f.label}</span>
                {url ? (
                  <a
                    href={url}
                    download
                    className="text-xs font-medium text-blue-600 hover:text-blue-800 flex items-center gap-1"
                  >
                    ↓ Baixar {f.ext}
                  </a>
                ) : (
                  <span className="text-xs text-gray-400">indisponível</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Pending note */}
      {(mode === "profile_local" || mode === "cad_local") && (
        <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
          <span className="font-medium">Pendente:</span> Validar com Amilson exemplos reais de
          DXF/KML para reproduzir o padrão final da ScanSOLO. Quando os arquivos de referência
          estiverem disponíveis, faça upload e use &ldquo;Regenerar&rdquo;.
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-3 justify-end pt-2">
        {!isAlreadyConfirmed && (
          <>
            <form action={`/projetos/${project.id}/cartografia?regenerar=1`}>
              <button
                type="submit"
                className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Regenerar
              </button>
            </form>
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="rounded-md bg-gray-900 px-5 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50 transition-colors"
            >
              {confirming ? "Confirmando…" : "Confirmar e prosseguir"}
            </button>
          </>
        )}
        {isAlreadyConfirmed && (
          <span className="text-sm text-teal-700 font-medium">✓ Cartografia confirmada</span>
        )}
      </div>
    </div>
  );
}
