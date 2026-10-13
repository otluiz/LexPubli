"""Fontes de descoberta (ADR-0007) e a regra de fonte oficial (ADR-0002)."""
import datetime as dt

import pytest
from django.core.exceptions import ValidationError

from concursos.models import Descoberta, Fonte, Orgao, OutboxEvent
from concursos.util import dominio_oficial

PCI = "https://www.pciconcursos.com.br/noticias/sefaz-al-2026"
BANCAS = ["https://www.cebraspe.org.br", "https://conhecimento.fgv.br"]


@pytest.mark.parametrize("url,oficial", [
    ("https://www.in.gov.br/web/dou/-/portaria-1", True),
    ("https://www.trt8.jus.br/concursos", True),
    ("https://www.camara.leg.br/concursos", True),
    ("https://www.mpf.mp.br/concursos", True),
    ("https://www.dpu.def.br/concursos", True),
    ("https://cdn.cebraspe.org.br/concursos/a.pdf", True),     # subdomínio da banca
    ("https://conhecimento.fgv.br/concursos/tjgo2025", True),
    (PCI, False),                                                # agregador: só índice
    ("https://evilgov.br/x", False),                             # sufixo sem o ponto
    ("https://cebraspe.org.br.exemplo.com/x", False),
    ("https://fakecebraspe.org.br/x", False),
    ("", False),
])
def test_dominio_oficial(url, oficial):
    assert dominio_oficial(url, BANCAS) is oficial


def _fonte(**kw):
    dados = dict(nome="TRT da 8ª Região", poder=Fonte.Poder.JUDICIARIO,
                 esfera=Orgao.Esfera.FEDERAL, url="https://www.trt8.jus.br/concursos")
    return Fonte(**{**dados, **kw})


def test_fonte_oficial_e_valida(db):
    _fonte().full_clean()


def test_fonte_de_agregador_e_recusada(db):
    with pytest.raises(ValidationError) as exc:
        _fonte(url=PCI).full_clean()
    assert "url" in exc.value.message_dict


def test_fonte_so_ativa_depois_de_conferida(db):
    with pytest.raises(ValidationError, match="Confira"):
        _fonte(ativa=True).full_clean()
    _fonte(ativa=True, conferida_em=dt.date(2026, 10, 13)).full_clean()


def test_fonte_conferida_e_inativa_precisa_de_motivo(db):
    with pytest.raises(ValidationError):
        _fonte(conferida_em=dt.date(2026, 10, 13)).full_clean()
    _fonte(conferida_em=dt.date(2026, 10, 13), motivo_inativa="página só com JS").full_clean()


def test_dou_e_diario(db):
    with pytest.raises(ValidationError):
        _fonte(tipo=Fonte.Tipo.DOU, url="https://www.in.gov.br/leiturajornal",
               intervalo_horas=6, poder=Fonte.Poder.EXECUTIVO).full_clean()


def test_concurso_com_fonte_de_agregador_e_recusado(exemplo):
    c = exemplo["concurso"]
    c.fonte_url = PCI
    with pytest.raises(ValidationError) as exc:
        c.clean()
    assert "fonte_url" in exc.value.message_dict


def test_aprovar_exige_fonte_oficial_no_concurso(exemplo):
    c = exemplo["concurso"]
    type(c).objects.filter(pk=c.pk).update(fonte_url=PCI)   # dado legado, antes da regra
    d = exemplo["descoberta"]
    d.status, d.concurso = Descoberta.Status.APROVADA, type(c).objects.get(pk=c.pk)
    with pytest.raises(ValidationError, match="não é oficial"):
        d.full_clean()


def test_descoberta_de_agregador_anuncia_a_fonte_oficial_do_concurso(exemplo):
    """O agregador pode apontar (origem da descoberta, auditoria); o evento
    leva a página oficial do concurso, que é por onde o LexCorpus resolve o
    alvo."""
    d = exemplo["descoberta"]
    Descoberta.objects.filter(pk=d.pk).update(fonte_url=PCI)
    d.refresh_from_db()
    d.status, d.concurso = Descoberta.Status.APROVADA, exemplo["concurso"]
    d.full_clean()
    d.save()
    data = OutboxEvent.objects.get().envelope["data"]
    assert data["source_url"] == exemplo["concurso"].fonte_url
    assert "pciconcursos" not in data["source_url"]


def test_carregar_onda_a(db):
    from io import StringIO

    from django.core.management import call_command

    call_command("carregar_fontes", "A", stdout=StringIO())
    assert Fonte.objects.count() == 22
    assert Fonte.objects.filter(ativa=True).count() == 17
    inativas = Fonte.objects.filter(ativa=False)
    assert all(f.motivo_inativa for f in inativas)          # conferida e inativa: diz por quê
    assert set(Fonte.objects.values_list("poder", flat=True)) == set(Fonte.Poder.values)
    dou = Fonte.objects.get(tipo=Fonte.Tipo.DOU)
    assert dou.intervalo_horas == 24 and not dou.ativa


def test_carregar_de_novo_nao_desfaz_o_curador(db):
    from io import StringIO

    from django.core.management import call_command

    call_command("carregar_fontes", "A", stdout=StringIO())
    stj = Fonte.objects.get(nome__startswith="STJ")
    stj.prioridade = 1
    stj.save()
    saida = StringIO()
    call_command("carregar_fontes", "A", stdout=saida)
    assert "22 mantida(s)" in saida.getvalue()
    assert Fonte.objects.get(pk=stj.pk).prioridade == 1
    call_command("carregar_fontes", "A", "--atualizar", stdout=StringIO())
    assert Fonte.objects.get(pk=stj.pk).prioridade == 2


def test_carregar_onda_b_concursos_e_noticias(db):
    from io import StringIO

    from django.core.management import call_command

    call_command("carregar_fontes", "B", stdout=StringIO())
    b = Fonte.objects.filter(onda="B")
    assert b.count() == 220 and b.filter(ativa=True).count() == 160
    assert b.filter(ativa=True, conteudo="noticias").count() == 84
    assert all(f.motivo_inativa for f in b.filter(ativa=False))
    assert {f.esfera for f in b} == {"federal", "estadual"}
