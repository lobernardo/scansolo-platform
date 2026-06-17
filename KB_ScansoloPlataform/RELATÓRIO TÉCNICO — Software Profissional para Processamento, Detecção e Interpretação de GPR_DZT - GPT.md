# **RELATÓRIO TÉCNICO — Software Profissional para Processamento, Detecção e Interpretação de GPR/DZT**

**Base de pesquisa:** documentação oficial GSSI/RADAN/SIR-3000, Sensors & Software/EKKO, Sandmeier/ReflexW, MALÅ/Guideline Geo, IDS GeoRadar, ImpulseRadar, Roadscanners/Road Doctor, EPA/CLU-IN, papers científicos e bibliotecas open source.

**Legenda usada no relatório:**

* **\[FATO DOCUMENTADO\]**: confirmado em documentação oficial, manual, paper ou repositório.  
* **\[CONSENSO TÉCNICO\]**: prática recorrente em manuais, softwares e literatura.  
* **\[INFERÊNCIA TÉCNICA\]**: conclusão de engenharia derivada das fontes.  
* **\[NÃO ENCONTRADO NAS FONTES PESQUISADAS\]**: não localizado com evidência documental suficiente.

---

## **1\. Sumário Executivo**

Um software profissional de GPR não deve ser construído apenas como “conversor DZT → imagem”. O núcleo correto é um **pipeline auditável de dados geofísicos**, com preservação do dado bruto, controle de metadados, filtros parametrizados, métricas de qualidade, detecção assistida e interpretação com rastreabilidade.

A literatura e os manuais convergem em quatro pontos centrais:

1. **A interpretação depende fortemente da qualidade do dado bruto.** GPR mede tempo duplo de percurso e depende da velocidade eletromagnética no meio; a conversão tempo-profundidade usa velocidade estimada por permissividade, refletor conhecido, CMP ou valores de literatura.  
2. **Filtros melhoram legibilidade, mas podem destruir informação geofísica.** Background removal, por exemplo, remove bandas horizontais, mas também pode remover refletores reais como lençol freático ou limites estratigráficos.  
3. **A ordem do processamento importa.** O manual do RADAN recomenda Time Zero antes de Background Removal, porque o background removal pode remover o pulso de acoplamento direto/superfície.  
4. **IA é promissora, mas não substitui validação geofísica.** Revisões recentes mostram uso de SVM, KNN, ANN, HMM, CNN e deep learning em A-scan, B-scan e C-scan, mas ainda há limitações de datasets, generalização e dependência de pré-processamento.

**Decisão arquitetural recomendada:** criar três ramificações de processamento:

| Ramificação | Objetivo | Característica |
| ----- | ----- | ----- |
| **Bruta / científica** | Preservar o máximo de informação física | mínimo processamento, amplitude rastreável |
| **Visual / relatório** | Melhor leitura humana | ganho, contraste, filtros de ruído, imagem limpa |
| **Detecção / IA** | Maximizar alvos detectáveis e reduzir falso positivo | processamento calibrado por métricas SNR/SCR/TCR e validação por ROI |

---

## **2\. Fontes Utilizadas**

### **2.1 Documentação oficial e manuais**

* **GSSI SIR-3000 Manual**: contém o Addendum A com estrutura de header RADAN/DZT para SIR-3000. O próprio manual declara que a informação é apenas informativa e não suportada pelo suporte técnico da GSSI.  
* **GSSI RADAN 7 Manual**: documenta Time Zero, Background Removal, FIR filters, migration, exportações e módulos.  
* **Sensors & Software EKKO Processing Module User Guide**: documenta background average subtraction, background subtraction, dewow, average frequency spectrum, mute, rectify e amplitude fall-off.  
* **Sandmeier ReflexW GPR Processing Guide**: documenta fluxo de importação, filtros principais, dewow, gain, background removal, clutter reduction e migration.  
* **MALÅ Vision Desktop User Guide**: documenta toolbox de filtros, FK migration e ajuste de velocidade até colapsar pernas de hipérbole.  
* **IDS GeoRadar / GRED HD**: página oficial informa uso de background removal, gain e mitigação no domínio do tempo para facilitar interpretação de B-scan.  
* **ImpulseRadar Condor / ViewR**: documentação oficial descreve Condor como software de processamento, visualização e interpretação 3D GPR para dados Raptor; ViewR é voltado a inspeção rápida e preparação de dados.  
* **Road Doctor / Roadscanners**: documentação oficial descreve sincronização de múltiplas fontes, exportação KML/ESRI/DXF e IA para layer tracing e object detection.

### **2.2 Fontes técnicas e científicas**

* **EPA — Ground Penetrating Radar**: fundamentos de velocidade, permissividade, TWT e profundidade.  
* **CLU-IN — Ground Penetrating Radar**: frequência, penetração, resolução, limitações e necessidade de validação.  
* **Ciampoli et al. 2019 — Signal Processing of GPR Data for Road Surveys**: processamento de sinal para levantamentos rodoviários, band-pass e qualidade do dado.  
* **Dou et al. 2017 — Real-Time Hyperbola Recognition and Fitting**: detecção de hipérboles com C3, pré-processamento, machine learning e ajuste geométrico.  
* **Bai et al. 2023 — Review ML/DL GPR**: revisão de machine learning e deep learning aplicados a A-scan, B-scan e C-scan.

---

## **3\. Fundamentos de GPR**

### **3.1 Princípio físico**

**\[FATO DOCUMENTADO\]** GPR utiliza pulsos eletromagnéticos de alta frequência que se propagam no meio e são refletidos, refratados ou espalhados quando encontram contrastes de propriedades eletromagnéticas, principalmente permissividade dielétrica, condutividade e permeabilidade magnética. A EPA descreve que a profundidade é estimada por tempo duplo de percurso, velocidade da onda e aproximação `v ≈ c / √ε`.

A equação base para conversão tempo-profundidade em configuração monostática/bistática simplificada é:

z=v⋅t2z \= \\frac{v \\cdot t}{2}z=2v⋅t​

Onde:

* `z` \= profundidade estimada;  
* `v` \= velocidade da onda no meio;  
* `t` \= tempo duplo de percurso;  
* o fator 2 existe porque o sinal percorre ida e volta.

### **3.2 Frequência, resolução e profundidade**

**\[FATO DOCUMENTADO\]** Antenas de menor frequência tendem a penetrar mais, mas com menor resolução; antenas de maior frequência fornecem maior resolução, mas menor profundidade de investigação. O CLU-IN descreve frequências típicas entre 10 e 1.000 MHz, com equipamentos comerciais chegando a faixas mais altas, e reforça o trade-off entre frequência, penetração e resolução.

**\[CONSENSO TÉCNICO\]** Para software, isso significa que o pipeline deve conhecer ou inferir:

* frequência central da antena;  
* janela temporal;  
* amostragem;  
* velocidade/permissividade;  
* distância entre traços;  
* objetivo do levantamento: utilidades, concreto, geologia rasa, pavimento, cavidades, arqueologia etc.

### **3.3 Hipérboles**

**\[FATO DOCUMENTADO\]** Objetos pontuais ou aproximadamente cilíndricos aparecem como hipérboles em B-scans porque a antena detecta o alvo antes, durante e depois de passar sobre ele. O manual do RADAN descreve que objetos de dimensões finitas podem aparecer como refletores hiperbólicos e que a migration busca colapsar a hipérbole em um ponto representando o topo do alvo.

### **3.4 Limitações práticas**

**\[FATO DOCUMENTADO\]** Interpretação de GPR não é única; o CLU-IN recomenda integração com métodos diretos ou outros métodos geofísicos para reduzir incerteza.

Limitações principais:

| Limitação | Impacto |
| ----- | ----- |
| Solo condutivo/úmido/argiloso | maior atenuação, menor profundidade |
| Frequência alta | ótima resolução, baixa penetração |
| Frequência baixa | melhor penetração, baixa resolução |
| Velocidade mal estimada | erro direto na profundidade |
| Background removal agressivo | pode apagar refletores horizontais reais |
| AGC excessivo | melhora visual, mas distorce amplitudes |
| Migration com velocidade errada | hiperfoco, submigração ou sobremigração |
| Falta de ground truth | reduz confiabilidade da IA |

---

## **4\. Formato DZT**

### **4.1 Natureza do DZT**

**\[FATO DOCUMENTADO\]** DZT é o formato nativo dos sistemas GSSI. A documentação do readgssi descreve DZT como formato binário que segue regras estritas e exige software especializado; ela aponta a página 55 do manual GSSI SIR-3000 como referência de formato.

**\[FATO DOCUMENTADO\]** O manual SIR-3000 contém um “RADAN File Header Format” no Addendum A, mas a própria GSSI informa que esse conteúdo é apenas informativo, não suportado pelo suporte técnico e voltado a usuários confortáveis em ambiente C.

### **4.2 Estrutura geral**

**\[FATO DOCUMENTADO\]** O Addendum A define constantes como `MINHEADSIZE = 1024`, `PARAREASIZE = 128` e estruturas internas como `tagRFDate`, `tagRFCoords`, `RGPS` e `tagRFHeader`.

Estrutura lógica recomendada para leitura:

```
Arquivo .DZT
│
├── Header mínimo / principal
│   ├── Identificação do arquivo
│   ├── Número de amostras por traço
│   ├── Bits por amostra
│   ├── Range temporal
│   ├── Ganhos
│   ├── Número de canais
│   ├── Constante dielétrica
│   ├── Profundidade aproximada
│   ├── Nome da antena
│   ├── Sistema / versão
│   └── Offsets para áreas adicionais
│
├── Área de parâmetros
├── Área GPS, quando existente
├── Área textual / notas
├── Área de processamento, quando existente
└── Dados dos traços
   ├── Trace 1: amostras no tempo
   ├── Trace 2: amostras no tempo
   └── Trace N: amostras no tempo
```

### **4.3 Campos relevantes do header**

Campos documentados no Addendum A do SIR-3000:

| Campo | Função esperada |
| ----- | ----- |
| `rh_nsamp` | número de amostras por scan/traço |
| `rh_bits` | bits por amostra |
| `rh_zero` | posição/amostra de zero |
| `rhf_sps` | scans por segundo |
| `rhf_spm` | scans por metro |
| `rhf_mpm` | marcas por metro |
| `rhf_position` | posição |
| `rhf_range` | range temporal |
| `rh_npass` | passes |
| `rh_rgain` / `rh_nrgain` | referência e quantidade de ganhos |
| `rh_text` / `rh_ntext` | área textual |
| `rh_proc` / `rh_nproc` | área de processamento |
| `rh_nchan` | número de canais |
| `rhf_epsr` | permissividade dielétrica relativa usada |
| `rhf_top` | topo |
| `rhf_depth` | profundidade estimada |
| `rh_antname` | nome da antena |
| `rh_system` | sistema |
| `rh_name` | nome do arquivo |
| GPS records | latitude, longitude, altitude, tempo, quando disponível |

Fonte: estrutura `tagRFHeader` do Addendum A do manual SIR-3000.

### **4.4 Estratégia de parsing recomendada**

**\[INFERÊNCIA TÉCNICA\]** Como a documentação oficial é informativa e não garantida para todas as versões, o parser deve ser defensivo.

Pipeline de parsing:

```
1. Abrir arquivo binário
2. Ler primeiros 1024 bytes
3. Interpretar header principal com endianness validado
4. Validar:
  - nsamp > 0
  - bits ∈ {8, 16, 32}
  - range temporal plausível
  - tamanho de arquivo compatível com nsamp × ntraces × bytes/sample
5. Identificar áreas adicionais:
  - texto
  - ganho
  - processamento
  - GPS
6. Ler matriz de traços
7. Converter para formato interno float32/float64
8. Preservar:
  - raw samples
  - header bruto
  - metadados interpretados
  - warnings de inconsistência
```

### **4.5 Bibliotecas úteis para DZT**

| Biblioteca | Linguagem | Função | Licença/maturidade |
| ----- | ----- | ----- | ----- |
| `readgssi` | Python | ler, processar e exibir dados GSSI/DZT | projeto específico para dados GSSI |
| `GPRPy` | Python | processamento e visualização GPR; suporta DZT, DT1 e BSQ | open source, MIT no GitHub |
| `RGPR` | R | ler, exportar, analisar, processar e visualizar GPR | open source/GPL, multi-OS |
| `pygssi` | Python | abrir arquivos GSSI, acessar header e retornos brutos | open source, com limitações declaradas no parsing de gain |
| `gprMax` | Python/Cython/ecossistema científico | simulação FDTD de GPR, útil para dados sintéticos | GPLv3+, resolve Maxwell em 3D via FDTD |

**Rust:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS** como biblioteca madura e confiável para parsing/processamento GPR/DZT.

---

## **5\. Pipeline de Processamento Utilizado na Indústria**

### **5.1 Fluxo recomendado**

**\[CONSENSO TÉCNICO\]** Manuais comerciais e guias técnicos indicam um fluxo geral:

```
Arquivo bruto
↓
Leitura + validação de metadados
↓
Correção geométrica / distância / marcas
↓
Time Zero Correction
↓
Dewow / DC removal
↓
Filtro temporal: bandpass / notch / band reject
↓
Background removal / clutter suppression
↓
Ganho: SEC / power gain / exponential gain / AGC
↓
Equalização / normalização de traços
↓
Estimativa de velocidade
↓
Migration
↓
Conversão tempo-profundidade
↓
Radargrama final
↓
Detecção de alvos
↓
Interpretação geofísica / IA
↓
Relatório
```

O ReflexW apresenta filtros principais como static correction, time-gain, dewow/bandpass e clutter reduction. O RADAN documenta Time Zero, Background Removal, FIR filters, Frequency Filtering e Migration. O EKKO documenta background average subtraction, background subtraction, dewow e análise espectral.

### **5.2 Ordem crítica**

| Ordem | Etapa | Motivo |
| ----- | ----- | ----- |
| 1 | Leitura e validação | sem metadados confiáveis não há profundidade confiável |
| 2 | Distance normalization | corrige espaçamento irregular entre traços |
| 3 | Time Zero | define topo do scan próximo à superfície |
| 4 | Dewow / DC removal | remove componentes de baixa frequência e drift |
| 5 | Bandpass / notch | remove frequências fora da banda útil |
| 6 | Background removal | remove bandas horizontais e acoplamento direto residual |
| 7 | Gain / AGC | compensa decaimento com o tempo/profundidade |
| 8 | Migration | colapsa hipérboles após velocidade estimada |
| 9 | Depth conversion | converte tempo para profundidade usando velocidade |
| 10 | Detecção/IA | roda sobre dado calibrado e com métricas registradas |

**\[FATO DOCUMENTADO\]** O RADAN recomenda Time Zero antes de Background Removal, pois o filtro remove o pulso de superfície/acoplamento direto.

---

## **6\. Processamento de Radargramas**

### **6.1 Técnicas principais**

| Técnica | Objetivo | Formulação resumida | Benefício | Limitação | Impacto no SNR |
| ----- | ----- | ----- | ----- | ----- | ----- |
| **Time Zero Correction** | alinhar superfície/topo do scan | deslocamento vertical por traço ou global | melhora cálculo de profundidade | erro desloca todas as profundidades | indireto |
| **Dewow** | remover drift/baixa frequência | `x’(t)=x(t)-mean_window(x)` | remove oscilação lenta | pode alterar forma do pulso | melhora se wow for ruído |
| **Bandpass** | manter banda útil | `Y’(ω)=Y(ω)H(ω)` | remove ruído fora da banda | passband ruim corta sinal real | geralmente melhora |
| **Band Reject / Notch** | remover frequência específica | rejeição estreita em frequência | remove interferência | pode criar ringing | melhora ruído tonal |
| **Background Removal** | remover bandas horizontais | subtrair traço médio/global/local | realça hipérboles | apaga refletores horizontais reais | melhora para alvos pontuais |
| **Background Subtraction local** | remover clutter localizado | média móvel espacial | reduz eventos planos locais | agressivo se janela curta | melhora SCR/SNR local |
| **Gain / SEC** | compensar atenuação | `xg=x·t^p·e^(αt)` | melhora eventos profundos | distorce amplitude relativa | melhora visual; cuidado físico |
| **AGC** | equalizar energia local | `xg=x/(RMS_window+ε)` | melhora visual profunda | destrói amplitude absoluta | pode inflar ruído |
| **Trace Equalization** | equalizar traços | normalização por energia/percentil | reduz variação lateral | pode mascarar variação real | depende do caso |
| **Median Filter** | remover spikes | mediana temporal/espacial | robusto contra outliers | suaviza detalhes | melhora ruído impulsivo |
| **Spatial Filter** | filtrar no eixo x | média/derivada/mediana espacial | reduz ruído lateral | perde resolução lateral | depende |
| **FK Filter** | separar eventos por inclinação/velocidade aparente | FFT 2D `t-x → f-k` | remove clutter coerente | requer parametrização | melhora SCR |
| **Hilbert / Envelope** | gerar amplitude instantânea | \` | x+jH{x} | \` | facilita detecção de energia |
| **Migration** | colapsar difrações/hipérboles | Kirchhoff/FK/Stolt | posiciona alvos melhor | depende de velocidade correta | melhora foco, não necessariamente SNR |
| **Clutter Suppression SVD/KL** | remover componentes coerentes dominantes | decomposição matricial | reduz background forte | pode remover alvos se mal calibrado | melhora SCR |

### **6.2 Dewow**

**\[CONSENSO TÉCNICO\]** Dewow é um filtro passa-alta temporal para remover componente de baixa frequência/DC shift. O guia ReflexW descreve dewow como subtração de média móvel e informa que filtros bandpass também podem cumprir papel semelhante com menor alteração de forma de sinal em alguns casos.

Formulação prática:

xi′\[n\]=xi\[n\]−12L+1∑k=−LLxi\[n+k\]x\_i'\[n\] \= x\_i\[n\] \- \\frac{1}{2L+1}\\sum\_{k=-L}^{L}x\_i\[n+k\]xi′​\[n\]=xi​\[n\]−2L+11​k=−L∑L​xi​\[n+k\]

Onde:

* `i` \= índice do traço;  
* `n` \= amostra no tempo;  
* `L` \= meia janela temporal.

### **6.3 Background Removal**

**\[FATO DOCUMENTADO\]** O EKKO define Background Average Subtraction como subtração do traço médio de toda a linha, realçando eventos inclinados como hipérboles e removendo respostas horizontais comuns a todos os traços.

Formulação global:

b\[n\]=1Nx∑i=1NxX\[n,i\]b\[n\] \= \\frac{1}{N\_x}\\sum\_{i=1}^{N\_x}X\[n,i\]b\[n\]=Nx​1​i=1∑Nx​​X\[n,i\] X′\[n,i\]=X\[n,i\]−b\[n\]X'\[n,i\] \= X\[n,i\] \- b\[n\]X′\[n,i\]=X\[n,i\]−b\[n\]

**\[FATO DOCUMENTADO\]** O RADAN alerta que Background Removal pode remover refletores horizontais reais, como lençol freático ou fronteira estratigráfica.

### **6.4 Bandpass**

**\[FATO DOCUMENTADO\]** Ciampoli et al. descrevem band-pass filtering como etapa comum para remover ruído randômico de alta frequência e melhorar a qualidade visual dos dados.

Formulação:

Y′(ω)=Y(ω)H(ω)Y'(\\omega)=Y(\\omega)H(\\omega)Y′(ω)=Y(ω)H(ω)

Onde:

* `Y(ω)` \= FFT do traço;  
* `H(ω)` \= resposta do filtro;  
* `Y’(ω)` \= espectro filtrado.

### **6.5 Gain, SEC e AGC**

**\[CONSENSO TÉCNICO\]** Ganhos compensam perdas de energia por espalhamento geométrico, atenuação intrínseca e scattering. O guia ReflexW descreve time-varying gain como compensação de perdas de energia e alerta que mudanças rápidas de ganho podem criar artefatos.

Modelos práticos:

Power gain:

xg(t)=x(t)tαx\_g(t)=x(t)t^\\alphaxg​(t)=x(t)tα

Exponential gain:

xg(t)=x(t)eβtx\_g(t)=x(t)e^{\\beta t}xg​(t)=x(t)eβt

AGC:

xg(t)=x(t)1M∑k=t−M/2t+M/2x(k)2+ϵx\_g(t)=\\frac{x(t)}{\\sqrt{\\frac{1}{M}\\sum\_{k=t-M/2}^{t+M/2}x(k)^2}+\\epsilon}xg​(t)=M1​∑k=t−M/2t+M/2​x(k)2​+ϵx(t)​

**\[INFERÊNCIA TÉCNICA\]** Para detecção automática, AGC deve ser usado com cautela: melhora visual, mas reduz confiabilidade de amplitudes absolutas. Melhor manter uma ramificação sem AGC para métricas físicas e outra com AGC para visualização.

### **6.6 Migration**

**\[FATO DOCUMENTADO\]** O RADAN descreve que a migration colapsa caudas de hipérboles e deixa um ponto representando o topo do alvo quando bem aplicada.

**\[FATO DOCUMENTADO\]** O MALÅ Vision orienta ajustar a velocidade da FK-migration até que as pernas da hipérbole sejam minimizadas e reste uma resposta pontual.

Kirchhoff migration simplificada:

t(x)=t02+(2(x−x0)v)2t(x)=\\sqrt{t\_0^2+\\left(\\frac{2(x-x\_0)}{v}\\right)^2}t(x)=t02​+(v2(x−x0​)​)2​

A energia é somada ao longo da trajetória hiperbólica. Custo computacional: maior que filtros simples, mas aceitável em 2D; para grandes volumes 3D, exige otimização, paralelismo ou GPU.

### **6.7 FK Filtering**

**\[CONSENSO TÉCNICO\]** FK filtering atua no domínio frequência-número de onda para separar eventos por inclinação/velocidade aparente. O guia ReflexW mostra uso de FK para reduzir clutter horizontal/coerente.

Pipeline:

```
X(t,x)
↓ FFT2
X(f,k)
↓ máscara de inclinação / velocidade aparente
X’(f,k)
↓ IFFT2
X’(t,x)
```

### **6.8 Hilbert Transform / Envelope**

Uso recomendado:

* detecção de regiões de alta energia;  
* criação de mapas de envelope;  
* extração de features para ML;  
* C-scan/time-slice amplitude.

Fórmula:

a(t)=x(t)+jH{x(t)}a(t)=x(t)+j\\mathcal{H}\\{x(t)\\}a(t)=x(t)+jH{x(t)} Envelope(t)=∣a(t)∣Envelope(t)=|a(t)|Envelope(t)=∣a(t)∣

**\[INFERÊNCIA TÉCNICA\]** Envelope é útil para detectar energia, mas não substitui o radargrama bipolar original, porque perde informação de fase.

---

## **7\. Métricas de Qualidade: SNR, CNR, PSNR, SCR, TCR**

### **7.1 Ponto crítico**

**\[NÃO ENCONTRADO NAS FONTES PESQUISADAS\]** Não foi encontrada documentação oficial pública confirmando como RADAN, GRED HD, MALÅ Vision, Condor, ReflexW ou GPR-SLICE calculam internamente SNR, CNR, PSNR, SCR ou TCR como métricas automáticas de qualidade.

**\[FATO DOCUMENTADO\]** O RADAN traz definição de SNR em glossário, mas não foi encontrada descrição pública de algoritmo operacional de cálculo automático. A literatura científica usa métricas como SNR, PSNR, SCR e entropia em estudos de filtragem/remoção de clutter, mas normalmente com definição dependente do experimento.

### **7.2 SNR — Signal-to-Noise Ratio**

Fórmula clássica:

SNRdB=10log⁡10(PsignalPnoise)SNR\_{dB}=10\\log\_{10}\\left(\\frac{P\_{signal}}{P\_{noise}}\\right)SNRdB​=10log10​(Pnoise​Psignal​​)

Implementação prática em radargrama:

```
1. Definir ROI de sinal:
  - alvo manualmente marcado
  - janela ao redor de hipérbole
  - região pós-detecção

2. Definir ROI de ruído:
  - região sem alvo
  - região pré-evento
  - fundo lateral equivalente

3. Calcular potência:
  P_signal = mean(ROI_signal²)
  P_noise  = mean(ROI_noise²)

4. SNR_dB = 10 log10(P_signal / P_noise)
```

Uso correto:

| Uso | Recomendação |
| ----- | ----- |
| validar melhoria de filtro | calcular SNR antes/depois na mesma ROI |
| comparar pipelines | usar mesmas janelas e mesmos dados |
| classificar levantamento | usar SNR por profundidade/faixa |
| alimentar IA | usar SNR local como feature auxiliar |

Limitações:

* depende da escolha da ROI;  
* não há threshold universal;  
* AGC pode inflar ruído e distorcer SNR;  
* em GPR, “ruído” e “clutter” nem sempre são separáveis.

### **7.3 CNR — Contrast-to-Noise Ratio**

CNR=∣μT−μB∣σT2+σB2CNR \= \\frac{|\\mu\_T-\\mu\_B|}{\\sqrt{\\sigma\_T^2+\\sigma\_B^2}}CNR=σT2​+σB2​​∣μT​−μB​∣​

Onde:

* `μT` \= média da região alvo;  
* `μB` \= média do fundo;  
* `σT`, `σB` \= desvios-padrão.

Uso:

* medir separabilidade visual alvo/fundo;  
* útil para segmentação e detecção por imagem;  
* melhor que SNR quando o alvo não é apenas “mais forte”, mas tem contraste estrutural.

Limitação:

* depende de ROI;  
* pode favorecer filtros que aumentam contraste artificial.

### **7.4 PSNR — Peak Signal-to-Noise Ratio**

PSNR=10log⁡10(MAXI2MSE)PSNR \= 10\\log\_{10}\\left(\\frac{MAX\_I^2}{MSE}\\right)PSNR=10log10​(MSEMAXI2​​)

Onde:

MSE=1mn∑i=1m∑j=1n(I(i,j)−K(i,j))2MSE \= \\frac{1}{mn}\\sum\_{i=1}^{m}\\sum\_{j=1}^{n}(I(i,j)-K(i,j))^2MSE=mn1​i=1∑m​j=1∑n​(I(i,j)−K(i,j))2

Uso:

* avaliação de denoising quando existe referência limpa;  
* útil em dados sintéticos gerados por gprMax;  
* menos adequado para campo real sem ground truth.

**\[CONSENSO TÉCNICO\]** PSNR é mais forte em simulação, laboratório controlado ou comparação com referência sintética; em campo real, SNR/SCR/TCR e validação geofísica são mais práticos. Estudos de clutter removal com U-Net e modelos similares usam PSNR/qualidade quantitativa em dados sintéticos e laboratoriais.

### **7.5 SCR — Signal-to-Clutter Ratio**

SCRdB=10log⁡10(PtargetPclutter)SCR\_{dB}=10\\log\_{10}\\left(\\frac{P\_{target}}{P\_{clutter}}\\right)SCRdB​=10log10​(Pclutter​Ptarget​​)

Uso:

* medir alvo contra clutter coerente;  
* avaliar background removal, FK filtering, SVD/KL;  
* muito relevante para detecção automática.

Diferença para SNR:

| Métrica | Compara |
| ----- | ----- |
| SNR | sinal vs ruído aleatório/estimado |
| SCR | alvo vs clutter estrutural/coerente |
| TCR | alvo vs clutter ou não-alvo definido pelo experimento |

### **7.6 TCR — Target-to-Clutter Ratio**

TCRdB=10log⁡10(PtargetPclutter)TCR\_{dB}=10\\log\_{10}\\left(\\frac{P\_{target}}{P\_{clutter}}\\right)TCRdB​=10log10​(Pclutter​Ptarget​​)

Na prática, SCR e TCR podem ser equivalentes se “signal” e “target” forem definidos como a mesma ROI. A diferença deve ser padronizada no software:

* **SCR:** métrica geral de sinal detectável contra clutter.  
* **TCR:** métrica específica por alvo candidato detectado.

### **7.7 Validação automática do pipeline por métricas**

Proposta prática:

```
Para cada arquivo/perfil:
1. Calcular métricas no bruto:
  - SNR_raw
  - SCR_raw
  - energia por profundidade
  - saturação/clipping
  - ruído superficial
  - penetração efetiva

2. Aplicar pipeline candidato.

3. Calcular métricas pós-processamento:
  - SNR_proc
  - SCR_proc
  - CNR_proc
  - perda de energia útil
  - alteração de amplitude
  - supressão de horizontais

4. Gerar delta:
  ΔSNR = SNR_proc - SNR_raw
  ΔSCR = SCR_proc - SCR_raw
  ΔCNR = CNR_proc - CNR_raw

5. Aprovar/reprovar pipeline:
  - melhora alvo?
  - preserva hipérbole?
  - não apagou refletor relevante?
  - não aumentou falso positivo superficial?
```

**\[INFERÊNCIA TÉCNICA\]** A melhor estratégia não é usar um único SNR global, e sim **SNR/SCR/CNR por faixa de profundidade e por ROI de alvo**.

---

## **8\. Funcionamento do RADAN**

### **8.1 Funcionalidades oficialmente documentadas**

**\[FATO DOCUMENTADO\]** O RADAN 7 documenta:

* Time Zero Correction;  
* Background Removal;  
* FIR filters;  
* Frequency Filtering;  
* Migration;  
* Gain Adjustment;  
* visualização 3D;  
* coordenadas X/Y/Z;  
* alteração de cores para documentação;  
* interpretações;  
* exportação para Excel e JPG em módulos específicos.

### **8.2 Time Zero no RADAN**

O RADAN descreve Time Zero Correction como ajuste vertical do perfil para aproximar o topo do scan da superfície, melhorando cálculo de profundidade. Métodos documentados incluem manual, automático, scan-by-scan, drift tracking, MiniTrack e threshold tracking.

### **8.3 Background Removal no RADAN**

O RADAN define Background Removal como filtro FIR horizontal para remover bandas horizontais. Ele alerta que essas bandas podem ser ruído de baixa frequência/antenna ringing ou refletores reais; por isso há risco de remover feições desejadas.

### **8.4 Migration no RADAN**

O manual descreve migration com ajuste de hipérbole: o operador posiciona uma hipérbole guia sobre a hipérbole real e ajusta a forma até que as caudas colapsem, restando um ponto que representa o topo do alvo.

### **8.5 Funcionalidades inferidas por comportamento observado**

**\[INFERÊNCIA TÉCNICA\]** O RADAN usa uma lógica fortemente orientada a fluxo manual/semiassistido:

```
Abrir dado
↓
Corrigir posição/distância
↓
Time Zero
↓
Background Removal
↓
Filtros FIR/frequência
↓
Gain/display
↓
Migration/focus
↓
Interpretação
↓
Exportação
```

### **8.6 O que não foi encontrado**

* Algoritmo interno exato do **Adaptive Background Removal**: **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.  
* Fórmula interna exata do **Gain Adjustment** do RADAN: **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.  
* Algoritmo interno exato do **Focus/Migration** em todos os módulos: **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.  
* Cálculo automático público de qualidade por SNR/CNR/SCR/TCR: **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.

---

## **9\. Comparativo de Softwares**

| Software | Fabricante | Pontos documentados | Processamento | IA/Automação | Observação |
| ----- | ----- | ----- | ----- | ----- | ----- |
| **RADAN 7** | GSSI | Time Zero, BR, FIR, migration, gain, exportações | forte em processamento e interpretação GSSI | não documentado como IA moderna | referência para DZT/GSSI |
| **GRED HD** | IDS GeoRadar | background removal, gain, mitigação time-domain | voltado a B-scan interpretável | não confirmado publicamente | docs públicas limitadas |
| **MALÅ Vision** | Guideline Geo/MALÅ | filtros, FK migration, ajuste por hipérbole | fluxo moderno de filtros | não encontrado como IA | boa referência de UX visual |
| **EKKO\_Project** | Sensors & Software | dewow, AFS, background subtraction, mute, rectify | muito didático em filtros | não encontrado como IA central | bom manual de processamento |
| **ReflexW** | Sandmeier | importação, static correction, gain, dewow, clutter, migration | muito forte em geofísica 2D/3D | não encontrado como IA | referência acadêmica/industrial |
| **GPR-SLICE** | GPR-SLICE | processamento e criação de imagens/time-slices | foco em 2D/3D/time-slice | não confirmado | referência em arqueologia/3D |
| **Condor** | ImpulseRadar | processamento, visualização e interpretação 3D Raptor | foco em arrays 3D | não confirmado publicamente | forte para grandes volumes 3D |
| **Road Doctor** | Roadscanners | integração multidado, KML/ESRI/DXF, IA | rodovias, GPR avançado | IA documentada para layer tracing/object detection | diferencial claro em IA aplicada |
| **Geolitix** | Geolitix | cloud processing/análise geofísica | automação cloud | IA não confirmada aqui | diferencial cloud, multiformato |
| **RGPR/GPRPy/readgssi** | open source | leitura/processamento/visualização | útil para prototipagem | sem IA nativa robusta | base técnica para implementação |

---

## **10\. Detecção Automática de Alvos**

### **10.1 Tipos de alvos**

| Alvo | Assinatura comum | Observação |
| ----- | ----- | ----- |
| Tubos/cabos/dutos | hipérbole em B-scan | assinatura clássica |
| Vazios/cavidades | zona anômala, reflexão forte, perda de continuidade | depende do contraste dielétrico |
| Interfaces geológicas | refletores horizontais/inclinados | cuidado com background removal |
| Objetos metálicos | alta amplitude, ringing/saturação possível | pode gerar múltiplas reflexões |
| Objetos não metálicos | contraste menor, assinatura mais fraca | depende de permissividade |
| Estruturas enterradas | padrões geométricos e refletivos | requer contexto espacial |
| Pavimento/camadas | refletores contínuos | layer tracing mais relevante |

### **10.2 Métodos clássicos**

| Método | Uso | Vantagem | Limitação |
| ----- | ----- | ----- | ----- |
| Threshold adaptativo | detectar regiões fortes | simples e rápido | sensível a ganho/ruído |
| Edge detection | extrair contornos | útil em hipérboles | ruído gera bordas falsas |
| Hough transform | detectar curvas | geométrico | pode falhar com hipérboles incompletas |
| Template matching | comparar padrão de hipérbole | interpretável | depende de escala/velocidade |
| Curve fitting | ajustar hipérbole | fornece velocidade/profundidade | precisa boa inicialização |
| C3 algorithm | clusterização por colunas | eficiente para hipérboles | requer pré-processamento |

**\[FATO DOCUMENTADO\]** Dou et al. propõem um algoritmo C3 para identificação de assinaturas hiperbólicas, seguido por modelo de machine learning e ajuste de hipérbole por distância ortogonal.

### **10.3 Uso de SNR/SCR/TCR na detecção**

**\[INFERÊNCIA TÉCNICA\]** O detector deve usar métricas de qualidade como suporte, não como critério isolado.

Score recomendado:

Score=w1⋅Pmodelo+w2⋅SCR+w3⋅CNR+w4⋅Ghiperbole−w5⋅RsuperficialScore \= w\_1 \\cdot P\_{modelo} \+ w\_2 \\cdot SCR \+ w\_3 \\cdot CNR \+ w\_4 \\cdot G\_{hiperbole} \- w\_5 \\cdot R\_{superficial}Score=w1​⋅Pmodelo​+w2​⋅SCR+w3​⋅CNR+w4​⋅Ghiperbole​−w5​⋅Rsuperficial​

Onde:

* `P_modelo` \= probabilidade do classificador;  
* `SCR` \= alvo contra clutter;  
* `CNR` \= contraste alvo/fundo;  
* `G_hiperbole` \= aderência geométrica à hipérbole;  
* `R_superficial` \= penalidade por falso positivo superficial.

### **10.4 Falsos positivos**

Principais fontes:

| Fonte | Como reduzir |
| ----- | ----- |
| ruído superficial | máscara de profundidade mínima |
| ringing horizontal | background/FK/SVD com cuidado |
| ganho excessivo | detector em branch sem AGC extremo |
| hipérboles incompletas | combinar geometria \+ CNN |
| objetos fora da linha | avaliar consistência espacial |
| interfaces horizontais | não confundir com alvo pontual |
| baixa SNR | reduzir confidence score |

### **10.5 Maturidade tecnológica**

| Abordagem | Maturidade | Comentário |
| ----- | ----- | ----- |
| Threshold \+ geometria | alta | simples, explicável, rápido |
| C3 \+ curve fitting | alta acadêmica | bom para hipérboles |
| SVD/KL/FK clutter suppression | média/alta | exige parametrização |
| CNN/YOLO/Faster-RCNN | média | bom desempenho, depende de dataset |
| U-Net segmentação | média | forte para segmentação/clutter |
| Vision Transformers | experimental | exige muito dado |
| IA multimodal com relatório | experimental/aplicada | depende de validação humana |

---

## **11\. IA Aplicada à Interpretação**

### **11.1 Modelos usados**

**\[FATO DOCUMENTADO\]** Revisões recentes documentam uso de SVM, KNN, ANN, HMM, CNN e deep learning em A-scan, B-scan e C-scan.

| Modelo | Aplicação |
| ----- | ----- |
| CNN | classificação de recortes de radargrama |
| Faster-RCNN | detecção de regiões alvo |
| YOLO | detecção rápida em B-scans |
| U-Net | segmentação de alvos/clutter/camadas |
| CR-Net / Attention U-Net | remoção de clutter e realce |
| ViT | classificação/segmentação experimental |
| Autoencoders | denoising/anomalia |
| GPRNet/DepthNet | reconstrução e inferência de profundidade |

### **11.2 Dados sintéticos**

**\[FATO DOCUMENTADO\]** gprMax é software open source para simular propagação eletromagnética, resolvendo as equações de Maxwell em 3D por FDTD, e é amplamente usado para gerar dados sintéticos de GPR.

Uso recomendado:

```
Dados reais anotados
+
Dados sintéticos gprMax
+
Augmentations realistas
+
Validação por geofísico
=
Dataset utilizável para IA
```

### **11.3 Benchmarks e datasets**

**\[FATO DOCUMENTADO\]** Trabalhos com Faster-RCNN usaram dados simulados gerados no gprMax devido à escassez de dados reais anotados.

**\[FATO DOCUMENTADO\]** Um estudo com DepthNet usou dados reais e sintéticos, reportando 350 imagens rotuladas, 92,64% de acurácia de detecção de features em B-scan e erro médio de profundidade de 0,112 em seu contexto experimental.

**Cuidado:** esses números **não devem ser generalizados** para outro solo, antena, frequência, profundidade, alvo ou pipeline.

### **11.4 Uso de métricas de qualidade na IA**

Recomendação:

| Métrica | Uso na IA |
| ----- | ----- |
| SNR local | feature auxiliar e penalização de baixa confiança |
| SCR | ranking de alvos contra clutter |
| CNR | avaliar separabilidade alvo/fundo |
| PSNR | treino/validação em dado sintético/denoising |
| TCR | score por alvo |
| entropia | avaliar textura/ruído |
| energia por profundidade | estimar penetração efetiva |
| saturação/clipping | detectar dado ruim |

**\[INFERÊNCIA TÉCNICA\]** A IA deve produzir não só “alvo encontrado”, mas:

```
- tipo provável
- profundidade estimada
- posição no perfil
- confidence score
- SNR/SCR/TCR local
- evidência visual
- parâmetros do pipeline usado
- alertas de baixa confiabilidade
```

---

## **12\. Bibliotecas e Ferramentas Open Source**

### **12.1 Python**

| Biblioteca | Uso |
| ----- | ----- |
| `readgssi` | leitura/processamento/exibição de dados GSSI/DZT |
| `GPRPy` | processamento, visualização, análise de velocidade, interpolação 3D |
| `pygssi` | leitura de arquivos GSSI e acesso ao header/raw returns, com limitações declaradas |
| `gprMax` | simulação FDTD para geração de dados sintéticos |
| `NumPy/SciPy` | filtros, FFT, matrizes |
| `OpenCV/scikit-image` | visão computacional clássica |
| `PyTorch` | IA, CNN, U-Net, YOLO custom |
| `ONNX Runtime` | inferência portável |

### **12.2 R**

| Biblioteca | Uso |
| ----- | ----- |
| `RGPR` | ler, exportar, analisar, processar e visualizar dados GPR |

### **12.3 MATLAB**

**\[NÃO ENCONTRADO NAS FONTES PESQUISADAS\]** Não foi encontrada uma biblioteca MATLAB open source, madura e generalista equivalente a RGPR/GPRPy/readgssi para todo o pipeline DZT → processamento → IA. Existem scripts acadêmicos e implementações específicas, mas não uma base pública consolidada comparável.

### **12.4 C++ / Rust**

* **C++:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS** como biblioteca open source madura e específica para DZT/GPR com pipeline completo.  
* **Rust:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS** como biblioteca madura para DZT/GPR.

---

## **13\. Arquitetura Recomendada**

### **13.1 Visão geral**

```
┌──────────────────────────────────────────────┐
│                 Frontend/UI                  │
│  Projetos | Radargramas | Alvos | Relatórios │
└───────────────────────┬──────────────────────┘
                       │
┌───────────────────────▼──────────────────────┐
│              API / Orquestrador              │
│ Jobs | Pipeline | Permissões | Auditoria      │
└───────────────────────┬──────────────────────┘
                       │
┌───────────────────────▼──────────────────────┐
│              Núcleo Geofísico                │
│ DZT Reader | Metadata | QC | Processing Graph │
└───────┬───────────────┬───────────────┬──────┘
       │               │               │
┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│ Raw Branch   │ │ Scientific  │ │ Report/UI   │
│ preservada   │ │ Branch      │ │ Branch      │
└───────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       └───────────────▼───────────────┘
               Quality Metrics
      SNR | CNR | PSNR | SCR | TCR | QC
                       │
┌───────────────────────▼──────────────────────┐
│          Detecção Automática de Alvos         │
│ Hyperbola | CV | ML | Deep Learning | Ranking │
└───────────────────────┬──────────────────────┘
                       │
┌───────────────────────▼──────────────────────┐
│              Interpretação Assistida          │
│ IA + Regras Geofísicas + Evidências           │
└───────────────────────┬──────────────────────┘
                       │
┌───────────────────────▼──────────────────────┐
│                  Relatórios                   │
│ PDF | PNG | CSV | GeoJSON | KML | DXF          │
└──────────────────────────────────────────────┘
```

### **13.2 Componentes**

| Componente | Responsabilidade |
| ----- | ----- |
| `DZTIngestService` | leitura binária, header, metadados, traços |
| `MetadataValidator` | validação de range, nsamp, bits, canais, distância |
| `RawDataStore` | preservação do dado bruto imutável |
| `ProcessingGraph` | DAG de filtros com parâmetros e checksums |
| `SignalQualityEngine` | SNR, CNR, PSNR, SCR, TCR, QC |
| `RadargramRenderer` | geração de imagens bruta/científica/relatório |
| `ClassicalDetector` | threshold, C3, Hough, curve fitting |
| `MLDetector` | CNN/YOLO/U-Net/Faster-RCNN |
| `InterpretationAgent` | análise textual assistida por IA |
| `ReportEngine` | PDF/HTML/CSV/GeoJSON/KML |
| `AuditTrail` | rastreabilidade técnica completa |

### **13.3 Pipeline interno recomendado**

```
1. Ingestão
  - abrir DZT
  - extrair header
  - validar tamanho/matriz
  - converter para float32

2. Normalização inicial
  - remover offset de ADC
  - validar saturação
  - corrigir orientação
  - distância/markers/GPS

3. Correções essenciais
  - time zero
  - dewow
  - bandpass/notch

4. Processamento geofísico
  - background removal controlado
  - gain/SEC/AGC em branch separada
  - equalização opcional
  - migration opcional

5. Qualidade
  - SNR por profundidade
  - SCR por candidato
  - CNR por ROI
  - PSNR somente com referência
  - TCR por alvo

6. Renderização
  - bruto
  - científico
  - relatório
  - detector overlay

7. Detecção
  - candidatos geométricos
  - candidatos CNN/YOLO
  - fusão de scores
  - filtro por profundidade mínima
  - ranking por qualidade

8. IA
  - recebe imagem + metadados + métricas + candidatos
  - gera interpretação assistida
  - informa incertezas

9. Relatório
  - imagens
  - alvos
  - parâmetros
  - métricas
  - limitações
  - recomendação de validação
```

### **13.4 Estratégia de validação**

Obrigatório:

```
- testes com DZT reais de diferentes equipamentos GSSI
- comparação visual com RADAN
- comparação quantitativa SNR/SCR antes/depois
- validação por geofísico
- dataset com ground truth quando possível
- testes de regressão por arquivo
- snapshot de parâmetros de pipeline
```

---

## **14\. Gap Analysis**

### **14.1 Itens obrigatórios**

| Item | Status esperado |
| ----- | ----- |
| Leitura DZT robusta | obrigatório |
| Preservação do bruto | obrigatório |
| Extração de metadados | obrigatório |
| Time Zero | obrigatório |
| Dewow | obrigatório |
| Bandpass/notch | obrigatório |
| Background removal parametrizado | obrigatório |
| Gain/AGC com branch separada | obrigatório |
| Geração de radargrama | obrigatório |
| Export PNG/CSV/PDF | obrigatório |
| Log de processamento | obrigatório |
| Validação por SNR/SCR | obrigatório |

### **14.2 Itens recomendados**

| Item | Status esperado |
| ----- | ----- |
| Distance normalization | recomendado |
| FK filtering | recomendado |
| Hilbert envelope | recomendado |
| Migration | recomendado |
| Velocity estimation | recomendado |
| Time-depth conversion calibrável | recomendado |
| Detector geométrico de hipérboles | recomendado |
| ROI manual | recomendado |
| Relatório técnico automático | recomendado |

### **14.3 Diferenciais competitivos**

| Item | Valor |
| ----- | ----- |
| SNR/SCR/TCR por alvo | aumenta confiabilidade |
| IA explicável com evidência visual | reduz “caixa preta” |
| Agente geofísico que conversa com usuário | acelera ajuste técnico |
| Active learning com correções do geofísico | melhora modelo continuamente |
| Comparação automática com pipeline RADAN-like | facilita validação |
| Processamento em lote | ganho operacional |
| Cloud/GPU para 3D | escala |
| Export GIS/KML/GeoJSON/DXF | integração profissional |

### **14.4 Experimental**

| Item | Classificação |
| ----- | ----- |
| Vision Transformers para GPR | experimental |
| IA generativa interpretando radargrama sem validação | experimental/alto risco |
| Sugestão automática de filtros por IA | experimental |
| Denoising neural sem controle geofísico | experimental |
| Synthetic-to-real sem calibração local | experimental |

---

## **15\. Recomendações Finais**

### **15.1 O software deve nascer com rastreabilidade**

Cada imagem gerada precisa carregar:

```
- arquivo original
- hash do arquivo
- header interpretado
- parâmetros do pipeline
- versão do algoritmo
- data/hora do processamento
- métricas antes/depois
- branch usada: bruta, científica, relatório, detecção
```

### **15.2 Não usar uma única imagem “processada”**

Gerar sempre:

| Saída | Uso |
| ----- | ----- |
| `radargrama_bruto.png` | auditoria |
| `radargrama_cientifico.png` | análise geofísica |
| `radargrama_relatorio.png` | cliente/leitura visual |
| `radargrama_detector.png` | IA/detecção |
| `alvos.geojson/csv` | integração |
| `relatorio.pdf` | entrega |

### **15.3 SNR deve ser métrica central, mas não única**

Usar:

* SNR global;  
* SNR por profundidade;  
* SNR por ROI;  
* SCR por alvo;  
* CNR alvo/fundo;  
* TCR por candidato;  
* score final ponderado.

Não usar:

* threshold universal fixo de SNR;  
* SNR calculado após AGC como verdade física;  
* PSNR em campo real sem referência.

### **15.4 IA deve ser assistiva, não decisória**

O relatório da IA deve dizer:

```
“Possível alvo”
“Evidência visual”
“Profundidade estimada”
“Confiança”
“SNR/SCR/TCR local”
“Limitações”
“Recomenda validação geofísica”
```

Não deve dizer:

```
“Alvo confirmado”
```

sem ground truth ou validação humana.

---

## **16\. Bibliografia Técnica Essencial**

### **Documentação oficial**

1. **GSSI SIR-3000 Manual — Addendum A: RADAN File Header Format**.  
2. **GSSI RADAN 7 Manual**.  
3. **Sensors & Software — EKKO Processing Module User Guide**.  
4. **Sandmeier — Introduction to the Processing of GPR Data within ReflexW**.  
5. **MALÅ Vision Desktop User Guide**.  
6. **IDS GeoRadar — RIS One/RIS Plus/GRED HD**.  
7. **ImpulseRadar — Condor / ViewR**.  
8. **Roadscanners — Road Doctor**.

### **Papers e revisões relevantes**

1. **Ciampoli et al. — Signal Processing of GPR Data for Road Surveys**.  
2. **Dou et al. — Real-Time Hyperbola Recognition and Fitting in GPR Data**.  
3. **Bai et al. — Comprehensive Review of Conventional and Deep Learning Algorithms in GPR**.  
4. **DepthNet — GPR-based Subsurface Object Detection and Reconstruction**.  
5. **Faster-RCNN for B-scan GPR detection**.  
6. **gprMax — Open source FDTD simulation for GPR**.

### **Bibliotecas open source**

1. **RGPR** — R package para GPR.  
2. **GPRPy** — Python processing/visualization.  
3. **readgssi** — Python para GSSI/DZT.  
4. **pygssi** — Python para arquivos GSSI.  
5. **gprMax** — simulação FDTD.

---

## **17\. Limitações Encontradas Durante a Pesquisa**

1. **Especificação DZT completa e atualizada para todas as versões GSSI:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**. O que existe publicamente no manual SIR-3000 é informativo e não suportado pelo suporte técnico GSSI.  
2. **Algoritmos internos completos do RADAN:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**. O manual documenta fluxo e funções, mas não abre todos os detalhes matemáticos internos.  
3. **Cálculo comercial oficial de SNR/CNR/PSNR/SCR/TCR nos softwares RADAN, GRED HD, MALÅ Vision, Condor, ReflexW:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.  
4. **Thresholds universais de SNR/SCR/TCR para detecção de alvos:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**. A literatura usa métricas dependentes de dataset, alvo, antena, solo e pipeline.  
5. **Biblioteca Rust madura para DZT/GPR:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.  
6. **Biblioteca C++ madura, open source e completa para DZT/GPR:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**.  
7. **Benchmark público universal para detecção de todos os tipos de alvos GPR:** **NÃO ENCONTRADO NAS FONTES PESQUISADAS**. Existem datasets e estudos específicos, mas não um padrão único universal.

---

## **18\. Conclusão Técnica**

A melhor abordagem para o seu software é criar uma plataforma **RADAN-like na operação**, mas **mais moderna na arquitetura**:

* preservar dado bruto;  
* expor pipeline parametrizado;  
* calcular métricas antes/depois;  
* manter branch científica e branch visual separadas;  
* detectar alvos com fusão de geometria \+ visão computacional \+ IA;  
* usar SNR/SCR/TCR como suporte de qualidade e ranking;  
* gerar relatórios auditáveis;  
* permitir feedback do geofísico para melhoria contínua.

O diferencial competitivo real não está em “aplicar filtros bonitos”. Está em entregar:

```
DZT confiável → processamento rastreável → imagem interpretável →
detecção explicável → IA assistiva → relatório técnico defensável.
```

