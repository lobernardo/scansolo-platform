"use client";

import { useState, useTransition } from "react";
import { deleteProject } from "./actions";

export function DeleteProjectButton({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function handleDelete() {
    setError(null);
    startTransition(async () => {
      const result = await deleteProject(projectId);
      if (!result?.ok) setError(result?.error ?? "Erro ao deletar projeto");
    });
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-md border border-red-500/40 px-3 py-1.5 text-sm font-medium text-red-400 hover:bg-red-500/10 transition-colors"
      >
        Excluir projeto
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
            <h2 className="text-base font-semibold text-slate-100 mb-2">Excluir projeto?</h2>
            <p className="text-sm text-slate-400 mb-6">
              Esta ação é irreversível. Todos os arquivos, perfis GPR, alvos detectados e
              resultados serão permanentemente removidos.
            </p>
            {error && (
              <p className="text-xs text-red-400 mb-4 font-mono break-all">{error}</p>
            )}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setOpen(false)}
                disabled={isPending}
                className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={handleDelete}
                disabled={isPending}
                className="rounded-md bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-500 transition-colors disabled:opacity-50"
              >
                {isPending ? "Excluindo…" : "Excluir permanentemente"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
