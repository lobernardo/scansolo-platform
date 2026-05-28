export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      ai_interpretations: {
        Row: {
          created_at: string
          custo_usd: number | null
          ia_confianca: string | null
          ia_descricao: string | null
          ia_justificativa_tecnica: string | null
          ia_justificativa_visual: string | null
          ia_recomendacao: string | null
          ia_tipo_sugerido: string | null
          id: string
          model_usado: string | null
          observacoes: string | null
          raw_response_json: Json | null
          target_id: string
          tokens_usados: number | null
          vai_para_planta_sugerido: boolean | null
          vai_para_relatorio_sugerido: boolean | null
        }
        Insert: {
          created_at?: string
          custo_usd?: number | null
          ia_confianca?: string | null
          ia_descricao?: string | null
          ia_justificativa_tecnica?: string | null
          ia_justificativa_visual?: string | null
          ia_recomendacao?: string | null
          ia_tipo_sugerido?: string | null
          id?: string
          model_usado?: string | null
          observacoes?: string | null
          raw_response_json?: Json | null
          target_id: string
          tokens_usados?: number | null
          vai_para_planta_sugerido?: boolean | null
          vai_para_relatorio_sugerido?: boolean | null
        }
        Update: {
          created_at?: string
          custo_usd?: number | null
          ia_confianca?: string | null
          ia_descricao?: string | null
          ia_justificativa_tecnica?: string | null
          ia_justificativa_visual?: string | null
          ia_recomendacao?: string | null
          ia_tipo_sugerido?: string | null
          id?: string
          model_usado?: string | null
          observacoes?: string | null
          raw_response_json?: Json | null
          target_id?: string
          tokens_usados?: number | null
          vai_para_planta_sugerido?: boolean | null
          vai_para_relatorio_sugerido?: boolean | null
        }
        Relationships: [
          {
            foreignKeyName: "ai_interpretations_target_id_fkey"
            columns: ["target_id"]
            isOneToOne: false
            referencedRelation: "detected_targets"
            referencedColumns: ["id"]
          },
        ]
      }
      audit_logs: {
        Row: {
          action: string
          created_at: string
          entity_id: string | null
          entity_type: string | null
          id: string
          ip_address: string | null
          metadata_json: Json | null
          project_id: string | null
          user_id: string | null
        }
        Insert: {
          action: string
          created_at?: string
          entity_id?: string | null
          entity_type?: string | null
          id?: string
          ip_address?: string | null
          metadata_json?: Json | null
          project_id?: string | null
          user_id?: string | null
        }
        Update: {
          action?: string
          created_at?: string
          entity_id?: string | null
          entity_type?: string | null
          id?: string
          ip_address?: string | null
          metadata_json?: Json | null
          project_id?: string | null
          user_id?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "audit_logs_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "audit_logs_user_id_fkey"
            columns: ["user_id"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      cartography_outputs: {
        Row: {
          created_at: string
          csv_path: string | null
          dxf_dropbox_path: string | null
          dxf_storage_url: string | null
          geojson_path: string | null
          id: string
          kml_dropbox_path: string | null
          kml_storage_url: string | null
          output_type: Database["public"]["Enums"]["output_type"] | null
          project_id: string
          status: string
        }
        Insert: {
          created_at?: string
          csv_path?: string | null
          dxf_dropbox_path?: string | null
          dxf_storage_url?: string | null
          geojson_path?: string | null
          id?: string
          kml_dropbox_path?: string | null
          kml_storage_url?: string | null
          output_type?: Database["public"]["Enums"]["output_type"] | null
          project_id: string
          status?: string
        }
        Update: {
          created_at?: string
          csv_path?: string | null
          dxf_dropbox_path?: string | null
          dxf_storage_url?: string | null
          geojson_path?: string | null
          id?: string
          kml_dropbox_path?: string | null
          kml_storage_url?: string | null
          output_type?: Database["public"]["Enums"]["output_type"] | null
          project_id?: string
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "cartography_outputs_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      detected_targets: {
        Row: {
          arquivo_dzt: string
          confianca_tipo: string | null
          confidence_label_relatorio: string | null
          confidence_label_tecnico: string | null
          confidence_score: number | null
          created_at: string
          crop_url: string | null
          depth_m: number | null
          diam_confianca: string | null
          diam_est_m: number | null
          evidencia_raw: boolean | null
          evidencia_sem_agc: boolean | null
          fit_ok: boolean | null
          id: string
          json_tecnico: Json | null
          motivo_confianca: string | null
          profile_id: string
          project_id: string
          rank: number | null
          run_id: string
          snr_local: number | null
          tipo_material: string | null
          x_m: number | null
        }
        Insert: {
          arquivo_dzt: string
          confianca_tipo?: string | null
          confidence_label_relatorio?: string | null
          confidence_label_tecnico?: string | null
          confidence_score?: number | null
          created_at?: string
          crop_url?: string | null
          depth_m?: number | null
          diam_confianca?: string | null
          diam_est_m?: number | null
          evidencia_raw?: boolean | null
          evidencia_sem_agc?: boolean | null
          fit_ok?: boolean | null
          id?: string
          json_tecnico?: Json | null
          motivo_confianca?: string | null
          profile_id: string
          project_id: string
          rank?: number | null
          run_id: string
          snr_local?: number | null
          tipo_material?: string | null
          x_m?: number | null
        }
        Update: {
          arquivo_dzt?: string
          confianca_tipo?: string | null
          confidence_label_relatorio?: string | null
          confidence_label_tecnico?: string | null
          confidence_score?: number | null
          created_at?: string
          crop_url?: string | null
          depth_m?: number | null
          diam_confianca?: string | null
          diam_est_m?: number | null
          evidencia_raw?: boolean | null
          evidencia_sem_agc?: boolean | null
          fit_ok?: boolean | null
          id?: string
          json_tecnico?: Json | null
          motivo_confianca?: string | null
          profile_id?: string
          project_id?: string
          rank?: number | null
          run_id?: string
          snr_local?: number | null
          tipo_material?: string | null
          x_m?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "detected_targets_profile_id_fkey"
            columns: ["profile_id"]
            isOneToOne: false
            referencedRelation: "gpr_profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "detected_targets_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      gpr_profiles: {
        Row: {
          arquivo_dzt: string
          config_hash: string | null
          created_at: string
          csv_alvos_url: string | null
          distancia_max_m: number | null
          dropbox_output_path: string | null
          id: string
          imagem_alta_conf_url: string | null
          imagem_anotada_url: string | null
          imagem_bruta_url: string | null
          imagem_processada_url: string | null
          n_amostras: number | null
          n_tracos: number | null
          profundidade_max_m: number | null
          project_id: string
          run_id: string
          status: string
          velocity_calibrada: boolean | null
          velocity_mns: number | null
        }
        Insert: {
          arquivo_dzt: string
          config_hash?: string | null
          created_at?: string
          csv_alvos_url?: string | null
          distancia_max_m?: number | null
          dropbox_output_path?: string | null
          id?: string
          imagem_alta_conf_url?: string | null
          imagem_anotada_url?: string | null
          imagem_bruta_url?: string | null
          imagem_processada_url?: string | null
          n_amostras?: number | null
          n_tracos?: number | null
          profundidade_max_m?: number | null
          project_id: string
          run_id: string
          status?: string
          velocity_calibrada?: boolean | null
          velocity_mns?: number | null
        }
        Update: {
          arquivo_dzt?: string
          config_hash?: string | null
          created_at?: string
          csv_alvos_url?: string | null
          distancia_max_m?: number | null
          dropbox_output_path?: string | null
          id?: string
          imagem_alta_conf_url?: string | null
          imagem_anotada_url?: string | null
          imagem_bruta_url?: string | null
          imagem_processada_url?: string | null
          n_amostras?: number | null
          n_tracos?: number | null
          profundidade_max_m?: number | null
          project_id?: string
          run_id?: string
          status?: string
          velocity_calibrada?: boolean | null
          velocity_mns?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "gpr_profiles_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      processing_jobs: {
        Row: {
          created_at: string
          error_message: string | null
          finished_at: string | null
          id: string
          job_type: Database["public"]["Enums"]["job_type"]
          logs_path: string | null
          project_id: string
          started_at: string | null
          status: Database["public"]["Enums"]["job_status"]
          tentativas: number
          worker_version: string | null
        }
        Insert: {
          created_at?: string
          error_message?: string | null
          finished_at?: string | null
          id?: string
          job_type: Database["public"]["Enums"]["job_type"]
          logs_path?: string | null
          project_id: string
          started_at?: string | null
          status?: Database["public"]["Enums"]["job_status"]
          tentativas?: number
          worker_version?: string | null
        }
        Update: {
          created_at?: string
          error_message?: string | null
          finished_at?: string | null
          id?: string
          job_type?: Database["public"]["Enums"]["job_type"]
          logs_path?: string | null
          project_id?: string
          started_at?: string | null
          status?: Database["public"]["Enums"]["job_status"]
          tentativas?: number
          worker_version?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "processing_jobs_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      profiles: {
        Row: {
          active: boolean
          created_at: string
          email: string
          id: string
          name: string
          role: Database["public"]["Enums"]["user_role"]
        }
        Insert: {
          active?: boolean
          created_at?: string
          email: string
          id: string
          name: string
          role?: Database["public"]["Enums"]["user_role"]
        }
        Update: {
          active?: boolean
          created_at?: string
          email?: string
          id?: string
          name?: string
          role?: Database["public"]["Enums"]["user_role"]
        }
        Relationships: []
      }
      project_files: {
        Row: {
          created_at: string
          dropbox_path: string | null
          extension: string | null
          file_name: string
          file_type: string | null
          hash_sha256: string | null
          id: string
          project_id: string
          size_bytes: number | null
          status: Database["public"]["Enums"]["file_status"]
          supabase_storage_path: string | null
          uploaded_by: string | null
          version: number
        }
        Insert: {
          created_at?: string
          dropbox_path?: string | null
          extension?: string | null
          file_name: string
          file_type?: string | null
          hash_sha256?: string | null
          id?: string
          project_id: string
          size_bytes?: number | null
          status?: Database["public"]["Enums"]["file_status"]
          supabase_storage_path?: string | null
          uploaded_by?: string | null
          version?: number
        }
        Update: {
          created_at?: string
          dropbox_path?: string | null
          extension?: string | null
          file_name?: string
          file_type?: string | null
          hash_sha256?: string | null
          id?: string
          project_id?: string
          size_bytes?: number | null
          status?: Database["public"]["Enums"]["file_status"]
          supabase_storage_path?: string | null
          uploaded_by?: string | null
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "project_files_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "project_files_uploaded_by_fkey"
            columns: ["uploaded_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      projects: {
        Row: {
          antena_freq_mhz: number | null
          assigned_to: string | null
          cliente: string
          codigo_interno: string | null
          created_at: string
          created_by: string | null
          data_levantamento: string
          dropbox_project_path: string | null
          endereco: string | null
          equipamento_gpr: string | null
          estado: string
          id: string
          local: string | null
          nome: string
          observacoes: string | null
          prazo_desejado: string | null
          prioridade: string | null
          saida_desejada: Database["public"]["Enums"]["saida_desejada"] | null
          status: Database["public"]["Enums"]["project_status"]
          tem_dwg: boolean | null
          tem_dzg: boolean | null
          tem_kml: boolean | null
          tem_pipe_locator: boolean | null
          tipo_servico: string | null
          updated_at: string
        }
        Insert: {
          antena_freq_mhz?: number | null
          assigned_to?: string | null
          cliente: string
          codigo_interno?: string | null
          created_at?: string
          created_by?: string | null
          data_levantamento: string
          dropbox_project_path?: string | null
          endereco?: string | null
          equipamento_gpr?: string | null
          estado: string
          id?: string
          local?: string | null
          nome: string
          observacoes?: string | null
          prazo_desejado?: string | null
          prioridade?: string | null
          saida_desejada?: Database["public"]["Enums"]["saida_desejada"] | null
          status?: Database["public"]["Enums"]["project_status"]
          tem_dwg?: boolean | null
          tem_dzg?: boolean | null
          tem_kml?: boolean | null
          tem_pipe_locator?: boolean | null
          tipo_servico?: string | null
          updated_at?: string
        }
        Update: {
          antena_freq_mhz?: number | null
          assigned_to?: string | null
          cliente?: string
          codigo_interno?: string | null
          created_at?: string
          created_by?: string | null
          data_levantamento?: string
          dropbox_project_path?: string | null
          endereco?: string | null
          equipamento_gpr?: string | null
          estado?: string
          id?: string
          local?: string | null
          nome?: string
          observacoes?: string | null
          prazo_desejado?: string | null
          prioridade?: string | null
          saida_desejada?: Database["public"]["Enums"]["saida_desejada"] | null
          status?: Database["public"]["Enums"]["project_status"]
          tem_dwg?: boolean | null
          tem_dzg?: boolean | null
          tem_kml?: boolean | null
          tem_pipe_locator?: boolean | null
          tipo_servico?: string | null
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "projects_assigned_to_fkey"
            columns: ["assigned_to"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "projects_created_by_fkey"
            columns: ["created_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
        ]
      }
      report_outputs: {
        Row: {
          approved_by: string | null
          created_at: string
          dados_usados_json: Json | null
          docx_dropbox_path: string | null
          generated_by: string | null
          id: string
          pdf_dropbox_path: string | null
          pdf_storage_url: string | null
          project_id: string
          status: string
          version: number
        }
        Insert: {
          approved_by?: string | null
          created_at?: string
          dados_usados_json?: Json | null
          docx_dropbox_path?: string | null
          generated_by?: string | null
          id?: string
          pdf_dropbox_path?: string | null
          pdf_storage_url?: string | null
          project_id: string
          status?: string
          version?: number
        }
        Update: {
          approved_by?: string | null
          created_at?: string
          dados_usados_json?: Json | null
          docx_dropbox_path?: string | null
          generated_by?: string | null
          id?: string
          pdf_dropbox_path?: string | null
          pdf_storage_url?: string | null
          project_id?: string
          status?: string
          version?: number
        }
        Relationships: [
          {
            foreignKeyName: "report_outputs_approved_by_fkey"
            columns: ["approved_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "report_outputs_generated_by_fkey"
            columns: ["generated_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "report_outputs_project_id_fkey"
            columns: ["project_id"]
            isOneToOne: false
            referencedRelation: "projects"
            referencedColumns: ["id"]
          },
        ]
      }
      technical_reviews: {
        Row: {
          diametro_ajustado: number | null
          id: string
          observacao: string | null
          profundidade_ajustada: number | null
          reviewed_at: string | null
          reviewed_by: string | null
          status_review: Database["public"]["Enums"]["review_status"]
          target_id: string
          tipo_final: string | null
          vai_para_planta: boolean | null
          vai_para_relatorio: boolean | null
        }
        Insert: {
          diametro_ajustado?: number | null
          id?: string
          observacao?: string | null
          profundidade_ajustada?: number | null
          reviewed_at?: string | null
          reviewed_by?: string | null
          status_review?: Database["public"]["Enums"]["review_status"]
          target_id: string
          tipo_final?: string | null
          vai_para_planta?: boolean | null
          vai_para_relatorio?: boolean | null
        }
        Update: {
          diametro_ajustado?: number | null
          id?: string
          observacao?: string | null
          profundidade_ajustada?: number | null
          reviewed_at?: string | null
          reviewed_by?: string | null
          status_review?: Database["public"]["Enums"]["review_status"]
          target_id?: string
          tipo_final?: string | null
          vai_para_planta?: boolean | null
          vai_para_relatorio?: boolean | null
        }
        Relationships: [
          {
            foreignKeyName: "technical_reviews_reviewed_by_fkey"
            columns: ["reviewed_by"]
            isOneToOne: false
            referencedRelation: "profiles"
            referencedColumns: ["id"]
          },
          {
            foreignKeyName: "technical_reviews_target_id_fkey"
            columns: ["target_id"]
            isOneToOne: false
            referencedRelation: "detected_targets"
            referencedColumns: ["id"]
          },
        ]
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      auth_user_role: {
        Args: never
        Returns: Database["public"]["Enums"]["user_role"]
      }
    }
    Enums: {
      file_status: "pendente" | "confirmado" | "erro"
      job_status:
        | "aguardando"
        | "processando_gpr"
        | "processando_ia"
        | "processando"
        | "concluido"
        | "erro"
      job_type: "gpr" | "ia" | "cartografia" | "relatorio"
      output_type: "dxf" | "kml" | "geojson" | "csv"
      project_status:
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
        | "pendente_dados"
      review_status: "pendente" | "aprovado" | "descartado" | "ajustado"
      saida_desejada: "autocad" | "google_earth" | "ambos" | "decidir_depois"
      user_role: "operador_campo" | "tecnico" | "socio" | "admin"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      file_status: ["pendente", "confirmado", "erro"],
      job_status: [
        "aguardando",
        "processando_gpr",
        "processando_ia",
        "processando",
        "concluido",
        "erro",
      ],
      job_type: ["gpr", "ia", "cartografia", "relatorio"],
      output_type: ["dxf", "kml", "geojson", "csv"],
      project_status: [
        "criado",
        "aguardando_arquivos",
        "aguardando_confirmacao_operador",
        "backup_em_andamento",
        "backup_confirmado",
        "aguardando_processamento",
        "processando_gpr",
        "gpr_concluido",
        "processando_ia",
        "ia_concluida",
        "ia_pendente_erro",
        "aguardando_decisao_revisao",
        "revisao_opcional",
        "revisao_em_andamento",
        "revisao_concluida",
        "aguardando_cartografia",
        "cartografia_concluida",
        "cartografia_pendente_dados",
        "aguardando_relatorio",
        "relatorio_em_andamento",
        "relatorio_gerado",
        "aguardando_aprovacao",
        "finalizado",
        "erro",
        "pendente_dados",
      ],
      review_status: ["pendente", "aprovado", "descartado", "ajustado"],
      saida_desejada: ["autocad", "google_earth", "ambos", "decidir_depois"],
      user_role: ["operador_campo", "tecnico", "socio", "admin"],
    },
  },
} as const
