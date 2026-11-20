"""Gera concursos/dados/mapa_uf.json: o contorno de cada UF em path SVG, no
mesmo viewBox do radar (-100 a 100), mais o ponto central de cada uma.

Rodado uma vez; o JSON vai para o git e o portal não depende deste script.
Malha: IBGE, na versão simplificada da CodeGeo publicada pelo projeto
Click That 'Hood (Code for America, licença MIT):
https://github.com/codeforgermany/click_that_hood/blob/main/public/data/brazil-states.geojson

    python3 scripts/gerar_mapa_uf.py brazil-states.geojson > concursos/dados/mapa_uf.json
"""
import json
import math
import sys

COS = math.cos(math.radians(-15))      # equirretangular centrada no meio do país
TOLERANCIA = 0.45                      # Douglas-Peucker, em unidades do viewBox
ESCALA, CX, CY = 4.35, -54.4, -13.6    # cabe no disco do radar (raio 98)


def projeta(lon, lat):
    return (lon - CX) * COS * ESCALA, -(lat - CY) * ESCALA


def _dist(p, a, b):
    (x, y), (x1, y1), (x2, y2) = p, a, b
    dx, dy = x2 - x1, y2 - y1
    if dx == dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - x1 - t * dx, y - y1 - t * dy)


def simplifica(pts):
    if len(pts) < 3:
        return pts
    i, d = max(((i, _dist(p, pts[0], pts[-1])) for i, p in enumerate(pts[1:-1], 1)), key=lambda t: t[1])
    if d <= TOLERANCIA:
        return [pts[0], pts[-1]]
    return simplifica(pts[:i + 1])[:-1] + simplifica(pts[i:])


def area(pts):
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1])) / 2


def centro(pts):
    a = area(pts)
    cx = sum((x1 + x2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
    cy = sum((y1 + y2) * (x1 * y2 - x2 * y1) for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]))
    return cx / (6 * a), cy / (6 * a)


def main(caminho):
    ufs = {}
    for f in json.load(open(caminho))["features"]:
        g = f["geometry"]
        poligonos = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        aneis = [[projeta(*c) for c in p[0]] for p in poligonos]
        aneis = [a for a in aneis if abs(area(a)) > 0.8]          # ilhas pequenas saem
        maior = max(aneis, key=lambda a: abs(area(a)))
        d = " ".join("M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in simplifica(a)) + " Z" for a in aneis)
        x, y = centro(maior)
        ufs[f["properties"]["sigla"]] = {"d": d, "x": round(x, 1), "y": round(y, 1)}
    json.dump({"fonte": "Malha do IBGE, simplificada pela CodeGeo (via Click That 'Hood, MIT)",
               "ufs": dict(sorted(ufs.items()))}, sys.stdout, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main(sys.argv[1])
