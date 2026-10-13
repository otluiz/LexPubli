"""Radar de sinais de concurso futuro (ADR-0008)."""
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from concursos import radar
from concursos.models import ConcursoPage, Orgao, Sinal, StatusConcurso

DOU = "https://www.in.gov.br/web/dou/-/portaria-1"
PNCP = "https://pncp.gov.br/app/contratos/1"


class S:
    """Sinal em memória, para o cálculo puro."""

    def __init__(self, tipo, data):
        self.tipo, self.data_documento = tipo, data


def test_tipos_do_modelo_e_do_arquivo_de_janelas_sao_os_mesmos():
    assert set(Sinal.Tipo.values) == set(radar.regras()["tipos"])


def test_autorizacao_vira_edital_em_2_a_3_meses():
    assert radar.janela("autorizacao", date(2026, 5, 10)) == (date(2026, 7, 10), date(2026, 8, 10))


@pytest.mark.parametrize("mes", [10, 11, 12])
def test_autorizacao_no_fim_do_ano_so_depois_do_carnaval(mes):
    inicio, fim = radar.janela("autorizacao", date(2026, mes, 15))
    assert (inicio, fim) == (radar.somar_meses(date(2026, mes, 15), 3),
                             radar.somar_meses(date(2026, mes, 15), 5))
    assert inicio.year == 2027


def test_banca_contratada_antecede_o_edital_em_3_a_4_meses():
    assert radar.janela("banca_contratada", date(2026, 1, 31)) == (date(2026, 4, 30), date(2026, 5, 31))


def test_comissao_usa_a_janela_da_autorizacao():
    assert radar.janela("comissao", date(2026, 7, 1), date(2026, 5, 10)) == \
        radar.janela("autorizacao", date(2026, 5, 10))


def test_previsao_orcamentaria_vale_o_exercicio_seguinte_e_pedido_nao_tem_janela():
    assert radar.janela("previsao_orcamentaria", date(2026, 8, 31)) == (date(2027, 1, 1), date(2027, 12, 31))
    assert radar.janela("pedido_autorizacao", date(2026, 8, 31)) is None


def test_nota_e_do_sinal_mais_forte_e_prazo_vencido_e_atrasado():
    sinais = [S("previsao_orcamentaria", date(2025, 8, 31)), S("autorizacao", date(2026, 3, 2))]
    av = radar.avaliar(sinais, hoje=date(2026, 5, 1))
    assert av.forca == 4 and av.sinal.tipo == "autorizacao" and av.prazo == "no_prazo"
    assert radar.avaliar(sinais, hoje=date(2026, 7, 1)).prazo == "atrasado"
    assert av.publica_sozinho
    assert not radar.avaliar([S("orcamento_aprovado", date(2026, 3, 2))]).publica_sozinho


# --- publicação (opção b) ---------------------------------------------------------

@pytest.fixture
def trt8(db, exemplo):
    return Orgao.objects.create(nome="Tribunal Regional do Trabalho da 8ª Região", sigla="TRT-8",
                                esfera=Orgao.Esfera.FEDERAL, uf="PA")


def _sinal(orgao, tipo, data, url=DOU, **kw):
    s = Sinal(orgao=orgao, tipo=tipo, data_documento=data, documento_url=url,
              resumo=f"{tipo} do {orgao.sigla}", **kw)
    s.full_clean()
    s.save()
    return s


def test_documento_de_agregador_nao_e_sinal(trt8):
    with pytest.raises(ValidationError):
        _sinal(trt8, "autorizacao", date(2026, 9, 1), url="https://www.pciconcursos.com.br/x")


def test_abaixo_da_autorizacao_o_radar_nao_publica(trt8):
    _sinal(trt8, "orcamento_aprovado", date(2026, 3, 2))
    assert radar.aplicar(trt8) is None
    assert not ConcursoPage.objects.filter(orgao=trt8).exists()


def test_autorizacao_publica_a_chamada_sozinho_e_liga_os_sinais(trt8):
    _sinal(trt8, "orcamento_aprovado", date(2026, 3, 2), url="https://www.trt8.jus.br/loa")
    _sinal(trt8, "autorizacao", date(2026, 9, 1))
    chamada = radar.aplicar(trt8, hoje=date(2026, 10, 13))
    assert chamada.live and chamada.status == StatusConcurso.AUTORIZADO
    assert chamada.fonte_url == DOU and chamada.ano == 2026
    assert set(trt8.sinais.values_list("concurso", flat=True)) == {chamada.pk}
    # rodar de novo não duplica
    assert radar.aplicar(trt8, hoje=date(2026, 10, 13)).pk == chamada.pk
    assert ConcursoPage.objects.filter(orgao=trt8).count() == 1


def test_chamada_prevista_do_curador_sobe_para_autorizado(trt8, exemplo):
    indice = exemplo["concurso"].get_parent().specific
    previsto = ConcursoPage(title="TRT-8: concurso previsto", orgao=trt8, ano=2027,
                            status=StatusConcurso.PREVISTO, fonte_url="https://www.trt8.jus.br/n")
    indice.add_child(instance=previsto)
    _sinal(trt8, "autorizacao", date(2026, 9, 1))
    chamada = radar.aplicar(trt8)
    assert chamada.pk == previsto.pk
    previsto.refresh_from_db()
    assert previsto.status == StatusConcurso.AUTORIZADO
    assert previsto.title == "TRT-8: concurso previsto"            # o texto do curador fica


def test_pagina_mostra_nota_previsao_e_linha_do_tempo(client, trt8):
    _sinal(trt8, "autorizacao", date(2026, 9, 1))
    _sinal(trt8, "banca_contratada", date(2026, 10, 1), url=PNCP)
    chamada = radar.aplicar(trt8)
    html = client.get(chamada.url).content.decode()
    assert "Nota 7 de 7" in html and "Banca contratada" in html
    assert "Edital esperado entre" in html and "janeiro de 2027" in html and "fevereiro de 2027" in html
    assert html.count("documento oficial") >= 2 and PNCP in html
    inicio = client.get("/").content.decode()
    assert "No radar" in inicio and "TRT-8 2027" in inicio      # contratada em out/26: edital em 2027
