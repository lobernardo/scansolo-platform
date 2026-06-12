"use client";

import { useEffect } from "react";

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[Dashboard Error]", error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-4">
      <div className="max-w-md w-full rounded-xl border border-red-500/30 bg-red-500/10 p-6 space-y-4">
        <h2 className="text-lg font-semibold text-red-400">Erro inesperado</h2>
        <p className="text-sm text-slate-400 font-mono break-all">{error.message}</p>
        {error.digest && (
          <p className="text-xs text-slate-600">ID: {error.digest}</p>
        )}
        <button
          onClick={reset}
          className="w-full rounded-lg bg-slate-800 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    </div>
  );
}
