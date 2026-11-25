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


def em_ordem(sinais) -> list:
    """Linha do tempo (ADR-0013 D3). Dentro de um processo, a ordem é a do
    procedimento (a força do tipo: licitação antes do contrato), porque as
    datas são de naturezas diferentes: o contrato tem a data de assinatura, a
    licitação a de publicação no PNCP. Entre processos, e para os sinais sem
    processo, vale a data: cada processo entra pela data do primeiro sinal."""
    sinais = list(sinais)
    inicio = {}
    for s in sinais:
        if s.processo_pncp:
            inicio[s.processo_pncp] = min(inicio.get(s.processo_pncp, s.data_documento), s.data_documento)
    return sorted(sinais, key=lambda s: (inicio.get(s.processo_pncp, s.data_documento), s.processo_pncp or str(s.pk),
                                         forca(s.tipo), s.data_documento))


def ano_do_concurso(av, sinais) -> int:
    """O ano que nomeia o concurso ({órgão}_{ano}, ADR-0013). Sai de um
    documento, nunca da janela: a janela é estimativa do edital e atravessa
    o ano quando o sinal sai no fim do exercício (a licitação da RFB de
    23/11/2026 dava 2027, mas o concurso autorizado em 07/2026, com edital
    previsto para 12/2026, é o "Receita 2026"). Vale o ano da autorização
    mais recente do ciclo (até 18 meses antes do sinal principal: uma
    autorização esquecida de um concurso anterior não conta); sem ela, o ano
    do sinal principal."""
    base = av.sinal.data_documento
    autorizacoes = [s.data_documento for s in sinais
                    if s.tipo == "autorizacao" and s.data_documento >= somar_meses(base, -18)]
    return (max(autorizacoes) if autorizacoes else base).year


ROTULO_PRAZO = {"no_prazo": "no prazo", "atrasado": "atrasado", "sem_janela": "sem previsão"}
STATUS_DO_RADAR = ("previsto", "autorizado")
# concurso do órgão já com edital e ainda não encerrado: o radar não cria outra página por cima
STATUS_EM_ANDAMENTO = ("edital_aberto", "inscricoes_encerradas", "prova_realizada")


def aplicar(orgao, hoje: date | None = None):
    """Leva os sinais do órgão ao portal (ADR-0008 §5, opção b; ADR-0013 D2).
    Devolve a ConcursoPage da chamada, ou None.

    Um sinal solto só é ligado a uma página quando não há dúvida de que é o
    mesmo concurso:
    - tem processo PNCP, e algum sinal da página é do mesmo processo; ou
    - não tem processo, e o órgão tem uma única página no radar.
    Fora disso fica solto, no painel "Sinal de outro processo do mesmo órgão",
    e quem decide é o curador. O radar não chuta.

    Sem nenhuma página, e com força 4 ou mais, cria e publica a chamada com o
    sinal mais forte, mais os do mesmo processo e os sem processo. Uma página
    Prevista sobe para Autorizada quando os sinais DELA chegam à força 4.
    Nunca rebaixa nem mexe no que o curador escreveu.
    """
    from .models import ConcursoPage

    sinais = list(orgao.sinais.all())
    if not sinais:
        return None
    paginas = {s.concurso_id: s.concurso for s in sinais if s.concurso_id}
    for p in ConcursoPage.objects.filter(orgao=orgao, status__in=STATUS_DO_RADAR):
        paginas.setdefault(p.pk, p)
    soltos = [s for s in sinais if not s.concurso_id]

    if not paginas:
        if ConcursoPage.objects.filter(orgao=orgao, status__in=STATUS_EM_ANDAMENTO).exists():
            return None      # pode ser o sinal atrasado do concurso que já está no portal: o curador decide
        av = avaliar(soltos, hoje)
        if not av.publica_sozinho:
            return None
        chamada = _nova_chamada(orgao, av, soltos)
        if chamada is None:
            return None
        grupo = av.sinal.processo_pncp
        ligar = [s for s in soltos if s.processo_pncp in ("", grupo)]
    else:
        do_processo = {s.processo_pncp: s.concurso for s in sinais if s.concurso_id and s.processo_pncp}
        unica = next(iter(paginas.values())) if len(paginas) == 1 else None
        ligar = []
        for s in soltos:
            destino = do_processo.get(s.processo_pncp) if s.processo_pncp else unica
            if destino is not None:
                s.concurso = destino
                ligar.append(s)
        chamada = max(paginas.values(), key=lambda p: p.pk)        # a página mais nova do órgão

    for s in ligar:
        s.concurso = s.concurso or chamada
        s.save(update_fields=["concurso"])
    for p in {s.concurso for s in ligar} | ({chamada} if chamada else set()):
        _subir_status(p, hoje)
    return chamada


def _nova_chamada(orgao, av, sinais):
    from .models import ConcursoPage, ConcursosIndexPage, StatusConcurso

    indice = ConcursosIndexPage.objects.first()
    if indice is None:
        return None
    ano = ano_do_concurso(av, sinais)
    if ConcursoPage.objects.filter(contest_slug=f"{orgao.slug}_{ano}").exists():
        return None      # já há concurso do órgão naquele ano: decisão do curador
    banca = next((s.banca for s in sinais if s.banca_id), None)
    chamada = ConcursoPage(
        title=f"{orgao.sigla or orgao.nome_com_estado} {ano}: concurso autorizado",
        orgao=orgao, banca=banca, ano=ano, status=StatusConcurso.AUTORIZADO,
        fonte_url=av.sinal.documento_url,
        resumo=f"<p>{av.sinal.resumo}</p>",
        search_description=f"{orgao.nome_com_estado}: concurso autorizado. Previsão do edital e "
                           "documentos oficiais.",
    )
    indice.add_child(instance=chamada)
    chamada.save_revision().publish()
    return chamada


def _subir_status(pagina, hoje):
    from .models import StatusConcurso

    av = avaliar(pagina.sinais.all(), hoje)
    if av and av.forca >= forca("autorizacao") and pagina.status == StatusConcurso.PREVISTO:
        pagina.status = StatusConcurso.AUTORIZADO
        pagina.save_revision().publish()


def sinais_de_outro_processo():
    """Sinais soltos de órgão que já tem página: o curador decide se é o mesmo
    concurso ou um concurso novo (ADR-0013 D2)."""
    from django.db.models import Q

    from .models import ConcursoPage, Sinal

    no_radar = ConcursoPage.objects.filter(status__in=STATUS_DO_RADAR + STATUS_EM_ANDAMENTO).values("orgao")
    ligados = Sinal.objects.filter(concurso__isnull=False).values("orgao")
    return list(Sinal.objects.filter(concurso__isnull=True)
                .filter(Q(orgao__in=no_radar) | Q(orgao__in=ligados))
                .select_related("orgao").order_by("orgao__nome", "data_documento"))
