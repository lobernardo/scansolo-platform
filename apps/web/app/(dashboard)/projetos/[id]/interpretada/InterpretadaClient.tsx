"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { aprovarInterpretada, regenerarInterpretada, salvarAnotacaoManual } from "../revisao/actions";
import type { ManualAnnotation } from "../revisao/actions";

const TIPOS = [
  { value: "tubulacao_agua",   label: "Tubulação água",    cor: "#1e90ff" },
  { value: "tubulacao_gas",    label: "Tubulação gás",     cor: "#ffa500" },
  { value: "tubulacao_esgoto", label: "Tubulação esgoto",  cor: "#8b4513" },
  { value: "cabo_eletrico",    label: "Cabo elétrico",     cor: "#ff3232" },
  { value: "cabo_telecom",     label: "Cabo telecom",      cor: "#a020f0" },
  { value: "galeria_concreto", label: "Galeria concreto",  cor: "#646464" },
  { value: "vazio",            label: "Vazio/cavidade",    cor: "#00c8c8" },
  { value: "rocha",            label: "Rocha",             cor: "#969696" },
  { value: "desconhecido",     label: "Desconhecido",      cor: "#b4b4b4" },
];

type Marker = ManualAnnotation & { id: number };

type Profile = {
  id: string;
  arquivo_dzt: string | null;
  imagem_processada_url: string | null;
  imagem_interpretada_url: string | null;
  imagem_interpretada_status: string | null;
};

type Mode = "view" | "manual";

export function InterpretadaClient({
  project,
  profiles,
}: {
  project: { id: string; nome: string };
  profiles: Profile[];
}) {
  const [activeProfileIdx, setActiveProfileIdx] = useState(0);
  const [mode, setMode] = useState<Mode>("view");
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState<{ tipo: "ok" | "erro"; msg: string } | null>(null);

  const profile = profiles[activeProfileIdx];
  if (!profile) return <p className="p-6 text-gray-500">Nenhum perfil encontrado.</p>;

  const status = profile.imagem_interpretada_status ?? "pendente";
  const interpretadaUrl = profile.imagem_interpretada_url;
  const processadaUrl = profile.imagem_processada_url;

  async function handleAprovar() {
    setBusy(true);
    setFeedback(null);
    const r = await aprovarInterpretada(profile.id, project.id);
    setBusy(false);
    setFeedback(r.ok
      ? { tipo: "ok", msg: "✅ Imagem aprovada! Será usada no relatório e a IA aprendeu com este exemplo." }
      : { tipo: "erro", msg: r.error ?? "Erro ao aprovar." });
  }

  async function handleRegerar() {
    setBusy(true);
    setFeedback(null);
    const r = await regenerarInterpretada(profile.id, project.id);
    setBusy(false);
    setFeedback(r.ok
      ? { tipo: "ok", msg: "🔄 Solicitação enviada. A IA está gerando uma nova interpretação..." }
      : { tipo: "erro", msg: r.error ?? "Erro ao solicitar regeneração." });
  }

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Imagem Interpretada</h1>
        <p className="text-sm text-gray-500 mt-1">{project.nome}</p>
      </div>

      {/* Seletor de perfil */}
      {profiles.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {profiles.map((p, i) => (
            <button
              key={p.id}
              onClick={() => { setActiveProfileIdx(i); setMode("view"); setFeedback(null); }}
              className={`px-3 py-1.5 rounded text-sm font-medium border transition ${
                i === activeProfileIdx
                  ? "bg-gray-900 text-white border-gray-900"
                  : "bg-white text-gray-700 border-gray-300 hover:border-gray-500"
              }`}
            >
              {p.arquivo_dzt ?? `Perfil ${i + 1}`}
            </button>
          ))}
        </div>
      )}

      {/* Status badge */}
      <StatusBadge status={status} />

      {/* Feedback */}
      {feedback && (
        <div className={`rounded-lg px-4 py-3 text-sm font-medium ${
          feedback.tipo === "ok" ? "bg-green-50 text-green-800" : "bg-red-50 text-red-700"
        }`}>
          {feedback.msg}
        </div>
      )}

      {mode === "view" ? (
        <>
          {/* Imagem interpretada */}
          <div className="rounded-xl overflow-hidden border border-gray-200 bg-black">
            {interpretadaUrl ? (
              <img
                src={interpretadaUrl}
                alt="Radargrama interpretado"
                className="w-full"
              />
            ) : (
              <div className="flex items-center justify-center h-48 text-gray-400 text-sm">
                {status === "regenerando"
                  ? "Aguardando processamento da IA..."
                  : "Imagem ainda não gerada. Aguarde o processamento."}
              </div>
            )}
          </div>

          {/* Download */}
          {interpretadaUrl && (
            <div className="flex gap-3 flex-wrap">
              <a
                href={interpretadaUrl}
                download={`${profile.arquivo_dzt ?? "interpretada"}_interpretada.png`}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
              >
                ⬇ Baixar interpretada
              </a>
              {processadaUrl && (
                <a
                  href={processadaUrl}
                  download={`${profile.arquivo_dzt ?? "processada"}_processada.png`}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-300 bg-white text-sm font-medium text-gray-700 hover:bg-gray-50 transition"
                >
                  ⬇ Baixar processada
                </a>
              )}
            </div>
          )}

          {/* 3 botões de workflow */}
          {interpretadaUrl && (
            <div className="flex gap-3 flex-wrap pt-2">
              <button
                onClick={handleAprovar}
                disabled={busy || status === "aprovado"}
                className="flex-1 min-w-[140px] px-4 py-3 rounded-xl bg-green-600 text-white font-semibold text-sm hover:bg-green-700 disabled:opacity-50 transition"
              >
                {status === "aprovado" ? "✅ Aprovada" : "✅ Aprovar"}
              </button>

              <button
                onClick={handleRegerar}
                disabled={busy || status === "regenerando"}
                className="flex-1 min-w-[140px] px-4 py-3 rounded-xl bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 disabled:opacity-50 transition"
              >
                🔄 Regenerar
              </button>

              <button
                onClick={() => { setMode("manual"); setFeedback(null); }}
                disabled={busy}
                className="flex-1 min-w-[140px] px-4 py-3 rounded-xl bg-amber-500 text-white font-semibold text-sm hover:bg-amber-600 disabled:opacity-50 transition"
              >
                ✏️ Interpretar manualmente
              </button>
            </div>
          )}

          {/* Explicação */}
          <div className="rounded-xl bg-gray-50 border border-gray-200 p-4 text-sm text-gray-600 space-y-1">
            <p><strong>✅ Aprovar</strong> — confirma que a interpretação está correta. A IA aprende com este exemplo para melhorar nas próximas.</p>
            <p><strong>🔄 Regenerar</strong> — solicita uma nova rodada da IA, usando os exemplos aprovados até agora como referência.</p>
            <p><strong>✏️ Interpretar manualmente</strong> — você marca os alvos diretamente na imagem. A IA aprende com suas marcações.</p>
          </div>
        </>
      ) : (
        /* Modo canvas de anotação manual */
        <CanvasAnotacao
          profileId={profile.id}
          projectId={project.id}
          imagemUrl={processadaUrl ?? ""}
          onConcluir={(msg) => { setMode("view"); setFeedback({ tipo: "ok", msg }); }}
          onCancelar={() => setMode("view")}
        />
      )}
    </div>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    pendente:     { label: "Aguardando aprovação",   cls: "bg-gray-100 text-gray-600" },
    aprovado:     { label: "Aprovada ✅",             cls: "bg-green-100 text-green-700" },
    regenerando:  { label: "Regenerando 🔄",          cls: "bg-blue-100 text-blue-700" },
    manual:       { label: "Anotada manualmente ✏️",  cls: "bg-amber-100 text-amber-700" },
  };
  const s = map[status] ?? map["pendente"];
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${s.cls}`}>
      {s.label}
    </span>
  );
}

// ── Canvas de anotação manual ─────────────────────────────────────────────────

function CanvasAnotacao({
  profileId,
  projectId,
  imagemUrl,
  onConcluir,
  onCancelar,
}: {
  profileId: string;
  projectId: string;
  imagemUrl: string;
  onConcluir: (msg: string) => void;
  onCancelar: () => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const [markers, setMarkers] = useState<Marker[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [nextId, setNextId] = useState(1);
  const [busy, setBusy] = useState(false);
  const [tipoAtivo, setTipoAtivo] = useState(TIPOS[0].value);
  const [imgLoaded, setImgLoaded] = useState(false);

  // Carrega imagem no canvas
  useEffect(() => {
    if (!canvasRef.current || !imagemUrl) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d")!;
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      imgRef.current = img;
      setImgLoaded(true);
      redraw(ctx, img, []);
    };
    img.src = imagemUrl;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [imagemUrl]);

  const redraw = useCallback((
    ctx: CanvasRenderingContext2D,
    img: HTMLImageElement,
    currentMarkers: Marker[],
  ) => {
    ctx.clearRect(0, 0, ctx.canvas.width, ctx.canvas.height);
    ctx.drawImage(img, 0, 0);
    for (const m of currentMarkers) {
      const px = m.x_pct * ctx.canvas.width;
      const py = m.y_pct * ctx.canvas.height;
      const tipo = TIPOS.find(t => t.value === m.tipo);
      const cor = tipo?.cor ?? "#ffdc00";
      ctx.beginPath();
      ctx.arc(px, py, 14, 0, 2 * Math.PI);
      ctx.fillStyle = cor + "88";
      ctx.fill();
      ctx.strokeStyle = cor;
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(px - 5, py); ctx.lineTo(px + 5, py);
      ctx.moveTo(px, py - 5); ctx.lineTo(px, py + 5);
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2;
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.font = "bold 12px sans-serif";
      ctx.fillText(`${m.profundidade_m.toFixed(2)}m`, px + 16, py + 4);
    }
  }, []);

  useEffect(() => {
    if (!canvasRef.current || !imgRef.current || !imgLoaded) return;
    const ctx = canvasRef.current.getContext("2d")!;
    redraw(ctx, imgRef.current, markers);
  }, [markers, imgLoaded, redraw]);

  function handleCanvasClick(e: React.MouseEvent<HTMLCanvasElement>) {
    const canvas = canvasRef.current!;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    const x_pct = ((e.clientX - rect.left) * scaleX) / canvas.width;
    const y_pct = ((e.clientY - rect.top)  * scaleY) / canvas.height;

    const newMarker: Marker = {
      id: nextId,
      x_pct,
      y_pct,
      tipo: tipoAtivo,
      profundidade_m: parseFloat((y_pct * 5).toFixed(2)), // estimativa simples
      diametro_m: 0.05,
      observacao: "",
    };
    setNextId(n => n + 1);
    setMarkers(prev => [...prev, newMarker]);
    setSelectedId(newMarker.id);
  }

  function updateMarker(id: number, field: string, value: string | number) {
    setMarkers(prev => prev.map(m => m.id === id ? { ...m, [field]: value } : m));
  }

  function removeMarker(id: number) {
    setMarkers(prev => prev.filter(m => m.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  async function handleConfirmar() {
    if (!markers.length) return;
    setBusy(true);
    const r = await salvarAnotacaoManual(profileId, projectId, markers, imagemUrl);
    setBusy(false);
    if (r.ok) {
      onConcluir(`✅ ${markers.length} alvo(s) registrado(s) manualmente. A IA aprendeu com este exemplo e uma nova imagem interpretada será gerada.`);
    }
  }

  const selected = markers.find(m => m.id === selectedId);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Anotação manual</h2>
        <button onClick={onCancelar} className="text-sm text-gray-500 hover:text-gray-700">← Voltar</button>
      </div>

      {/* Seletor de tipo ativo */}
      <div className="flex gap-2 flex-wrap">
        {TIPOS.map(t => (
          <button
            key={t.value}
            onClick={() => setTipoAtivo(t.value)}
            style={{ borderColor: tipoAtivo === t.value ? t.cor : undefined, color: tipoAtivo === t.value ? t.cor : undefined }}
            className={`px-3 py-1 rounded-full text-xs font-medium border transition ${
              tipoAtivo === t.value ? "border-2 font-bold" : "border-gray-300 text-gray-600"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="text-xs text-gray-500">
        Clique na imagem para marcar um alvo com o tipo selecionado acima.
        Ajuste profundidade e diâmetro no painel lateral.
      </p>

      <div className="flex gap-4 flex-col lg:flex-row">
        {/* Canvas */}
        <div className="flex-1 rounded-xl overflow-hidden border border-gray-200 bg-black">
          {imagemUrl ? (
            <canvas
              ref={canvasRef}
              onClick={handleCanvasClick}
              className="w-full cursor-crosshair"
              style={{ imageRendering: "pixelated" }}
            />
          ) : (
            <div className="flex items-center justify-center h-40 text-gray-400 text-sm">
              Sem imagem processada disponível.
            </div>
          )}
        </div>

        {/* Painel de marcadores */}
        <div className="w-full lg:w-72 space-y-2">
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">
            {markers.length} alvo(s) marcado(s)
          </p>

          {markers.length === 0 && (
            <p className="text-xs text-gray-400">
              Clique na imagem para adicionar o primeiro alvo.
            </p>
          )}

          {markers.map((m, i) => {
            const tipo = TIPOS.find(t => t.value === m.tipo);
            return (
              <div
                key={m.id}
                onClick={() => setSelectedId(m.id)}
                className={`rounded-xl border p-3 cursor-pointer transition text-sm space-y-2 ${
                  selectedId === m.id ? "border-gray-900 bg-gray-50" : "border-gray-200 hover:border-gray-400"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-semibold" style={{ color: tipo?.cor }}>
                    Alvo {i + 1} — {tipo?.label ?? m.tipo}
                  </span>
                  <button
                    onClick={e => { e.stopPropagation(); removeMarker(m.id); }}
                    className="text-red-400 hover:text-red-600 text-xs"
                  >
                    ✕
                  </button>
                </div>

                {selectedId === m.id && (
                  <div className="space-y-2" onClick={e => e.stopPropagation()}>
                    <label className="block">
                      <span className="text-xs text-gray-500">Tipo</span>
                      <select
                        value={m.tipo}
                        onChange={e => updateMarker(m.id, "tipo", e.target.value)}
                        className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-xs"
                      >
                        {TIPOS.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
                      </select>
                    </label>
                    <div className="flex gap-2">
                      <label className="flex-1 block">
                        <span className="text-xs text-gray-500">Prof. (m)</span>
                        <input
                          type="number" step="0.01" min="0" max="10"
                          value={m.profundidade_m}
                          onChange={e => updateMarker(m.id, "profundidade_m", parseFloat(e.target.value) || 0)}
                          className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-xs"
                        />
                      </label>
                      <label className="flex-1 block">
                        <span className="text-xs text-gray-500">Diâm. (m)</span>
                        <input
                          type="number" step="0.01" min="0" max="2"
                          value={m.diametro_m}
                          onChange={e => updateMarker(m.id, "diametro_m", parseFloat(e.target.value) || 0)}
                          className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-xs"
                        />
                      </label>
                    </div>
                    <label className="block">
                      <span className="text-xs text-gray-500">Observação</span>
                      <input
                        type="text"
                        value={m.observacao ?? ""}
                        onChange={e => updateMarker(m.id, "observacao", e.target.value)}
                        placeholder="opcional"
                        className="mt-0.5 w-full rounded border border-gray-300 px-2 py-1 text-xs"
                      />
                    </label>
                  </div>
                )}
              </div>
            );
          })}

          {markers.length > 0 && (
            <button
              onClick={handleConfirmar}
              disabled={busy}
              className="w-full mt-2 px-4 py-2.5 rounded-xl bg-gray-900 text-white text-sm font-semibold hover:bg-gray-700 disabled:opacity-50 transition"
            >
              {busy ? "Salvando..." : "✓ Confirmar interpretação"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
