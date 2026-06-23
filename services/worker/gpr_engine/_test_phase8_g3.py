"""
Fase G3 — testes unitarios.

Cobertura:
  G3-01  _resolve_antfreq: codigo 50350 -> 350 MHz (override local)
  G3-02  _resolve_antfreq: codigo 50270 -> 270 MHz (ANT dict nativo)
  G3-03  _resolve_antfreq: frequencia direta 270 -> 270 MHz
  G3-04  _resolve_antfreq: codigo desconhecido -> 0
  G3-05  render_radargram: normalization=linear_percentile (default) - gera PNG sem excecao
  G3-06  render_radargram: normalization=symlog - gera PNG sem excecao
  G3-07  render_radargram: normalization=linear_minmax - gera PNG sem excecao
  G3-08  render_radargram: polarity=normal - colormap sem sufixo _r
  G3-09  render_radargram: polarity=inverted - colormap com sufixo _r; array nao mutado
  G3-10  render_radargram: polarity=inverted nao muta o array de entrada
  G3-11  render_radargram: display_depth_m no eixo Y sem alterar array
  G3-12  process_dzt: display_depth_m=None -> depth_max_m fisico no index_row
  G3-13  process_dzt: display_depth_m explicito propagado ao index_row
  G3-14  process_dzt: normalization/polarity em render_kw via config
  G3-15  pipeline _DEFAULTS: normalization/polarity/display_depth_m presentes e auditaveis
  G3-16  _DEFAULTS: display_depth_m=None (nunca um valor hardcoded invisivel)
  G3-17  metrics _render_profile_fields: polarity/display_depth_m registrados
  G3-18  timezero >= n_samples: process_dzt nao corta o array (apenas loga)
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pytest

# Adiciona raiz do worker ao path
_WORKER_ROOT = Path(__file__).parent.parent
if str(_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKER_ROOT))

from gpr_engine.reader import DZTReader, _GSSI_MODEL_CODES_EXTRA
from gpr_engine.pipeline import _DEFAULTS
from gpr_engine.metrics import _render_profile_fields


# ---------------------------------------------------------------------------
# Fixtures de arrays minimos
# ---------------------------------------------------------------------------

def _small_arr(n_samples: int = 16, n_traces: int = 32) -> np.ndarray:
    rng = np.random.default_rng(seed=42)
    arr = rng.standard_normal((n_samples, n_traces)).astype(np.float32)
    arr[0, :] *= 10  # onda direta simulada
    return arr


# ---------------------------------------------------------------------------
# G3-01 a G3-04 — _resolve_antfreq
# ---------------------------------------------------------------------------

class TestResolveAntfreq:
    def test_g3_01_code_50350_returns_350(self):
        """G3-01: GSSI model code 50350 (50350HSUS, SIR-30) -> 350 MHz."""
        header = {
            "antfreq": [50350, None, None, None],
            "rh_antname": ["50350HSUS", None, None, None],
        }
        assert DZTReader._resolve_antfreq(header) == 350

    def test_g3_02_code_50270_returns_270(self):
        """G3-02: Codigo 50270 esta no ANT nativo -> 270 MHz."""
        header = {"antfreq": [50270, None], "rh_antname": [None]}
        assert DZTReader._resolve_antfreq(header) == 270

    def test_g3_03_direct_mhz_270(self):
        """G3-03: Valor direto 270 (10-5000) retornado sem lookup."""
        header = {"antfreq": [270], "rh_antname": [None]}
        assert DZTReader._resolve_antfreq(header) == 270

    def test_g3_04_unknown_code_returns_0(self):
        """G3-04: Codigo nao mapeado retorna 0 (frequencia desconhecida)."""
        header = {"antfreq": [99999], "rh_antname": [None]}
        assert DZTReader._resolve_antfreq(header) == 0

    def test_g3_01b_50350_in_local_overrides(self):
        """G3-01b: '50350' presente em _GSSI_MODEL_CODES_EXTRA com valor 350."""
        assert "50350" in _GSSI_MODEL_CODES_EXTRA
        assert _GSSI_MODEL_CODES_EXTRA["50350"] == 350


# ---------------------------------------------------------------------------
# G3-05 a G3-11 — render_radargram
# ---------------------------------------------------------------------------

class TestRenderRadargram:
    """Testes de render_radargram (normalizacao, polaridade, display_depth_m)."""

    def _render(self, arr: np.ndarray, tmp_path: Path, **kwargs) -> Path:
        from gpr_engine.images import render_radargram
        out = tmp_path / "test.png"
        return render_radargram(arr, out, dist_total_m=5.0, depth_max_m=2.0, **kwargs)

    def test_g3_05_linear_percentile_default(self, tmp_path):
        """G3-05: normalization=linear_percentile (default) gera PNG valido."""
        arr = _small_arr()
        p = self._render(arr, tmp_path, normalization="linear_percentile")
        assert p.exists() and p.stat().st_size > 0

    def test_g3_06_symlog_gera_png(self, tmp_path):
        """G3-06: normalization=symlog gera PNG valido."""
        arr = _small_arr()
        p = self._render(arr, tmp_path, normalization="symlog")
        assert p.exists() and p.stat().st_size > 0

    def test_g3_07_linear_minmax_gera_png(self, tmp_path):
        """G3-07: normalization=linear_minmax gera PNG valido."""
        arr = _small_arr()
        p = self._render(arr, tmp_path, normalization="linear_minmax")
        assert p.exists() and p.stat().st_size > 0

    def test_g3_08_polarity_normal_nao_altera_cmap(self, tmp_path):
        """G3-08: polarity=normal (default) — imagem gerada sem _r no colormap."""
        from gpr_engine import images as img_mod
        arr = _small_arr()
        calls: list[str] = []
        orig_imshow = None

        import matplotlib.pyplot as _plt
        import matplotlib
        matplotlib.use("Agg")

        original_imshow = _plt.Axes.imshow

        def capture_imshow(self_ax, data, **kw):
            calls.append(kw.get("cmap", ""))
            return original_imshow(self_ax, data, **kw)

        with patch.object(_plt.Axes, "imshow", capture_imshow):
            self._render(arr, tmp_path, normalization="linear_percentile", polarity="normal", colormap="gray")

        assert any(c == "gray" for c in calls), f"Expected 'gray', got {calls}"

    def test_g3_09_polarity_inverted_usa_cmap_r(self, tmp_path):
        """G3-09: polarity=inverted -> colormap='gray_r' (nunca inverte array)."""
        import matplotlib.pyplot as _plt
        original_imshow = _plt.Axes.imshow
        calls: list[str] = []

        def capture_imshow(self_ax, data, **kw):
            calls.append(kw.get("cmap", ""))
            return original_imshow(self_ax, data, **kw)

        arr = _small_arr()
        with patch.object(_plt.Axes, "imshow", capture_imshow):
            self._render(arr, tmp_path, polarity="inverted", colormap="gray")

        assert any(c == "gray_r" for c in calls), f"Expected 'gray_r', got {calls}"

    def test_g3_10_polarity_inverted_nao_muta_array(self, tmp_path):
        """G3-10: polarity=inverted nao muta o array de entrada."""
        arr = _small_arr()
        original = arr.copy()
        self._render(arr, tmp_path, polarity="inverted")
        np.testing.assert_array_equal(arr, original)

    def test_g3_11_display_depth_no_titulo_nao_muta_array(self, tmp_path):
        """G3-11: depth_max_m=5.0 (display) com array de 2.0 m fisico — array nao mutado."""
        from gpr_engine.images import render_radargram
        arr = _small_arr()
        original = arr.copy()
        out = tmp_path / "deep.png"
        render_radargram(arr, out, dist_total_m=5.0, depth_max_m=5.0)
        np.testing.assert_array_equal(arr, original)
        assert out.exists()


# ---------------------------------------------------------------------------
# G3-12 a G3-14 — process_dzt
# ---------------------------------------------------------------------------

def _mock_dzt_data(n_samples=128, n_traces=64, timezero_sample=5):
    """Cria DZTData mock com valores realistas para HELPER."""
    from gpr_engine._types import DZTData
    rng = np.random.default_rng(seed=7)
    arr = rng.standard_normal((n_samples, n_traces)).astype(np.float32)
    return DZTData(
        arr_raw=arr,
        n_samples=n_samples,
        n_traces=n_traces,
        twtt_max_ns=49.38,
        dt_ns=49.38 / (n_samples - 1),
        samp_freq_hz=float(n_samples) / (49.38e-9),
        dist_total_m=8.5,
        dist_per_trace_m=8.5 / n_traces,
        modo_coleta="distancia",
        antfreq_mhz=350,
        rhf_epsr=11.11,
        wave_speed_mns=0.090,
        timezero_sample=timezero_sample,
        rhf_spm=40.0,
        rhf_sps=100.0,
        rhf_range_ns=49.38,
        dzt_filename="HELPER_0001.DZT",
        dzt_sha256="abc123",
        has_dzg=False,
        has_dzx=False,
        dzx_marks=[],
        dzx_data={},
        header_raw={},
    )


def _run_process_dzt(tmp_path: Path, config: dict | None = None):
    """Executa process_dzt com DZTReader mockado."""
    from gpr_engine.pipeline import process_dzt
    dzt_path = tmp_path / "HELPER_0001.DZT"
    dzt_path.write_bytes(b"\x00" * 32)

    mock_dzt = _mock_dzt_data()
    with patch("gpr_engine.pipeline.DZTReader") as MockReader:
        MockReader.return_value.read.return_value = mock_dzt
        return process_dzt(str(dzt_path), str(tmp_path / "out"), config=config)


class TestProcessDztG3:
    def test_g3_12_display_depth_none_index_row_none(self, tmp_path):
        """G3-12: display_depth_m=None -> index_row.display_depth_m=None; profundidade fisica inalterada."""
        result = _run_process_dzt(tmp_path, config={"display_depth_m": None})
        physical = round(49.38 * 0.10 / 2.0, 4)
        assert abs(result.index_row["profundidade_max_m"] - physical) < 0.01
        assert result.index_row["display_depth_m"] is None  # nao configurado → None

    def test_g3_13_display_depth_explicito_propagado(self, tmp_path):
        """G3-13: display_depth_m=5.0 -> index_row registra 5.0; profundidade fisica inalterada."""
        result = _run_process_dzt(tmp_path, config={"display_depth_m": 5.0})
        physical = round(49.38 * 0.10 / 2.0, 4)
        assert result.index_row["display_depth_m"] == 5.0
        assert abs(result.index_row["profundidade_max_m"] - physical) < 0.01

    def test_g3_13b_display_depth_nao_muta_profundidade_max_m(self, tmp_path):
        """G3-13b: display_depth_m=5.0 nao altera profundidade_max_m (fisica)."""
        sub_a = tmp_path / "a"; sub_a.mkdir()
        sub_b = tmp_path / "b"; sub_b.mkdir()
        result_default = _run_process_dzt(sub_a, config={})
        result_display = _run_process_dzt(sub_b, config={"display_depth_m": 5.0})
        assert abs(
            result_default.index_row["profundidade_max_m"] -
            result_display.index_row["profundidade_max_m"]
        ) < 0.01

    def test_g3_14_normalization_polarity_em_config_nao_readgssi(self, tmp_path):
        """G3-14: normalization e polarity registrados nas metricas (visual_profile=scientific)."""
        result = _run_process_dzt(tmp_path, config={
            "normalization": "symlog",
            "polarity": "inverted",
            "visual_profile": "scientific",  # forca perfil nao-readgssi para testar campo
        })
        # normalization e "symlog" porque visual_profile != readgssi_reference
        assert result.metrics.get("normalization") == "symlog"
        assert result.metrics.get("polarity") == "inverted"

    def test_g3_14b_readgssi_default_normalization_symlog(self, tmp_path):
        """G3-14b: visual_profile=readgssi_reference (default) -> metrics.normalization=SymLogNorm."""
        result = _run_process_dzt(tmp_path, config={})
        # readgssi_reference sempre usa SymLogNorm — correto gravar isso nas metricas
        assert result.metrics.get("normalization") == "SymLogNorm"

    def test_g3_14c_depth_display_mode_no_stretch(self, tmp_path):
        """G3-14c: metrics registra depth_display_mode=axis_limit_no_stretch."""
        result = _run_process_dzt(tmp_path, config={})
        assert result.metrics.get("depth_display_mode") == "axis_limit_no_stretch"

    def test_g3_14d_visual_crop_false_when_no_display_depth(self, tmp_path):
        """G3-14d: visual_crop_occurred=False quando display_depth_m nao configurado."""
        result = _run_process_dzt(tmp_path, config={})
        assert result.metrics.get("visual_crop_occurred") is False

    def test_g3_14e_visual_crop_true_when_display_less_than_physical(self, tmp_path):
        """G3-14e: visual_crop_occurred=True quando display_depth_m < profundidade fisica."""
        physical = round(49.38 * 0.10 / 2.0, 4)
        display = round(physical * 0.5, 2)  # metade da profundidade fisica
        result = _run_process_dzt(tmp_path, config={"display_depth_m": display})
        assert result.metrics.get("visual_crop_occurred") is True


# ---------------------------------------------------------------------------
# G3-15 a G3-17 — _DEFAULTS e _render_profile_fields
# ---------------------------------------------------------------------------

class TestDefaultsAndMetrics:
    def test_g3_15_defaults_tem_normalization(self):
        """G3-15: _DEFAULTS inclui normalization, polarity, display_depth_m."""
        assert "normalization" in _DEFAULTS
        assert "polarity" in _DEFAULTS
        assert "display_depth_m" in _DEFAULTS

    def test_g3_16_display_depth_default_none(self):
        """G3-16: display_depth_m default e None (nunca valor hardcoded invisivel)."""
        assert _DEFAULTS["display_depth_m"] is None

    def test_g3_17_render_profile_fields_registra_polarity(self):
        """G3-17: _render_profile_fields inclui polarity e display_depth_m."""
        config = {
            "visual_profile": "scientific",
            "polarity": "inverted",
            "display_depth_m": 3.5,
            "normalization": "linear_percentile",
        }
        fields = _render_profile_fields(config)
        assert fields["polarity"] == "inverted"
        assert fields["display_depth_m"] == 3.5

    def test_g3_17b_render_profile_fields_none_display_depth(self):
        """G3-17b: display_depth_m=None em config -> None no campo de metricas."""
        fields = _render_profile_fields({"visual_profile": "scientific"})
        assert fields["display_depth_m"] is None


# ---------------------------------------------------------------------------
# G3-18 — timezero invalido nao corta array
# ---------------------------------------------------------------------------

class TestTimezeroInvalido:
    def test_g3_18_timezero_invalido_nao_corta(self, tmp_path):
        """G3-18: timezero_sample >= n_samples nao corta array (apenas loga warning)."""
        from gpr_engine.pipeline import process_dzt
        dzt_path = tmp_path / "HELPER_INVALID_TZ.DZT"
        dzt_path.write_bytes(b"\x00" * 32)

        # DZT com timezero invalido: rh_zero=341 >= n_samples=128
        mock_dzt = _mock_dzt_data(n_samples=128, n_traces=64, timezero_sample=341)
        original_shape = mock_dzt.arr_raw.shape

        with patch("gpr_engine.pipeline.DZTReader") as MockReader:
            MockReader.return_value.read.return_value = mock_dzt
            result = process_dzt(str(dzt_path), str(tmp_path / "out_tz"), config={})

        # Array nao deve ter sido cortado — shape fisico inalterado
        assert result.dzt_data.arr_raw.shape == original_shape
        # n_tracos tambem deve estar correto
        assert result.index_row["n_tracos"] == 64


# ---------------------------------------------------------------------------
# G3-19 a G3-21 — extent fisico / ylim visual / default readgssi_reference
# ---------------------------------------------------------------------------

class TestExtentVsYlim:
    def test_g3_19_render_radargram_extent_usa_profundidade_fisica(self):
        """G3-19: render_radargram usa depth_max_m (fisico) no extent, nao display_depth_m."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from gpr_engine.images import render_radargram
        import tempfile, os
        arr = np.ones((64, 64), dtype=np.float32)
        extent_calls = []
        orig_imshow = plt.Axes.imshow
        def mock_imshow(self, *a, **kw):
            extent_calls.append(kw.get("extent"))
            return orig_imshow(self, *a, **kw)
        with patch.object(plt.Axes, "imshow", mock_imshow):
            with tempfile.TemporaryDirectory() as td:
                out = os.path.join(td, "test.png")
                render_radargram(
                    arr, out,
                    dist_total_m=10.0,
                    depth_max_m=2.22,       # profundidade FISICA
                    display_depth_m=5.0,    # limite VISUAL (maior)
                )
        assert extent_calls, "imshow nunca chamado"
        ext = extent_calls[0]
        assert ext is not None, "extent=None passado para imshow"
        # extent[2] deve ser profundidade FISICA (2.22), nao display (5.0)
        physical_in_extent = ext[2]  # extent=[xmin, xmax, ymax(depth), ymin(0)]
        assert abs(physical_in_extent - 2.22) < 0.05, (
            f"extent usa {physical_in_extent:.3f} em vez da profundidade fisica 2.22"
        )

    def test_g3_20_render_radargram_ylim_usa_display_depth(self):
        """G3-20: render_radargram usa display_depth_m para o eixo Y (set_ylim)."""
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from gpr_engine.images import render_radargram
        import tempfile, os
        arr = np.ones((64, 64), dtype=np.float32)
        ylim_calls = []
        orig_ylim = plt.Axes.set_ylim
        def mock_ylim(self, *a, **kw):
            ylim_calls.append(a)
            return orig_ylim(self, *a, **kw)
        with patch.object(plt.Axes, "set_ylim", mock_ylim):
            with tempfile.TemporaryDirectory() as td:
                out = os.path.join(td, "test.png")
                render_radargram(
                    arr, out,
                    dist_total_m=10.0,
                    depth_max_m=2.22,
                    display_depth_m=5.0,
                )
        assert ylim_calls, "set_ylim nunca chamado"
        # set_ylim pode ser chamado multiplas vezes pelo matplotlib internamente.
        # Procuramos a chamada onde o primeiro valor e proximo de 5.0 (ylim_depth).
        def _first_val(c):
            v = c[0]
            return v[0] if isinstance(v, (list, tuple)) else float(v)
        found = any(abs(_first_val(c) - 5.0) < 0.05 for c in ylim_calls)
        assert found, (
            f"set_ylim(5.0, ...) nunca chamado. Chamadas capturadas: {ylim_calls}"
        )

    def test_g3_21_visual_profile_default_e_readgssi_reference(self):
        """G3-21: _DEFAULTS['visual_profile'] = 'readgssi_reference' (produto-padrao)."""
        from gpr_engine.pipeline import _DEFAULTS
        assert _DEFAULTS.get("visual_profile") == "readgssi_reference", (
            f"_DEFAULTS['visual_profile'] = {_DEFAULTS.get('visual_profile')!r} "
            f"— esperado 'readgssi_reference'"
        )


# ---------------------------------------------------------------------------
# G3-22 a G3-24 — _filtros_to_pipeline_config mapeamento G3 fields
# ---------------------------------------------------------------------------

class TestFiltrosToPipelineConfig:
    """Testa que _filtros_to_pipeline_config mapeia display_depth_m, normalization, polarity."""

    def _convert(self, filtros: dict) -> dict:
        from job_gpr import _filtros_to_pipeline_config
        return _filtros_to_pipeline_config(filtros)

    def test_g3_22_display_depth_m_mapeado(self):
        """G3-22: display_depth_m explicito e mapeado para a config do pipeline."""
        cfg = self._convert({"display_depth_m": 5.0})
        assert cfg.get("display_depth_m") == 5.0, (
            f"display_depth_m nao mapeado: {cfg}"
        )

    def test_g3_22b_display_depth_none_nao_mapeado(self):
        """G3-22b: display_depth_m=None nao insere a chave na config."""
        cfg = self._convert({"display_depth_m": None})
        assert "display_depth_m" not in cfg, (
            "display_depth_m=None nao deve inserir a chave na config"
        )

    def test_g3_23_normalization_mapeada(self):
        """G3-23: normalization e mapeada para a config do pipeline."""
        cfg = self._convert({"normalization": "symlog"})
        assert cfg.get("normalization") == "symlog", (
            f"normalization nao mapeada: {cfg}"
        )

    def test_g3_23b_normalization_linear_minmax(self):
        """G3-23b: normalization=linear_minmax e preservada."""
        cfg = self._convert({"normalization": "linear_minmax"})
        assert cfg.get("normalization") == "linear_minmax"

    def test_g3_24_polarity_mapeada(self):
        """G3-24: polarity e mapeada para a config do pipeline."""
        cfg = self._convert({"polarity": "inverted"})
        assert cfg.get("polarity") == "inverted", (
            f"polarity nao mapeada: {cfg}"
        )

    def test_g3_24b_polarity_normal_preservada(self):
        """G3-24b: polarity=normal e preservada."""
        cfg = self._convert({"polarity": "normal"})
        assert cfg.get("polarity") == "normal"

    def test_g3_24c_preview_visual_depth_mode_mapeado(self):
        """G3-24c: preview_visual_depth_mode e mapeado para a config do pipeline."""
        cfg = self._convert({"preview_visual_depth_mode": "axis_limit_no_stretch"})
        assert cfg.get("preview_visual_depth_mode") == "axis_limit_no_stretch"


# ---------------------------------------------------------------------------
# G3-25 a G3-28 — preview_visual_depth_mode no pipeline e metricas
# ---------------------------------------------------------------------------

class TestPreviewVisualDepthMode:
    """Testa os dois modos de profundidade visual para a imagem de preview."""

    def test_g3_25_default_preview_mode_e_stretch(self):
        """G3-25: _DEFAULTS['preview_visual_depth_mode'] = 'stretch_to_preview_depth'."""
        from gpr_engine.pipeline import _DEFAULTS
        assert _DEFAULTS.get("preview_visual_depth_mode") == "stretch_to_preview_depth", (
            f"Default errado: {_DEFAULTS.get('preview_visual_depth_mode')!r}"
        )

    def test_g3_26_stretch_mode_records_visual_stretch_true(self, tmp_path):
        """G3-26: modo stretch + depth_preview != physical → visual_stretch_occurred=True nas metricas."""
        result = _run_process_dzt(tmp_path, config={
            "preview_visual_depth_mode": "stretch_to_preview_depth",
            "depth_preview_m": 5.0,  # physical e ~2.22 m → esticamento
        })
        assert result.metrics.get("visual_stretch_occurred") is True, (
            f"visual_stretch_occurred deveria ser True: {result.metrics.get('visual_stretch_occurred')}"
        )

    def test_g3_27_no_stretch_mode_records_visual_stretch_false(self, tmp_path):
        """G3-27: axis_limit_no_stretch → visual_stretch_occurred=False nas metricas."""
        result = _run_process_dzt(tmp_path, config={
            "preview_visual_depth_mode": "axis_limit_no_stretch",
            "depth_preview_m": 5.0,
        })
        assert result.metrics.get("visual_stretch_occurred") is False, (
            f"visual_stretch_occurred deveria ser False: {result.metrics.get('visual_stretch_occurred')}"
        )

    def test_g3_28_stretch_nao_muta_profundidade_fisica(self, tmp_path):
        """G3-28: visual_stretch_occurred=True nao altera physical_depth_m."""
        sub_a = tmp_path / "a"; sub_a.mkdir()
        sub_b = tmp_path / "b"; sub_b.mkdir()
        result_default = _run_process_dzt(sub_a, config={})
        result_stretch = _run_process_dzt(sub_b, config={
            "preview_visual_depth_mode": "stretch_to_preview_depth",
            "depth_preview_m": 5.0,
        })
        assert abs(
            result_default.metrics.get("physical_depth_m", 0) -
            result_stretch.metrics.get("physical_depth_m", 0)
        ) < 0.01, "physical_depth_m nao deve mudar com stretch"

    def test_g3_28b_preview_visual_depth_mode_em_metricas(self, tmp_path):
        """G3-28b: preview_visual_depth_mode registrado nas metricas."""
        result = _run_process_dzt(tmp_path, config={
            "preview_visual_depth_mode": "axis_limit_no_stretch",
        })
        assert result.metrics.get("preview_visual_depth_mode") == "axis_limit_no_stretch"

    def test_g3_28c_stretch_mode_em_index_row(self, tmp_path):
        """G3-28c: index_row contem preview_visual_depth_mode e visual_stretch_occurred."""
        result = _run_process_dzt(tmp_path, config={
            "preview_visual_depth_mode": "stretch_to_preview_depth",
            "depth_preview_m": 5.0,
        })
        assert "preview_visual_depth_mode" in result.index_row
        assert "visual_stretch_occurred" in result.index_row
        assert result.index_row["visual_stretch_occurred"] is True
