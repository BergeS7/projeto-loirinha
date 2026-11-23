"""Projeção pública do GPS sobre o traçado; nenhuma identidade privada é copiada.

O catálogo é publicado por administrador (scripts/publish_passenger_catalog.py).
ETA usa distância pela rua e velocidade instantânea: parado ou fora do traçado
não gera uma previsão numérica enganosa. Não é um modelo de trânsito histórico.
"""

from __future__ import annotations

import math
from typing import Any


def meters(a, b):
    """Distância Haversine, limitada para evitar erros de arredondamento."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 12_742_000 * math.asin(min(1, math.sqrt(h)))


def project(coords, lat, lng):
    """Projeção no segmento mais próximo, progresso e distância lateral em metros."""
    lengths = [meters(a, b) for a, b in zip(coords, coords[1:])]
    total = sum(lengths)
    if total <= 0:
        raise ValueError("Traçado sem comprimento")
    best = (float("inf"), 0.0)
    accumulated = 0.0
    scale = math.cos(math.radians(lat))
    for a, b, length in zip(coords, coords[1:], lengths):
        ax, ay = (a[1] - lng) * scale, a[0] - lat
        dx, dy = (b[1] - a[1]) * scale, b[0] - a[0]
        squared = dx * dx + dy * dy
        t = max(0, min(1, -(ax * dx + ay * dy) / squared)) if squared else 0
        nearest = [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]
        candidate = (meters([lat, lng], nearest), (accumulated + t * length) / total)
        if candidate[0] < best[0]:
            best = candidate
        accumulated += length
    return best[1], best[0], total


def projection(line: dict, fix: dict) -> dict:
    """ETA por parada; percurso aberto não dá uma volta artificial no fim."""
    progress, offset, total = project(line["tracado"], fix["lat"], fix["lng"])
    speed = fix["speed"] / 3.6
    arrivals = {}
    upcoming = []
    for stop, fraction in zip(line["pontoIds"], line["pontoFracoes"]):
        delta = fraction - progress
        if delta < 0 and line.get("circular", False):
            delta += 1
        if delta < 0:
            continue
        upcoming.append((delta, stop))
        if speed >= 1 and offset <= 100 and fix["status"] != "out_of_route":
            minutes = max(1, math.ceil(delta * total / speed / 60))
            arrivals[stop] = min(arrivals.get(stop, minutes), minutes)
    next_stop = min(upcoming)[1] if upcoming else None
    return {
        "progresso": progress,
        "offRoute": offset > 100 or fix["status"] == "out_of_route",
        "proximoPontoId": next_stop,
        "minutosProximoPonto": arrivals.get(next_stop),
        "previsoes": arrivals,
    }


def public_projection(db, fix: dict) -> dict:
    """Só ônibus publicados têm linha/ETA. Não infere número da placa nem ocupação."""
    bus = db.collection("public_buses").document(fix["bus_id"]).get().to_dict()
    if not bus:
        return {}
    line_id = bus.get("linhaId")
    if not isinstance(line_id, str) or not line_id:
        return {}
    line = db.collection("public_lines").document(line_id).get().to_dict()
    if not line:
        return {}
    # Firestore proíbe arrays aninhados; persistimos vértices como mapas lat/lng.
    line = {
        **line,
        "tracado": [[point["lat"], point["lng"]] for point in line["tracado"]],
    }
    return {"linhaId": line_id, "lotacao": "desconhecida", **projection(line, fix)}


def catalog_document(item: dict) -> dict:
    """Serializa catálogo validado para Firestore sem arrays aninhados nem IDs redundantes."""
    body = {key: value for key, value in item.items() if key != "id"}
    if "tracado" in body:
        body["tracado"] = [{"lat": lat, "lng": lng} for lat, lng in body["tracado"]]
    return body


def validate_catalog(catalog: Any) -> dict:
    """Valida referências, limites GPS e campos públicos antes de qualquer escrita.

    Campos desconhecidos são recusados para impedir publicação acidental de PII.
    Frações das paradas são calculadas no servidor, nunca confiadas ao arquivo.
    """
    if not isinstance(catalog, dict) or set(catalog) != {
        "lines",
        "stops",
        "buses",
        "notices",
    }:
        raise ValueError("Catálogo deve conter lines, stops, buses e notices")
    allowed = {
        "stops": {"id", "nome", "referencia", "lat", "lng"},
        "lines": {
            "id",
            "numero",
            "nome",
            "cor",
            "pontoIds",
            "operacao",
            "intervalo",
            "tracado",
            "circular",
        },
        "buses": {"id", "prefixo", "linhaId", "sentido"},
        "notices": {"id", "tipo", "titulo", "descricao", "linhas", "horario"},
    }
    import re
    import copy

    result = copy.deepcopy(catalog)
    for group, keys in allowed.items():
        entries = result[group]
        if not isinstance(entries, list) or len(entries) > 1000:
            raise ValueError(f"Lista inválida: {group}")
        ids = set()
        for item in entries:
            if not isinstance(item, dict) or set(item) != keys:
                raise ValueError(f"Campos inválidos: {group}")
            if (
                not isinstance(item["id"], str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", item["id"])
                or item["id"] in ids
            ):
                raise ValueError("ID inválido ou duplicado")
            ids.add(item["id"])
            for key in keys - {
                "tracado",
                "pontoIds",
                "circular",
                "lat",
                "lng",
                "linhas",
            }:
                if (
                    not isinstance(item[key], str)
                    or not item[key].strip()
                    or len(item[key]) > 2000
                ):
                    raise ValueError(f"Texto inválido: {key}")

    def coord(pair):
        return (
            isinstance(pair, (list, tuple))
            and len(pair) == 2
            and all(
                isinstance(x, (int, float))
                and not isinstance(x, bool)
                and math.isfinite(x)
                and abs(x) <= limit
                for x, limit in zip(pair, (90, 180))
            )
        )

    stops = {stop["id"]: stop for stop in result["stops"]}
    for stop in stops.values():
        if not coord([stop["lat"], stop["lng"]]):
            raise ValueError("Coordenada de parada inválida")
    lines = {line["id"]: line for line in result["lines"]}
    for line in lines.values():
        coords = line["tracado"]
        if (
            not isinstance(coords, list)
            or not 2 <= len(coords) <= 5000
            or not all(coord(pair) for pair in coords)
        ):
            raise ValueError("Traçado inválido")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", line["cor"]) or not isinstance(
            line["circular"], bool
        ):
            raise ValueError("Cor ou circular inválido")
        if (
            not isinstance(line["pontoIds"], list)
            or not line["pontoIds"]
            or not all(isinstance(s, str) and s in stops for s in line["pontoIds"])
        ):
            raise ValueError("Paradas da linha inválidas")
        fractions = [
            project(coords, stops[s]["lat"], stops[s]["lng"]) for s in line["pontoIds"]
        ]
        # Parada inicial repetida no fim de uma circular representa a chegada (100%).
        if line["circular"]:
            if meters(coords[0], coords[-1]) > 100:
                raise ValueError("Traçado circular precisa retornar ao início")
            if len(fractions) > 1 and line["pontoIds"][0] == line["pontoIds"][-1]:
                fractions[-1] = (
                    1.0,
                    meters(
                        coords[-1],
                        [
                            stops[line["pontoIds"][-1]]["lat"],
                            stops[line["pontoIds"][-1]]["lng"],
                        ],
                    ),
                    fractions[-1][2],
                )
        if any(offset > 100 for _, offset, _ in fractions):
            raise ValueError("Parada distante do traçado")
        line["pontoFracoes"] = [fraction for fraction, _, _ in fractions]
        if line["pontoFracoes"] != sorted(line["pontoFracoes"]):
            raise ValueError("Paradas fora da ordem do traçado")
    for bus in result["buses"]:
        if bus["linhaId"] not in lines:
            raise ValueError("Ônibus com linha inexistente")
    for notice in result["notices"]:
        if (
            notice["tipo"] not in ("atraso", "desvio", "informacao")
            or not isinstance(notice["linhas"], list)
            or not all(isinstance(n, str) for n in notice["linhas"])
        ):
            raise ValueError("Aviso inválido")
    return result
