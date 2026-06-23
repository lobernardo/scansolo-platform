"""
DZT/DZG/DZX reader — wrapper de readgssi.dzt com lógica específica do ScanSOLO.

Usa readgssi.dzt.readdzt() como parser binário canônico para arquivos GSSI.
Nenhum filtro de sinal é aplicado — arr_raw é a saída direta do instrumento.

Contratos:
  - arr_raw é sempre np.ndarray float32 (nunca np.matrix)
  - Arquivos .DZG e .DZX são lidos automaticamente quando co-localizados
  - Exceções de readdzt são capturadas e relançadas como DZTReadError
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np

# readgssi — dependência pip, fork lobernardo/readgssi
from readgssi.dzt import readdzt
from readgssi.constants import ANT, C

# parse_dzx.py do ScanSOLO — parser stdlib-only para DZX (primário)
try:
    from pipeline.parse_dzx import parse_dzx as _parse_dzx
    _PARSE_DZX_AVAILABLE = True
except ImportError:
    _PARSE_DZX_AVAILABLE = False

# readgssi.dzx — fallback para user marks quando parse_dzx indisponível
try:
    from readgssi.dzx import get_user_marks as _readgssi_user_marks
    _READGSSI_DZX_AVAILABLE = True
except ImportError:
    _READGSSI_DZX_AVAILABLE = False

from gpr_engine._types import DZTData


# GSSI model codes known to be missing from the readgssi ANT dictionary.
# Keys are str(int(code)) — same format as ANT.get(). Values are MHz.
# Do NOT modify the readgssi fork; extend here instead.
_GSSI_MODEL_CODES_EXTRA: dict[str, int] = {
    "50350": 350,   # 50350HSUS — 350 MHz HS horn antenna (GSSI SIR-30)
}


class DZTReadError(Exception):
    """Levantada quando um arquivo DZT não pode ser aberto ou interpretado."""


class DZTReader:
    """
    Lê um arquivo GSSI .DZT e retorna DZTData.

    Usa readgssi.dzt.readdzt() como parser binário. Nenhum filtro é aplicado:
    arr_raw é a saída verbatim do instrumento, como ndarray float32.

    Arquivos .DZG (GPS) e .DZX (user marks) são lidos automaticamente
    quando encontrados no mesmo diretório que o .DZT.
    """

    def __init__(
        self,
        velocidade_operador_ms: float = 1.2,
        verbose: bool = False,
    ) -> None:
        """
        :param velocidade_operador_ms: Velocidade de caminhada (m/s) usada para
            estimar distância em levantamentos por tempo (rhf_spm == 0).
            Padrão: 1.2 m/s.
        :param verbose: Repassado ao readgssi para logging detalhado.
        """
        self.velocidade_operador_ms = velocidade_operador_ms
        self.verbose = verbose

    def read(self, dzt_path: str | Path) -> DZTData:
        """
        Lê um arquivo DZT e retorna DZTData.

        :param dzt_path: Caminho absoluto ou relativo para o arquivo .DZT.
        :raises FileNotFoundError: Se o arquivo não existir.
        :raises DZTReadError: Se readdzt falhar ou retornar array vazio.
        """
        dzt_path = Path(dzt_path)
        if not dzt_path.exists():
            raise FileNotFoundError(f"DZT não encontrado: {dzt_path}")

        sha256 = self._sha256(dzt_path)

        # ── Leitura via readgssi ─────────────────────────────────────────────
        # readdzt tenta ler .DZG co-localizado automaticamente (por existência
        # do arquivo, independente de parâmetros passados).
        try:
            header, data, gps = readdzt(str(dzt_path), verbose=self.verbose)
        except Exception as exc:
            raise DZTReadError(
                f"readdzt falhou em '{dzt_path.name}': {exc}"
            ) from exc

        if not data or 0 not in data:
            raise DZTReadError(f"Sem dados no canal 0 em '{dzt_path.name}'")

        # ── arr_raw: forçar ndarray float32 ─────────────────────────────────
        # np.asarray garante que np.matrix (legado) ou qualquer subclasse
        # seja convertido para ndarray puro.
        arr_raw = np.asarray(data[0], dtype=np.float32)
        if arr_raw.ndim != 2:
            raise DZTReadError(
                f"Array 2-D esperado em '{dzt_path.name}', obtido shape {arr_raw.shape}"
            )
        n_samples, n_traces = arr_raw.shape
        if n_samples == 0 or n_traces == 0:
            raise DZTReadError(
                f"Array vazio em '{dzt_path.name}' (shape={arr_raw.shape})"
            )

        # ── Eixo de tempo ────────────────────────────────────────────────────
        rhf_range_ns = float(header.get("rhf_range") or 0)
        dt_ns = rhf_range_ns / max(n_samples - 1, 1)

        # readgssi calcula samp_freq = n_samples * cr / (2 * dzt_depth_m)
        samp_freq_hz = float(header.get("samp_freq") or 0)
        if samp_freq_hz <= 0:
            # fallback: amostras / tempo total
            samp_freq_hz = n_samples / max(rhf_range_ns * 1e-9, 1e-12)

        # ── Eixo de espaço ───────────────────────────────────────────────────
        rhf_spm = float(header.get("rhf_spm") or 0)
        rhf_sps = float(header.get("rhf_sps") or 0) or 100.0
        modo_coleta, dist_total_m, dist_per_trace_m = self._calc_distance(
            n_traces, rhf_spm, rhf_sps
        )

        # ── Antena e física ──────────────────────────────────────────────────
        antfreq_mhz = self._resolve_antfreq(header)
        rhf_epsr = float(header.get("rhf_epsr") or 1.0)

        # readgssi calcula header['cr'] = 1/sqrt(Mu_0 * Eps_0 * epsr)
        cr_ms = float(header.get("cr") or 0)
        if cr_ms <= 0:
            cr_ms = C / max(rhf_epsr ** 0.5, 1.0)
        wave_speed_mns = cr_ms / 1e9

        # ── Time-zero (valor do header — snr.py refinará com os dados) ───────
        tz_list = header.get("timezero") or [0]
        timezero_sample = int(tz_list[0] or 0) if tz_list else 0

        # ── DZX (user marks) ──────────────────────────────────────────────────
        has_dzx, dzx_marks, dzx_data = self._read_dzx(dzt_path)

        # ── DZG (lido internamente pelo readdzt quando .DZG co-existe) ───────
        try:
            has_dzg = not gps.empty
        except AttributeError:
            has_dzg = False

        return DZTData(
            arr_raw=arr_raw,
            n_samples=n_samples,
            n_traces=n_traces,
            twtt_max_ns=rhf_range_ns,
            dt_ns=dt_ns,
            samp_freq_hz=samp_freq_hz,
            dist_total_m=dist_total_m,
            dist_per_trace_m=dist_per_trace_m,
            modo_coleta=modo_coleta,
            antfreq_mhz=antfreq_mhz,
            rhf_epsr=rhf_epsr,
            wave_speed_mns=wave_speed_mns,
            timezero_sample=timezero_sample,
            rhf_spm=rhf_spm,
            rhf_sps=rhf_sps,
            rhf_range_ns=rhf_range_ns,
            dzt_filename=dzt_path.name,
            dzt_sha256=sha256,
            has_dzg=has_dzg,
            has_dzx=has_dzx,
            dzx_marks=dzx_marks,
            dzx_data=dzx_data,
            header_raw=header,
        )

    # ── Métodos privados ─────────────────────────────────────────────────────

    @staticmethod
    def _sha256(path: Path) -> str:
        """SHA-256 do arquivo em blocos de 8 MB — nunca levanta exceção."""
        h = hashlib.sha256()
        try:
            with open(path, "rb") as fh:
                for chunk in iter(lambda: fh.read(8 * 1024 * 1024), b""):
                    h.update(chunk)
        except OSError:
            return "ERROR"
        return h.hexdigest()

    def _calc_distance(
        self,
        n_traces: int,
        rhf_spm: float,
        rhf_sps: float,
    ) -> tuple[str, float, float]:
        """Determina modo de coleta e calcula distância a partir do header."""
        if rhf_spm > 0:
            # Coleta por distância (encoder odométrico)
            dist_per_trace_m = 1.0 / rhf_spm
            modo = "distancia"
        else:
            # Coleta por tempo (velocidade de operador estimada)
            dist_per_trace_m = self.velocidade_operador_ms / max(rhf_sps, 1.0)
            modo = "tempo"
        dist_total_m = round(n_traces * dist_per_trace_m, 3)
        return modo, dist_total_m, dist_per_trace_m

    @staticmethod
    def _resolve_antfreq(header: dict) -> int:
        """Retorna frequência da antena em MHz a partir do header DZT.

        O GSSI armazena a frequência de duas formas dependendo do modelo:
        - valor direto em MHz (10–5000): e.g. 270 para uma antena de 270 MHz
        - código de modelo (>5000): e.g. 50270 → lookup em ANT → 270 MHz
        """
        freq_list = header.get("antfreq") or []
        if freq_list:
            f = freq_list[0]
            if isinstance(f, (int, float)) and f > 0:
                # Valor direto em MHz (DZTs modernos)
                if 10 <= f <= 5000:
                    return int(f)
                # Código de modelo GSSI (ex: 50270 → 270 MHz)
                code_str = str(int(f))
                if code_str in _GSSI_MODEL_CODES_EXTRA:
                    return _GSSI_MODEL_CODES_EXTRA[code_str]
                mhz = ANT.get(code_str)
                if isinstance(mhz, int):
                    return mhz
        # Fallback: comparar nome da antena com readgssi.constants.ANT
        rh_antname = header.get("rh_antname")
        if rh_antname:
            antname = (rh_antname[0] or "").strip() if isinstance(rh_antname, list) else str(rh_antname).strip()
            for name, mhz in ANT.items():
                if antname and name in antname and isinstance(mhz, int):
                    return mhz
        return 0  # frequência desconhecida

    def _read_dzx(self, dzt_path: Path) -> tuple[bool, list[int], dict]:
        """
        Lê marks do DZX. Retorna (has_dzx, lista_traços, dzx_data_dict).

        Estratégia:
        1. parse_dzx.py do ScanSOLO (parser stdlib completo, primário)
        2. readgssi.dzx.get_user_marks (fallback se parse_dzx não disponível)
        """
        dzx_path = dzt_path.with_suffix(".DZX")
        if not dzx_path.exists():
            dzx_path = dzt_path.with_suffix(".dzx")
        if not dzx_path.exists():
            return False, [], {}

        # Primário: parse_dzx.py do ScanSOLO (contém coordenadas GPS dos marks)
        if _PARSE_DZX_AVAILABLE:
            try:
                dzx_data = _parse_dzx(dzx_path)
                marks = dzx_data.get("dzx_marks", [])
                # Cada mark é um dict com chave 'trace' (int)
                trace_numbers: list[int] = [
                    int(m["trace"])
                    for m in marks
                    if isinstance(m, dict) and m.get("trace") is not None
                ]
                return True, trace_numbers, dzx_data
            except Exception:
                pass  # degradar para fallback

        # Fallback: readgssi.dzx retorna lista de inteiros diretamente
        if _READGSSI_DZX_AVAILABLE:
            try:
                trace_numbers = list(
                    _readgssi_user_marks(str(dzx_path), verbose=self.verbose)
                )
                return True, trace_numbers, {}
            except Exception:
                pass

        # Arquivo existe mas não foi possível parsear
        return True, [], {}
