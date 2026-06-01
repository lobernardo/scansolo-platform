import { createProject } from "./actions";

export default function NovaEntradaPage() {
  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Nova entrada</h1>
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
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Data levantamento *
            </label>
            <input
              type="date"
              name="data_levantamento"
              required
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Área levantada (m²)
            </label>
            <input
              type="number"
              name="area_m2"
              min="1"
              step="1"
              placeholder="500"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Antena GPR (MHz)
            </label>
            <select
              name="antena_freq_mhz"
              defaultValue="270"
              className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
            >
              <option value="270">270 MHz</option>
              <option value="400">400 MHz</option>
              <option value="900">900 MHz</option>
            </select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            name="tem_pipe_locator"
            id="tem_pipe_locator"
            value="true"
            className="h-4 w-4 rounded border-gray-300 text-gray-900"
          />
          <label htmlFor="tem_pipe_locator" className="text-sm text-gray-700">
            Levantamento inclui Pipe Locator
          </label>
        </div>

        <div className="pt-2">
          <button
            type="submit"
            className="w-full rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 transition-colors"
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
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type="text"
        name={name}
        required={required}
        placeholder={placeholder}
        maxLength={maxLength}
        className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-gray-900"
      />
    </div>
  );
}
