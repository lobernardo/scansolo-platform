"""
Cartografia job handler — Fase 4.

Flow:
  1. Analyze project files → detect cartography mode (auto-detection)
  2. Fetch reviewed targets (vai_para_planta OR vai_para_relatorio = true)
  3. Generate outputs: CSV (always), GeoJSON (always), DXF cross-section (always),
     KML (only when real GPS coords extracted from KML/KMZ/DZG)
  4. Upload to Storage bucket gpr-tabelas/{project_id}/cartografia/
  5. Insert cartography_outputs record
  6. Update project to aguardando_cartografia (waiting for human confirmation)

Detection logic:
  - KML/KMZ present  → georeferenced (alta confidence)
  - DZG present      → try readgssi GPS extraction → georeferenced or profile_local
  - DXF/DWG present  → cad_local (baixa confidence, needs Amilson validation)
  - DZT only         → profile_local (alta confidence, cross-section mode)

PENDENTE: Validar com Amilson exemplos reais de DXF/KML para reproduzir
padrão final ScanSOLO. Arquitetura já suporta os dois cenários.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from clients.supabase_client import SupabaseClient

log = structlog.get_logger()

STORAGE_BUCKET = "gpr-tabelas"

# DXF AutoCAD standard colors by underground utility type
_TIPO_DXF_COLOR: dict[str, int] = {
    "tubulacao_agua": 4,   # cyan
    "tubulacao_gas":  2,   # yellow
    "cabo_eletrico":  1,   # red
    "cabo_telecom":   6,   # magenta
    "vazio":          3,   # green
    "raiz":           5,   # blue
    "rocha":          8,   # dark gray
    "desconhecido":   7,   # white
}

# KML icon colors (aabbggrr format) per type
_TIPO_KML_COLOR: dict[str, str] = {
    "tubulacao_agua": "ffffff00",  # cyan
    "tubulacao_gas":  "ff00ffff",  # yellow
    "cabo_eletrico":  "ff0000ff",  # red
    "cabo_telecom":   "ffff00ff",  # magenta
    "vazio":          "ff00ff00",  # green
    "rocha":          "ff888888",  # gray
    "raiz":           "ff0080ff",  # orange
    "desconhecido":   "ffffffff",  # white
}


# ── Job entry point ──────────────────────────────────────────────────────────

def handle_cartografia_job(supa: "SupabaseClient", job: dict) -> None:
    job_id: str = job["id"]
    project_id: str = job["project_id"]

    log.info("cartografia_job_start", job_id=job_id, project_id=project_id)
    supa.update_job_status(job_id, "processando")
    supa.update_project_status(project_id, "aguardando_cartografia")

    project = supa.get_project(project_id)
    if not project:
        raise RuntimeError(f"Project {project_id} not found")

    # Step 1: detect mode from uploaded files
    all_files = supa.get_all_project_files(project_id)
    mode, confidence, source, notes, gps_path = _detect_mode(supa, all_files)
    log.info("cartografia_mode", mode=mode, confidence=confidence, source=source)

    # Step 2: get reviewed targets
    targets = supa.get_reviewed_targets(project_id)
    log.info("cartografia_targets", count=len(targets))

    if not targets:
        notes += " ATENÇÃO: Nenhum alvo com vai_para_planta ou vai_para_relatorio = true encontrado."
        supa.insert_cartography_output({
            "project_id": project_id,
            "cartography_mode": mode,
            "cartography_confidence": confidence,
            "cartography_source": source,
            "cartography_notes": notes,
            "status": "aguardando_confirmacao",
        })
        supa.update_job_status(job_id, "concluido")
        return

    # Step 3: get profiles for DXF scale reference
    profiles = supa.get_profiles_for_project(project_id)
    run_id = supa.get_latest_run_id(project_id)
    profiles = [p for p in profiles if p.get("run_id") == run_id]

    prefix = f"{project_id}/cartografia"
    pid8 = project_id[:8]
    urls: dict[str, str] = {}

    # CSV — always
    csv_path = f"{prefix}/{pid8}_alvos.csv"
    supa.upload_file(STORAGE_BUCKET, csv_path, _gen_csv(targets, project), "text/csv")
    urls["csv_path"] = csv_path
    log.info("cartografia_csv_done")

    # GeoJSON — always (local coords if no GPS)
    geojson_path = f"{prefix}/{pid8}_alvos.geojson"
    supa.upload_file(STORAGE_BUCKET, geojson_path, _gen_geojson(targets, project, gps_path), "application/geo+json")
    urls["geojson_path"] = geojson_path
    log.info("cartografia_geojson_done")

    # DXF — always (cross-section view)
    try:
        dxf_path = f"{prefix}/{pid8}_alvos.dxf"
        supa.upload_file(STORAGE_BUCKET, dxf_path, _gen_dxf(targets, profiles, project), "application/dxf")
        urls["dxf_dropbox_path"] = dxf_path
        log.info("cartografia_dxf_done")
    except Exception as exc:
        log.warning("cartografia_dxf_failed", error=str(exc))
        notes += f" DXF falhou: {str(exc)[:120]}."

    # KML — only when real GPS coords available
    if gps_path:
        try:
            kml_path = f"{prefix}/{pid8}_alvos.kml"
            supa.upload_file(STORAGE_BUCKET, kml_path, _gen_kml(targets, gps_path, project), "application/vnd.google-earth.kml+xml")
            urls["kml_dropbox_path"] = kml_path
            log.info("cartografia_kml_done")
        except Exception as exc:
            log.warning("cartografia_kml_failed", error=str(exc))
            notes += f" KML falhou: {str(exc)[:120]}."

    supa.insert_cartography_output({
        "project_id": project_id,
        "cartography_mode": mode,
        "cartography_confidence": confidence,
        "cartography_source": source,
        "cartography_notes": notes,
        "status": "aguardando_confirmacao",
        **urls,
    })

    supa.update_job_status(job_id, "concluido")
    log.info(
        "cartografia_job_done",
        job_id=job_id, mode=mode, targets=len(targets),
        files=list(urls.keys()),
    )


# ── Detection ────────────────────────────────────────────────────────────────

def _detect_mode(
    supa: "SupabaseClient",
    files: list[dict],
) -> tuple[str, str, str, str, list[tuple[float, float]] | None]:
    """
    Returns (mode, confidence, source, notes, gps_path_coords_or_None).
    gps_path_coords: list of (lon, lat) tuples representing the survey path.
    """
    kml_files = [f for f in files if f["extension"] in ("kml", "kmz")]
    dzg_files = [f for f in files if f["extension"] == "dzg"]
    cad_files = [f for f in files if f["extension"] in ("dxf", "dwg")]

    if kml_files:
        f = kml_files[0]
        coords = _try_extract_kml_coords(supa, f)
        if coords:
            return (
                "georeferenced", "alta", "kml",
                f"KML encontrado: '{f['file_name']}' — {len(coords)} pontos GPS extraídos. "
                "Saídas georreferenciadas disponíveis. "
                "PENDENTE: validar com Amilson padrão de layers/blocos DXF da ScanSOLO.",
                coords,
            )
        return (
            "georeferenced", "media", "kml",
            f"KML/KMZ encontrado: '{f['file_name']}', mas extração de coordenadas falhou. "
            "Saída local gerada como alternativa. Verificar formato do arquivo.",
            None,
        )

    if dzg_files:
        f = dzg_files[0]
        coords = _try_extract_dzg_gps(supa, f)
        if coords:
            return (
                "georeferenced", "media", "dzg",
                f"DZG encontrado: '{f['file_name']}' — {len(coords)} pontos GPS extraídos via NMEA. "
                "Validar precisão antes de uso em produção. "
                "PENDENTE: validar com Amilson padrão de saída.",
                coords,
            )
        return (
            "profile_local", "media", "dzg",
            f"DZG encontrado: '{f['file_name']}', mas GPS não extraído "
            "(readgssi indisponível ou arquivo sem dados NMEA). "
            "Saída local gerada. PENDENTE: instalar readgssi e reprocessar.",
            None,
        )

    if cad_files:
        f = cad_files[0]
        return (
            "cad_local", "baixa", "dxf",
            f"Arquivo CAD encontrado: '{f['file_name']}'. "
            "Coordenadas não verificadas — pode ser local ou georreferenciado. "
            "PENDENTE: validar com Amilson se coordenadas são UTM/GPS ou locais, "
            "e mapear padrão de layers/blocos ScanSOLO.",
            None,
        )

    # Default: only DZT files
    return (
        "profile_local", "alta", "inferred",
        "Apenas arquivos DZT encontrados. Modo local: X = distância ao longo do perfil (m), "
        "Y = profundidade (m). DXF gerado como seção transversal. "
        "PENDENTE: validar com Amilson exemplos reais de DXF/KML para "
        "reproduzir padrão final da ScanSOLO.",
        None,
    )


def _try_extract_kml_coords(
    supa: "SupabaseClient",
    kml_file: dict,
) -> list[tuple[float, float]] | None:
    try:
        data = supa.download_file("gpr-uploads", kml_file["supabase_storage_path"])

        if kml_file["extension"] == "kmz":
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                kml_names = [n for n in zf.namelist() if n.lower().endswith(".kml")]
                if not kml_names:
                    return None
                data = zf.read(kml_names[0])

        root = ET.fromstring(data)
        KML_NS = "http://www.opengis.net/kml/2.2"

        # Prefer LineString (survey path)
        for ls in root.iter(f"{{{KML_NS}}}LineString"):
            c = ls.find(f"{{{KML_NS}}}coordinates")
            if c is not None and c.text:
                return _parse_kml_coords(c.text)

        # Fallback: collect all Point coordinates
        points: list[tuple[float, float]] = []
        for coord_el in root.iter(f"{{{KML_NS}}}coordinates"):
            if coord_el.text:
                points.extend(_parse_kml_coords(coord_el.text))
        return points if len(points) >= 2 else None

    except Exception as exc:
        log.warning("kml_extract_failed", error=str(exc))
        return None


def _parse_kml_coords(text: str) -> list[tuple[float, float]]:
    coords = []
    for entry in text.strip().split():
        parts = entry.split(",")
        if len(parts) >= 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return coords


def _try_extract_dzg_gps(
    supa: "SupabaseClient",
    dzg_file: dict,
) -> list[tuple[float, float]] | None:
    try:
        data = supa.download_file("gpr-uploads", dzg_file["supabase_storage_path"])
        text = data.decode("latin-1", errors="replace")

        coords: list[tuple[float, float]] = []
        # Parse NMEA GPGGA sentences embedded in DZG binary
        for match in re.finditer(r"\$GPGGA,([^*\n]+)", text):
            parts = match.group(1).split(",")
            if len(parts) < 6:
                continue
            try:
                lat_r, lat_d = float(parts[1]), parts[2]
                lon_r, lon_d = float(parts[3]), parts[4]
                lat = int(lat_r / 100) + (lat_r % 100) / 60
                lon = int(lon_r / 100) + (lon_r % 100) / 60
                if lat_d == "S":
                    lat = -lat
                if lon_d == "W":
                    lon = -lon
                coords.append((lon, lat))
            except (ValueError, IndexError):
                pass

        return coords if len(coords) >= 2 else None

    except Exception as exc:
        log.warning("dzg_gps_failed", error=str(exc))
        return None


# ── Generators ───────────────────────────────────────────────────────────────

def _gen_csv(targets: list[dict[str, Any]], project: dict[str, Any]) -> bytes:
    buf = io.StringIO()
    fields = [
        "rank", "arquivo_dzt", "x_m", "depth_m", "diam_est_m",
        "tipo_final", "confidence_label_tecnico", "ia_tipo_sugerido", "ia_confianca",
        "vai_para_planta", "vai_para_relatorio", "observacao_revisao",
    ]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for t in sorted(targets, key=lambda x: (x.get("arquivo_dzt", ""), x.get("rank", 0))):
        w.writerow({f: t.get(f) for f in fields})
    return buf.getvalue().encode("utf-8-sig")  # BOM for Excel


def _gen_geojson(
    targets: list[dict[str, Any]],
    project: dict[str, Any],
    gps_path: list[tuple[float, float]] | None,
) -> bytes:
    features = []
    for t in targets:
        x_m = t.get("x_m") or 0
        depth_m = t.get("depth_m") or 0

        if gps_path and len(gps_path) >= 2:
            # Interpolate position along GPS path
            lon, lat = _interpolate_along_path(gps_path, x_m)
            coord = [lon, lat, -depth_m]
            crs_note = "WGS84"
        else:
            coord = [x_m, -depth_m, 0]
            crs_note = "local_profile"

        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": coord},
            "properties": {
                "rank": t.get("rank"),
                "arquivo_dzt": t.get("arquivo_dzt"),
                "x_m": x_m,
                "depth_m": depth_m,
                "diam_est_m": t.get("diam_est_m"),
                "tipo_final": t.get("tipo_final"),
                "vai_para_planta": t.get("vai_para_planta"),
                "vai_para_relatorio": t.get("vai_para_relatorio"),
                "ia_confianca": t.get("ia_confianca"),
                "crs": crs_note,
            },
        })

    geojson = {
        "type": "FeatureCollection",
        "name": project.get("nome", ""),
        "crs": {"type": "name", "properties": {"name": "local_profile" if not gps_path else "EPSG:4326"}},
        "features": features,
    }
    return json.dumps(geojson, ensure_ascii=False, indent=2).encode("utf-8")


def _gen_dxf(
    targets: list[dict[str, Any]],
    profiles: list[dict[str, Any]],
    project: dict[str, Any],
) -> bytes:
    import ezdxf

    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 6  # meters

    msp = doc.modelspace()
    proj_name = project.get("nome", "ScanSOLO")

    # Define layers
    _setup_dxf_layers(doc)

    # Group targets by profile
    by_profile: dict[str, list[dict]] = {}
    for t in targets:
        pid = t.get("profile_id", "unknown")
        by_profile.setdefault(pid, []).append(t)

    profile_map = {p["id"]: p for p in profiles}
    y_offset = 0.0
    gap = 2.0  # gap between profiles (meters)

    for i, (pid, ptargets) in enumerate(by_profile.items()):
        prof = profile_map.get(pid, {})
        dist_max = prof.get("distancia_max_m") or max((t.get("x_m") or 0) for t in ptargets) + 1
        depth_max = prof.get("profundidade_max_m") or max((t.get("depth_m") or 0) for t in ptargets) + 0.5
        arquivo = prof.get("arquivo_dzt", f"Perfil {i+1}")

        # Surface line
        msp.add_line(
            (0, y_offset),
            (dist_max, y_offset),
            dxfattribs={"layer": "SCANSOLO_SUPERFICIE"},
        )

        # Depth scale marks
        for d in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
            if d > depth_max + 0.1:
                break
            y = y_offset - d
            msp.add_line((-0.2, y), (0, y), dxfattribs={"layer": "SCANSOLO_ESCALA"})
            msp.add_text(
                f"{d:.1f}m",
                dxfattribs={"layer": "SCANSOLO_ESCALA", "height": 0.08, "insert": (-0.6, y - 0.04)},
            )

        # Profile label
        msp.add_text(
            arquivo,
            dxfattribs={"layer": "SCANSOLO_TITULO", "height": 0.12, "insert": (0, y_offset + 0.25)},
        )

        # Targets
        for t in ptargets:
            x = t.get("x_m") or 0
            y = y_offset - (t.get("depth_m") or 0)
            r = max((t.get("diam_est_m") or 0.06) / 2, 0.02)
            tipo = t.get("tipo_final") or "desconhecido"
            color = _TIPO_DXF_COLOR.get(tipo, 7)

            msp.add_circle(
                (x, y), r,
                dxfattribs={"layer": "SCANSOLO_ALVOS", "color": color},
            )
            msp.add_text(
                f"#{t.get('rank')} {tipo[:12]} {(t.get('depth_m') or 0):.2f}m",
                dxfattribs={
                    "layer": "SCANSOLO_TEXTOS",
                    "height": 0.07,
                    "insert": (x, y - r - 0.12),
                },
            )

        y_offset -= depth_max + gap

    # Title block
    msp.add_text(
        f"ScanSOLO | {proj_name}",
        dxfattribs={"layer": "SCANSOLO_TITULO", "height": 0.25, "insert": (0, y_offset - 0.5)},
    )
    msp.add_text(
        "Seção transversal GPR — coordenadas locais. PENDENTE: validar padrão DXF com Amilson.",
        dxfattribs={"layer": "SCANSOLO_TITULO", "height": 0.10, "insert": (0, y_offset - 0.85)},
    )

    buf = io.BytesIO()
    doc.write(buf)
    return buf.getvalue()


def _setup_dxf_layers(doc: Any) -> None:
    layers = [
        ("SCANSOLO_ALVOS",      1),
        ("SCANSOLO_TEXTOS",     7),
        ("SCANSOLO_SUPERFICIE", 5),
        ("SCANSOLO_ESCALA",     8),
        ("SCANSOLO_TITULO",     3),
    ]
    for name, color in layers:
        doc.layers.new(name=name, dxfattribs={"color": color})


def _gen_kml(
    targets: list[dict[str, Any]],
    gps_path: list[tuple[float, float]],
    project: dict[str, Any],
) -> bytes:
    proj_name = project.get("nome", "ScanSOLO")
    dist_max = max((t.get("x_m") or 0) for t in targets)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<kml xmlns="http://www.opengis.net/kml/2.2">',
        "<Document>",
        f"  <name>{proj_name}</name>",
        "  <description>Alvos GPR gerados automaticamente pela plataforma ScanSOLO.</description>",
    ]

    # Style for each type
    seen_tipos: set[str] = set()
    for t in targets:
        tipo = t.get("tipo_final") or "desconhecido"
        if tipo not in seen_tipos:
            seen_tipos.add(tipo)
            color = _TIPO_KML_COLOR.get(tipo, "ffffffff")
            lines += [
                f'  <Style id="{tipo}">',
                "    <IconStyle>",
                f"      <color>{color}</color>",
                "      <scale>1.0</scale>",
                "      <Icon><href>http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png</href></Icon>",
                "    </IconStyle>",
                "  </Style>",
            ]

    # Survey path
    path_coords = " ".join(f"{lon},{lat},0" for lon, lat in gps_path)
    lines += [
        "  <Placemark>",
        "    <name>Perfil GPR</name>",
        "    <LineString>",
        "      <tessellate>1</tessellate>",
        f"      <coordinates>{path_coords}</coordinates>",
        "    </LineString>",
        "  </Placemark>",
    ]

    # Targets
    for t in targets:
        x_m = t.get("x_m") or 0
        lon, lat = _interpolate_along_path(gps_path, x_m)
        tipo = t.get("tipo_final") or "desconhecido"
        rank = t.get("rank", "?")
        depth = t.get("depth_m") or 0
        diam = t.get("diam_est_m") or 0

        lines += [
            "  <Placemark>",
            f"    <name>#{rank} {tipo}</name>",
            "    <description>"
            f"Prof: {depth:.2f}m | Diâm: {diam:.3f}m | "
            f"Planta: {'Sim' if t.get('vai_para_planta') else 'Não'} | "
            f"Relatório: {'Sim' if t.get('vai_para_relatorio') else 'Não'}"
            "</description>",
            f"    <styleUrl>#{tipo}</styleUrl>",
            "    <Point>",
            f"      <coordinates>{lon},{lat},0</coordinates>",
            "    </Point>",
            "  </Placemark>",
        ]

    lines += ["</Document>", "</kml>"]
    return "\n".join(lines).encode("utf-8")


# ── GPS interpolation ─────────────────────────────────────────────────────────

def _path_length_m(path: list[tuple[float, float]]) -> float:
    """Total length of a GPS path in meters using haversine."""
    total = 0.0
    for i in range(1, len(path)):
        total += _haversine(path[i - 1], path[i])
    return total


def _interpolate_along_path(
    path: list[tuple[float, float]],
    x_m: float,
) -> tuple[float, float]:
    """Return (lon, lat) at distance x_m along the GPS path."""
    if len(path) == 1:
        return path[0]

    total = _path_length_m(path)
    if total == 0:
        return path[0]

    target_frac = min(x_m / total, 1.0)
    target_dist = target_frac * total

    cumulative = 0.0
    for i in range(1, len(path)):
        seg = _haversine(path[i - 1], path[i])
        if cumulative + seg >= target_dist or i == len(path) - 1:
            frac = (target_dist - cumulative) / seg if seg > 0 else 0
            lon = path[i - 1][0] + frac * (path[i][0] - path[i - 1][0])
            lat = path[i - 1][1] + frac * (path[i][1] - path[i - 1][1])
            return (lon, lat)
        cumulative += seg

    return path[-1]


def _haversine(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Distance between two (lon, lat) points in meters."""
    import math
    lon1, lat1 = math.radians(p1[0]), math.radians(p1[1])
    lon2, lat2 = math.radians(p2[0]), math.radians(p2[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(a))
