// Phase 0 stub — Phase 1+: generate proper types with `supabase gen types`

export type UserRole = "operador_campo" | "tecnico" | "socio" | "admin";

export type ProjectStatus =
  | "criado"
  | "aguardando_arquivos"
  | "aguardando_confirmacao_operador"
  | "backup_em_andamento"
  | "backup_confirmado"
  | "aguardando_processamento"
  | "processando_gpr"
  | "gpr_concluido"
  | "processando_ia"
  | "ia_concluida"
  | "ia_pendente_erro"
  | "aguardando_decisao_revisao"
  | "revisao_opcional"
  | "revisao_em_andamento"
  | "revisao_concluida"
  | "aguardando_cartografia"
  | "cartografia_concluida"
  | "cartografia_pendente_dados"
  | "aguardando_relatorio"
  | "relatorio_em_andamento"
  | "relatorio_gerado"
  | "aguardando_aprovacao"
  | "finalizado"
  | "erro"
  | "pendente_dados";

export type JobType = "gpr" | "ia" | "cartografia" | "relatorio";

export type JobStatus =
  | "aguardando"
  | "processando_gpr"
  | "processando_ia"
  | "processando"
  | "concluido"
  | "erro";

export type ReviewStatus = "pendente" | "aprovado" | "descartado" | "ajustado";

export type SaidaDesejada =
  | "autocad"
  | "google_earth"
  | "ambos"
  | "decidir_depois";

export interface Profile {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  active: boolean;
  created_at: string;
}

export interface Project {
  id: string;
  nome: string;
  cliente: string;
  local: string | null;
  estado: string;
  endereco: string | null;
  data_levantamento: string;
  codigo_interno: string | null;
  tipo_servico: string | null;
  equipamento_gpr: string | null;
  antena_freq_mhz: number | null;
  tem_pipe_locator: boolean | null;
  tem_dzg: boolean | null;
  tem_kml: boolean | null;
  tem_dwg: boolean | null;
  saida_desejada: SaidaDesejada | null;
  observacoes: string | null;
  prioridade: "normal" | "urgente" | "baixa" | null;
  prazo_desejado: string | null;
  status: ProjectStatus;
  dropbox_project_path: string | null;
  created_by: string | null;
  assigned_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessingJob {
  id: string;
  project_id: string;
  job_type: JobType;
  status: JobStatus;
  tentativas: number;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  logs_path: string | null;
  worker_version: string | null;
  created_at: string;
}
