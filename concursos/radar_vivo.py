"""Radar vivo da home (SPEC-0003 D2, revisto em 19/11).

Cada ponto do radar é uma `ConcursoPage` publicada de verdade, desenhada no
mapa do Brasil, no estado do órgão (`Orgao.lugar`): quem chega escolhe onde
quer prestar. Órgão federal de alcance nacional fica na caixa "Nacional", no
oceano, para não inflar o DF. Vários concursos no mesmo estado se espalham em
espiral em volta do centro dele, o mais recente no meio.

O desenho é SVG e a animação é CSS (D3). A CSP do portal não aceita estilo
inline, então nada aqui vira `style="..."`: a posição vai em atributos do
SVG (cx, cy), que não são estilo, e o momento em que o varredor acende cada
ponto vem de uma classe `setor-N`, tirada do ângulo do ponto em relação ao
centro do disco, com o atraso definido no site.css.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path

from django.utils import timezone

JANELA_DIAS = 90        # recência generosa: com poucas descobertas, 7 dias deixaria o radar vazio
RECENTE_DIAS = 7        # ponto maior: publicado na última semana
SETORES = 24            # 15° cada; precisa bater com os .setor-N do site.css
NACIONAL = (62.0, 60.0)     # no Atlântico, a sudeste do mapa
PASSO = 3.6             # afastamento da espiral entre pontos do mesmo estado
ANGULO_DOURADO = math.radians(137.5)


@cache
def _mapa() -> dict:
    """UF -> {"d": path SVG, "x", "y": centro}. Gerado por scripts/gerar_mapa_uf.py."""
    return json.loads((Path(__file__).parent / "dados/mapa_uf.json").read_text())["ufs"]


@dataclass(frozen=True)
class Ponto:
    concurso: object
    x: float
    y: float
    setor: int
    dias: int

    rotulo: tuple = (9, 3.5, "start")    # dx, dy, text-anchor (só o ponto mais recente tem rótulo)

    @property
    def recente(self) -> bool:
        return self.dias <= RECENTE_DIAS

    @property
    def texto_rotulo(self) -> str:
        c = self.concurso
        sigla = c.orgao.sigla or ""
        if not sigla:
            return c.title[:22]
        uf = c.orgao.uf if c.orgao.estado and c.orgao.uf not in sigla else ""
        return f"{sigla}{'-' + uf if uf else ''} {c.ano}"


def _setor(x: float, y: float) -> int:
    """O setor de 15° em que o feixe passa pelo ponto (y cresce para baixo: sentido horário)."""
    return int(math.degrees(math.atan2(y, x)) % 360 // (360 / SETORES)) % SETORES


def pontos(concursos, hoje=None) -> list[Ponto]:
    """Pontos dos concursos publicados nos últimos JANELA_DIAS, do mais recente ao mais antigo."""
    agora = hoje or timezone.now()
    recentes = []
    for c in concursos:
        if not c.first_published_at:
            continue
        dias = max(0, (agora - c.first_published_at).days)
        if dias <= JANELA_DIAS:
            recentes.append((dias, c))
    recentes.sort(key=lambda par: par[0])

    resultado, por_lugar = [], {}
    for dias, c in recentes:
        lugar = c.orgao.lugar
        cx, cy = NACIONAL if lugar == "BR" else (_mapa()[lugar]["x"], _mapa()[lugar]["y"])
        i = por_lugar[lugar] = por_lugar.get(lugar, -1) + 1
        x = round(cx + PASSO * math.sqrt(i) * math.cos(i * ANGULO_DOURADO), 1)
        y = round(cy + PASSO * math.sqrt(i) * math.sin(i * ANGULO_DOURADO), 1)
        resultado.append(Ponto(concurso=c, x=x, y=y, setor=_setor(x, y), dias=dias))
    if resultado:
        resultado[0] = _com_rotulo(resultado[0], resultado[1:])
    return resultado


def estados(contagem: dict[str, int], ativo: str = "") -> list[dict]:
    """Os 27 contornos do mapa; o estado com concurso vira link para filtrar a lista."""
    from .orgaos import ESTADO

    return [{"uf": uf, "d": m["d"], "nome": ESTADO[uf], "n": contagem.get(uf, 0), "ativo": uf == ativo}
            for uf, m in _mapa().items()]


# posições candidatas do rótulo em volta do ponto: direita, esquerda, acima, abaixo
_POSICOES = [(9, 3.5, "start"), (-9, 3.5, "end"), (0, -10, "middle"), (0, 16, "middle")]


def _caixa(p: Ponto, dx: float, dy: float, ancora: str) -> tuple[float, float, float, float]:
    largura, altura = 4.9 * len(p.texto_rotulo), 9.0      # fonte de 8 no viewBox
    x0 = p.x + dx - {"start": 0, "end": largura, "middle": largura / 2}[ancora]
    y1 = p.y + dy + 2
    return x0, y1 - altura, x0 + largura, y1


def _com_rotulo(p: Ponto, outros: list[Ponto]) -> Ponto:
    """Escolhe a primeira posição em que o rótulo não cobre outro ponto nem sai do disco."""
    for pos in _POSICOES:
        x0, y0, x1, y1 = _caixa(p, *pos)
        dentro = -100 <= x0 and x1 <= 100 and -100 <= y0 and y1 <= 100
        livre = all(not (x0 - 8 <= o.x <= x1 + 8 and y0 - 8 <= o.y <= y1 + 8) for o in outros)
        if dentro and livre:
            return replace(p, rotulo=pos)
    return p
