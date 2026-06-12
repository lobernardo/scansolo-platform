# Decisoes Tecnicas — Pipeline GPR ScanSOLO
> Atualizado: 2026-06-12
> Referencia: pipeline_v1.py v2.0.0

---

## D1: GPRPy em vez de readgssi para leitura de DZTs

**Decisao:** usar gprpy.gprpy como biblioteca de leitura/filtros, nao readgssi.

**Motivo:** readgssi nao exporta arrays numpy diretamente acessiveis para manipulacao
pos-filtro. GPRPy expoe prof.data como ndarray mutavel, permitindo:
- Captura de arr_raw antes de qualquer filtro
- Captura de arr_dewow_bp no meio da cadeia
- Aplicacao manual de tpow via _aplicar_tpow_manual (sem modificar prof.data)

**Trade-off:** GPRPy requer irlib para fkMigration (nao instalado). Solucao atual:
migracao Kirchhoff propria via numpy. Qualidade a validar com Amilson.

---

## D2: Migracao F-K via numpy proprio

**Decisao:** implementar Kirchhoff migration via numpy, nao usar GPRPy.fkMigration.

**Motivo:** GPRPy.fkMigration requer irlib que nao e instalavel no Railway Dockerfile.

**Status:** implementado, nao validado com Amilson. Comparacao quantitativa pendente.

---

## D3: Detector opera sobre arr_raw por padrao

**Decisao:** detector_input_mode default = "raw" (dado bruto, sem filtros).

**Motivo empirico (benchmark 2026-06-12, 4 DZTs PATIO):**
- arr_raw: 82% CurveFit, score medio 56.8
- arr_proc+AGC (v1.2.0): 24% CurveFit, 46% falsos positivos

**Causa fisica:** AGC distorce o formato das hiperboles (apice comprimido, asas amplificadas).
O CurveFit (minimos quadrados) falha porque o shape hiperbolico real foi destruido.

**Alternativa conservadora:** raw_dewow_bandpass (75% CF) — mais robusta contra picos de ruido
DC, porem ligeiramente menos candidatos.

---

## D4: Tres fluxos separados — cientifico, relatorio, detector

**Decisao:** separar o pipeline em 3 fluxos independentes a partir do ponto dewow+bp.

**Motivo:** cada finalidade tem requisitos opostos:
- Amilson (geofisico): quer ver o decaimento real de amplitude, refletores horizontais,
  relacoes de fase. BGRemoval e AGC destroem essa informacao.
- Cliente (PDF): quer imagem limpa, uniforme, legivel. BGRemoval + AGC sao necessarios.
- Detector: quer o formato correto das hiperboles para CurveFit convergir. AGC e prejudicial.

**Custo:** +~1s de processamento por DZT (tpow manual + SNR extra). Aceitavel.

---

## D5: SNR medido em 3 pontos do pipeline

**Decisao:** calcular Hilbert per-trace SNR em raw, cientifico e relatorio.

**Motivo:** permite rastreabilidade do impacto de cada etapa de filtragem:
- snr_raw: governa modo de processamento (minimo/padrao/agressivo)
- snr_cientifico: confirma que dewow+bp melhora SNR (esperado +5-6 dB em PATIO)
- snr_relatorio: documenta o impacto do bgremoval (sempre negativo em dB mas necessario visualmente)

**Observacao:** snr_relatorio negativo nao e problema — e esperado. O bgremoval remove a media
de 30 tracos, que inclui parte do sinal. O que importa e o resultado visual, nao o SNR absoluto.

---

## D6: Anotacoes desenhadas sobre radargrama_cientifico

**Decisao:** _anotada_completa.png e _anotada_alta_confianca.png sao geradas sobre
arr_cientifico (dewow+bp+tpow), nao sobre arr_proc (com AGC).

**Motivo:** a imagem entregue ao Amilson para revisao deve ser o radargrama_cientifico.
Mostrar as anotacoes sobre a imagem que ele vai usar facilita a validacao.
Mostrar sobre arr_proc (com AGC e bgremoval) seria inconsistente com o que ele aprova.

---

## D7: det_depth_min_m = 0.30m como filtro de airwave

**Decisao:** descartar candidatos com depth_m < 0.30m antes do CSV e do plot.

**Motivo:** na versao v1.2.0 (proc+AGC), 22/50 candidatos top eram airwave com depth<=0.18m,
score=15, fit_ok=False. Com detector_input_mode=raw, a airwave nao e equalizada e raramente
passa o gate Hough. Mas o filtro e mantido como salvaguarda para qualquer modo.

**Valor 0.30m:** conservador em relacao ao minimo esperado de alvo real (~0.20m de tubulacao
rasa). Em campo com Amilson, validar se ha alvos reais entre 0.20-0.30m.

---

## D8: _processada.png como alias backward compat

**Decisao:** manter _processada.png como copia exata de _radargrama_relatorio.png.

**Motivo:** worker (job_gpr.py) e frontend fazem referencia a imagem_processada_url que
apontava para _processada.png. Em vez de alterar todas as referencias, criamos o alias
via shutil.copy2. Migration de banco nao necessaria nesta versao.

**Impacto:** duplicacao de arquivo no Storage (~300KB por DZT). Aceitavel.

---

## D9: velocity_estimada por semblance (nao calibrada)

**Decisao:** usar semblance para estimar velocity (0.06-0.16 m/ns), nao valor fixo.

**Motivo:** velocity fixa (0.1 m/ns) gera profundidades erradas em solos heterogeneos.
Semblance e automatico e nao requer input humano.

**Limitacao:** sem alvo de profundidade conhecida, a velocity_estimada nao pode ser validada.
Todos os 4 DZTs PATIO tem velocity_usada = velocity_estimada (fonte: semblance).

**Pendencia:** sessao com Amilson usando DZT com alvo a profundidade conhecida.

---

## D10: Prompt GPT-4o em ingles, contexto minimo

**Decisao atual:** prompt GPT-4o em ingles, sem contexto do projeto.

**Problema identificado (2026-06-09):** 80% dos alvos classificados como galeria_concreto
em teste com 13 imagens RADAN do Amilson (HELPAVPA). Causa provavel: sem contexto, o modelo
escolhe a categoria de maior diâmetro como "segura".

**Mitigacao planejada:** adicionar ao prompt: tipo de obra, cliente, historico de tipos
no mesmo projeto, solo predominante.

**Prioridade:** media — nao altera o detector, so a interpretacao semantica dos alvos.

---

*Documento tecnico interno ScanSOLO — nao distribuir a clientes*
