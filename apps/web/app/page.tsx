export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center min-h-screen px-4">
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold tracking-tight text-gray-900">
          ScanSOLO
        </h1>
        <p className="text-gray-500 text-lg">
          Plataforma operacional GPR
        </p>
        <div className="mt-8 space-y-2 text-sm text-gray-400">
          <p>Fase 0 — Fundação em andamento</p>
          <a
            href="/login"
            className="inline-block mt-4 px-6 py-2 rounded-md bg-gray-900 text-white text-sm font-medium hover:bg-gray-700 transition-colors"
          >
            Entrar
          </a>
        </div>
      </div>
    </main>
  );
}
