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
  alta: "bg-emerald-500/15 text-emerald-400 border border-emerald-500/30",
  media: "bg-amber-500/15 text-amber-400 border border-amber-500/30",
  baixa: "bg-red-500/15 text-red-400 border border-red-500/30",
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
        <div className="w-4 h-4 rounded-full bg-indigo-400 animate-pulse mx-auto" />
        <p className="text-sm text-slate-400">
          Gerando arquivos cartográficos… A página atualiza automaticamente.
        </p>
      </div>
    );
  }

  // No output yet
  if (!output) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-12 text-center">
        <p className="text-sm text-slate-500">Nenhum resultado disponível ainda.</p>
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
        <div className="rounded-xl bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-400 flex justify-between">
          {error}
          <button onClick={() => setError(null)} className="ml-3 text-red-500 hover:text-red-300">✕</button>
        </div>
      )}

      {/* Detection result card */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold text-slate-400">Modo cartográfico detectado</h2>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{MODE_LABEL[mode] ?? mode}</p>
          </div>
          <div className="flex gap-2 shrink-0">
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CONFIDENCE_STYLE[confidence] ?? "bg-slate-700 text-slate-400"}`}>
              Confiança: {confidence}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-700 text-slate-400">
              Fonte: {SOURCE_LABEL[source] ?? source}
            </span>
          </div>
        </div>

        {output.cartography_notes && (
          <div className="rounded-lg bg-slate-800/50 border border-slate-700 p-3 text-xs text-slate-400 leading-relaxed">
            {output.cartography_notes}
          </div>
        )}
      </div>

      {/* Files */}
      <div className="rounded-xl border border-slate-800 bg-slate-900 p-5 space-y-3">
        <h2 className="text-sm font-semibold text-slate-300">Arquivos gerados</h2>
        {files.length === 0 && (
          <p className="text-sm text-slate-500">Nenhum arquivo gerado.</p>
        )}
        <div className="divide-y divide-slate-800">
          {files.map((f) => {
            const url = downloadUrl(f.path);
            return (
              <div key={f.label} className="flex items-center justify-between py-2.5">
                <span className="text-sm text-slate-300">{f.label}</span>
                {url ? (
                  <a
                    href={url}
                    download
                    className="text-xs font-medium text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors"
                  >
                    ↓ Baixar {f.ext}
                  </a>
                ) : (
                  <span className="text-xs text-slate-600">indisponível</span>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Pending note */}
      {(mode === "profile_local" || mode === "cad_local") && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-400">
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
                className="rounded-md bg-slate-800 border border-slate-700 px-4 py-2 text-sm text-slate-200 hover:bg-slate-700 transition-colors"
              >
                Regenerar
              </button>
            </form>
            <button
              onClick={handleConfirm}
              disabled={confirming}
              className="rounded-md bg-cyan-500 px-5 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50 transition-colors"
            >
              {confirming ? "Confirmando…" : "Confirmar e prosseguir"}
            </button>
          </>
        )}
        {isAlreadyConfirmed && (
          <span className="text-sm text-emerald-400 font-medium">✓ Cartografia confirmada</span>
        )}
      </div>
    </div>
  );
}
