"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type {
  GroundTruthStats,
  TrainingSession,
  RecalibracaoResult,
  RecalibracaoContent,
  ProjectForTraining,
  ProfileForTraining,
  DetectedTargetForTraining,
} from "@/app/actions/training-actions";
import {
  getProjectsForTraining,
  getProfilesForProject,
  getTargetsForProfile,
  createTrainingSession,
  saveGroundTruthEntry,
  finalizeTrainingSession,
  triggerRecalibracao,
  getRecalibracaoContent,
  applyRecalibracao,
} from "@/app/actions/training-actions";

// ── Types ─────────────────────────────────────────────────────────────────────

type Verdict = "vp" | "fp" | "skip" | null;

type VPForm = {
  tipo_alvo: string;
  material: string;
  depth_real_m: string;
  diametro_real_mm: string;
  fonte: string;
};

type FNEntry = {
  id: string;
  x_real_m: string;
  depth_real_m: string;
  tipo_alvo: string;
  material: string;
  fonte: string;
};

type SessionMeta = {
  descricao: string;
  tipo_solo: string;
  umidade_solo: string;
  tipo_superficie: string;
  dias_sem_chuva: string;
  profundidade_lencol_m: string;
};

const FONTE_CONFIANCA: Record<string, number> = {
  escavacao: 100,
  cadastro_concessionaria: 80,
  sondagem: 70,
  avaliacao_especialista: 60,
};

const TIPOS_ALVO = [
  "tubulacao_agua", "tubulacao_gas", "tubulacao_esgoto",
  "cabo_eletrico", "cabo_telecom", "galeria_concreto",
  "vazio_ar", "rocha", "outro",
];

const MIN_AMOSTRAS = 20;

// ── Main component ─────────────────────────────────────────────────────────────

export function TreinamentoClient({
  initialStats,
  initialSessions,
  initialRecalResults,
}: {
  initialStats: GroundTruthStats;
  initialSessions: TrainingSession[];
  initialRecalResults: RecalibracaoResult[];
}) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  // Stats (refreshed after session finalize)
  const [stats, setStats] = useState(initialStats);
  const [sessions, setSessions] = useState(initialSessions);
  const [recalResults] = useState(initialRecalResults);

  // Recalibration modal
  const [recalModal, setRecalModal] = useState<RecalibracaoContent | null>(null);
  const [recalModalName, setRecalModalName] = useState<string>("");
  const [loadingRecal, setLoadingRecal] = useState(false);
  const [applyingRecal, setApplyingRecal] = useState(false);
  const [recalMsg, setRecalMsg] = useState<string | null>(null);

  // Wizard state
  type WizardStep = "idle" | "select" | "metadata" | "validate" | "done";
  const [wizardStep, setWizardStep] = useState<WizardStep>("idle");
  const [projects, setProjects] = useState<ProjectForTraining[]>([]);
  const [profiles, setProfiles] = useState<ProfileForTraining[]>([]);
  const [targets, setTargets] = useState<DetectedTargetForTraining[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectForTraining | null>(null);
  const [selectedProfile, setSelectedProfile] = useState<ProfileForTraining | null>(null);
  const [sessionMeta, setSessionMeta] = useState<SessionMeta>({
    descricao: "", tipo_solo: "standard", umidade_solo: "normal",
    tipo_superficie: "terra", dias_sem_chuva: "", profundidade_lencol_m: "",
  });

  // Validation state
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Verdict>>({});
  const [vpForms, setVpForms] = useState<Record<string, VPForm>>({});
  const [expandedVp, setExpandedVp] = useState<Set<string>>(new Set());
  const [falsoNegativos, setFalsoNegativos] = useState<FNEntry[]>([]);
  const [showFnForm, setShowFnForm] = useState(false);
  const [newFn, setNewFn] = useState<Omit<FNEntry, "id">>({
    x_real_m: "", depth_real_m: "", tipo_alvo: "tubulacao_agua",
    material: "metal", fonte: "avaliacao_especialista",
  });

  const [saving, setSaving] = useState(false);
  const [errMsg, setErrMsg] = useState<string | null>(null);
  const [triggeringRecal, setTriggeringRecal] = useState(false);

  // ── Wizard helpers ─────────────────────────────────────────────────────────

  async function openWizard() {
    const projs = await getProjectsForTraining();
    setProjects(projs);
    setSelectedProject(null);
    setSelectedProfile(null);
    setProfiles([]);
    setTargets([]);
    setDecisions({});
    setVpForms({});
    setExpandedVp(new Set());
    setFalsoNegativos([]);
    setWizardStep("select");
  }

  async function handleProjectSelect(id: string) {
    const proj = projects.find(p => p.id === id) ?? null;
    setSelectedProject(proj);
    setSelectedProfile(null);
    setProfiles([]);
    if (id) {
      const profs = await getProfilesForProject(id);
      setProfiles(profs);
    }
  }

  async function handleProfileSelect(id: string) {
    const prof = profiles.find(p => p.id === id) ?? null;
    setSelectedProfile(prof);
    if (id) {
      const tgts = await getTargetsForProfile(id);
      setTargets(tgts);
    }
  }

  async function goToValidate() {
    if (!selectedProject || !selectedProfile) return;
    setSaving(true);
    setErrMsg(null);
    const result = await createTrainingSession(
      selectedProject.id,
      selectedProfile.id,
      sessionMeta.descricao,
    );
    setSaving(false);
    if (!result.ok) { setErrMsg(result.error ?? "Erro"); return; }
    setCurrentSessionId(result.session_id!);
    setWizardStep("validate");
  }

  function setVerdict(targetId: string, v: Verdict) {
    setDecisions(prev => ({ ...prev, [targetId]: v }));
    if (v === "vp") {
      setExpandedVp(prev => { const s = new Set(prev); s.add(targetId); return s; });
      if (!vpForms[targetId]) {
        const tgt = targets.find(t => t.id === targetId);
        setVpForms(prev => ({
          ...prev,
          [targetId]: {
            tipo_alvo: "tubulacao_agua",
            material: "metal",
            depth_real_m: String(tgt?.depth_m ?? ""),
            diametro_real_mm: "",
            fonte: "avaliacao_especialista",
          },
        }));
      }
    } else {
      setExpandedVp(prev => { const s = new Set(prev); s.delete(targetId); return s; });
    }
  }

  function addFN() {
    if (!newFn.depth_real_m || !newFn.tipo_alvo) return;
    setFalsoNegativos(prev => [...prev, { ...newFn, id: crypto.randomUUID() }]);
    setNewFn({ x_real_m: "", depth_real_m: "", tipo_alvo: "tubulacao_agua", material: "metal", fonte: "avaliacao_especialista" });
    setShowFnForm(false);
  }

  async function handleFinalize() {
    if (!currentSessionId || !selectedProject || !selectedProfile) return;
    setSaving(true);
    setErrMsg(null);

    const common = {
      session_id: currentSessionId,
      project_id: selectedProject.id,
      profile_id: selectedProfile.id,
      tipo_solo: sessionMeta.tipo_solo,
      umidade_solo: sessionMeta.umidade_solo,
      tipo_superficie: sessionMeta.tipo_superficie,
      dias_sem_chuva: sessionMeta.dias_sem_chuva ? parseInt(sessionMeta.dias_sem_chuva) : null,
      profundidade_lencol_m: sessionMeta.profundidade_lencol_m ? parseFloat(sessionMeta.profundidade_lencol_m) : null,
    };

    const errors: string[] = [];

    // Save VP and FP entries
    for (const tgt of targets) {
      const verdict = decisions[tgt.id];
      if (!verdict || verdict === "skip") continue;

      const isVp = verdict === "vp";
      const form = vpForms[tgt.id];
      const res = await saveGroundTruthEntry({
        ...common,
        detected_target_id: tgt.id,
        e_verdadeiro_positivo: isVp,
        e_falso_negativo: false,
        ...(isVp && form ? {
          depth_real_m: form.depth_real_m ? parseFloat(form.depth_real_m) : null,
          tipo_alvo_confirmado: form.tipo_alvo || null,
          material_alvo: form.material || null,
          diametro_real_mm: form.diametro_real_mm ? parseFloat(form.diametro_real_mm) : null,
          fonte_confirmacao: form.fonte,
          confianca_fonte: FONTE_CONFIANCA[form.fonte] ?? 60,
        } : {
          fonte_confirmacao: "avaliacao_especialista",
          confianca_fonte: 60,
        }),
      });
      if (!res.ok) errors.push(`Alvo rank ${tgt.rank}: ${res.error}`);
    }

    // Save FN entries
    for (const fn of falsoNegativos) {
      const res = await saveGroundTruthEntry({
        ...common,
        detected_target_id: null,
        e_verdadeiro_positivo: true,
        e_falso_negativo: true,
        x_real_m: fn.x_real_m ? parseFloat(fn.x_real_m) : null,
        depth_real_m: fn.depth_real_m ? parseFloat(fn.depth_real_m) : null,
        tipo_alvo_confirmado: fn.tipo_alvo || null,
        material_alvo: fn.material || null,
        fonte_confirmacao: fn.fonte,
        confianca_fonte: FONTE_CONFIANCA[fn.fonte] ?? 60,
      });
      if (!res.ok) errors.push(`FN: ${res.error}`);
    }

    if (errors.length > 0) {
      setErrMsg(errors.join(" | "));
      setSaving(false);
      return;
    }

    await finalizeTrainingSession(currentSessionId);
    setSaving(false);
    setWizardStep("done");

    // Refresh page data
    startTransition(() => router.refresh());
  }

  async function handleTriggerRecal() {
    setTriggeringRecal(true);
    const result = await triggerRecalibracao();
    setTriggeringRecal(false);
    if (!result.ok) setErrMsg(result.error ?? "Erro ao disparar recalibração");
    else setErrMsg(null);
  }

  async function openRecalModal(r: RecalibracaoResult) {
    setLoadingRecal(true);
    setRecalMsg(null);
    const result = await getRecalibracaoContent(r.signed_url);
    setLoadingRecal(false);
    if (result.ok && result.content) {
      setRecalModal(result.content);
      setRecalModalName(r.name);
    }
  }

  async function handleApplyRecal() {
    if (!recalModal) return;
    setApplyingRecal(true);
    setRecalMsg(null);
    const result = await applyRecalibracao(recalModal.thresholds_sugeridos);
    setApplyingRecal(false);
    if (result.ok) {
      setRecalMsg("Preset criado com sucesso! Vá em /presets para revisar antes de usar em produção.");
    } else {
      setRecalMsg(`Erro: ${result.error}`);
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  const canRecalibrate = stats.total_entries >= MIN_AMOSTRAS;

  return (
    <>
      {/* ── SEÇÃO 1: Estatísticas ──────────────────────────────────────────── */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-slate-100 mb-1">Treinamento do Detector</h1>
        <p className="text-sm text-slate-500 mb-6">
          Valide alvos detectados pelo pipeline para melhorar a calibração automática dos thresholds.
        </p>

        {/* Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
          <StatCard label="Total de entradas" value={stats.total_entries} color="slate" />
          <StatCard label="Verdadeiros positivos" value={stats.total_vp} color="green" />
          <StatCard label="Falsos positivos" value={stats.total_fp} color="red" />
          <StatCard label="Falsos negativos" value={stats.total_fn} color="amber" />
        </div>

        {/* F1 */}
        <div className="flex items-center gap-4 mb-4">
          <div className="rounded-lg bg-slate-800/50 border border-slate-700 px-4 py-2 flex items-center gap-3">
            <span className="text-sm text-slate-400">F1-score estimado</span>
            <span className={`text-xl font-bold ${stats.f1_estimado >= 0.7 ? "text-green-400" : stats.f1_estimado >= 0.5 ? "text-amber-400" : "text-red-400"}`}>
              {stats.total_entries > 0 ? stats.f1_estimado.toFixed(3) : "—"}
            </span>
          </div>

          {!canRecalibrate && (
            <p className="text-xs text-amber-400 bg-amber-400/10 border border-amber-400/20 rounded-lg px-3 py-2">
              Base precisa de ≥{MIN_AMOSTRAS} entradas para recalibração confiável
              ({stats.total_entries}/{MIN_AMOSTRAS})
            </p>
          )}

          {canRecalibrate && (
            <button
              onClick={handleTriggerRecal}
              disabled={triggeringRecal}
              className="rounded-lg bg-violet-500 hover:bg-violet-400 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-white transition-colors"
            >
              {triggeringRecal ? "Disparando…" : "Rodar Recalibração Automática"}
            </button>
          )}
        </div>

        {/* Distribuição por tipo de solo */}
        {Object.keys(stats.por_tipo_solo).length > 0 && (
          <div className="grid sm:grid-cols-2 gap-4 mb-4">
            <MiniChart
              label="Entradas por tipo de solo"
              data={stats.por_tipo_solo}
              total={stats.total_entries}
            />
            <MiniChart
              label="VPs por tipo de alvo confirmado"
              data={stats.por_tipo_alvo}
              total={stats.total_vp}
            />
          </div>
        )}

        {/* Última recalibração */}
        {recalResults.length > 0 && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/30 px-4 py-3 flex items-center justify-between">
            <div>
              <span className="text-xs text-slate-500">Última recalibração: </span>
              <span className="text-xs text-slate-300 font-mono">{recalResults[0].name.replace("candidato_", "").replace(".json", "")}</span>
            </div>
            <button
              onClick={() => openRecalModal(recalResults[0])}
              disabled={loadingRecal}
              className="text-xs text-cyan-400 hover:text-cyan-300 underline"
            >
              {loadingRecal ? "Carregando…" : "Ver resultado"}
            </button>
          </div>
        )}
      </div>

      {/* ── SEÇÃO 2: Nova sessão ───────────────────────────────────────────── */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold text-slate-200">Nova sessão de validação</h2>
          {wizardStep === "idle" && (
            <button
              onClick={openWizard}
              className="rounded-lg bg-cyan-500 hover:bg-cyan-400 px-4 py-1.5 text-sm font-semibold text-slate-950 transition-colors"
            >
              + Nova sessão
            </button>
          )}
        </div>

        {wizardStep === "idle" && (
          <p className="text-sm text-slate-600">Clique em &ldquo;+ Nova sessão&rdquo; para validar alvos de um perfil.</p>
        )}

        {/* Step 1: Selecionar projeto + perfil */}
        {wizardStep === "select" && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-300">Passo 1 — Selecionar projeto e perfil</h3>

            <div>
              <label className="block text-xs text-slate-400 mb-1">Projeto</label>
              <select
                className={selectCls}
                value={selectedProject?.id ?? ""}
                onChange={e => handleProjectSelect(e.target.value)}
              >
                <option value="">— Selecione —</option>
                {projects.map(p => (
                  <option key={p.id} value={p.id}>{p.nome} — {p.cliente}</option>
                ))}
              </select>
            </div>

            {profiles.length > 0 && (
              <div>
                <label className="block text-xs text-slate-400 mb-1">Perfil (DZT)</label>
                <select
                  className={selectCls}
                  value={selectedProfile?.id ?? ""}
                  onChange={e => handleProfileSelect(e.target.value)}
                >
                  <option value="">— Selecione —</option>
                  {profiles.map(p => (
                    <option key={p.id} value={p.id}>{p.arquivo_dzt}</option>
                  ))}
                </select>
              </div>
            )}

            {selectedProfile?.imagem_anotada_url && (
              <div>
                <p className="text-xs text-slate-500 mb-1">Imagem Anotada IA do perfil:</p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={selectedProfile.imagem_anotada_url}
                  alt="Anotada IA"
                  className="rounded-lg border border-slate-700 max-h-48 object-contain w-full bg-slate-900"
                />
              </div>
            )}

            <div className="flex gap-2">
              <button onClick={() => setWizardStep("idle")} className={btnSecondary}>Cancelar</button>
              <button
                disabled={!selectedProject || !selectedProfile}
                onClick={() => setWizardStep("metadata")}
                className={btnPrimary}
              >
                Continuar →
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Metadados */}
        {wizardStep === "metadata" && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-300">Passo 2 — Metadados do escaneamento</h3>
            <p className="text-xs text-slate-500">
              Projeto: <span className="text-slate-300">{selectedProject?.nome}</span> ·
              Perfil: <span className="text-slate-300">{selectedProfile?.arquivo_dzt}</span>
            </p>

            <div className="grid grid-cols-2 gap-3">
              <MetaSelect label="Tipo de solo" value={sessionMeta.tipo_solo} onChange={v => setSessionMeta(p => ({ ...p, tipo_solo: v }))} options={[
                ["standard", "Misto/padrão"], ["arenoso", "Arenoso"], ["argiloso", "Argiloso"],
                ["umido", "Úmido"], ["pedregoso", "Pedregoso"], ["outro", "Outro"],
              ]} />
              <MetaSelect label="Umidade do solo" value={sessionMeta.umidade_solo} onChange={v => setSessionMeta(p => ({ ...p, umidade_solo: v }))} options={[
                ["seco", "Seco"], ["normal", "Normal"], ["umido", "Úmido"], ["saturado", "Saturado"],
              ]} />
              <MetaSelect label="Tipo de superfície" value={sessionMeta.tipo_superficie} onChange={v => setSessionMeta(p => ({ ...p, tipo_superficie: v }))} options={[
                ["terra", "Terra"], ["asfalto", "Asfalto"], ["concreto", "Concreto"],
                ["paralelepipedo", "Paralelepípedo"], ["outro", "Outro"],
              ]} />
              <div>
                <label className="block text-xs text-slate-400 mb-1">Dias sem chuva (aprox.)</label>
                <input type="number" min={0} value={sessionMeta.dias_sem_chuva} onChange={e => setSessionMeta(p => ({ ...p, dias_sem_chuva: e.target.value }))} className={inputCls} placeholder="7" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Prof. lençol freático (m)</label>
                <input type="number" min={0} step={0.1} value={sessionMeta.profundidade_lencol_m} onChange={e => setSessionMeta(p => ({ ...p, profundidade_lencol_m: e.target.value }))} className={inputCls} placeholder="—" />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Descrição da sessão</label>
                <input type="text" value={sessionMeta.descricao} onChange={e => setSessionMeta(p => ({ ...p, descricao: e.target.value }))} className={inputCls} placeholder="HELPER 0013 — SABESP cadastro" />
              </div>
            </div>

            {errMsg && <p className="text-xs text-red-400">{errMsg}</p>}
            <div className="flex gap-2">
              <button onClick={() => setWizardStep("select")} className={btnSecondary}>← Voltar</button>
              <button onClick={goToValidate} disabled={saving} className={btnPrimary}>
                {saving ? "Criando sessão…" : "Iniciar Validação →"}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Validação por alvo */}
        {wizardStep === "validate" && selectedProfile && (
          <div className="rounded-xl border border-slate-700 bg-slate-800/40 p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-300">
              Passo 3 — Validação por alvo · {selectedProfile.arquivo_dzt}
            </h3>

            <div className="grid lg:grid-cols-2 gap-4">
              {/* Image */}
              <div>
                {selectedProfile.imagem_anotada_url ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={selectedProfile.imagem_anotada_url} alt="Anotada IA" className="rounded-lg border border-slate-700 w-full object-contain bg-slate-900 sticky top-20" />
                ) : (
                  <div className="rounded-lg border border-slate-700 h-48 flex items-center justify-center text-slate-600 text-sm">Sem imagem anotada</div>
                )}
              </div>

              {/* Targets */}
              <div className="space-y-2 max-h-[70vh] overflow-y-auto pr-1">
                {targets.length === 0 && (
                  <p className="text-sm text-slate-500">Nenhum alvo detectado neste perfil.</p>
                )}

                {targets.map(tgt => {
                  const verdict = decisions[tgt.id] ?? null;
                  const isExpanded = expandedVp.has(tgt.id);
                  const form = vpForms[tgt.id];

                  return (
                    <div
                      key={tgt.id}
                      className={`rounded-lg border p-3 transition-colors ${verdict === "vp" ? "border-green-600/50 bg-green-500/5" : verdict === "fp" ? "border-red-600/50 bg-red-500/5" : "border-slate-700 bg-slate-900/40"}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-mono text-slate-400">#{tgt.rank}</span>
                          <span className="text-xs text-slate-300">{tgt.depth_m?.toFixed(2)}m prof.</span>
                          {tgt.diam_est_m && <span className="text-xs text-slate-400">Ø{(tgt.diam_est_m * 100).toFixed(0)}cm</span>}
                          <span className="text-xs text-slate-400">score={tgt.confidence_score_0_100?.toFixed(0)}</span>
                          {tgt.tipo_material && <span className="text-[10px] text-slate-500">{tgt.tipo_material}</span>}
                        </div>
                        <div className="flex gap-1">
                          <VerdictBtn label="✓" title="Verdadeiro positivo" active={verdict === "vp"} color="green" onClick={() => setVerdict(tgt.id, "vp")} />
                          <VerdictBtn label="✗" title="Falso positivo" active={verdict === "fp"} color="red" onClick={() => setVerdict(tgt.id, "fp")} />
                          <VerdictBtn label="~" title="Pular" active={verdict === "skip"} color="slate" onClick={() => setVerdict(tgt.id, "skip")} />
                        </div>
                      </div>

                      {/* VP inline form */}
                      {verdict === "vp" && isExpanded && form && (
                        <div className="mt-2 pt-2 border-t border-green-600/20 grid grid-cols-2 gap-2">
                          <div className="col-span-2">
                            <label className="block text-[10px] text-slate-400 mb-0.5">Tipo confirmado</label>
                            <select value={form.tipo_alvo} onChange={e => setVpForms(p => ({ ...p, [tgt.id]: { ...p[tgt.id], tipo_alvo: e.target.value } }))} className={inputCls}>
                              {TIPOS_ALVO.map(t => <option key={t} value={t}>{t}</option>)}
                            </select>
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">Material</label>
                            <select value={form.material} onChange={e => setVpForms(p => ({ ...p, [tgt.id]: { ...p[tgt.id], material: e.target.value } }))} className={inputCls}>
                              <option value="metal">Metal</option>
                              <option value="pvc">PVC</option>
                              <option value="concreto">Concreto</option>
                              <option value="ceramica">Cerâmica</option>
                              <option value="outro">Outro</option>
                            </select>
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">Prof. real (m)</label>
                            <input type="number" step={0.01} value={form.depth_real_m} onChange={e => setVpForms(p => ({ ...p, [tgt.id]: { ...p[tgt.id], depth_real_m: e.target.value } }))} className={inputCls} />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">Diâm. real (mm)</label>
                            <input type="number" step={1} value={form.diametro_real_mm} onChange={e => setVpForms(p => ({ ...p, [tgt.id]: { ...p[tgt.id], diametro_real_mm: e.target.value } }))} className={inputCls} placeholder="—" />
                          </div>
                          <div className="col-span-2">
                            <label className="block text-[10px] text-slate-400 mb-0.5">Fonte da confirmação</label>
                            <select value={form.fonte} onChange={e => setVpForms(p => ({ ...p, [tgt.id]: { ...p[tgt.id], fonte: e.target.value } }))} className={inputCls}>
                              <option value="escavacao">Escavação física</option>
                              <option value="cadastro_concessionaria">Cadastro de concessionária</option>
                              <option value="sondagem">Sondagem geotécnica</option>
                              <option value="avaliacao_especialista">Avaliação de especialista</option>
                            </select>
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Falsos negativos */}
                {falsoNegativos.length > 0 && (
                  <div className="rounded-lg border border-amber-600/40 bg-amber-500/5 p-3 space-y-1">
                    <p className="text-xs font-semibold text-amber-400">Falsos negativos ({falsoNegativos.length})</p>
                    {falsoNegativos.map((fn, i) => (
                      <div key={fn.id} className="flex items-center justify-between text-xs text-slate-400">
                        <span>#{i + 1} — {fn.tipo_alvo} @ {fn.depth_real_m}m</span>
                        <button onClick={() => setFalsoNegativos(prev => prev.filter(f => f.id !== fn.id))} className="text-red-400 hover:text-red-300">✕</button>
                      </div>
                    ))}
                  </div>
                )}

                {/* Add FN */}
                {!showFnForm ? (
                  <button onClick={() => setShowFnForm(true)} className="text-xs text-amber-400 hover:text-amber-300 underline">
                    + Adicionar Falso Negativo (o detector perdeu um alvo)
                  </button>
                ) : (
                  <div className="rounded-lg border border-amber-600/40 bg-amber-500/5 p-3 space-y-2">
                    <p className="text-xs font-semibold text-amber-400">Novo Falso Negativo</p>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">X (m) — opcional</label>
                        <input type="number" step={0.1} value={newFn.x_real_m} onChange={e => setNewFn(p => ({ ...p, x_real_m: e.target.value }))} className={inputCls} />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Prof. real (m) *</label>
                        <input type="number" step={0.01} value={newFn.depth_real_m} onChange={e => setNewFn(p => ({ ...p, depth_real_m: e.target.value }))} className={inputCls} />
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Tipo *</label>
                        <select value={newFn.tipo_alvo} onChange={e => setNewFn(p => ({ ...p, tipo_alvo: e.target.value }))} className={inputCls}>
                          {TIPOS_ALVO.map(t => <option key={t} value={t}>{t}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="block text-[10px] text-slate-400 mb-0.5">Fonte *</label>
                        <select value={newFn.fonte} onChange={e => setNewFn(p => ({ ...p, fonte: e.target.value }))} className={inputCls}>
                          <option value="escavacao">Escavação física</option>
                          <option value="cadastro_concessionaria">Cadastro de concessionária</option>
                          <option value="sondagem">Sondagem geotécnica</option>
                          <option value="avaliacao_especialista">Avaliação de especialista</option>
                        </select>
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button onClick={() => setShowFnForm(false)} className={btnSecondary}>Cancelar</button>
                      <button onClick={addFN} disabled={!newFn.depth_real_m} className={btnPrimary}>Adicionar FN</button>
                    </div>
                  </div>
                )}

                {errMsg && <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-2 py-1">{errMsg}</p>}

                <button
                  onClick={handleFinalize}
                  disabled={saving}
                  className="w-full rounded-lg bg-violet-500 hover:bg-violet-400 disabled:opacity-50 px-4 py-2 text-sm font-semibold text-white transition-colors"
                >
                  {saving ? "Salvando…" : "Concluir Sessão"}
                </button>
              </div>
            </div>
          </div>
        )}

        {wizardStep === "done" && (
          <div className="rounded-xl border border-green-600/40 bg-green-500/5 p-5 flex items-center justify-between">
            <p className="text-sm text-green-400">Sessão concluída e salva com sucesso.</p>
            <button onClick={() => setWizardStep("idle")} className={btnPrimary}>Nova sessão</button>
          </div>
        )}
      </div>

      {/* ── SEÇÃO 3: Histórico de sessões ─────────────────────────────────── */}
      <div>
        <h2 className="text-lg font-semibold text-slate-200 mb-3">Histórico de sessões</h2>
        {sessions.length === 0 ? (
          <p className="text-sm text-slate-600">Nenhuma sessão concluída ainda.</p>
        ) : (
          <div className="overflow-x-auto rounded-xl border border-slate-700">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-700 bg-slate-800/50">
                  <th className="text-left px-3 py-2 text-xs text-slate-400 font-medium">Data</th>
                  <th className="text-left px-3 py-2 text-xs text-slate-400 font-medium">Projeto / Perfil</th>
                  <th className="text-left px-3 py-2 text-xs text-slate-400 font-medium">Descrição</th>
                  <th className="text-right px-3 py-2 text-xs text-slate-400 font-medium">VP</th>
                  <th className="text-right px-3 py-2 text-xs text-slate-400 font-medium">FP</th>
                  <th className="text-right px-3 py-2 text-xs text-slate-400 font-medium">FN</th>
                  <th className="text-left px-3 py-2 text-xs text-slate-400 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} className="border-b border-slate-800 hover:bg-slate-800/30">
                    <td className="px-3 py-2 text-xs text-slate-500 font-mono whitespace-nowrap">
                      {new Date(s.created_at).toLocaleDateString("pt-BR")}
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-300">
                      {(s.projects as unknown as {nome: string} | null)?.nome ?? s.project_id.slice(0, 8)}
                      <span className="text-slate-500 ml-1">
                        {(s.gpr_profiles as unknown as {arquivo_dzt: string} | null)?.arquivo_dzt ?? ""}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-400 max-w-[200px] truncate">{s.descricao ?? "—"}</td>
                    <td className="px-3 py-2 text-xs text-green-400 text-right">{s.total_vp}</td>
                    <td className="px-3 py-2 text-xs text-red-400 text-right">{s.total_fp}</td>
                    <td className="px-3 py-2 text-xs text-amber-400 text-right">{s.total_fn}</td>
                    <td className="px-3 py-2">
                      <StatusBadge status={s.status} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Modal recalibração ─────────────────────────────────────────────── */}
      {recalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg overflow-y-auto max-h-[90vh]">
            <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-100">Resultado da Recalibração</h2>
              <button onClick={() => { setRecalModal(null); setRecalMsg(null); }} className="text-slate-400 hover:text-slate-200 text-xl">×</button>
            </div>

            <div className="p-6 space-y-4">
              <div className="flex flex-wrap gap-3 text-xs text-slate-400">
                <span>Gerado: {new Date(recalModal.gerado_em).toLocaleString("pt-BR")}</span>
                <span className="font-mono">{recalModalName}</span>
              </div>
              <div className="flex gap-3">
                <span className="text-xs text-slate-400">Amostras: <span className="text-slate-200">{recalModal.n_amostras}</span></span>
                <span className="text-xs text-green-400">VP: {recalModal.n_vp}</span>
                <span className="text-xs text-red-400">FP: {recalModal.n_fp}</span>
                <span className="text-xs font-bold text-slate-100">F1: {recalModal.f1_score.toFixed(3)}</span>
              </div>

              {/* Comparativo de thresholds */}
              <div className="rounded-lg border border-slate-700 overflow-hidden">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-slate-800 text-slate-400">
                      <th className="text-left px-3 py-2">Parâmetro</th>
                      <th className="text-right px-3 py-2">Atual</th>
                      <th className="text-right px-3 py-2 text-cyan-400">Sugerido</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(Object.entries(recalModal.thresholds_sugeridos) as [string, number][]).map(([k, v]) => (
                      <tr key={k} className="border-t border-slate-700">
                        <td className="px-3 py-1.5 font-mono text-slate-400">{k}</td>
                        <td className="px-3 py-1.5 text-right text-slate-400">{recalModal.thresholds_atuais[k as keyof typeof recalModal.thresholds_atuais]}</td>
                        <td className="px-3 py-1.5 text-right text-cyan-300 font-semibold">{v}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <p className="text-xs text-slate-500">{recalModal.notas}</p>

              {recalMsg && (
                <p className={`text-xs rounded px-2 py-1 ${recalMsg.startsWith("Erro") ? "text-red-400 bg-red-500/10" : "text-green-400 bg-green-500/10"}`}>
                  {recalMsg}
                </p>
              )}
            </div>

            <div className="px-6 py-4 border-t border-slate-700 flex gap-3 justify-end">
              <button onClick={() => { setRecalModal(null); setRecalMsg(null); }} className={btnSecondary}>Fechar</button>
              <button
                onClick={handleApplyRecal}
                disabled={applyingRecal}
                className="px-4 py-2 text-sm font-semibold bg-cyan-500 hover:bg-cyan-400 text-slate-950 rounded-lg transition-colors disabled:opacity-50"
              >
                {applyingRecal ? "Aplicando…" : "Aplicar ao preset padrão"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatCard({ label, value, color }: { label: string; value: number; color: "slate" | "green" | "red" | "amber" }) {
  const colors: Record<string, string> = {
    slate: "text-slate-100 border-slate-700",
    green: "text-green-400 border-green-600/40",
    red: "text-red-400 border-red-600/40",
    amber: "text-amber-400 border-amber-600/40",
  };
  return (
    <div className={`rounded-xl border ${colors[color]} bg-slate-800/40 p-4 text-center`}>
      <p className={`text-2xl font-bold ${colors[color].split(" ")[0]}`}>{value}</p>
      <p className="text-xs text-slate-500 mt-1">{label}</p>
    </div>
  );
}

function MiniChart({ label, data, total }: { label: string; data: Record<string, number>; total: number }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]).slice(0, 6);
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-3">
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">{label}</p>
      <div className="space-y-1.5">
        {entries.map(([k, n]) => (
          <div key={k}>
            <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
              <span className="truncate max-w-[140px]">{k}</span>
              <span>{n}</span>
            </div>
            <div className="h-1 rounded-full bg-slate-700">
              <div
                className="h-1 rounded-full bg-cyan-500"
                style={{ width: total > 0 ? `${(n / total) * 100}%` : "0%" }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function VerdictBtn({ label, title, active, color, onClick }: {
  label: string; title: string; active: boolean; color: "green" | "red" | "slate"; onClick: () => void;
}) {
  const cls: Record<string, string> = {
    green: active ? "bg-green-500 text-white border-green-500" : "border-slate-600 text-slate-400 hover:border-green-500 hover:text-green-400",
    red: active ? "bg-red-500 text-white border-red-500" : "border-slate-600 text-slate-400 hover:border-red-500 hover:text-red-400",
    slate: active ? "bg-slate-600 text-white border-slate-500" : "border-slate-600 text-slate-500 hover:border-slate-400",
  };
  return (
    <button
      title={title}
      onClick={onClick}
      className={`w-7 h-7 rounded border text-xs font-bold transition-colors ${cls[color]}`}
    >
      {label}
    </button>
  );
}

function MetaSelect({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <div>
      <label className="block text-xs text-slate-400 mb-1">{label}</label>
      <select value={value} onChange={e => onChange(e.target.value)} className={selectCls}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const map: Record<string, string> = {
    rascunho: "text-slate-400 bg-slate-700",
    concluida: "text-green-400 bg-green-500/10",
    usada_recalibracao: "text-violet-400 bg-violet-500/10",
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${map[status] ?? "text-slate-400 bg-slate-700"}`}>
      {status === "usada_recalibracao" ? "Usada em recalibracao" : status}
    </span>
  );
}

// ── CSS helpers ───────────────────────────────────────────────────────────────

const selectCls = "w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-cyan-500";
const inputCls = "w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-lg px-2 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-cyan-500";
const btnPrimary = "rounded-lg bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 px-4 py-1.5 text-sm font-semibold text-slate-950 transition-colors";
const btnSecondary = "rounded-lg border border-slate-600 text-slate-400 hover:text-slate-200 hover:border-slate-500 px-4 py-1.5 text-sm transition-colors";
