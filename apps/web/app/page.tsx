export default function HomePage() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center min-h-screen px-4 bg-slate-950">
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold tracking-tight">
          <span className="text-cyan-400">SCAN</span>
          <span className="text-slate-100">SOLO</span>
        </h1>
        <p className="text-slate-400 text-lg">
          Plataforma operacional GPR
        </p>
        <div className="mt-8 space-y-2 text-sm text-slate-600">
          <p>Fase 0 — Fundação em andamento</p>
          <a
            href="/login"
            className="inline-block mt-4 px-6 py-2 rounded-md bg-cyan-500 text-slate-950 text-sm font-semibold hover:bg-cyan-400 transition-colors"
          >
            Entrar
          </a>
        </div>
      </div>
    </main>
  );
}
