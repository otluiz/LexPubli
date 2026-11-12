"""Radar vivo da home (SPEC-0003 D2).

Cada ponto do radar é uma `ConcursoPage` publicada de verdade. A distância
ao centro diz a recência da publicação: quanto mais recente, mais perto do
centro. O ângulo é estável (sai do slug), para o ponto não pular de lugar a
cada visita.

O desenho é SVG e a animação é CSS (D3). A CSP do portal não aceita estilo
inline, então nada aqui vira `style="..."`: a posição vai em atributos do
SVG (cx, cy), que não são estilo, e o momento em que o varredor acende cada
ponto vem de uma classe `setor-N`, com o atraso definido no site.css.
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, replace

from django.utils import timezone

JANELA_DIAS = 90        # recência generosa: com poucas descobertas, 7 dias deixaria o radar vazio
SETORES = 24            # 15° cada; precisa bater com os .setor-N do site.css
RAIO_MIN, RAIO_MAX = 18.0, 88.0    # no viewBox de -100 a 100; o centro fica livre


@dataclass(frozen=True)
class Ponto:
    concurso: object
    x: float
    y: float
    setor: int
    dias: int

    rotulo: tuple = (9, 3.5, "start")    # dx, dy, text-anchor (só o ponto mais recente tem rótulo)

    @property
    def texto_rotulo(self) -> str:
        c = self.concurso
        sigla = c.orgao.sigla or ""
        if not sigla:
            return c.title[:22]
        uf = c.orgao.uf if c.orgao.estado and c.orgao.uf not in sigla else ""
        return f"{sigla}{'-' + uf if uf else ''} {c.ano}"


def _setor_inicial(chave: str) -> int:
    return zlib.crc32(chave.encode()) % SETORES


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

    resultado, ocupados = [], set()
    for dias, c in recentes:
        raio = RAIO_MIN + (RAIO_MAX - RAIO_MIN) * dias / JANELA_DIAS
        anel = int(raio // 12)
        setor = _setor_inicial(c.contest_slug or c.slug)
        # dois concursos no mesmo setor e mesmo anel ficariam um em cima do
        # outro: anda um setor até achar lugar livre
        for _ in range(SETORES):
            if (setor, anel) not in ocupados:
                break
            setor = (setor + 1) % SETORES
        ocupados.add((setor, anel))
        angulo = math.radians(setor * 360 / SETORES)
        resultado.append(Ponto(concurso=c, x=round(raio * math.cos(angulo), 1),
                               y=round(raio * math.sin(angulo), 1), setor=setor, dias=dias))
    if resultado:
        resultado[0] = _com_rotulo(resultado[0], resultado[1:])
    return resultado


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
