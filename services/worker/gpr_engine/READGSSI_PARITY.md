# READGSSI_PARITY.md — Auditoria de Paridade Tecnica

> Fase 8.6 | Auditado em 2026-06-21
> Repositorio auditado: `lobernardo/readgssi` (fork de iannesbitt/readgssi)
> Path local: `C:/Users/leool/OneDrive/Documentos/Claude/Projects/ScanSOLO/readgssi/`

---

## Resumo executivo

O readgssi e nosso `gpr_engine` diferem principalmente em dois pontos:

| Dimensao | readgssi | gpr_engine (padrao) | Impacto visual |
|---|---|---|---|
| **Normalizacao** | SymLogNorm (linthresh=std/gain) | Percentil-99 linear | ALTO — readgssi preserva detalhes em amplitude baixa |
| **Interpolacao** | `bicubic` | padrao matplotlib | MEDIO — readgssi e mais suavizado |
| **Dewow** | Polinomial (grau 3, experimental) | Media movel (window=5) | BAIXO — ambos removem DC lento |
| **Bandpass FIR** | firwin numtaps=25, lfilter | firwin2 adaptativo + filtfilt | BAIXO-MEDIO — readgssi e mais rapido, menos seletivo |
| **BGR** | Global mean sempre; windowed opcional | Global OU windowed | BAIXO — logica ligeiramente diferente |
| **AGC** | Nao tem (ganho so no display) | AGC por RMS janelado | ALTO — readgssi nao normaliza amplitudes |
| **Tpow** | Nao tem | Rampa t^power | MEDIO — readgssi nao compensa atenuacao |

---

## Normalizacao visual — divergencia principal

### readgssi (`plot.radargram()`, linhas ~310-340)

```python
mean = np.mean(ar)
std  = np.std(ar)
ll   = mean - (std * 3)          # lower color limit
ul   = mean + (std * 3)          # upper color limit
norm = colors.SymLogNorm(
    linthresh = float(std) / float(gain),
    linscale  = 1,
    vmin      = ll,
    vmax      = ul,
    base      = np.e,
)
ax.imshow(ar, cmap='gray', interpolation='bicubic', norm=norm, ...)
```

**O que SymLogNorm faz:**
- Zona linear: `[-linthresh, +linthresh]` = `[-std/gain, +std/gain]`
  - Amplitudes pequenas (noise floor, reflexoes fracas) sao renderizadas linearmente
- Zona log: fora do intervalo linear
  - Grandes amplitudes (onda direta, multiplas) sao comprimidas para nao saturar
- `gain=1` (readgssi default): zona linear = [-std, +std] = amplitude tipica do dado
- `gain>1`: zona linear mais estreita (mais compressao) = maior contraste

**Por que e melhor que percentil-99 linear para GPR:**
- GPR tem dinamica muito alta: onda direta pode ser 100x maior que a reflexao mais fraca
- Percentil-99 linear: se onda direta domina, reflexoes fracas ficam todas na mesma cor
- SymLogNorm: comprime a onda direta logaritmicamente e expande as reflexoes fracas

### gpr_engine atual (`images.py`, `_compute_vrange`)

```python
vm = float(np.percentile(np.abs(finite), 99))
vmin = -vm / contrast   # contrast=2.5 padrao
vmax = +vm / contrast
ax.imshow(arr, vmin=vmin, vmax=vmax, ...)  # linear, sem norm
```

### Perfil implementado: `readgssi_reference`

Adicionado em `images.py::render_radargram_readgssi_reference()`:
- SymLogNorm identico ao readgssi (linthresh=std/gain, linscale=1, base=e)
- interpolation='bicubic'
- Gerado sempre como `{stem}_radargrama_readgssi_reference.png`
- Array de entrada: `arr_raw -> bgremoval_readgssi(window=0)` (minimal processing)

---

## Filtros — divergencias detalhadas

### 1. Dewow

| | readgssi | gpr_engine |
|---|---|---|
| Algoritmo | Polynomial fit grau 3 em trace[10], aplica como offset | Media movel window=5 por coluna |
| Estabilidade | Marcado "experimental" no codigo | Bem estabelecido (equivale GPRPy.dewow) |
| Parametro | Sem parametro de window | `dewow_window=5` |

Decisao: manter nossa implementacao. Dewow polinomial do readgssi e instavel e nao tem parametros uteis.

### 2. Bandpass (triangular FIR)

| | readgssi | gpr_engine |
|---|---|---|
| Funcao scipy | `firwin(numtaps=25, window='triangle')` | `firwin2(freqs, gains)` com resposta triangular |
| numtaps | 25 (fixo) | `max(101, ceil(fs/fl)*3)` (adaptativo) |
| Aplicacao | `lfilter` + reverso (zerophase aproximado) | `filtfilt` (zerophase exato) |

- readgssi numtaps=25 e muito baixo para 270 MHz antena (fs ~4 GHz):
  resolucao em frequencia ~160 MHz/tap, insuficiente para separar 80-500 MHz
- Nossa versao e superior; implementamos `bandpass_triangular_readgssi` em `filters.py`
  para fins de auditoria/reproducao exata

### 3. Background removal (BGR)

| | readgssi | gpr_engine |
|---|---|---|
| Global | `row -= np.mean(row)` por linha | `f - f.mean(axis=1, keepdims=True)` — identico |
| Windowed | global DEPOIS `uniform_filter1d(mode='constant', cval=0)` | global OU windowed (nao ambos) |
| Ordem windowed | Dois passes: global + janela | Um passe: janela apenas |

Implementamos `bgremoval_readgssi()` em `filters.py` com logica exata do readgssi.

### 4. AGC

readgssi nao tem AGC como step de processamento. Usa SymLogNorm como "AGC visual" no display.

Nosso gpr_engine separa AGC (array) de normalizacao visual — abordagem mais transparente para analise quantitativa.

### 5. Tpow

readgssi nao tem tpow. Compensacao de atenuacao e feita implicitamente pela SymLogNorm (log de amplitudes maiores = menos ganho).

---

## Ordem dos filtros no readgssi

Sequencia confirmada em `readgssi/readgssi/readgssi.py`:

```
normalize (offset DC) -> dewow -> triangular bandpass -> stack -> bgr -> reverse
```

Sequencia no gpr_engine (fluxo cientifico):
```
dewow -> bandpass -> tpow
```

Sequencia no gpr_engine (fluxo relatorio):
```
dewow -> bandpass -> bgremoval -> tpow -> AGC
```

---

## Leitura de DZT — paridade confirmada

### Shape do array

readgssi (`dzt.arraylist()`, linha ~57-71):
```python
data = data.astype(np.int32)
img_arr = data[:header['rh_nchan']*header['rh_nsamp']]
new_arr[ar] = a[header['timezero'][ar]:, :]  # timezero slicing
```
Shape final: `(n_samples - timezero, n_traces)` — mesma convencao que nosso engine.

**Diferenca**: readgssi faz crop pelo timezero; nosso engine retorna o array completo
(timezero detectado mas nao aplicado nesta fase).

### samp_freq

readgssi:
```python
header['samp_freq'] = 1 / ((dzt_depth * 2) / (rh_nsamp * cr_true))
                    = rh_nsamp * cr_true / (2 * dzt_depth)
                    = rh_nsamp / twtt_max_s
```

gpr_engine:
```python
samp_freq_hz = 1.0 / (dt_ns * 1e-9) = n_samples / twtt_max_s
```

Identico. Nenhuma divergencia.

---

## Implementacoes adicionadas (Fase 8.6)

### `filters.py`

```python
bgremoval_readgssi(arr, window=0) -> np.ndarray
    # Replica exata do readgssi/filtering.bgr()

bandpass_triangular_readgssi(arr, samp_freq_hz, low_mhz, high_mhz, zerophase=True) -> np.ndarray
    # Replica exata de readgssi/filtering.triangular()
    # numtaps=25, firwin window='triangle', lfilter + reverse
```

### `images.py`

```python
render_radargram_readgssi_reference(arr, output_path, dist_total_m, depth_max_m,
                                    gain=1.0, ...) -> Path
    # SymLogNorm(linthresh=std/gain, linscale=1, vmin=mean-3*std, vmax=mean+3*std, base=e)
    # interpolation='bicubic'
```

### `pipeline.py`

Novos campos em `_DEFAULTS`:
```python
"visual_profile": "scientific",  # "scientific" | "readgssi_reference"
"gain": 1.0,
```

Novo output em `process_dzt`:
- `{stem}_radargrama_readgssi_reference.png` — sempre gerado, entrada arr_raw -> bgr_readgssi
- Disponivel em `ProcessResult.image_paths["readgssi_reference"]`
- Disponivel em `index_row["imagem_readgssi_reference"]`

---

## Pendencias para calibracao com Amilson

1. **Comparacao visual readgssi_reference vs cientifico vs RADAN real**
   Mostrar os tres lado a lado para o mesmo DZT e decidir qual e o canal principal de revisao tecnica.

2. **gain otimo**: readgssi usa `gain=1` por padrao. Testar `gain=2` (linthresh=std/2)
   para maior contraste em DZTs de solo argiloso (menor dinamica).

3. **Timezero crop**: nosso engine ainda nao faz crop pelo timezero.
   readgssi remove as amostras acima do "ar", o que muda a escala de profundidade.
   Validar se isso afeta interpretacao dos alvos detectados.

4. **BGRwindow**: readgssi usa dois passes (global + windowed); nosso `bgremoval()` faz
   apenas um. Para solos com gradiente de reflectividade, avaliar se dois passes melhoram.
