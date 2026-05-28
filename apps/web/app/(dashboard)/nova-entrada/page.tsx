import { createProject } from "./actions";

export default function NovaEntradaPage() {
  return (
    <div className="max-w-xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">Nova entrada</h1>
      <form action={createProject} className="space-y-4">
        <Field label="Nome do projeto *" name="nome" required placeholder="PATIO_001" />
        <Field label="Cliente *" name="cliente" required placeholder="Empresa XYZ" />
        <Field label="Local" name="local" placeholder="Rua das Flores, 100" />
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
