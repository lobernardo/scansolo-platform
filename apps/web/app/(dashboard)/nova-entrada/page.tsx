import { createProject } from "./actions";

export default function NovaEntradaPage() {
  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold text-slate-100 mb-6">Nova entrada</h1>
      <form action={createProject} className="space-y-4">
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
              Aprovação automática pela IA (sem revisão manual)
            </label>
          </div>
          <p className="text-xs text-slate-500 pl-6">
            Alta confiança → planta + relatório. Média confiança → só planta.
            Baixa confiança → descartado. Projeto avança direto para cartografia.
          </p>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            className="w-full rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-cyan-400 transition-colors"
          >
            Criar projeto e fazer upload
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
