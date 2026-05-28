"use client";

import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { uploadDztFiles } from "./actions";

export default function UploadPage() {
  const { id } = useParams<{ id: string }>();
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<"idle" | "uploading" | "error">("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!files.length) return;
    setStatus("uploading");
    setErrorMsg("");

    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));

    try {
      await uploadDztFiles(id, fd);
    } catch (err: unknown) {
      setStatus("error");
      setErrorMsg(err instanceof Error ? err.message : "Erro desconhecido");
    }
  }

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-2">Upload de arquivos .DZT</h1>
      <p className="text-sm text-gray-500 mb-6">Projeto: {id}</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 transition-colors"
          onClick={() => inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            multiple
            accept=".dzt"
            className="hidden"
            onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
          />
          {files.length === 0 ? (
            <p className="text-sm text-gray-500">
              Clique ou arraste os arquivos .DZT aqui
            </p>
          ) : (
            <ul className="text-sm text-left space-y-1">
              {files.map((f) => (
                <li key={f.name} className="text-gray-700">
                  {f.name}{" "}
                  <span className="text-gray-400">
                    ({(f.size / 1024 / 1024).toFixed(1)} MB)
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {errorMsg && (
          <p className="text-sm text-red-600 rounded-md bg-red-50 px-3 py-2">
            {errorMsg}
          </p>
        )}

        <button
          type="submit"
          disabled={!files.length || status === "uploading"}
          className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {status === "uploading" ? "Enviando…" : "Enviar e iniciar processamento"}
        </button>
      </form>
    </div>
  );
}
