"use client";

import { useActionState, useState } from "react";
import { createProject, type CreateProjectState } from "./actions";

const VELOCITY_OPTIONS = [
  { value: "0.06", label: "Solo úmido / argiloso — 0.06 m/ns (ε_r ≈ 25)" },
  { value: "0.10", label: "Solo misto padrão — 0.10 m/ns (ε_r ≈ 9)" },
  { value: "0.13", label: "Solo seco / pavimento — 0.13 m/ns (ε_r ≈ 5)" },
  { value: "0.20", label: "Areia seca / entulho seco — 0.20 m/ns (ε_r ≈ 2.2)" },
  { value: "custom", label: "Personalizado" },
];

export default function NovaEntradaPage() {
  const [state, formAction, pending] = useActionState<CreateProjectState, FormData>(
    createProject,
    null
  );
  const [velocitySelect, setVelocitySelect] = useState("0.10");

  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-100 mb-6">Nova entrada</h1>
      <form action={formAction} className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Nome do projeto *" name="nome" required placeholder="PATIO_001" />
          <Field label="Código interno" name="codigo_projeto" placeholder="PT-GPR-SOL-036" />
        </div>

        <Field label="Cliente *" name="cliente" required placeholder="Empresa XYZ Ltda" />

        <div className="grid grid-cols-2 gap-4">
          <Field label="A/C (contato)" name="contato_nome" placeholder="João Silva" />
          <Field label="Local" name="local" placeholder="Rua das Flores, 100" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Estado *" name="estado" required placeholder="SP" maxLength={2} />
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-1">
              Data levantamento *
            </label>
            <input
              type="date"
              name="data_levantamento"
              required
              className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 placeholder:text-slate-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-300 mb-1">
            Área levantada (m²)
          </label>
          <input
            type="number"
            name="area_m2"
            min="1"
            step="1"
            placeholder="500"
            className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 placeholder:text-slate-500"
          />
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            name="tem_pipe_locator"
            id="tem_pipe_locator"
            value="true"
            className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500"
          />
          <label htmlFor="tem_pipe_locator" className="text-sm text-slate-300">
            Levantamento inclui Pipe Locator
          </label>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              name="auto_accept_ia"
              id="auto_accept_ia"
              value="true"
              className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500"
            />
            <label htmlFor="auto_accept_ia" className="text-sm font-medium text-slate-200">
              Aprovação automática da interpretação IA (GPT-4o por alvo)
            </label>
          </div>
          <p className="text-xs text-slate-500 pl-6">
            Alta confiança → planta + relatório. Média confiança → só planta.
            Baixa confiança → descartado. Projeto avança direto para cartografia.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              name="skip_ia"
              id="skip_ia"
              value="true"
              className="h-4 w-4 rounded border-slate-600 bg-slate-800 text-cyan-500"
            />
            <label htmlFor="skip_ia" className="text-sm font-medium text-slate-200">
              Pular interpretação IA dos alvos (GPT-4o)
            </label>
          </div>
          <p className="text-xs text-slate-500 pl-6">
            Para validações locais. Evita chamadas ao GPT-4o por alvo.
            O pipeline GPR e a detecção de hipérboles rodam normalmente.
          </p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-800/50 p-3 space-y-2">
          <label className="block text-sm font-medium text-slate-200">
            Velocity do solo
          </label>
          <select
            name={velocitySelect !== "custom" ? "velocity_mns" : undefined}
            value={velocitySelect}
            onChange={(e) => setVelocitySelect(e.target.value)}
            className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500"
          >
            {VELOCITY_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          {velocitySelect === "custom" && (
            <input
              type="number"
              name="velocity_mns"
              min="0.05"
              max="0.30"
              step="0.01"
              placeholder="0.10"
              className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500"
            />
          )}
          <p className="text-xs text-slate-500">
            Afeta apenas a escala de profundidade. Padrão: 0.10 m/ns (solo misto). Use 0.20 m/ns para areia seca ou entulho urbano seco.
          </p>
        </div>

        {state?.error && (
          <p className="text-sm text-red-400 rounded-lg bg-red-500/10 border border-red-500/30 px-3 py-2">
            {state.error}
          </p>
        )}

        <div className="pt-2">
          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors disabled:opacity-50"
          >
            {pending ? "Criando projeto…" : "Criar projeto e fazer upload"}
          </button>
        </div>
      </form>
    </div>
  );
}

function Field({
  label,
  name,
  required,
  placeholder,
  maxLength,
}: {
  label: string;
  name: string;
  required?: boolean;
  placeholder?: string;
  maxLength?: number;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1">{label}</label>
      <input
        type="text"
        name={name}
        required={required}
        placeholder={placeholder}
        maxLength={maxLength}
        className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500 focus:border-cyan-500 placeholder:text-slate-500"
      />
    </div>
  );
}
