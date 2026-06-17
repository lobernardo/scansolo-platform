"""
Parser para arquivos .DZX do GSSI — metadados XML complementares ao .DZT.

O .DZX é gerado automaticamente pelo SIR-4000/SIR-30 junto com cada .DZT.
Contém: coordenadas GPS dos marks, metadados do survey (operador, data,
antena) e posição de cada traço. Este módulo extrai o subconjunto útil
para o pipeline ScanSOLO sem dependências externas (stdlib apenas).
"""

from __future__ import annotations

import logging
import math
import xml.etree.ElementTree as ET
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Haversine ─────────────────────────────────────────────────────────────────

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância geodésica aproximada entre dois pontos GPS, em metros."""
    R = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ── Helpers de extração XML ───────────────────────────────────────────────────

def _text(elem: ET.Element, *tags: str) -> str | None:
    """Retorna o text do primeiro tag encontrado na lista de variantes, ou None."""
    for tag in tags:
        found = elem.find(f".//{tag}")
        if found is not None and found.text:
            return found.text.strip()
    return None


def _float_safe(s: str | None) -> float | None:
    if s is None:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def _int_safe(s: str | None) -> int | None:
    if s is None:
        return None
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


# ── Parser principal ──────────────────────────────────────────────────────────

def parse_dzx(dzx_path: "str | Path") -> dict:
    """
    Extrai metadados e GPS marks de um arquivo .DZX do GSSI.

    Retorna dict com campos escalares e lista dzx_marks.
    Nunca levanta exceção — erros são capturados em dzx_parse_error.

    Campos retornados:
      dzx_disponivel (bool)
      dzx_operator, dzx_date, dzx_antenna, dzx_survey_notes (str | None)
      dzx_marks (list[dict])  — trace, lat, lon, ele, label, timestamp
      dzx_start_lat, dzx_start_lon, dzx_end_lat, dzx_end_lon (float | None)
      dzx_survey_length_m (float | None)
      dzx_n_marks (int)
      dzx_parse_error (str | None)
    """
    path = Path(dzx_path)

    _empty: dict = {
        "dzx_disponivel": False,
        "dzx_marks":      [],
        "dzx_n_marks":    0,
    }

    if not path.exists():
        return _empty

    # Parse XML
    try:
        tree = ET.parse(str(path))
        root = tree.getroot()
    except ET.ParseError as exc:
        logger.warning(f"DZX malformado ({path.name}): {exc}")
        return {
            "dzx_disponivel":  True,
            "dzx_parse_error": str(exc),
            "dzx_marks":       [],
            "dzx_n_marks":     0,
        }
    except Exception as exc:
        logger.warning(f"DZX erro de leitura ({path.name}): {exc}")
        return {
            "dzx_disponivel":  True,
            "dzx_parse_error": str(exc),
            "dzx_marks":       [],
            "dzx_n_marks":     0,
        }

    result: dict = {
        "dzx_disponivel":  True,
        "dzx_parse_error": None,
    }

    # METADATA — variantes de tag encontradas em arquivos GSSI SIR-4000 / SIR-30
    result["dzx_operator"]     = _text(root, "Operator",    "operator",    "OPERATOR")
    result["dzx_date"]         = _text(root, "Date",        "date",        "DATE")
    result["dzx_antenna"]      = _text(root,
                                       "Antenna",     "antenna",     "ANTENNA",
                                       "AntennaType", "Antenna_Type", "AntennaFreq")
    result["dzx_survey_notes"] = _text(root,
                                       "Notes",        "notes",       "NOTES",
                                       "SurveyNotes",  "Comment",     "Remarks")

    # GPS MARKS ───────────────────────────────────────────────────────────────
    # O GSSI usa containers variados: <Marks>, <GPS>, ou marks diretamente na raiz.
    marks: list[dict] = []
    seen_traces: set = set()

    mark_containers = (
        root.findall(".//Marks")
        + root.findall(".//GPS")
        + root.findall(".//GpsData")
        + [root]           # fallback: marks direto na raiz
    )

    for container in mark_containers:
        for mark_elem in (
            container.findall("Mark")
            + container.findall("mark")
            + container.findall("GPSMark")
            + container.findall("GpsMark")
        ):
            trace_str = _text(mark_elem,
                               "TraceNumber", "Trace", "trace",
                               "traceNumber", "ScanNumber")
            trace = _int_safe(trace_str)

            lat = _float_safe(_text(mark_elem,
                                    "Latitude",  "latitude",  "LAT",
                                    "lat",       "Lat",       "Y"))
            lon = _float_safe(_text(mark_elem,
                                    "Longitude", "longitude", "LON",
                                    "lon",       "Lon",       "X"))
            ele = _float_safe(_text(mark_elem,
                                    "Elevation", "elevation", "ELE",
                                    "ele",       "Altitude",  "Z"))
            label = (_text(mark_elem, "Label", "label", "Name", "name") or "")
            ts    = (_text(mark_elem,
                           "Timestamp", "timestamp", "Time",
                           "DateTime",  "datetime")            or "")

            # Descartar linhas sem trace nem coordenadas
            if trace is None and lat is None:
                continue

            # Deduplicar por número de traço (marcas duplicadas em containers)
            if trace is not None and trace in seen_traces:
                continue
            if trace is not None:
                seen_traces.add(trace)

            marks.append({
                "trace":     trace,
                "lat":       lat,
                "lon":       lon,
                "ele":       ele,
                "label":     label,
                "timestamp": ts,
            })

    result["dzx_marks"]   = marks
    result["dzx_n_marks"] = len(marks)

    # SURVEY LINE — primeira e última coordenada válida ────────────────────────
    gps_marks = [m for m in marks if m["lat"] is not None and m["lon"] is not None]

    if gps_marks:
        result["dzx_start_lat"] = gps_marks[0]["lat"]
        result["dzx_start_lon"] = gps_marks[0]["lon"]
        result["dzx_end_lat"]   = gps_marks[-1]["lat"]
        result["dzx_end_lon"]   = gps_marks[-1]["lon"]
        result["dzx_survey_length_m"] = (
            round(haversine_m(
                gps_marks[0]["lat"],  gps_marks[0]["lon"],
                gps_marks[-1]["lat"], gps_marks[-1]["lon"],
            ), 2)
            if len(gps_marks) >= 2
            else 0.0
        )
    else:
        result["dzx_start_lat"]       = None
        result["dzx_start_lon"]       = None
        result["dzx_end_lat"]         = None
        result["dzx_end_lon"]         = None
        result["dzx_survey_length_m"] = None

    gps_str = "disponível" if gps_marks else "ausente"
    logger.info(f"DZX: {len(marks)} marks, GPS {gps_str}")

    return result
