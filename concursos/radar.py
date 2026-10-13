"""Radar de sinais de concurso futuro (ADR-0008).

A força e a janela até o edital vêm do TIPO do sinal, num arquivo versionado
(concursos/dados/janelas_sinais.json), para calibrar sem mexer em código.
Tudo aqui é cálculo puro sobre os sinais de um órgão: explicável ao assinante.
"""
from __future__ import annotations

import calendar
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

JANELAS = Path(__file__).resolve().parent / "dados" / "janelas_sinais.json"


@lru_cache(maxsize=1)
def regras() -> dict:
    return json.loads(JANELAS.read_text(encoding="utf-8"))


def forca(tipo: str) -> int:
    return regras()["tipos"][tipo]["forca"]


def somar_meses(d: date, meses: int) -> date:
    m = d.month - 1 + meses
    ano, mes = d.year + m // 12, m % 12 + 1
    return date(ano, mes, min(d.day, calendar.monthrange(ano, mes)[1]))


def janela(tipo: str, data_doc: date, data_autorizacao: date | None = None) -> tuple[date, date] | None:
    """Intervalo em que o edital costuma sair, contado da data do documento."""
    r = regras()
    regra = r["tipos"][tipo]["janela"]
    if regra is None:
        return None
    if regra == "exercicio_seguinte":
        return date(data_doc.year + 1, 1, 1), date(data_doc.year + 1, 12, 31)
    if regra == "exercicio":
        return data_doc, date(data_doc.year, 12, 31)
    if regra == "da_autorizacao":
        # a comissão reforça a autorização: vale a janela dela, se houver;
        # sem autorização conhecida, a comissão conta como se fosse uma
        return janela("autorizacao", data_autorizacao or data_doc)
    meses = regra["meses"]
    if "fim_de_ano" in regra and data_doc.month in r["fim_de_ano_meses"]:
        meses = regra["fim_de_ano"]       # perto do fim do ano: depois do Carnaval
    return somar_meses(data_doc, meses[0]), somar_meses(data_doc, meses[1])


@dataclass
class Avaliacao:
    forca: int
    sinal: object                         # o Sinal que sustenta a nota
    inicio: date | None
    fim: date | None
    prazo: str                            # no_prazo | atrasado | sem_janela

    @property
    def publica_sozinho(self) -> bool:
        return self.forca >= regras()["forca_para_publicar_sozinho"]


def avaliar(sinais, hoje: date | None = None) -> Avaliacao | None:
    """A nota de um órgão: o sinal oficial mais forte (no empate, o mais
    recente), a janela dele e se o prazo usual já venceu sem edital."""
    sinais = list(sinais)
    if not sinais:
        return None
    hoje = hoje or date.today()
    principal = max(sinais, key=lambda s: (forca(s.tipo), s.data_documento))
    autorizacoes = [s.data_documento for s in sinais if s.tipo == "autorizacao"]
    jan = janela(principal.tipo, principal.data_documento, max(autorizacoes, default=None))
    if jan is None:
        prazo = "sem_janela"
    else:
        prazo = "atrasado" if hoje > jan[1] else "no_prazo"
    return Avaliacao(forca(principal.tipo), principal, *(jan or (None, None)), prazo)


ROTULO_PRAZO = {"no_prazo": "no prazo", "atrasado": "atrasado", "sem_janela": "sem previsão"}
STATUS_DO_RADAR = ("previsto", "autorizado")


def aplicar(orgao, hoje: date | None = None):
    """Leva a nota do órgão ao portal (ADR-0008 §5, opção b). Devolve a
    ConcursoPage da chamada, ou None.

    - Já há chamada (um sinal ligado a uma página, ou uma página Prevista ou
      Autorizada do órgão): liga a ela os sinais soltos e sobe o status para
      Autorizado se a força chegou a 4. Nunca rebaixa nem mexe no que o
      curador escreveu.
    - Não há, e a força é 4 ou mais: cria e publica a chamada sozinho.
    - Não há, e a força é menor: nada; abaixo da autorização, quem publica é
      o curador.
    """
    from .models import ConcursoPage, ConcursosIndexPage, StatusConcurso

    sinais = list(orgao.sinais.all())
    av = avaliar(sinais, hoje)
    if av is None:
        return None
    chamada = next((s.concurso for s in sinais if s.concurso_id), None) or (
        ConcursoPage.objects.filter(orgao=orgao, status__in=STATUS_DO_RADAR)
        .order_by("-first_published_at").first())
    if chamada is None:
        if not av.publica_sozinho:
            return None
        indice = ConcursosIndexPage.objects.first()
        if indice is None:
            return None
        ano = (av.inicio or av.sinal.data_documento).year
        if ConcursoPage.objects.filter(contest_slug=f"{orgao.slug}_{ano}").exists():
            return None      # já há concurso do órgão naquele ano: decisão do curador
        banca = next((s.banca for s in sinais if s.banca_id), None)
        chamada = ConcursoPage(
            title=f"{orgao.sigla or orgao.nome} {ano}: concurso autorizado",
            orgao=orgao, banca=banca, ano=ano, status=StatusConcurso.AUTORIZADO,
            fonte_url=av.sinal.documento_url,
            resumo=f"<p>{av.sinal.resumo}</p>",
            search_description=f"{orgao.nome}: concurso autorizado. Previsão do edital e "
                               "documentos oficiais.",
        )
        indice.add_child(instance=chamada)
        chamada.save_revision().publish()
    elif av.forca >= forca("autorizacao") and chamada.status == StatusConcurso.PREVISTO:
        chamada.status = StatusConcurso.AUTORIZADO
        chamada.save_revision().publish()
    orgao.sinais.filter(concurso__isnull=True).update(concurso=chamada)
    return chamada
