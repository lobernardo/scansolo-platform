# KB_MASTER — ScanSOLO GPR Platform
> Base de conhecimento técnica consolidada  
> Última atualização: 2026-06-16 v2  
> Fontes: GSSI SIR-30 Manual, RADAN 7 Manual, readgssi (iannesbitt), RGPR, pipeline_v1.py v2.0.0, CLAUDE.md, Especificação de Engenharia (Gemini), Relatório Técnico GPR/DZT (GPT)

---

## ÍNDICE

1. [Formato .DZT — Especificação Binária Completa](#1-formato-dzt--especificação-binária-completa)
2. [Formato .DZX e Ecossistema de Arquivos GSSI](#2-formato-dzx-e-ecossistema-de-arquivos-gssi)
3. [Física do GPR — Fundamentos](#3-física-do-gpr--fundamentos)
4. [Algoritmos de Processamento — Referência Completa](#4-algoritmos-de-processamento--referência-completa)
5. [Métricas de Qualidade de Sinal — SNR, CNR, PSNR, SCR, TCR](#5-métricas-de-qualidade-de-sinal--snr-cnr-psnr-scr-tcr)
6. [Detector de Hipérboles — Teoria e Implementação](#6-detector-de-hipérboles--teoria-e-implementação)
7. [Velocity e Calibração de Profundidade](#7-velocity-e-calibração-de-profundidade)
8. [Constantes Dielétricas de Materiais](#8-constantes-dielétricas-de-materiais)
9. [Workflow RADAN 7 — Referência Canônica](#9-workflow-radan-7--referência-canônica)
10. [Comparativo de Softwares GPR](#10-comparativo-de-softwares-gpr)
11. [readgssi — Referência de Implementação Aberta](#11-readgssi--referência-de-implementação-aberta)
12. [IA Aplicada ao GPR — Estado da Arte](#12-ia-aplicada-ao-gpr--estado-da-arte)
13. [Rastreabilidade e Auditoria de Pipeline](#13-rastreabilidade-e-auditoria-de-pipeline)
14. [Pipeline ScanSOLO v2.0.0 — Arquitetura Atual](#14-pipeline-scansolo-v200--arquitetura-atual)
15. [Análise GAP — Estado Atual vs. Sistema Pronto](#15-análise-gap--estado-atual-vs-sistema-pronto)
16. [Roadmap Técnico Priorizado](#16-roadmap-técnico-priorizado)
17. [Presets por Objetivo](#17-presets-por-objetivo)
18. [Checklist de Calibração com Amilson](#18-checklist-de-calibração-com-amilson)
19. [Referências e Fontes](#19-referências-e-fontes)

---

## 1. Formato .DZT — Especificação Binária Completa

### 1.1 Estrutura geral

O arquivo `.DZT` (RADAN Data format) é **binário little-endian**. Estrutura:

```
[HEADER — 1024 bytes por canal] × rh_nchan
[DATA — scans × amostras × bytes_por_amostra]
```

**Regra de offset:**
- Se `rh_data < MINHEADSIZE (1024)`: offset = `MINHEADSIZE * rh_data`
- Senão: offset = `MINHEADSIZE * rh_nchan`

### 1.1b Decodificação da data rfDateByte

O campo `rhb_cdt` (data de criação) e `rhb_mdt` (data de modificação) são armazenados em um inteiro de 32 bits com formato compactado `u5u6u5u5u4u7`:

| Campo | Bits | Posições |
|---|---|---|
| Segundos ÷ 2 | 5 | 27–31 |
| Minutos | 6 | 21–26 |
| Horas | 5 | 16–20 |
| Dia | 5 | 11–15 |
| Mês | 4 | 7–10 |
| Ano − 1980 | 7 | 0–6 |

```python
def decode_rf_date_byte(byte_array):
    val = int.from_bytes(byte_array, byteorder='little')
    second = ((val >> 27) & 0x1F) * 2
    minute  = (val >> 21) & 0x3F
    hour    = (val >> 16) & 0x1F
    day     = (val >> 11) & 0x1F
    month   = (val >>  7) & 0x0F
    year    = (val & 0x7F) + 1980
    return year, month, day, hour, minute, second
```

### 1.2 Estrutura C do Header (tagRFHeader)

| Campo | Tipo | Offset (bytes) | Descrição |
|---|---|---|---|
| `rh_tag` | short | 0 | `0x00ff` = header válido; `0xfnff` = formato antigo |
| `rh_data` | short | 2 | Offset para os dados desde o início do arquivo |
| `rh_nsamp` | short | 4 | **Amostras por scan (traço)** |
| `rh_bits` | short | 6 | Bits por palavra: 8, 16 ou 32 |
| `rh_zero` | short | 8 | SIR-30: repeats/sample; outros: 0x80 (8bit) ou 0x8000 (16bit) |
| `rhf_sps` | float | 10 | Scans por segundo |
| `rhf_spm` | float | 14 | **Scans por metro** |
| `rhf_mpm` | float | 18 | Metros por marca (user mark) |
| `rhf_position` | float | 22 | Posição em nanosegundos |
| `rhf_range` | float | 26 | **Range em nanosegundos (TWTT máximo)** |
| `rh_npass` | short | 30 | Número de passes (arquivos 2D) |
| `rhb_cdt` | rfDateByte | 32 | Data/hora de criação |
| `rhb_mdt` | rfDateByte | 36 | Data/hora de modificação |
| `rh_rgain` | short | 40 | Offset para função de range gain |
| `rh_nrgain` | short | 42 | Tamanho da função de range gain |
| `rh_text` | short | 44 | Offset para texto |
| `rh_ntext` | short | 46 | Tamanho do texto |
| `rh_proc` | short | 48 | Offset para histórico de processamento |
| `rh_nproc` | short | 50 | Tamanho do histórico |
| `rh_nchan` | short | 52 | **Número de canais** |
| `rhf_epsr` | float | 54 | **Constante dielétrica média (epsilon relativo)** |
| `rhf_top` | float | 58 | Posição do topo em metros |
| `rhf_depth` | float | 62 | **Range em metros** |
| `rh_coordX` | tagRFCoords | 66 | Coordenadas X (start/end) |
| `rhf_servo_level` | float | 74 | Nível de ganho servo |
| `reserved` | char[3] | 78 | Reservado |
| `rh_accomp` | BYTE | 81 | Ant Conf component |
| `rh_sconfig` | short | 82 | Setup config number |
| `rh_spp` | short | 84 | Scans por pass |
| `rh_linenum` | short | 86 | Número da linha |
| `rh_coordY` | tagRFCoords | 88 | Coordenadas Y |
| `rh_lineorder:4` | bits | 96 | Ordem da linha |
| `rh_slicetype:4` | bits | 96 | Tipo de slice |
| `rh_dtype` | char | 97 | Data type |
| `rh_antname[14]` | char | 98 | **Nome da antena** (ex: "270MHz", "50270") |
| `rh_pass0TX:4` | bits | 112 | Active Transmit mask |
| `rh_pass1TX:4` | bits | 112 | Active Transmit mask |
| `rh_version:3` | bits | 113 | 1=sem GPS; 2=com GPS |
| `rh_system:5` | bits | 113 | Código do sistema |
| `rh_name[12]` | char | 114 | Nome inicial do arquivo |
| `rh_chksum` | short | 126 | Checksum do header |
| `variable[INFOAREASIZE]` | char | 128 | Área variável |
| `rh_RGPS[2]` | RGPS | 944 | GPS sync records |

### 1.3 Códigos de sistema (rh_system)

| Código | Sistema |
|---|---|
| 0 | synthetic/gprMax |
| 2 | SIR 2000 |
| 3 | SIR 3000 |
| 4 | TerraVision |
| 6 | SIR 20 |
| 7 | StructureScan Mini |
| 8 | SIR 4000 |
| 9 | **SIR 30** (sistema do ScanSOLO) |
| 12 | UtilityScan DF |
| 13 | HS |
| 14 | StructureScan Mini XT |

### 1.4 Formato dos dados (depois do header)

| rh_bits | dtype numpy | Sinal |
|---|---|---|
| 8 | `np.uint8` | Unsigned |
| 16 | `np.uint16` | Unsigned |
| 32 | `np.int32` | **Signed** (SIR-30 usa 32-bit) |

**Nota crítica:** O SIR-30 armazena **32-bit signed integers**. A conversão correta antes de qualquer processamento é `data.astype(np.int32)` — nunca `np.float32` direto de uint sem ajuste de zero-point.

### 1.5 Leitura correta do array

```python
# Leitura conforme readgssi e manual oficial
import struct, numpy as np

MINHEADSIZE = 1024
with open('arquivo.DZT', 'rb') as f:
    rh_tag   = struct.unpack('<h', f.read(2))[0]   # deve ser 0x00ff
    rh_data  = struct.unpack('<h', f.read(2))[0]
    rh_nsamp = struct.unpack('<h', f.read(2))[0]   # amostras/scan
    rh_bits  = struct.unpack('<h', f.read(2))[0]   # bits/amostra
    rh_zero  = struct.unpack('<h', f.read(2))[0]
    rhf_sps  = struct.unpack('<f', f.read(4))[0]   # scans/s
    rhf_spm  = struct.unpack('<f', f.read(4))[0]   # scans/m
    rhf_mpm  = struct.unpack('<f', f.read(4))[0]
    rhf_pos  = struct.unpack('<f', f.read(4))[0]
    rhf_range= struct.unpack('<f', f.read(4))[0]   # TWTT max (ns)
    # ... demais campos ...
    
    dtype = {8: np.uint8, 16: np.uint16, 32: np.int32}[rh_bits]
    
    if rh_data < MINHEADSIZE:
        offset = MINHEADSIZE * rh_data
    else:
        offset = MINHEADSIZE * rh_nchan
    
    f.seek(offset)
    data = np.fromfile(f, dtype)
    data = data.reshape(-1, rh_nsamp).T  # shape: (rh_nsamp, n_traces)
```

### 1.6 Cálculo de depth e velocity

```
velocity (m/ns) = C / sqrt(epsr)         onde C = 0.3 m/ns (no vácuo)
depth_max (m)   = rhf_range (ns) × velocity (m/ns) / 2
                  (÷2 porque TWTT = tempo de ida + volta)

ns_per_sample   = rhf_range / rh_nsamp
m_per_sample    = ns_per_sample × velocity / 2
```

**Fórmula direta:**
```python
C = 0.299792458  # m/ns
velocity_mns = C / np.sqrt(rhf_epsr)    # m/ns
depth_max_m  = rhf_range * velocity_mns / 2.0
```

### 1.7 Coordenadas e GPS (RGPS)

A estrutura `RGPS` (9 bytes por record, 2 records = 18 bytes no final do header) contém:
- `RecordType[4]`: `"GGA"` para NMEA GGA
- `TickCount` (DWORD): CPU tick count
- `PositionGPS[4]`: Altitude, FIXUTC, Latitude (positivo=N), Longitude (positivo=E)

---

## 2. Formato .DZX e Ecossistema de Arquivos GSSI

### 2.0 Ecossistema completo de arquivos GSSI

Além do `.DZT` e `.DZX`, os sistemas GSSI geram vários arquivos companheiros:

| Extensão | Tipo | Conteúdo |
|---|---|---|
| `.DZT` | Binário | Dado bruto de amplitude (A-scans) |
| `.DZX` | XML | Metadados, picks, GPS, histórico de processamento |
| `.DZG` | Texto (NMEA) | GPS sincronizado traço a traço |
| `.DZA` | Binário | Acessórios acoplados (ex: LineTrac para EM de cabos energizados) |
| `.PLT` | Texto | Posicionamento legado (registradores Acumen externos) |
| `.TMF` | Texto | Posicionamento legado (registradores Acumen) |
| `.B3D` | Binário | Geometria de grade 3D rápida (SIR-3000) |
| `.M3D` | Binário | Grade 3D (SIR-3000) |
| `.BZX` | XML | Geometria de visualização volumétrica 3D (SIR-4000, StructureScan Mini XT) |
| `.S3D` | Binário | Visualização 3D moderna (SIR-4000) |

**Regra prática:** ao abrir qualquer `.DZT`, sempre verificar se existem `.DZX` e `.DZG` com o mesmo nome base. Eles contêm dados que não estão no binário.

### 2.1 Propósito do DZX

O `.DZX` é um **arquivo XML** companheiro do `.DZT` que armazena TUDO que não cabe no header binário. **Crítico: não abrir .DZT sem tentar o .DZX.**

Substitui o banco de dados Access do RADAN 6.

### 2.2 Elementos principais

| Elemento | Conteúdo |
|---|---|
| `GlobalProperties` | Unidades verticais/horizontais, dielétrico, scans/unit, configurações RADAN 7 |
| `ChannelProperties` | Posição das antenas relativa ao GPS ou coordenadas locais 3D |
| `WayPtNameProperties` | Nomes das marcas do usuário |
| `ProfileGroup` | Range de scans, configurações 3D, coords locais-globais, waypoints com localização |
| `LayerGroup` | Picks interativos de camadas (até 7): scan, sample, canal, tempo de chegada, amplitude, profundidade, velocity |
| `TargetGroup` | Picks de alvos (sem limite de número). Mesmo formato que LayerGroup. |
| `FreeDrawGroup` | Picks de desenho livre em datasets 3D, amarrados a coordenadas locais/globais |

### 2.3 O que o .DZX carrega que o .DZT não tem

- GPS completo por waypoint (lat/lon/altitude)
- Nomes de marcas do usuário
- Picks de camadas e alvos do RADAN (coordenadas em scan+sample+profundidade+velocity)
- Configurações de exibição: color table, color transform, display gain, unidades
- Informação 3D: coordenadas de início/fim de perfis para registro em grid
- Ground truth de picks

### 2.4 Implementação mínima para parser

```python
import xml.etree.ElementTree as ET

def parse_dzx(caminho_dzx):
    tree = ET.parse(caminho_dzx)
    root = tree.getroot()
    ns = {'dzx': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
    
    result = {'waypoints': [], 'layers': [], 'targets': [], 'gps': []}
    
    # WayPoints com GPS
    for profile in root.iter('Profile'):
        for waypt in profile.iter('WayPt'):
            wpt = {}
            for child in waypt:
                wpt[child.tag] = child.text
            result['waypoints'].append(wpt)
    
    # Layer picks
    for layer_group in root.iter('LayerGroup'):
        for pick in layer_group.iter('LayerWayPt'):
            result['layers'].append({c.tag: c.text for c in pick})
    
    # Target picks
    for target_group in root.iter('TargetGroup'):
        for pick in target_group.iter('TargetWayPt'):
            result['targets'].append({c.tag: c.text for c in pick})
    
    return result
```

---

## 3. Física do GPR — Fundamentos

### 3.0 Propagação eletromagnética — equações de Maxwell

A propagação GPR é regida pelas equações de Maxwell. As propriedades críticas do meio são:
- **εr** — permissividade dielétrica relativa (controla velocidade)
- **σ** — condutividade elétrica (controla atenuação)
- **tan δ = σ/(ω·ε)** — tangente de perda (razão atenuação/frequência)

À medida que a frequência aumenta, atenuação por absorção e espalhamento crescem → compromisso penetração vs. resolução.

### 3.1 Equação de propagação

Velocidade de fase no meio:
```
v = C / sqrt(μr × εr)

onde:
  C   = 2.998 × 10^8 m/s (velocidade da luz no vácuo)
  μr  = permeabilidade magnética relativa (≈ 1 para solos típicos)
  εr  = permissividade dielétrica relativa (constante dielétrica)
  
Simplificado para solos (μr ≈ 1):
  v = C / sqrt(εr)
  v (m/ns) = 0.3 / sqrt(εr)
```

### 3.2 Profundidade e TWTT

```
profundidade = v × TWTT / 2

onde TWTT = Two-Way Travel Time (tempo de ida e volta em ns)

Conversão amostras → profundidade:
  ns_por_amostra = rhf_range / rh_nsamp
  m_por_amostra  = ns_por_amostra × v / 2
```

### 3.3 Hipérbole de difração

Quando um objeto pontual ou cilíndrico é cruzado por um perfil GPR, a antena registra o sinal em distâncias crescentes antes e depois do cruzamento direto. Isso forma a curva hiperbólica característica:

```
t²(x) = t₀² + (2x/v)²  ÷  (1 + (2x/(v×t₀))²)

Simplificado (hipérbole exata):
  t(x) = (2/v) × sqrt(d² + x²)

onde:
  t(x) = tempo de chegada na posição x (ns)
  t₀   = tempo mínimo (alvo diretamente abaixo da antena, ns)
  d    = profundidade do alvo (m)
  x    = distância horizontal do alvo (m)
  v    = velocidade de propagação (m/ns)
```

**Colapso da hipérbole:** Na migração, a hipérbole deve colapsar para um ponto representando o **topo** do alvo (não o eixo).

### 3.4 Estimativa de diâmetro por DeltaT

Para tubos e cabos, a reflexão do **topo** e do **fundo** chega em tempos diferentes:

```
Δt = 2 × diâmetro / v

diâmetro = v × Δt / 2
```

Isso permite estimar diâmetro sem contato físico.

### 3.5 Atenuação e profundidade útil

```
Profundidade útil ≈ 1 / (α × f)

onde α depende de condutividade do solo e f = frequência da antena

Regras práticas para 270 MHz em GSSI:
- Solo seco (areia/cascalho):  profundidade útil ~3–5 m
- Solo úmido:                  profundidade útil ~1–2 m
- Solo argiloso:               profundidade útil ~0.5–1.5 m
- Argila saturada:             profundidade útil < 0.5 m
```

### 3.5b Coeficiente de reflexão na interface

Na interface entre dois meios com velocidades v₁ e v₂:

```
R = (sqrt(εr1) - sqrt(εr2)) / (sqrt(εr1) + sqrt(εr2))
  = (v2 - v1) / (v2 + v1)
```

**Casos extremos:**
- Condutor perfeito (metal): R ≈ −1 (reflexão total com inversão de fase)
- Vazio/ar: R depende de εr do solo — tipicamente R > 0 se solo → ar
- PVC: contraste menor, reflexão parcial — mais difícil de detectar que metal

**Calibração por placa metálica (RADAN):**
Usando uma placa metálica de referência (R ≈ −1), é possível calcular εr da camada de topo sem sondagem:
```
εr_0 = ((1 + A0/Amp) / (1 - A0/Amp))²
onde: A0 = amplitude da reflexão real, Amp = amplitude da placa metálica
```

### 3.6 Resolução

**Resolução vertical** (critério de Rayleigh λ/4):
```
Δz = λ/4 = v/(4×fc)
Para 270 MHz, v=0.1 m/ns: Δz ≈ 0.093 m (~9 cm)
```

**Resolução horizontal — ANTES da migração** (limitada pela zona de Fresnel):
```
Δx ≈ sqrt(λ×z/2 + λ²/16)
onde z = profundidade do alvo, λ = comprimento de onda no meio
Para 270 MHz a 1m de profundidade: Δx ≈ 0.24 m
```

**Resolução horizontal — APÓS migração** (limite teórico):
```
Δx_migrado ≈ λ/2 = v/(2×fc)
Para 270 MHz: ≈ 0.185 m
```

**Implicação prática:** Objetos menores que λ/4 no eixo vertical e λ/2 horizontalmente após migração não podem ser distinguidos espacialmente, mas ainda geram resposta hiperbólica detectável.

---

## 4. Algoritmos de Processamento — Referência Completa

### 4.1 Sequência canônica de processamento

Consenso da indústria (RADAN 7, EKKO, ReflexW, Sensors&Software, IDS GRED):

```
[DZT bruto]
   ↓
0. Validação + Distance normalization (corrige traços irregulares)
   ↓
1. Time-zero correction (ajuste superfície)       ← ANTES do BGR
   ↓
2. Dewow / DC removal (remove wow de baixíssima frequência)
   ↓
3. Bandpass FIR vertical (remove ruído fora da banda útil)
   ↓
[BIFURCAÇÃO — ponto de preservação do dado limpo]
   ↓                          ↓                    ↓
Fluxo Científico         Fluxo Relatório       Fluxo Detector
4a. tpow gain            4b. BGR               Sem BGR, sem AGC
    (preserva decaimento)     5b. tpow          Sem gain excessivo
                              6b. AGC (visual)
   ↓                          ↓                    ↓
_radargrama_cientifico.png  _radargrama_relatorio.png  arr_detector
(para geofísico)            (para cliente/PDF)       (para Hough+CurveFit)
```

**Consequências de alterar a ordem** (documentadas por Gemini/RADAN):
- Ganho ANTES de Dewow: amplifica drift DC → saturação → filtros de frequência falham
- BGR ANTES de Bandpass: insere artefatos horizontais que são amplificados pelos filtros espaciais
- Migração ANTES de Time-zero: deslocamento estático corrompe cálculo da curvatura hiperbólica → resultado borrado
- BGR ANTES de Time-zero: pode remover o próprio pulso de superfície (referência para time-zero)

### 4.2 Time-Zero Correction

**O que é:** Ajusta o topo do scan para alinhar com a superfície real. Sem isso, a profundidade de todos os alvos fica errada.

**Como funciona:**
- Identifica o primeiro pico positivo do primeiro traço (pulso de acoplamento direto)
- Desloca todas as amostras para que esse pico esteja na posição 0
- RADAN: `Processing > Time Zero` → "grab the first positive peak and adjust to top"

**Impacto:** Crítico para cálculo de profundidade correto. A ordem RADAN é sempre: **Time Zero antes de Background Removal**.

**Implementação:**
```python
def time_zero_correction(arr, rh_zero):
    """Remove amostras antes do zero (time-zero)."""
    if rh_zero > 0 and rh_zero < arr.shape[0]:
        return arr[rh_zero:, :]
    return arr
```

**Status no ScanSOLO:** Implicitamente tratado pelo GPRPy via `header['timezero']`. **Não há correção explícita no pipeline_v1.py.** Potencial gap.

### 4.3 Dewow (High-pass temporal)

**O que é:** Remove componentes de muito baixa frequência (WOW) que distorcem a linha base de cada traço. O WOW aparece como variação lenta na amplitude do traço ao longo do tempo.

**Método 1 — Moving average subtraction (implementado no ScanSOLO via GPRPy):**
```python
# GPRPy.dewow(window)
# Subtrai média deslizante de 'window' amostras de cada traço
arr_dewow = arr - moving_average(arr, window=5, axis=0)
```

**Método 2 — Polynomial fit subtraction (readgssi — experimental):**
```python
# Ajusta polinômio de grau 3 ao traço e subtrai
model = np.polyfit(range(n), signal, 3)
predicted = np.polyval(model, range(n))
arr_dewow = arr + predicted  # nota: soma (não subtrai) no código readgssi
```

**Parâmetro chave:** `dewow_window` — janela em amostras. Valor default ScanSOLO: 5.

**Quando pular:** Modo `minimo` de SNR pode pular se o dado já estiver limpo (embora no ScanSOLO atual o dewow é sempre aplicado).

**Impacto no detector:** Dewow sobre `arr_raw` antes de entrada no detector (modo `raw_dewow_bandpass`) resulta em 75% de CurveFit vs 82% com raw puro.

### 4.4 Bandpass FIR Vertical

**O que é:** Filtro passa-faixa aplicado ao eixo do tempo (vertical) de cada traço. Remove frequências abaixo da borda inferior (ruído wow residual) e acima da borda superior (ruído térmico/RF).

**Parâmetros para antena 270 MHz:**
- `bandpass_low_mhz = 80 MHz` (≈ fc/3.4)
- `bandpass_high_mhz = 500 MHz` (≈ fc × 1.85)
- GSSI recomenda: low ≈ fc/4 a fc/3, high ≈ 2×fc

**Implementação no ScanSOLO (Butterworth SOS via scipy):**
```python
from scipy import signal as sp_signal

def aplicar_bandpass(arr, low_mhz, high_mhz, order, fs_mhz):
    nyq = fs_mhz / 2.0
    low_n  = max(low_mhz  / nyq, 0.001)
    high_n = min(high_mhz / nyq, 0.999)
    sos = sp_signal.butter(order, [low_n, high_n], btype='band', output='sos')
    out = np.zeros_like(arr, dtype=float)
    for i in range(arr.shape[1]):
        out[:, i] = sp_signal.sosfiltfilt(sos, arr[:, i].astype(float))
    return out
```

**readgssi usa FIR triangular** (scipy.signal.firwin com window='triangle', numtaps=25) — mais próximo do filtro FIR do RADAN. **Recomendado para adotar no ScanSOLO** por menor distorção de fase.

**Implementação readgssi (referência):**
```python
from scipy.signal import firwin, lfilter

def triangular_bandpass(arr, freqmin_mhz, freqmax_mhz, samp_freq_hz, zerophase=True):
    samp_freq = samp_freq_hz
    freqmin = freqmin_mhz * 1e6
    freqmax = freqmax_mhz * 1e6
    numtaps = 25
    filt = firwin(numtaps, [freqmin, freqmax], window='triangle',
                  pass_zero='bandpass', fs=samp_freq)
    far = lfilter(filt, 1.0, arr, axis=0)
    if zerophase:
        far = lfilter(filt, 1.0, far[::-1], axis=0)[::-1]
    return far
```

**Frequência de amostragem:**
```python
# Cálculo correto da fs do sinal GPR
ns_per_zsample = (rhf_depth - rhf_top) * 2 / (rh_nsamp * cr)  # readgssi
samp_freq_hz   = 1 / ns_per_zsample  # Hz

# Forma simplificada:
dt_ns   = rhf_range / (rh_nsamp - 1)  # ns por amostra
fs_mhz  = 1000.0 / dt_ns              # MHz
```

**Quando não aplicar:** SNR muito alto (modo `minimo`) — pode introduzir artefatos em dados já limpos. No pipeline atual, bandpass é pulado em modo `minimo`.

### 4.5 Background Removal (BGR)

**O que é:** Remove faixas horizontais persistentes. Essas faixas podem ser: acoplamento direto antena-solo (onda direta), reflexões da superfície, ringing de múltiplas reflexões, ruído EMI horizontal.

**ALERTA CRÍTICO (RADAN 7 Manual + readgssi docs):**
> "BGR pode remover refletores reais horizontais: estratigrafia, camada d'água, pavimento, ou qualquer refletor contínuo. Use com cuidado."

**Implementação completa (readgssi bgr):**
```python
def bgr(arr, win=0):
    """
    win=0: remove média global de cada linha (full-width)
    win>1: remove média deslizante por janela de 'win' traços
    """
    # Passo 1: remove média total de cada linha
    for i, row in enumerate(arr):
        arr[i] = row - np.mean(row)
    
    # Passo 2: se janela especificada, remove média espacial local
    if win > 1:
        from scipy.ndimage.filters import uniform_filter1d
        arr -= uniform_filter1d(arr, size=win, mode='constant', cval=0, axis=1)
    return arr
```

**GPRPy `remMeanTrace(n)`:** Remove média dos últimos `n` traços de cada traço. Equivalente ao BGR com janela `n`.

**Parâmetro no ScanSOLO:** `bgremoval_traces=30` — janela de 30 traços.

**Uso correto:**
- Só no fluxo de relatório (visual), NUNCA no fluxo científico
- NUNCA como entrada do detector (destrói refletores horizontais reais)
- SEMPRE após time-zero

### 4.6 Time-Power (tpow) Gain

**O que é:** Compensação de atenuação geométrica. O sinal GPR decai com o tempo (profundidade). O tpow multiplica cada amostra pelo seu índice de tempo elevado a um expoente.

```python
def tpow_gain(arr, power=0.5):
    n = arr.shape[0]
    gains = (np.arange(n, dtype=float) / max(n-1, 1)) ** float(power)
    return arr * gains[:, np.newaxis]
```

**Power típico:** 0.5 (raiz quadrada). Valores maiores amplificam mais os sinais profundos.

**Ajuste por modo SNR no ScanSOLO:**
- Modo `minimo`: power × 0.6 (dado limpo, menos ganho)
- Modo `padrao`: power base (0.5)
- Modo `agressivo`: min(power × 1.5, 1.2) (dado ruidoso, mais ganho)

**Diferença entre fluxos:**
- Fluxo científico: tpow aplicado manualmente sobre `arr_dewow_bp` SEM modificar `prof.data`
- Fluxo relatório: `prof.tpowGain()` aplicado sobre `prof.data` (após bgremoval)

### 4.7 AGC (Automatic Gain Control)

**O que é:** Equalização de amplitude que torna cada janela local aproximadamente uniforme. Melhora muito a visualização, mas **destrói relações absolutas de amplitude**.

```python
def agc_gain(arr, window=150):
    """AGC por janela deslizante (RMS local)."""
    n_samples, n_traces = arr.shape
    arr_agc = np.zeros_like(arr)
    half = window // 2
    for col in range(n_traces):
        trace = arr[:, col]
        for i in range(n_samples):
            i0 = max(0, i - half)
            i1 = min(n_samples, i + half + 1)
            rms = float(np.sqrt(np.mean(trace[i0:i1] ** 2))) + 1e-10
            arr_agc[i, col] = trace[i] / rms
    return arr_agc
```

**Janela AGC no ScanSOLO:** 150 (base), ajustada por modo:
- Modo `minimo`: 300 (janela maior = suavização)
- Modo `agressivo`: 75 (janela menor = mais contraste local)

**Quando usar AGC:**
- SEMPRE no fluxo visual/relatório (cliente)
- NUNCA como entrada do detector de hipérboles
- NUNCA para análise de amplitude/fase de materiais
- Preview RADAN 5m usa AGC com janela=80 (separado do pipeline principal)

**Por que não no detector:** AGC equaliza amplitudes, destruindo a assimetria que distingue metal (alta amplitude, fase positiva) de não-metal (amplitude moderada, possível inversão de fase).

### 4.8 Migração de Kirchhoff (F-K Migration)

**O que é:** Colapsa hipérboles de difração em pontos, revelando a geometria real dos alvos. Melhora resolução lateral e posicionamento.

**Base teórica:** Cada ponto da hipérbole é a soma de contribuições de uma frente de onda esférica. A migração faz a operação inversa: distribui a energia de cada ponto para todos os pontos da frente de onda hiperbólica correspondente.

**Implementação atual no ScanSOLO:**
- Migração F-K Kirchhoff própria via NumPy (não usa `irlib` do GPRPy, pois requer dependência externa)
- Resultado em `_migrada.png`
- Flag `--sem-migracao` para pular

**Limitações conhecidas:**
- `fkMigration` do GPRPy requer `irlib` (não instalado)
- A implementação numpy própria pode ser de qualidade inferior ao GPRPy nativo
- **P3:** Avaliar qualidade com Amilson

**Uso recomendado:**
- Aplicar sobre fluxo científico (sem AGC) para não introduzir artefatos
- Requere velocity correta — sem calibração, a migração pode piorar o resultado

### 4.9 Stacking (empilhamento horizontal)

**O que é:** Média de N traços consecutivos. Reduz ruído aleatório por fator `sqrt(N)`, mas reduz resolução horizontal.

```python
# Stacking simples
def stack(arr, n):
    n_traces = arr.shape[1]
    new_n = n_traces // n
    return arr[:, :new_n*n].reshape(arr.shape[0], new_n, n).mean(axis=2)
```

**Parâmetros GSSI recomendados:** 3–7 traços. Valores acima de 7 removem feições de interesse.

**Status no ScanSOLO:** Não implementado explicitamente no pipeline. O SIR-30 pode aplicar stacking na coleta — ver `rh_zero` (repeats/sample no SIR-30).

### 4.10 Deconvolução

**O que é:** Remove ruído horizontal que não é consistente ao longo do perfil (ringing). Diferente do BGR que remove ruído consistente.

**Parâmetros RADAN:**
- `Operator Length`: número de amostras de 1 pulso (medir diferença entre picos)
- `Prediction Lag`: start em ½ do Operator Length, reduzir progressivamente
- `Prewhitening %`: deixar em default

**Status no ScanSOLO:** Não implementado. Candidato para futura adição ao fluxo científico.

### 4.11 Ganho SEC (Spreading and Exponential Compensation)

**O que é:** Alternativa ao AGC que **preserva relações relativas de amplitude** entre traços. Compensa geometricamente a atenuação sem normalizar cada janela local.

**Fórmula:**
```
g_SEC(t) = C · t^a · e^(α·t)

onde:
  t = tempo de viagem (ns)
  a = expoente de espalhamento geométrico (típico: 1.0–2.0 para dados 2D)
  α = coeficiente de atenuação do solo (Np/ns) — medido por CMP ou estimado
  C = constante de normalização

Para uso prático (adimensional):
  g_SEC(t) = (t/t_ref)^a · exp(α·(t - t_ref))
  onde t_ref = twtt da superfície
```

**Vantagem vs AGC:**
- AGC: amplitude local → absoluta impossível
- SEC: amplitude relativa entre traços preservada → permite identificar variações laterais de material

**Implementação (numpy):**
```python
def sec_gain(arr, twtt_ns, a=1.0, alpha_per_ns=0.0):
    """
    arr: (n_samples, n_traces)
    twtt_ns: vetor de tempos de 2 vias (ns), shape (n_samples,)
    """
    t_ref = max(twtt_ns[0], 1e-6)
    gains = (twtt_ns / t_ref) ** a * np.exp(alpha_per_ns * (twtt_ns - t_ref))
    gains = np.clip(gains, 0, 1e4)
    return arr * gains[:, np.newaxis]
```

**Status no ScanSOLO:** Não implementado — gap identificado. O tpow é um caso especial de SEC com `α=0`. Para análise física de amplitude, SEC é mais adequado que tpow.

### 4.12 Migração de Stolt (F-K)

**O que é:** Migração no domínio espectral (frequência-número de onda). Mais rápida que Kirchhoff para grandes volumes de dados. Assume velocidade constante (limitação).

**Fundamento matemático:**
```
Mapeamento espectral:
  kz = sqrt((2ω/v)² - kx²)

onde:
  ω  = frequência angular
  kx = número de onda horizontal
  kz = número de onda vertical (migrado)
  v  = velocidade do meio (constante)

O mapeamento move energia de (kx, ω) para (kx, kz):
  P_migrado(kx, kz) = P_original(kx, ω(kx, kz)) · Jacobiano
  Jacobiano = ω / (v · kz)
```

**Implementação conceitual (numpy):**
```python
def stolt_migration(arr, v_mns, dx_m, dt_ns):
    from numpy.fft import fft2, ifft2, fftfreq
    # Transformada 2D
    F = fft2(arr)
    n_t, n_x = arr.shape
    fx = fftfreq(n_x, d=dx_m)      # Hz/m → ciclos/m
    ft = fftfreq(n_t, d=dt_ns*1e-9)  # Hz
    
    kx = 2 * np.pi * fx[np.newaxis, :]
    omega = 2 * np.pi * ft[:, np.newaxis]
    
    # Mapeamento Stolt
    kz = np.sqrt(np.maximum(0, (2*omega/v_mns)**2 - kx**2))
    # Remapear F de omega → kz (interpolação 1D por coluna)
    # ... (interpolação complexa — ver implementação completa)
    return ifft2(F_migrado).real
```

**Vantagem:** O(N²logN) vs O(N³) do Kirchhoff clássico.
**Limitação:** Velocidade constante assumida. Para solos heterogêneos, Kirchhoff adaptativo é superior.
**Status no ScanSOLO:** Não implementado — usa Kirchhoff numpy próprio. Stolt seria alternativa para grandes datasets HELPER (126 DZTs).

### 4.13 Filtro F-K 2D (Dip Filter)

**O que é:** Filtro no domínio 2D frequência-número de onda. Separa eventos por velocidade aparente (dip). Não é migração — não colapsa hipérboles, apenas filtra por inclinação.

**Fundamento:**
```
Velocidade aparente de um evento: v_ap = Δx/Δt = f/kx

Região de máscara no espectro F-K:
  - Eventos lentos (quase-horizontais): alta kx, baixa f → BGR/ringing
  - Eventos inclinados (refração): kx/f ≈ constante
  - Difração (hipérbole): energia espalhada em todo o F-K
```

**Implementação:**
```python
def fk_filter(arr, dx_m, dt_ns, v_min=0.0, v_max=0.5):
    """
    Mantém apenas eventos com v_aparente entre v_min e v_max (m/ns).
    v_min=0, v_max=inf → sem filtro
    v_min=0, v_max=0.1 → remove refrações rápidas (manter difração)
    """
    from numpy.fft import fft2, ifft2, fftshift, fftfreq
    F = fft2(arr)
    n_t, n_x = arr.shape
    fx = fftshift(fftfreq(n_x, d=dx_m))
    ft = fftshift(fftfreq(n_t, d=dt_ns*1e-9))
    
    FX, FT = np.meshgrid(fx, ft)
    with np.errstate(divide='ignore', invalid='ignore'):
        v_ap = np.where(FX != 0, np.abs(FT / FX), np.inf)
    
    mask = (v_ap >= v_min) & (v_ap <= v_max)
    F_filtered = np.fft.ifftshift(np.fft.fftshift(F) * mask)
    return np.real(ifft2(F_filtered))
```

**Aplicação prática:** Separar eventos de tubulação (difração → quase toda a banda F-K) de reflexões de camadas horizontais (f alta, kx baixo).

### 4.14 Filtro Mediana e SVD/KL

**Filtro Mediana (Median Filter):**
Remove ruído do tipo "sal e pimenta" sem borrar as bordas dos refletores. Preserva melhor as interfaces que o filtro média.
```python
from scipy.signal import medfilt2d
arr_median = medfilt2d(arr.astype(float), kernel_size=(3, 3))
```
**Quando usar:** Para dados com spikes de amplitudes isoladas (EMI burst, artefatos de encoder).

**SVD/KL Clutter Suppression (Karhunen-Loève):**
Decomposição em valores singulares para identificar e remover componentes de clutter coerente (reflexões de superfície, ringing periódico) sem remover difração de alvos.
```
[U, S, V] = SVD(arr)

Clutter dominante → primeiros k valores singulares (mais altos)
Sinal de alvo → valores singulares menores (k+1 em diante)

arr_limpo = U[:, k:] · diag(S[k:]) · V[k:, :]
```
**Vantagem sobre BGR:** BGR remove qualquer evento horizontal, incluindo camadas reais. SVD/KL identifica componentes pela coerência estatística — mais cirúrgico.
**Desafio:** Escolher k correto (número de componentes de clutter). Regra prática: k = número de "joelhos" no scree plot dos valores singulares.
**Status no ScanSOLO:** Não implementado. Gap identificado para futura adição.

---

## 5. Métricas de Qualidade de Sinal — SNR, CNR, PSNR, SCR, TCR

### 5.1 Método de cálculo (ScanSOLO v2.0.0)

Baseado em envelope analítico de Hilbert por traço (padrão GPR):

```
SNR = max|H[x(t)]| / std[x_noise(t)]
```

Onde:
- `H[·]` = transformada de Hilbert (envelope analítico)
- Janela de sinal: amostras 10%–75% do total (exclui onda direta inicial)
- Janela de ruído: amostras 95%–100% (ruído térmico genuíno)
- Resultado: **mediana** sobre todos os traços (robusto a outliers)

```python
from scipy.signal import hilbert

def calcular_snr(arr_raw, tipo_solo='standard'):
    n_samples = arr_raw.shape[0]
    s0 = max(1, int(0.10 * n_samples))   # início janela sinal
    s1 = int(0.75 * n_samples)            # fim janela sinal
    r0 = int(0.95 * n_samples)            # início janela ruído
    
    snr_por_traco = []
    for i in range(arr_raw.shape[1]):
        trace = arr_raw[:, i].astype(float)
        envelope = np.abs(hilbert(trace[s0:s1]))
        pico_sinal = float(np.max(envelope))
        ruido_std  = float(np.std(trace[r0:])) + 1e-10
        snr_por_traco.append(pico_sinal / ruido_std)
    
    snr_ratio = float(np.median(snr_por_traco))
    snr_db    = 20.0 * np.log10(snr_ratio) if snr_ratio > 0 else 0.0
    return snr_db, snr_ratio
```

### 5.2 Limiares SNR por tipo de solo

| Solo | limiar_minimo (→MINIMO) | limiar_padrao (→PADRAO) | Modo abaixo |
|---|---|---|---|
| standard / arenoso | 30.0 | 4.0 | AGRESSIVO |
| argiloso | 20.0 | 3.5 | AGRESSIVO |
| umido | 15.0 | 3.0 | AGRESSIVO |
| pedregoso | 35.0 | 6.0 | AGRESSIVO |

**Referência Amilson:** S/sigma=100 (40dB) = limpo; =10 (20dB) = bom; =3 (10dB) = ruidoso

**Valores calibrados PATIO:** PATIO_001=9.25, 002=5.44, 003=6.45, 004=4.56 → todos em modo PADRAO

### 5.3 Comportamento por modo

| Modo | Condição SNR | Ajustes automáticos |
|---|---|---|
| `minimo` | ratio ≥ limiar_minimo | Bandpass pulado; tpow×0.6; AGC janela×2 |
| `padrao` | ratio ≥ limiar_padrao | Preset base (todos 4 DZTs PATIO ficam aqui) |
| `agressivo` | ratio < limiar_padrao | tpow×1.5; AGC janela÷2 |

### 5.4 SNR medido em 3 pontos (v2.0.0)

| Ponto | Campo CSV | Estágio | Comportamento esperado |
|---|---|---|---|
| Bruto | `snr_raw_db` | Antes de qualquer filtro | Referência; governa o modo |
| Científico | `snr_cientifico_db` | Após dewow+bp+tpow | Deve ser > snr_raw (+5–6 dB em PATIO) |
| Relatório | `snr_relatorio_db` | Após bgremoval+tpow (pré-AGC) | Deve ser << snr_raw (bgremoval remove fundo+sinal) |

### 5.5 CNR — Contrast-to-Noise Ratio

Quantifica o contraste entre a região do alvo e o fundo imediato:

```
CNR = |μ_T - μ_B| / sqrt(σ_T² + σ_B²)

onde:
  μ_T = amplitude média na janela do alvo (Hilbert envelope)
  μ_B = amplitude média no fundo adjacente (mesma profundidade, fora do alvo)
  σ_T = desvio padrão na janela do alvo
  σ_B = desvio padrão no fundo

CNR > 1: alvo distinguível do fundo (limiar mínimo)
CNR > 3: alvo bem definido
```

```python
def calcular_cnr(arr, x_alvo, z_alvo, raio_alvo_px=20, raio_bg=40):
    from scipy.signal import hilbert
    envelope = np.abs(hilbert(arr, axis=0))
    
    # Janela do alvo
    x0, x1 = max(0, x_alvo-raio_alvo_px), min(arr.shape[1], x_alvo+raio_alvo_px)
    z0, z1 = max(0, z_alvo-raio_alvo_px), min(arr.shape[0], z_alvo+raio_alvo_px)
    janela_alvo = envelope[z0:z1, x0:x1]
    
    # Fundo (banda horizontal adjacente, fora do raio do alvo)
    bg_mask = np.ones_like(envelope, dtype=bool)
    bg_mask[z0:z1, x0:x1] = False
    z0b, z1b = max(0, z_alvo-raio_bg), min(arr.shape[0], z_alvo+raio_bg)
    janela_bg = envelope[z0b:z1b, :][bg_mask[z0b:z1b, :]]
    
    mu_T, mu_B = janela_alvo.mean(), janela_bg.mean()
    sig_T, sig_B = janela_alvo.std(), janela_bg.std()
    return abs(mu_T - mu_B) / (np.sqrt(sig_T**2 + sig_B**2) + 1e-10)
```

### 5.6 PSNR — Peak Signal-to-Noise Ratio

Métrica clássica de processamento de imagem, aplicada ao radargrama:

```
PSNR = 10 · log10(MAX² / MSE)

onde:
  MAX = valor máximo possível do sinal (ex: 32767 para int16)
  MSE = mean((sinal_filtrado - sinal_referencia)²)

PSNR > 40 dB: excelente
PSNR 30–40 dB: boa qualidade
PSNR < 30 dB: ruído significativo
```

**Uso no GPR:** Comparar estágios de processamento. `arr_proc` vs `arr_raw` → PSNR indica quanto ruído foi removido vs sinal preservado.

### 5.7 SCR — Signal-to-Clutter Ratio

Distingue clutter (fundo coerente) de ruído aleatório:

```
SCR = 10 · log10(P_target / P_clutter)

onde:
  P_target = potência média na janela do alvo
  P_clutter = potência média em região homogênea de clutter
             (região sem alvos conhecidos, mesmo nível de profundidade)

SCR > 10 dB: alvo detectável acima do clutter
SCR > 20 dB: alvo bem separado do clutter
```

**Diferença SCR vs SNR:** SNR compara sinal vs ruído aleatório (térmico). SCR compara sinal vs ruído coerente estruturado (clutter de superfície, múltiplas reflexões, ringing).

### 5.8 TCR — Target-to-Clutter Ratio (variante)

Versão normalizada do SCR usada em literatura de detecção:

```
TCR = (μ_T - μ_C) / σ_C

onde:
  μ_T = amplitude média na caixa do alvo
  μ_C = amplitude média em região de clutter
  σ_C = desvio padrão do clutter

TCR > 2.5: boa detectabilidade (critério Neyman-Pearson)
TCR > 5.0: detectabilidade robusta
```

### 5.9 Score composto C3/Dou para detecção

O algoritmo C3 (Dou et al., 2017) propõe uma pontuação ponderada para candidatos a hipérbole que integra múltiplas métricas:

```
Score = w1·P_model + w2·SCR + w3·CNR + w4·G_hyperbola - w5·R_superficial

onde:
  P_model      = probabilidade do modelo hiperbólico (R² do CurveFit)
  SCR          = Signal-to-Clutter Ratio na janela do alvo
  CNR          = Contrast-to-Noise Ratio
  G_hyperbola  = grau de simetria da hipérbole (braço esq. vs dir.)
  R_superficial = penalização por proximidade à superfície (falsos positivos onda direta)
  
  Pesos originais Dou et al.: w1=0.4, w2=0.2, w3=0.2, w4=0.15, w5=0.05
```

**Adaptação no ScanSOLO:** O score atual usa R² (P_model) + amplitude relativa + simetria + DeltaT + SNR_local. A estrutura é equivalente, mas os pesos foram calibrados empiricamente com os DZTs PATIO.

### 5.10 Loop de validação de processamento

O documento GPT recomenda um loop de validação após cada estágio:

```
Para cada estágio [dewow, bandpass, bgremoval, tpow, AGC]:
  1. Calcular ΔSNR  = SNR_depois - SNR_antes    (deve ser ≥ 0)
  2. Calcular ΔSCR  = SCR_depois - SCR_antes    (deve ser ≥ 0)
  3. Calcular ΔCNR  = CNR_depois - CNR_antes    (deve ser ≥ 0 para alvos conhecidos)
  
  Se qualquer Δ < threshold_rejeição → ALERTA de pipeline
  (estágio pode estar degradando o sinal)
```

**Implementação prática (sprint futuro):** Calcular métricas antes/depois de cada filtro e salvar em `pipeline_metrics.json` por DZT. Comparar contra thresholds salvos na calibração com Amilson.

---

## 6. Detector de Hipérboles — Teoria e Implementação

### 6.1 Fundamento geofísico

Alvos pontuais ou cilíndricos subsuperficiais produzem **hipérboles de difração** no B-scan GPR. A forma exata da hipérbole é determinada pela velocidade do meio e pela profundidade do alvo.

Fit da hipérbole:
```
t(x) = (2/v) × sqrt(d² + (x - x₀)²)

parâmetros a estimar: d (profundidade), x₀ (posição horizontal), v (velocity)
```

### 6.2 Pipeline do detector (ScanSOLO v1.1)

```
[arr_detector] → Hough adaptado → CurveFit → DeltaT → Física → Score
```

**Etapa 1 — Hough transform adaptada:**
- Varre depths de h_min a h_max em passo h_step
- Para cada profundidade, calcula template de hipérbole teórica
- Acumula votos nos pontos que correspondem ao template
- Identifica picos de acumulação por NMS (Non-Maximum Suppression)

**Etapa 2 — CurveFit (mínimos quadrados):**
- Para cada candidato Hough, extrai janela de dados ao redor
- Ajusta hipérbole por `scipy.optimize.curve_fit` (NLLS)
- Valida R² e simetria dos braços
- 82% taxa CurveFit com entrada `arr_raw` (melhor resultado)
- 24% com `proc_agc_atual` (AGC distorce a forma da hipérbole)

**Etapa 3 — DeltaT:**
- Analisa diferença temporal entre reflexão do topo e do fundo do objeto
- Estima diâmetro: `diam_est_m = v × Δt / 2`
- Confiança da estimativa DeltaT: `dt_conf_frac` (default 0.20)

**Etapa 4 — Enriquecimento físico:**
- Usa `arr_sem_agc` para amplitude absoluta (AGC não aplicado)
- Usa `arr_raw` como evidência independente
- Classifica: possivel_metalico, possivel_nao_metalico, possivel_galeria_ou_vazio, inconclusivo

### 6.3 Score composto 0–100

O score é calculado como soma ponderada de critérios:

| Critério | Evidência | Peso indicativo |
|---|---|---|
| R² do CurveFit | fit_ok (R² ≥ limiar) | Alto |
| Amplitude relativa | > amp_threshold | Médio |
| Simetria dos braços | largura esq ≈ dir | Médio |
| DeltaT consistente | Δt razoável para diâmetro | Médio |
| SNR local | sinal/ruído na janela do alvo | Baixo–médio |
| Profundidade mínima | depth ≥ det_depth_min_m | Filtro hard |
| Evidência raw | confirmação no arr_raw | Bônus |
| Evidência sem AGC | confirmação no arr_sem_agc | Bônus |

**Labels por score:**
- score ≥ 70: `alta` confiança
- score 40–69: `media` confiança  
- score < 40: `baixa` confiança (em CSV mas não plotada se min_score_plot=40)

### 6.4 Parâmetros calibrados (PATIO 270 MHz)

```python
DEFAULT_PARAMS = {
    "v_m_per_s":          1.0e8,    # 0.1 m/ns — solo seco padrão
    "amp_threshold":      0.45,
    "h_min_m":            0.10,
    "h_max_m":            2.80,
    "h_step_m":           0.04,
    "col_search_half":    80,        # ≈ 3.0 * (n_traces / dist_max)
    "nms_radius_m":       0.50,
    "top_n":              30,
    "cf_wing_half_m":     2.0,
    "cf_amp_frac":        0.30,
    "dt_min_diam_m":      0.05,
    "dt_max_diam_m":      1.50,
    "dt_conf_frac":       0.20,
    "fis_amp_metal_thr":  0.75,     # [CALIBRAR]
    "fis_amp_nao_metal_thr": 0.40,  # [CALIBRAR]
}
```

### 6.5 Problema P10 — Pileup em 0.30m

Com DZTs de alto SNR (modo MINIMO, bandpass pulado), 232/341 alvos detectados estavam em exatamente `depth_m = 0.30m` nos 126 DZTs HELPER. Causas prováveis:
- Onda direta (airwave) aparece no topo do dado e passa pelo filtro de amplitude
- Com bandpass pulado, componentes de baixa frequência criam falsos picos de energia no topo
- `det_depth_min_m=0.30m` é justamente o limiar atual — esses alvos estão no limite

**Soluções possíveis:**
1. Elevar `det_depth_min_m` para `0.50m` em modo MINIMO
2. Forçar bandpass quando `snr_ratio > 100` (bandpass pulado só deveria ocorrer para dados já limpos com estrutura simples)
3. Aplicar time-zero correction explícita antes do detector
4. Adicionar penalização de score para candidatos com x_m muito baixo e depth ≈ depth_min

---

## 7. Velocity e Calibração de Profundidade

### 7.1 Métodos de estimativa de velocity

**Método 1 — DZT header (rhf_epsr):**
```
v = C / sqrt(rhf_epsr)  →  default, baixa confiança se epsr não calibrado
```

**Método 2 — Semblance velocity analysis (implementado no ScanSOLO):**
- Analisa coerência do sinal em função de velocity
- Máxima coerência → velocity estimada
- Vantagem: usa o dado real
- Desvantagem: requer hipérboles visíveis

**Método 3 — CMP (Common-Midpoint) analysis (RADAN 7):**
- Requer coleta bistática com antennas separadas
- Mais preciso, mas requer levantamento especial
- Não disponível nos dados ScanSOLO atuais

**Método 4 — Alvo de profundidade conhecida:**
- Usar estrutura de profundidade conhecida (tubo, cabo com registro)
- Medir TWTT do alvo e calcular v = 2×d / TWTT
- **Recomendado para calibração com Amilson**

### 7.2 Constantes dielétricas típicas e velocidades

| Material | εr | v (m/ns) | Profundidade útil 270MHz |
|---|---|---|---|
| Ar (vácuo) | 1.0 | 0.300 | ∞ |
| Água doce | 80.0 | 0.033 | Muito baixa |
| Gelo | 3.2 | 0.168 | Alta |
| Areia seca | 2–6 | 0.122–0.212 | Alta |
| Areia úmida | 10–30 | 0.055–0.095 | Média |
| Solo argiloso seco | 4–6 | 0.122–0.150 | Média–alta |
| Solo argiloso úmido | 10–40 | 0.047–0.095 | Baixa |
| Cascalho seco | 4–9 | 0.100–0.150 | Alta |
| Concreto | 6–11 | 0.090–0.122 | Média |
| Asfalto | 3–5 | 0.134–0.173 | Alta |
| Granito | 4–6 | 0.122–0.150 | Alta |

**Solo padrão ScanSOLO (PATIO/HELPER):** v = 0.1 m/ns, εr ≈ 9 (solo moderado)

### 7.3 Impacto de velocity errada

Uma velocity 20% errada resulta em:
- Profundidades 20% erradas em todos os alvos
- Diâmetros estimados via DeltaT 20% errados
- Hipérboles não colapsam corretamente na migração

**P2 (pendência):** `velocity_usada_mns` sempre = `velocity_estimada_mns` nos dados de teste. Requer sessão de calibração com Amilson.

---

## 8. Constantes Dielétricas de Materiais

Tabela estendida do Apêndice D do manual GSSI SIR-30:

| Material | εr (típico) | εr (range) | Aplicação |
|---|---|---|---|
| Ar | 1 | 1 | Referência |
| Água doce | 80 | 80 | — |
| Água salgada | 81 | 81 | — |
| Gelo | 3.2 | 3–4 | — |
| Neve fresca | 1.4 | — | — |
| Permafrost | 4–8 | 1–8 | — |
| Solo arenoso seco | 4 | 2–6 | Alta velocidade |
| Solo arenoso úmido | 25 | 10–30 | — |
| Solo argiloso | 8 | 5–40 | Variável conforme umidade |
| Solo úmido | 25 | 15–40 | — |
| Cascalho seco | 7 | 4–9 | — |
| Cascalho úmido | 15 | 10–20 | — |
| Calcário | 7 | 4–20 | — |
| Granito | 5 | 4–6 | — |
| Argila seca | 5 | 2–20 | — |
| Concreto | 8 | 6–11 | — |
| Asfalto | 4 | 3–5 | — |
| PVC | 3 | — | Tubulação plástica |
| Ferro/Aço | ∞ | — | Condutor perfeito |
| Cobre | ∞ | — | Cabos |

---

## 9. Workflow RADAN 7 — Referência Canônica

### 9.1 Fluxo "Easy Processing"

O RADAN 7 implementa um fluxo padrão:
1. **Time Zero Correction** — `Processing > Time Zero`
2. **Background Removal** — `Processing > FIR Filter > BKGR REMOVAL`
3. **Migration** — `Processing > Migration`

**Parâmetros FIR do RADAN:**
- Filter Design: `TRIANGLE` (FIR com janela triangular)
- Horizontal Type: `BKGR REMOVAL`
- Length: máximo de scans do perfil (ex: 1307 para full-width)

### 9.2 Workflow técnico completo RADAN

1. **Time Zero** — ajuste da superfície
2. **Background Removal (FIR BKGR REMOVAL)** — remove bandas horizontais
3. **Frequency Filtering** — visualizar espectro, identificar frequências ruins, aplicar FIR pass
4. **Migration (Constant Velocity)** — colapsa hipérboles
5. **CMP Velocity Analysis** — para dados bistáticos (step/offset CMP)
6. **Distance Normalization** — para dados coletados em modo tempo (não distância)
7. **Deconvolution** — remove ringing residual
8. **Horizontal Scaling** — stacking ou interpolação horizontal
9. **Range Gain** — ganho de alcance (tpow ou exponencial)

### 9.3 Process Lists (macros RADAN)

O RADAN 7 permite criar listas de processos (macros) reutilizáveis. Listas pré-definidas por aplicação:
- **Asphalt**: otimizado para pavimentos
- **Concrete**: otimizado para estruturas de concreto
- **Utilities**: otimizado para detecção de tubulações/cabos

### 9.4 IIR vs FIR — Quando usar cada um

| Filtro | Tipo | Fase | Uso recomendado GSSI |
|---|---|---|---|
| High Pass IIR | Vertical | Não-linear (leve shift) | **Coletar com High Pass IIR** — remove wow antes do ganho |
| Low Pass IIR | Vertical | Não-linear | Uso geral pós-coleta |
| High/Low Pass FIR | Vertical | Linear (sem distorção) | **Preferido no pós-processamento** |
| Background Removal IIR/FIR | Horizontal | — | Remover bandas horizontais |
| Stacking IIR/FIR | Horizontal | — | Suavização espacial, 3–7 traços |

**Princípio GSSI:** Usar High Pass IIR na coleta para remover wow antes do ganho. No pós-processamento, preferir FIR por melhor resposta de fase.

---

## 10. Comparativo de Softwares GPR

### 10.1 Tabela comparativa — funcionalidades principais

Baseado em Especificação de Engenharia (Gemini) + Relatório Técnico (GPT), 2026:

| Software | Fabricante | DZT | Processamento | Migração | IA/ML | Licença | Nota |
|---|---|---|---|---|---|---|---|
| **RADAN 7** | GSSI | ✅ Nativo | BGR, FIR, Deconv, Distance Norm, EZ Tracker | Kirchhoff constante | ❌ | Proprietária | Referência canônica para GSSI |
| **GPR-SLICE** | Geophysical Archaeometry Lab | ✅ | Foco em análise 3D, time slices, volume | Sim | ❌ | Proprietária | Melhor para grids 3D |
| **ReflexW** | Sandmeier Software | ✅ | Suite completa (dewow, BP, BGR, deconv, migration) | Kirchhoff, Stolt, difração | Limitado | Proprietária | Mais completo para pesquisa |
| **IDS GRED HD** | IDS GeoRadar | Formato próprio | Orientado a inspeção civil | Sim | Básico | Proprietária | Forte em redes de utilities |
| **MALÅ Vision** | MALÅ / Guideline Geo | Formato MALÅ | Processamento integrado | Sim | ❌ | Proprietária | Integrado ao hardware MALÅ |
| **EKKO_Project** | Sensors & Software | Formato EKKO | Processamento completo | Kirchhoff | ❌ | Proprietária | Padrão Sensors & Software |
| **GPRPy** | NSGeophysics | ✅ (parcial) | dewow, bgremoval, agcGain, tpow, migração | FK Kirchhoff (irlib) | ❌ | MIT (open) | Referência Python científica |
| **readgssi** | iannesbitt | ✅ Completo | BGR, dewow, FIR triangular, bandpass | ❌ | Apache 2.0 (open) | Parser DZT mais completo em Python |
| **Road Doctor** | Roadscanners | Formato próprio | Orientado a pavimentos | Sim | ML básico | Proprietária | Líder em road inspection |
| **Geolitix** | Geolitix | Múltiplos | Cloud-based | Sim | ML (cloud) | SaaS | Processamento na nuvem |
| **Condor** | n/d | Múltiplos | Detecção automática | Sim | ML/DL | Proprietária | Foco em detecção automática |
| **RGPR** | E. Huber | ✅ (parcial) | Suite completa (R language) | Kirchhoff, topographic | ❌ | GPL (open) | Melhor documentação científica |

### 10.2 Funcionalidades específicas relevantes

**Distance Normalization (RADAN 7, ReflexW):**
Essencial para dados coletados em modo tempo (time mode). Reamostras traços para espaçamento uniforme em distância. **Ausente no ScanSOLO — GAP identificado (P10-pendência nova).**

**EZ Tracker (RADAN 7):**
Rastreamento semi-automático de horizontes ("Oreo pattern" — reflexão positiva-negativa-positiva). Identifica a wavelet e rastreia ao longo do perfil. Candidato para futura implementação no ScanSOLO (rastreamento de pipes contínuos).

**Kirchhoff vs Stolt (ReflexW, RADAN):**
- Kirchhoff: funciona com velocidade variável, mais lento
- Stolt (ReflexW): velocidade constante, O(N²logN) — 10× mais rápido para grandes datasets

**IIR na coleta vs FIR no pós-processamento (RADAN 7):**
- IIR High Pass: coletar com este filtro ativo para remover wow antes do ganho automático da unidade
- FIR no pós: melhor resposta de fase, sem distorção temporal

### 10.3 Posicionamento do ScanSOLO

| Capacidade | RADAN 7 | ReflexW | ScanSOLO v2.0.0 | Gap |
|---|---|---|---|---|
| Leitura DZT nativa | ✅ | ✅ | ✅ (via GPRPy) | — |
| Parser .DZX | ✅ | ✅ | ❌ | GAP-02 |
| Distance Normalization | ✅ | ✅ | ❌ | **Novo GAP** |
| Time-zero automático | ✅ | ✅ | Parcial (via GPRPy) | GAP-01 |
| FIR Triangular | ✅ | ✅ | ❌ (usa Butterworth) | GAP-06 |
| Migração Kirchhoff | ✅ | ✅ | ✅ (numpy próprio) | Qualidade não validada |
| Migração Stolt | ❌ | ✅ | ❌ | Baixa prioridade |
| SVD/KL clutter | ❌ | Parcial | ❌ | GAP novo |
| BGR | ✅ | ✅ | ✅ | — |
| Detecção automática | EZ Tracker (semi) | ❌ | ✅ Hough+CurveFit | ScanSOLO superior |
| IA por alvo | ❌ | ❌ | ✅ GPT-4o | ScanSOLO único |
| Pipeline automatizado | Manual | Manual | ✅ worker Railway | ScanSOLO superior |
| Web/cloud | ❌ | ❌ | ✅ Vercel+Railway | ScanSOLO único |
| Rastreabilidade | Limitada | Limitada | ❌ | **Novo GAP** |

---

## 11. readgssi — Referência de Implementação Aberta

### 10.1 O que o readgssi faz

Biblioteca Python open-source para leitura e processamento de dados GSSI. Referência canônica para parsing de DZT.

**GitHub:** https://github.com/iannesbitt/readgssi

### 10.2 Módulos principais

| Módulo | Função |
|---|---|
| `readgssi.dzt` | Parser do arquivo .DZT (header + array + GPS) |
| `readgssi.dzx` | Parser do arquivo .DZX (metadados XML, marks, picks) |
| `readgssi.filtering` | BGR, dewow, bandpass (butterworth e triangular FIR) |
| `readgssi.functions` | Utilitários (printmsg, etc.) |
| `readgssi.gps` | Leitura de arquivo .DZG (GPS) |
| `readgssi.plot` | Renderização de radargramas |
| `readgssi.translate` | Exportação para CSV, NumPy, etc. |
| `readgssi.constants` | Constantes físicas, tabela de antenas, BPS |

### 10.3 Tabela de antenas GSSI (readgssi constants)

```python
ANT = {
    '100MHz': 100, '200MHz': 200, '200HS': 200, '270MHz': 270,
    '350MHz': 350, '400MHz': 400, '500MHz': 500, '800MHz': 800,
    '900MHz': 900, '1600MHz': 1600, '2000MHz': 2000,
    '50270': 270, '50270S': 270,     # códigos internos 270 MHz
    '5103': 400, '5103A': 400,        # códigos internos 400 MHz
    # ... demais antenas ...
}
```

**Importante:** A antena `270MHz` (código `50270` ou `50270S`) é usada no ScanSOLO. Confirmar que o header DZT contém o nome correto para identificação automática.

### 10.4 Output do readdzt()

```python
header, data, gps = readdzt('arquivo.DZT')

# header — dicionário com todos os campos do header
# data   — dict de arrays por canal: {0: array(n_samples, n_traces)}
# gps    — DataFrame com dados GPS (ou DataFrame vazio se não houver)

# Campos importantes do header:
header['rh_nsamp']   # amostras por traço
header['rh_nchan']   # número de canais
header['rhf_range']  # TWTT máximo (ns)
header['rhf_spm']    # scans por metro
header['rhf_epsr']   # constante dielétrica
header['antfreq']    # lista de frequências de antena por canal
header['timezero']   # time-zero por canal
header['samp_freq']  # frequência de amostragem (Hz)
header['marks']      # lista de índices de marcas do usuário
header['picks']      # picks do DZX
```

### 10.5 Diferenças readgssi vs GPRPy

| Aspecto | readgssi | GPRPy |
|---|---|---|
| Foco | Processamento batch/field QC | Análise científica interativa |
| Saída header | Dict detalhado (todos campos) | Dict simplificado (campos principais) |
| Filtragem | BGR, dewow, triangular FIR | dewow, bgremoval, agcGain, tpow |
| GPS | Suporta DZG + CSV | Limitado |
| DZX | Suporta marks + picks | Não suporta |
| Exportação | CSV, NumPy, PNG, SGY | PNG, CSV |
| Migração | Não implementada | `fkMigration` (requer irlib) |

---

## 12. IA Aplicada ao GPR — Estado da Arte

### 12.1 Arquiteturas de ML para detecção de hipérboles

| Arquitetura | Input | Saída | Performance reportada | Dataset |
|---|---|---|---|---|
| **YOLOv8m-CAFM** | B-scan (imagem) | Bounding box da hipérbole | >95% mAP (metal/plástico) | CLT-GPR público |
| **Faster-RCNN** | B-scan | Bounding box | ~90% AP em pipelines | Bridge Deck dataset |
| **U-Net** | B-scan | Máscara pixel-a-pixel | Alta precisão para delineação | Dados sintéticos |
| **CNN custom** | Patch da hipérbole | Classificação tipo | ~85% em condições controladas | Variados |
| **ViT (Vision Transformer)** | B-scan patches | Detecção/classificação | Emergente, dados requerem muitos exemplos | Limitado |

### 12.2 Datasets públicos disponíveis

| Dataset | Conteúdo | Uso | Fonte |
|---|---|---|---|
| **CLT-GPR** | B-scans rotulados, hipérboles de tubulações | Treino/validação YOLOv8 | Público |
| **Bridge Deck** | Dados de inspeção de pontes (concreto, armadura) | Treino Faster-RCNN | Público (parcial) |
| **Dados sintéticos gprMax** | FDTD simulado com ground truth exato | Augmentação de dados | Gerado localmente |
| **HELPAVPA** | 126 DZTs + imagens RADAN do Amilson | Gold set ScanSOLO | Interno (disponível) |

### 12.3 gprMax — Simulador FDTD

**O que é:** Simulador de diferenças finitas no domínio do tempo (FDTD) para GPR. Gera dados sintéticos com ground truth perfeito.

```python
# Exemplo de configuração gprMax para tubulação circular a 1m
# arquivo: pipe.in
#domain: 5.0 5.0 0.001   # 5m x 5m (x, z)
#dx_dy_dz: 0.005 0.005 0.001  # resolução 5mm
#time_window: 4e-8           # 40ns window
#
#material: 4 0.001 1 0 soil   # solo: epsr=4, sigma=0.001
#cylinder: 2.5 1.0 0.0 2.5 1.0 1.0 0.05 free_space  # tubo oco, centro 2.5m,1m, raio 0.05m
#
#waveform: ricker 1 2.7e8 myricker
#hertzian_dipole: z 0.0 0.0 0.0 myricker   # transmissor em x=0
#rx: 0.1 0.0 0.0                            # receptor 10cm atrás
#src_steps: 0.02 0 0  # passo 2cm
#rx_steps: 0.02 0 0
```

**Estratégia de augmentação para ScanSOLO:**
1. Simular alvos de cada tipo (metal, PVC, concreto, vazio) em solos PATIO-like (ε_r=4–9)
2. Adicionar ruído realístico (ruído branco + clutter sintético)
3. Mixar com dados reais HELPER para treino
4. Manter conjunto PATIO 100% como teste independente (nunca visto no treino)

### 12.4 Princípio: IA como assistente, não árbitro

O documento GPT estabelece o princípio fundamental:

> **"IA deve ser assistiva, não decisória."**

Implicações concretas para o ScanSOLO:
- O detector Hough+CurveFit gera candidatos com razões auditáveis (R², amplitude, simetria)
- O GPT-4o interpreta mas NÃO decide — Amilson (geofísico) tem veto
- `vai_para_relatorio` nunca é `true` sem confirmação humana (exceto `auto_accept_ia=true` por decisão explícita do usuário)
- O score composto é **explicável por componente** — o relatório deve mostrar POR QUE cada alvo tem score X

### 12.5 Pipeline IA recomendado (baseado no estado da arte)

```
[arr_detector] 
    ↓
[Detector clássico Hough+CurveFit] → candidatos com score e razões
    ↓
[Classificador CNN/YOLO — quando disponível] → probabilidades por tipo
    ↓
[GPT-4o multimodal] → interpretação contextual (tipo_obra, solo, histórico)
    ↓
[Interface Amilson] → aprovação, rejeição, ajuste de tipo
    ↓
[Relatório com rastreabilidade completa]
```

**Integração score clássico + ML:**
```python
score_final = 0.6 * score_classico + 0.4 * prob_ml_classe_correta
# Pesos revisáveis após calibração com gold set
```

---

## 13. Rastreabilidade e Auditoria de Pipeline

### 13.1 Por que rastreabilidade é crítica

Em GPR profissional (utilities mapping), os resultados têm implicações de segurança. Um relatório errado pode levar a uma retroescavadeira perfurar um cabo de alta tensão. Portanto:

- Cada imagem gerada deve ser reproduzível exatamente
- Cada decisão de detecção deve ter fundamento auditável
- Cada versão de pipeline deve ser identificável no output

### 13.2 Metadados obrigatórios por imagem (recomendação Gemini/GPT)

Cada PNG/imagem gerada deve carregar no nome do arquivo e/ou em JSON associado:

```json
{
  "file_hash_sha256": "abc123...",   // hash do DZT original
  "pipeline_version": "2.0.0",
  "pipeline_branch": "main",         // ou hash do commit git
  "run_id": "uuid-do-run",
  "timestamp_utc": "2026-06-16T14:30:00Z",
  "preset_used": "270mhz",
  "filter_overrides": {},            // quaisquer overrides manuais
  "snr_raw_db": 20.6,
  "snr_cientifico_db": 26.1,
  "snr_relatorio_db": 8.3,
  "modo_processamento": "padrao",
  "tipo_solo": "standard",
  "detector_input_mode": "raw",
  "n_candidatos_hough": 45,
  "n_candidatos_curvefit": 37,
  "n_alvos_csv": 12,
  "metrics": {
    "ΔSNR_dewow": 1.2,
    "ΔSNR_bandpass": 2.8,
    "ΔSNR_tpow": 3.1
  }
}
```

### 13.3 Quatro imagens de saída obrigatórias

Para cada DZT processado, o pipeline deve sempre gerar:

| Imagem | Conteúdo | Fluxo | Finalidade |
|---|---|---|---|
| `_bruta.png` | Dado bruto sem qualquer processamento | Raw | Evidência de campo, QC visual |
| `_radargrama_cientifico.png` | dewow+bp+tpow, sem AGC/BGR | Científico | Revisão geofísica, base das anotações |
| `_radargrama_relatorio.png` | +BGR+AGC | Relatório | Entrega ao cliente, PDF |
| `_anotada_completa.png` | Científico + hipérboles detectadas | Detector | Revisão técnica Amilson |

Imagens adicionais (preview RADAN 5m, migrada, interpretada) são extensões, não substitutos.

### 13.4 AuditTrail — componente de rastreamento

Cada execução do pipeline deve registrar em `audit_trail.jsonl` (append-only):

```python
import json
from datetime import datetime, timezone

def registrar_auditoria(projeto_id, run_id, evento, dados):
    entrada = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "projeto_id": projeto_id,
        "run_id": run_id,
        "evento": evento,    # ex: "pipeline_iniciado", "alvo_detectado", "job_ia_concluido"
        "dados": dados,
        "pipeline_version": "2.0.0",
    }
    caminho = f"logs/{projeto_id}/audit_trail.jsonl"
    with open(caminho, 'a') as f:
        f.write(json.dumps(entrada) + '\n')
```

**Eventos a registrar:**
- `pipeline_iniciado` — parâmetros, hash do DZT, modo
- `snr_calculado` — valor raw, modo selecionado
- `filtro_aplicado` — estágio, ΔSNR antes/depois
- `alvo_detectado` — rank, profundidade, score, componentes do score
- `ia_interpretacao` — tipo, confiança, custo token
- `revisao_tecnica` — aprovado/rejeitado, tipo_confirmado, revisado_por
- `relatorio_gerado` — versão do relatório, hash PDF

### 13.5 Métricas de validação de imagem

Além das métricas de sinal (SNR/CNR/SCR), o documento GPT recomenda validar as imagens por:

```python
def metricas_imagem(arr):
    envelope = np.abs(hilbert(arr, axis=0))
    return {
        # Entropia da imagem — alta = mais informação vs baixa = imagem saturada/plana
        "entropia": -np.sum(p * np.log2(p + 1e-10) 
                    for p in np.histogram(envelope, 256, density=True)[0]),
        
        # Energia por faixa de profundidade — detecta se ganho foi excessivo
        "energia_por_quarto": [
            float(np.mean(envelope[i*n//4:(i+1)*n//4, :]**2))
            for i, n in [(j, envelope.shape[0]) for j in range(4)]
        ],
        
        # Saturação — % de amostras no máximo do range
        "saturacao_pct": float(np.mean(np.abs(arr) > 0.95 * np.max(np.abs(arr))) * 100),
    }
```

**Thresholds de alerta:**
- `saturacao_pct > 5%` → AGC ou ganho excessivo → reduzir AGC window
- `entropia < 3 bits` → imagem muito uniforme → verificar BGR excessivo
- `energia_por_quarto[3] > energia_por_quarto[0]` → mais energia profunda que superficial → pode indicar erro de tpow

---

## 14. Pipeline ScanSOLO v2.0.0 — Arquitetura Atual

### 14.1 Três fluxos separados

```
DZT
 ↓ GPRPy read
arr_raw (float32) ────────────────────────────────→ [raw.npy]
 ↓ SNR gate
modo = {minimo, padrao, agressivo}
 ↓ dewow(window=5)
 ↓ bandpass(80-500MHz, order=5)  [pular se modo=minimo]
arr_dewow_bp ─────────────────────────────────────→ [Preview RADAN 5m]
 ↓ tpow manual (sobre cópia)              ↓ bgremoval(30 traces)
arr_cientifico ──────────────────→ [PNG]  ↓ tpow (no prof.data)
[radargrama_cientifico.npy]       arr_sem_agc ────→ [PNG relatório]
                                  [processado_sem_agc.npy]
                                   ↓ AGC(150)
                                  arr_visual ─────→ [processado.npy]

Detector ← arr selecionado por detector_input_mode (default: arr_raw)
         → Hough + CurveFit + DeltaT + Física
         → anotações desenhadas sobre arr_cientifico
```

### 14.2 Matrices numpy e suas finalidades

| Arquivo | Pipeline | Uso | Modificar? |
|---|---|---|---|
| `raw.npy` | Nenhum | Auditoria, ML futuro, evidência independente | NUNCA |
| `radargrama_cientifico.npy` | dewow+bp+tpow | Base das imagens anotadas; revisão Amilson | Somente leitura |
| `processado_sem_agc.npy` | bgremoval+tpow | Análise física: amplitude/fase/classificação | Somente leitura |
| `processado_visual.npy` | +AGC | Backward compat | Somente leitura |
| `processado.npy` | Alias visual | Backward compat | Somente leitura |

### 14.3 Flags CLI

```bash
python pipeline_v1.py \
  --input <pasta_dzts> \
  --output <pasta_saida> \
  --preset 270mhz \
  --sem-detector          # pula detecção
  --sem-fisica            # pula análises físicas
  --sem-ia-imagem         # pula gpt-image-1 [SEMPRE ATIVO no worker]
  --sem-migracao          # pula Kirchhoff
  --filter-config <json>  # override de parâmetros
  --solo {standard,arenoso,argiloso,umido,pedregoso}
  --detector-input {raw,raw_dewow_bandpass,sem_agc,proc_agc_atual}
```

### 14.4 Resultados de benchmark (PATIO 270 MHz)

| Modo detector | Taxa CurveFit | Falsos positivos |
|---|---|---|
| `raw` | **82%** | Baixo |
| `raw_dewow_bandpass` | 75% | Baixo |
| `sem_agc` | 70% | Médio |
| `proc_agc_atual` | 24% | **46%** |

---

## 15. Análise GAP — Estado Atual vs. Sistema Pronto

### 15.1 O que já funciona bem ✅

| Item | Status | Observação |
|---|---|---|
| Leitura de DZT via GPRPy | ✅ Funcional | Todos 4 DZTs PATIO lidos corretamente |
| Três fluxos separados (científico/relatório/detector) | ✅ Implementado v2.0.0 | Arquitetura correta |
| SNR gate automático | ✅ Calibrado para PATIO | Limiares precisam validação para outros solos |
| Detector Hough+CurveFit+DeltaT | ✅ 82% com arr_raw | Melhor resultado já alcançado |
| Imagem bruta, científica, relatório, anotada | ✅ 5 saídas por DZT | Incluindo Preview RADAN 5m |
| Reprocessamento individual por perfil | ✅ Polling + router.refresh | Resolvido em 2026-06-16 |
| Análise física (amplitude, fase, espectro) | ✅ Implementado | Thresholds não calibrados |
| Migração Kirchhoff (numpy) | ✅ Funcional | Qualidade vs GPRPy nativo não confirmada |
| Pipeline completo no Railway | ✅ Deploy estável | LibreOffice incluso para PDF |
| Relatório DOCX + PDF | ✅ Funcional | Via python-docx + LibreOffice |
| Cartografia DXF/KML/GeoJSON/CSV | ✅ Funcional | |
| IA GPT-4o por alvo | ✅ Funcional | Viés para galeria_concreto (P7) |
| Workflow de revisão técnica | ✅ Funcional | Aprovação/regeneração/canvas manual |

### 15.2 Gaps técnicos críticos ❌

#### GAP-01 — Time-Zero Correction explícita (PRIORIDADE ALTA)
**Problema:** O pipeline não realiza correção de time-zero explícita antes do processamento. O GPRPy usa `header['timezero']` implicitamente, mas não há validação se esse valor está correto para cada DZT.

**Impacto:** Profundidades de TODOS os alvos podem estar deslocadas por um valor fixo (o erro de time-zero). Isso invalida calibrações de velocity e comparações entre perfis.

**Solução:**
```python
def detectar_time_zero(arr_raw):
    """Detecta time-zero como amostra do primeiro pico positivo da média dos traços."""
    trace_media = np.mean(arr_raw, axis=1)
    envelope = np.abs(hilbert(trace_media))
    # Pico mais proeminente nas primeiras 20% das amostras
    search_end = int(0.20 * len(trace_media))
    time_zero = int(np.argmax(envelope[:search_end]))
    return time_zero

def aplicar_time_zero(arr, time_zero):
    return arr[time_zero:, :]
```

**Ação:** Adicionar ao início de `processar_dzt()`, antes do dewow.

---

#### GAP-02 — Parser .DZX não implementado (PRIORIDADE ALTA)
**Problema:** O sistema não lê o `.DZX`. Perde: GPS por waypoint, marcas do usuário, picks do RADAN, configurações do display, informação 3D.

**Impacto:** Dados de campo coletados com GPS perdem georreferenciamento por ponto. Marcas do operador de campo (indicando início/fim de seção) são ignoradas.

**Solução:** Implementar parser DZX baseado no readgssi `dzx.py` (XML com `xml.etree.ElementTree`). Salvar resultado em `metadata.json` junto com cada DZT processado.

---

#### GAP-03 — Velocity não calibrada (PRIORIDADE ALTA)
**Problema:** `velocity_usada_mns = velocity_estimada_mns` sempre. Não há validação com alvo de profundidade conhecida.

**Impacto:** Profundidades reportadas aos clientes podem estar erradas sistematicamente.

**Solução:** Implementar sessão de calibração — um único DZT com alvo de profundidade conhecida (ex: tubo de 1.5m de profundidade documentado). Salvar `velocity_calibrada=True` e o valor.

---

#### GAP-04 — Parâmetros físicos do detector não calibrados (PRIORIDADE ALTA)
**Problema:** `fis_amp_metal_thr=0.75` e `fis_amp_nao_metal_thr=0.40` são valores padrão sem calibração com dados reais.

**Impacto:** Classificação metal/não-metal incorreta. Relatórios para clientes podem conter classificações erradas.

**Solução:** Sessão com Amilson usando ~10 alvos de tipo conhecido. Atualizar thresholds no preset e adicionar campo `calibracao_fisica_data` no config.

---

#### GAP-05 — Pileup em depth_min=0.30m (PRIORIDADE MÉDIA)
**Problema:** 232/341 alvos em exatamente 0.30m nos DZTs HELPER (modo MINIMO).

**Solução imediata:**
```python
# Em vez de um limiar fixo, usar limiar adaptativo por modo
det_depth_min_m = {
    'minimo':    0.50,  # dados de alto SNR têm mais ruído superficial
    'padrao':    0.30,
    'agressivo': 0.20,
}[modo]
```

---

#### GAP-06 — FIR Triangular (estilo RADAN) não implementado (PRIORIDADE MÉDIA)
**Problema:** O bandpass usa Butterworth SOS (`scipy.butter`). O RADAN usa FIR triangular (`firwin` com `window='triangle'`). Resultados visuais diferentes.

**Impacto:** Output do ScanSOLO pode parecer diferente do RADAN para o mesmo dado, dificultando comparações com Amilson.

**Solução:** Implementar a variante FIR triangular do readgssi como opção `bandpass_tipo: 'fir_triangular'` no preset, mantendo o Butterworth como padrão para compatibilidade.

---

#### GAP-07 — Sem análise do espectro por frequência (PRIORIDADE MÉDIA)
**Problema:** Não há análise de espectro vertical antes do bandpass para identificar frequências problemáticas.

**Impacto:** O bandpass pode ser mal configurado se houver RFI (Radio Frequency Interference) em frequências específicas.

**Solução:**
```python
def analise_espectro_vertical(arr, fs_mhz):
    """Calcula espectro médio de amplitude por frequência."""
    from numpy.fft import fft, fftfreq
    n = arr.shape[0]
    freqs = fftfreq(n, d=1.0/fs_mhz)[:n//2]
    espectro = np.abs(fft(arr, axis=0))[:n//2, :].mean(axis=1)
    return freqs, espectro  # freqs em MHz

# Adicionar ao QC inicial: salvar spectrum.png e spectrum.json por DZT
```

---

#### GAP-08 — Deconvolução não implementada (PRIORIDADE BAIXA)
**Problema:** Ringing residual após bgremoval não é removido.

**Impacto:** Imagens de relatório podem ter artefatos de múltiplos que confundem o cliente.

---

#### GAP-09 — Sem presets por tipo de obra (PRIORIDADE MÉDIA)
**Problema:** Existe apenas o preset `270mhz` e um `default` idêntico. Para estratigrafia, pavimentos, ou solos muito úmidos, os parâmetros ideais são diferentes.

**Solução:** Implementar presets por objetivo (ver seção 14).

---

#### GAP-10 — IA com viés galeria_concreto (PRIORIDADE MÉDIA)
**Problema:** GPT-4o classifica ~80% dos alvos como `galeria_concreto` sem contexto do projeto.

**Solução:** Incluir no prompt:
- Tipo de obra (utilities, estruturas, pavimento)
- Tipo de solo
- Profundidade esperada dos alvos
- Histórico de alvos aprovados do mesmo projeto

---

#### GAP-11 — 113 imagens HELPER não processadas (PRIORIDADE BAIXA)
**Problema:** Apenas 13/126 imagens RADAN do Amilson foram testadas pelo `testar_imagem_externa.py`.

---

#### GAP-12 — Storage órfão no delete de projeto (PRIORIDADE BAIXA)
**Problema:** `deleteProject` remove registros do DB mas não arquivos do Supabase Storage.

---

#### GAP-13 — Distance Normalization ausente (PRIORIDADE MÉDIA)
**Problema:** Para dados coletados em modo tempo (não distância), os traços podem ter espaçamento irregular. Sem normalização, a escala horizontal está errada e a migração produz hipérboles deformadas.

**Impacto:** Medidas de posição horizontal de alvos incorretas. Migração produz resultado incorreto.

**Solução:** Implementar reamostramento linear ou cúbico dos traços para distância uniforme usando `rhf_spm` (scans/metro) do header DZT. Disponível em RADAN 7 como "Distance Normalization" step.

---

#### GAP-14 — Rastreabilidade de pipeline ausente (PRIORIDADE MÉDIA)
**Problema:** As imagens geradas não carregam metadados de rastreabilidade (hash do DZT, versão do pipeline, parâmetros usados). Não é possível reproduzir exatamente o mesmo resultado sem o código da data do processamento.

**Impacto:** Auditoria de resultados impossível. Em caso de questionamento de um relatório, não há como provar quais parâmetros geraram os resultados.

**Solução:** Implementar `audit_trail.jsonl` e metadados em `config_used.json` + `pipeline_metrics.json` por run (ver Seção 13).

---

#### GAP-15 — SVD/KL clutter não implementado (PRIORIDADE BAIXA)
**Problema:** Para dados com clutter intenso (ambiente urbano com EMI), o BGR remove apenas médias horizontais. SVD/KL seria mais cirúrgico.

**Solução:** Implementar como opção `bgremoval_metodo: 'svd'` com `svd_n_componentes: 3` no preset. Requer avaliação com Amilson.

---

### 15.3 Resumo GAP por impacto

| GAP | Impacto no cliente | Esforço estimado | Prioridade |
|---|---|---|---|
| GAP-01 Time-zero | ALTO (profundidades erradas) | Baixo (1-2h) | **CRÍTICO** |
| GAP-03 Velocity | ALTO (profundidades erradas) | Médio (requer sessão Amilson) | **CRÍTICO** |
| GAP-04 Física não calibrada | ALTO (tipo de material errado) | Médio (requer Amilson) | **CRÍTICO** |
| GAP-02 Parser DZX | MÉDIO (perde GPS/marcas) | Médio (2-4h) | ALTO |
| GAP-05 Pileup depth_min | MÉDIO (falsos positivos) | Baixo (30min) | ALTO |
| GAP-13 Distance Normalization | MÉDIO (escala horizontal errada) | Médio (3h) | ALTO |
| GAP-14 Rastreabilidade | MÉDIO (auditoria impossível) | Médio (4h) | ALTO |
| GAP-06 FIR Triangular | MÉDIO (diferença visual vs RADAN) | Baixo (1h) | MÉDIO |
| GAP-07 Análise espectro | BAIXO | Baixo (2h) | MÉDIO |
| GAP-09 Presets por obra | MÉDIO | Médio (4h) | MÉDIO |
| GAP-10 IA viés | MÉDIO (relatório impreciso) | Baixo (1h prompt) | MÉDIO |
| GAP-08 Deconvolução | BAIXO | Médio | BAIXO |
| GAP-11 Dataset HELPER | BAIXO | Alto (precisa Amilson) | BAIXO |
| GAP-12 Storage órfão | BAIXO | Baixo | BAIXO |
| GAP-15 SVD/KL clutter | BAIXO (ambiente urbano) | Médio | BAIXO |

---

## 16. Roadmap Técnico Priorizado

### Sprint 1 — Qualidade Técnica Fundamental (antes de qualquer entrega para produção)

**S1-01 — Time-zero correction explícita**
- Implementar `detectar_time_zero()` em `pipeline_v1.py`
- Registrar `time_zero_sample` no `index_projeto.csv`
- Validar com Amilson em 2 DZTs conhecidos

**S1-02 — Depth_min adaptativo por modo SNR**
- Trocar valor fixo `0.30m` por lookup `{minimo: 0.50, padrao: 0.30, agressivo: 0.20}`
- Teste imediato nos 126 DZTs HELPER (espera-se redução de 232 → << 50 falsos positivos)

**S1-03 — Distance Normalization**
- Verificar se DZTs são coletados em modo tempo ou distância
- Se modo tempo: implementar reamostramento linear por `rhf_spm`
- Adicionar campo `distance_normalized: bool` no `config_used.json`

**S1-04 — Rastreabilidade mínima (audit trail)**
- Gerar `pipeline_metrics.json` com ΔSNR por estágio
- Adicionar hash SHA256 do DZT ao `index_projeto.csv`
- Registrar versão do pipeline no `config_used.json` (já parcialmente feito)

**S1-05 — FIR Triangular como opção de bandpass**
- Implementar função baseada em readgssi `filtering.triangular()`
- Adicionar parâmetro `bandpass_tipo: 'butterworth'|'fir_triangular'` ao preset
- Gerar comparação visual para Amilson

**S1-06 — Prompt GPT-4o com contexto do projeto**
- Adicionar ao payload do job IA: `tipo_obra`, `tipo_solo`, `antena_freq`, histórico de tipos aprovados
- Esperado: redução do viés `galeria_concreto`

### Sprint 2 — Calibração e Dados Contextuais

**S2-01 — Sessão de calibração com Amilson**
- DZT com alvo de profundidade conhecida → calibrar velocity
- ~10 alvos de tipo confirmado → calibrar `fis_amp_metal_thr` e `fis_amp_nao_metal_thr`
- Comparação visual: `_radargrama_relatorio.png` vs output RADAN lado a lado

**S2-02 — Parser .DZX**
- Implementar leitura de GPS por waypoint, marcas e picks
- Salvar `metadata_dzx.json` junto ao processamento
- Integrar GPS no CSV de alvos (coordenadas absolutas por alvo)

**S2-03 — Análise de espectro vertical**
- Implementar `analise_espectro_vertical()` como step de QC
- Salvar `spectrum.png` e `spectrum.json` por DZT
- Alertar no log se houver pico de RFI acima de threshold

### Sprint 3 — Presets e Escalabilidade

**S3-01 — Presets por objetivo de obra**
- Implementar os 6 presets descritos na seção 14
- UI: seleção de objetivo na Nova Entrada
- Lógica: resolver preset final = base + override por tipo de solo + override manual

**S3-02 — Dataset HELPER completo**
- Processar as 113 imagens restantes com `testar_imagem_externa.py`
- Criar gold set anotado por Amilson
- Base para futura validação de precisão e treinamento de modelo

**S3-03 — Deconvolução**
- Implementar como step opcional no fluxo científico
- Parâmetro: `deconv_ativo: false` no preset, `deconv_operator_length` e `deconv_lag`

### Sprint 4 — IA e Produção

**S4-01 — Modelo YOLO/Faster-RCNN (fase futura)**
- Pré-requisito: gold set anotado (S3-02) + dados sintéticos gprMax (ver Seção 12)
- Estrutura: detector clássico fornece candidatos, modelo de IA refina score
- Score final = 0.6 × score_clássico + 0.4 × prob_ML
- Nunca substituir o detector clássico auditável — IA como segunda camada assistiva

**S4-02 — Storage cleanup no delete de projeto**
- Adicionar limpeza de Storage na `deleteProject` server action
- Listar arquivos por project_id em todos os buckets antes de deletar DB

---

## 17. Presets por Objetivo

### Tabela de presets recomendados

| Preset | Objetivo | Bandpass (MHz) | tpow | BGR | AGC | Notas |
|---|---|---|---|---|---|---|
| `utilities_270` | **Padrão ScanSOLO** | 80–500 | 0.5 | 30 traços | 150 | Atual, calibrado PATIO |
| `conservative` | Preservar sinal | 100–450 | 0.3 | **0 (off)** | **0 (off)** | Para revisão geofísica profunda |
| `detector` | Maximizar detecção | 80–500 | 0.4 | **0 (off)** | **0 (off)** | Entrada: arr_raw; sem AGC |
| `visual_report` | Relatório cliente | 80–500 | 0.5 | 30 traços | **100** | AGC agressivo para visual limpo |
| `stratigraphy` | Camadas/Estratigrafia | 80–300 | 0.3 | **0** | 0 | BGR off: preserva refletores horizontais |
| `high_freq_800` | Antena 800 MHz | 200–1500 | 0.4 | 30 traços | 100 | Para estruturas superficiais (<1m) |

### Configuração `conservative` (para revisão técnica Amilson)

```python
"conservative": {
    "descricao":          "Conservador — preserva sinal geofísico",
    "dewow_window":       5,
    "bandpass_low_mhz":   100,
    "bandpass_high_mhz":  450,
    "bandpass_order":     3,        # ordem menor = menos ripple
    "bgremoval_traces":   0,        # desativado
    "tpow_power":         0.3,      # ganho mínimo
    "agc_window":         0,        # desativado
    "velocity_mns":       0.1,
    "contrast":           3.0,
    "colormap":           "gray",
    "dpi":                150,
    "detector_input_mode": "raw_dewow_bandpass",
}
```

### Configuração `stratigraphy` (camadas, pavimentos)

```python
"stratigraphy": {
    "descricao":          "Estratigrafia — preserva refletores horizontais",
    "dewow_window":       7,
    "bandpass_low_mhz":   80,
    "bandpass_high_mhz":  300,       # menos agressivo no high
    "bandpass_order":     5,
    "bgremoval_traces":   0,         # CRÍTICO: off para não remover camadas
    "tpow_power":         0.3,
    "agc_window":         0,         # off
    "velocity_mns":       0.1,
    "contrast":           2.5,
    "colormap":           "gray",
    "dpi":                150,
    "det_depth_min_m":    0.50,      # evita ruído superficial
    "detector_input_mode": "raw_dewow_bandpass",
}
```

---

## 18. Checklist de Calibração com Amilson

### Sessão 1 — Validação visual (urgente, 2h)

- [ ] Comparar `_radargrama_cientifico.png` vs output RADAN para PATIO_001–004
- [ ] Confirmar que top-25 candidatos em cada PATIO são hipérboles reais (não artefatos)
- [ ] Validar se Preview RADAN 5m é comparável ao display RADAN (depth e velocity_preview)
- [ ] Confirmar se BGRemoval no fluxo de relatório está removendo refletores reais indesejados

### Sessão 2 — Calibração de velocity (1 campo + 2h análise)

- [ ] Identificar alvo de profundidade conhecida em campo (tubo documentado)
- [ ] Coletar DZT passando sobre o alvo
- [ ] Medir TWTT do alvo e calcular velocity real: `v = 2 × d_real / TWTT`
- [ ] Comparar `velocity_estimada_mns` (semblance) com velocity real
- [ ] Atualizar `velocity_mns` no preset se discrepância > 5%

### Sessão 3 — Calibração física do detector (2h com dados)

- [ ] Selecionar 10+ alvos com tipo confirmado (ex: 5 tubos metálicos, 5 plásticos)
- [ ] Extrair `amplitude_relativa_sem_agc` de cada alvo no CSV
- [ ] Plotar distribuição: metálicos vs não-metálicos
- [ ] Ajustar `fis_amp_metal_thr` e `fis_amp_nao_metal_thr` para separação ótima
- [ ] Validar em 5 alvos adicionais (hold-out)

### Sessão 4 — Validação do detector em HELPER

- [ ] Rodar pipeline completo nos 126 DZTs HELPER (aguarda calibração de velocity)
- [ ] Comparar com resultado RADAN de Amilson (imagens de referência disponíveis)
- [ ] Medir: taxa de detecção, falsos positivos, falsos negativos por tipo de alvo
- [ ] Decidir threshold `det_min_score_csv` adequado para este conjunto

### Sessão 5 — Prompt GPT-4o

- [ ] Testar prompt com contexto vs sem contexto em 20 alvos
- [ ] Medir: distribuição de tipos antes e depois do contexto
- [ ] Calibrar categorias de tipo para a realidade dos projetos ScanSOLO

---

## 19. Referências e Fontes

### Fontes primárias (confirmadas, documentadas)

| Fonte | Localização | Confiabilidade |
|---|---|---|
| GSSI SIR-30 Manual | `KB_ScansoloPlataform/GSSI-SIR-30-Manual.pdf` | ★★★★★ Oficial |
| RADAN 7 Manual | `KB_ScansoloPlataform/GSSI-RADAN-7-Manual.pdf` | ★★★★★ Oficial |
| readgssi — dzt.py | https://github.com/iannesbitt/readgssi | ★★★★★ Open source, ativo |
| readgssi — filtering.py | https://github.com/iannesbitt/readgssi | ★★★★★ Open source |
| readgssi — constants.py | https://github.com/iannesbitt/readgssi | ★★★★★ Open source |
| pipeline_v1.py v2.0.0 | `services/worker/pipeline/pipeline_v1.py` | ★★★★★ Código próprio |
| detector_hiperboles.py v1.1 | `services/worker/pipeline/detector_hiperboles.py` | ★★★★★ Código próprio |
| CLAUDE.md | `scansolo-platform/.claude/CLAUDE.md` | ★★★★★ Doc interna |
| Especificação de Engenharia (Gemini) | `KB_ScansoloPlataform/Sistema de Processamento...GEMINI.md` | ★★★★☆ Síntese técnica verificada |
| Relatório Técnico GPR/DZT (GPT) | `KB_ScansoloPlataform/RELATÓRIO TÉCNICO...GPT.md` | ★★★★☆ Análise crítica com rating de fontes |

### Fontes secundárias (para aprofundamento)

| Fonte | URL | Tema |
|---|---|---|
| RGPR | https://emanuelhuber.github.io/RGPR/ | Processamento GPR aberto (R) |
| GPRPy | https://github.com/NSGeophysics/GPRPy | Processamento GPR Python |
| gprMax | http://www.gprmax.com/ | Simulação FDTD para GPR |
| Dou et al. 2017 | C3 algorithm paper | Detecção automática hipérboles por clustering colunar |
| Yoder et al. 2012 | (paper) | Detecção automática hipérboles |
| YOLOv8m-CAFM | (paper, dataset CLT-GPR) | Detecção hipérboles com atenção cross-attention |
| ReflexW | https://www.sandmeier-geo.de/reflexw.html | Suite científica GPR completa |
| Dou Q. et al. | Bridge Deck dataset | Dataset público detecção GPR |

### Constantes físicas de referência

```python
C     = 2.99792458e8   # m/s (velocidade da luz no vácuo)
C_NS  = 0.299792458    # m/ns (conveniente para GPR)
Eps_0 = 8.8541878e-12  # F/m (permissividade do vácuo)
Mu_0  = 1.2566370e-6   # H/m (permeabilidade do vácuo)

# v = C / sqrt(Mu_0 * Eps_0 * epsr) = C / sqrt(epsr) para Mu_r = 1
```

---

*Documento gerado em 2026-06-16 — v2 (19 seções). Para uso interno do projeto ScanSOLO.*  
*Fontes: GSSI SIR-30 Manual, RADAN 7 Manual, readgssi, RGPR, pipeline_v1.py v2.0.0, CLAUDE.md, Especificação Gemini, Relatório GPT.*  
*Atualizar após cada sessão de calibração com Amilson.*  
*Manter sincronizado com CLAUDE.md.*
