# Preview RADAN 5m — Documento Técnico

> Última atualização: 2026-06-15
> Pipeline: v2.0.0 | Saída: `_radargrama_preview_radan_5m.png`

---

## 1. Por que a imagem oficial científica vai até ~2,47 m

O pipeline usa `velocity_mns = 0.10 m/ns` (valor padrão para solo seco, calibração
pendente com o geofísico responsável). Com o HELPER_0001.dzt:

```
twtt_max = 49,38 ns
depth_max = twtt_max × velocity_mns / 2 = 49,38 × 0,10 / 2 = 2,47 m
```

Esse é o valor registrado no CSV de alvos, nas cartografias, no relatório técnico
e em todas as saídas oficiais do pipeline.

---

## 2. Por que a imagem RADAN aparece até ~5 m

O software RADAN (GSSI) aplica uma velocity padrão diferente ao exibir o radargrama.
Pelo aspecto visual da imagem de referência `HELPER_0001_radargrama.jpg`, o eixo
vertical vai até aproximadamente 5 m com o mesmo `twtt_max = 49,38 ns`.

Isso implica que o RADAN usa internamente:

```
velocity_radan ≈ 2 × 5,0 / 49,38 ≈ 0,2025 m/ns
```

Essa velocity (~0,20 m/ns) não é necessariamente mais correta — é apenas a
configuração padrão do software de aquisição para exibição, que pode não refletir
a velocidade real de propagação no solo levantado.

---

## 3. Velocity necessária para exibir 5 m

```
velocity_preview_mns = (2 × depth_preview_m) / twtt_max_ns
velocity_preview_mns = (2 × 5,0) / 49,38
velocity_preview_mns ≈ 0,2025 m/ns
```

Essa velocity é calculada **dinamicamente por DZT** na função
`salvar_imagem_preview_radan_5m()` e registrada nos campos:
- `preview_velocity_mns` no `index_projeto.csv`
- `velocity_preview_mns` nos metadados de retorno da função
- Log do pipeline: `v_preview=0.2025 m/ns`

Ela **não** é usada em nenhuma outra parte do pipeline.

---

## 4. AGC visual reproduz a textura profunda da imagem RADAN

A imagem RADAN mostra textura visual uniforme em toda a profundidade, incluindo
regiões abaixo de 2,5 m onde o sinal físico é muito fraco. Isso é resultado de
um ganho automático de controle (AGC) aplicado pelo RADAN durante a exportação.

Para reproduzir essa textura, `salvar_imagem_preview_radan_5m()` aplica um AGC
próprio (`agc_window_preview = 80` traços por padrão) **sobre uma cópia de
`arr_dewow_bp`**, sem afetar os arrays principais do pipeline.

O AGC equaliza a amplitude por janela deslizante, trazendo para visibilidade
reflexos profundos que de outra forma ficariam no ruído de fundo.

---

## 5. Esta imagem é apenas visual/comparativa

| O que esta imagem É | O que esta imagem NÃO É |
|---|---|
| Referência visual para comparação com RADAN | Profundidade oficial de nenhum alvo |
| Entrada de conversas com o geofísico responsável sobre calibração | Input do detector de hipérboles |
| Evidência de que o pipeline cobre a mesma janela temporal do RADAN | Dado para cartografia, KML ou DXF |
| Saída de arquivo `.png` nomeada `_radargrama_preview_radan_5m.png` | Input da IA de interpretação |
| Campo `imagem_preview_radan_5m` no `index_projeto.csv` | Substituição do radargrama científico ou de relatório |

O aviso de rodapé na imagem torna isso explícito:

> *"Preview ~5m | AGC visual | escala não calibrada | v_preview=0.2025 m/ns"*

---

## 6. A profundidade oficial depende de calibração

O valor `velocity_mns = 0.10 m/ns` usado nas saídas oficiais é um padrão para
solo seco e heterogêneo. A profundidade real dos alvos detectados pode variar
significativamente dependendo do tipo de solo.

Calibração correta requer:
- Identificação de um alvo de profundidade **conhecida** no campo (ex: tubulação
  com cota confirmada em projeto ou escavação controlada)
- Leitura do `twtt` do alvo no radargrama
- Cálculo: `velocity_real = 2 × depth_real / twtt_alvo`
- Atualização de `velocity_mns` no preset para o projeto

Até a calibração, todos os valores de `depth_m` e `diam_est_m` no CSV devem ser
tratados como **estimativas com incerteza de ±15–25%**.

---

## 7. Próximo passo: velocity calibration por hipérbole (P1)

A calibração por semblance (já implementada em `velocity_estimada_mns`) é um
primeiro passo automático. Para produção, o próximo passo (P1) é implementar
calibração por fitting de hipérbole com ground truth:

1. Selecionar alvo de profundidade conhecida
2. Fazer o fit da hipérbole no radargrama científico
3. Calcular `velocity_real` a partir dos parâmetros do fit
4. Registrar como `velocity_calibrada = True` no perfil
5. Propagar para `depth_m` e `diam_est_m` no CSV e no relatório

Isso eliminará a necessidade da imagem preview como referência visual e tornará
as profundidades oficiais confiáveis para cartografia.

---

## Arquivos gerados (validação HELPER_0001)

| Arquivo | Descrição |
|---|---|
| `HELPER_0001_01_radan_original.jpg` | Referência RADAN original |
| `HELPER_0001_02_cientifico_scansolo.png` | Radargrama científico (dewow+bp+tpow) |
| `HELPER_0001_03_relatorio_scansolo.png` | Radargrama relatório (bgremoval+tpow) |
| `HELPER_0001_04_preview_radan_5m_scansolo.png` | Preview RADAN 5m (novo) |
| `HELPER_0001_comparativo_preview_radan_5m.png` | Comparativo 4 painéis |

Localização: `benchmark_real/05_validacao_amilson/pacote_visual_v2/`

---

## Parâmetros registrados (HELPER_0001)

| Campo | Valor |
|---|---|
| `twtt_max_ns` | 49,38 ns |
| `velocity_mns_oficial` | 0,10 m/ns |
| `depth_max_oficial_m` | 2,47 m |
| `depth_preview_m` | 5,0 m |
| `velocity_preview_mns` | 0,2025 m/ns |
| `agc_visual_preview` | true |
| `agc_window_preview` | 80 |
