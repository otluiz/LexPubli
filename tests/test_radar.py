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


# --- ADR-0013 D2: só junta o que é do mesmo processo ---------------------------------
A, B = "02390435000115-1-000021/2026", "02390435000115-1-000099/2026"


def test_mesmo_processo_vai_para_a_pagina_e_outro_processo_fica_solto(trt8):
    _sinal(trt8, "banca_contratada", date(2026, 9, 1), url=PNCP, processo_pncp=A)
    chamada = radar.aplicar(trt8)
    mesmo = _sinal(trt8, "licitacao_banca", date(2026, 8, 1), url=PNCP + "/l", processo_pncp=A)
    outro = _sinal(trt8, "banca_contratada", date(2026, 11, 1), url=PNCP + "/b", processo_pncp=B)
    radar.aplicar(trt8)
    mesmo.refresh_from_db(), outro.refresh_from_db()
    assert mesmo.concurso_id == chamada.pk and outro.concurso_id is None
    assert ConcursoPage.objects.filter(orgao=trt8).count() == 1      # não cria outra página sozinho
    assert radar.sinais_de_outro_processo() == [outro]


def test_sem_processo_so_junta_quando_o_orgao_tem_uma_pagina(trt8, exemplo):
    _sinal(trt8, "autorizacao", date(2026, 9, 1), processo_pncp=A)
    radar.aplicar(trt8)
    um = _sinal(trt8, "comissao", date(2026, 9, 20), url=DOU + "/c")
    radar.aplicar(trt8)
    um.refresh_from_db()
    assert um.concurso_id is not None                                 # uma página só: sem dúvida
    indice = exemplo["concurso"].get_parent().specific
    indice.add_child(instance=ConcursoPage(title="TRT-8 2027: outro", orgao=trt8, ano=2027,
                                           status=StatusConcurso.PREVISTO, fonte_url=DOU))
    dois = _sinal(trt8, "comissao", date(2026, 10, 20), url=DOU + "/d")
    radar.aplicar(trt8)
    dois.refresh_from_db()
    assert dois.concurso_id is None and dois in radar.sinais_de_outro_processo()


def test_pagina_nova_leva_o_processo_mais_forte_e_deixa_o_outro_solto(trt8):
    forte = _sinal(trt8, "banca_contratada", date(2026, 9, 1), url=PNCP, processo_pncp=A)
    sem = _sinal(trt8, "autorizacao", date(2026, 6, 1))
    outro = _sinal(trt8, "licitacao_banca", date(2026, 10, 1), url=PNCP + "/l", processo_pncp=B)
    chamada = radar.aplicar(trt8)
    for s in (forte, sem, outro):
        s.refresh_from_db()
    assert forte.concurso_id == sem.concurso_id == chamada.pk and outro.concurso_id is None


def test_curador_liga_um_sinal_e_o_resto_do_processo_vai_junto(trt8, exemplo):
    _sinal(trt8, "banca_contratada", date(2026, 9, 1), url=PNCP, processo_pncp=A)
    radar.aplicar(trt8)
    indice = exemplo["concurso"].get_parent().specific
    novo = ConcursoPage(title="TRT-8 2027 — nível superior", orgao=trt8, ano=2027,
                        status=StatusConcurso.PREVISTO, fonte_url=DOU)
    indice.add_child(instance=novo)
    b1 = _sinal(trt8, "licitacao_banca", date(2026, 10, 1), url=PNCP + "/l", processo_pncp=B)
    b2 = _sinal(trt8, "banca_contratada", date(2026, 11, 1), url=PNCP + "/b", processo_pncp=B)
    b1.concurso = novo
    b1.save()                                    # o que o curador faz no admin
    radar.aplicar(trt8)
    b2.refresh_from_db(), novo.refresh_from_db()
    assert b2.concurso_id == novo.pk and novo.status == StatusConcurso.AUTORIZADO


def test_painel_do_admin_lista_o_sinal_solto(admin_client, trt8):
    _sinal(trt8, "banca_contratada", date(2026, 9, 1), url=PNCP, processo_pncp=A)
    radar.aplicar(trt8)
    _sinal(trt8, "banca_contratada", date(2026, 11, 1), url=PNCP + "/b", processo_pncp=B)
    radar.aplicar(trt8)
    html = admin_client.get("/painel/").content.decode()
    assert "Sinal de outro processo do mesmo órgão (1)" in html and B in html


# --- ADR-0013 D3: ordem do procedimento e o rótulo de cada data -----------------------

def test_no_mesmo_processo_a_licitacao_vem_antes_do_contrato(trt8):
    """O caso da PCAC: contrato assinado em 22/10, licitação publicada no PNCP
    em 06/11. As datas são de naturezas diferentes; vale a ordem do procedimento."""
    contrato = _sinal(trt8, "banca_contratada", date(2026, 10, 22), url=PNCP, processo_pncp=A,
                      origem=Sinal.Origem.PNCP)
    licitacao = _sinal(trt8, "licitacao_banca", date(2026, 11, 6), url=PNCP + "/l", processo_pncp=A,
                       origem=Sinal.Origem.PNCP)
    autorizacao = _sinal(trt8, "autorizacao", date(2026, 6, 1))
    outro = _sinal(trt8, "licitacao_banca", date(2026, 9, 1), url=PNCP + "/b", processo_pncp=B,
                   origem=Sinal.Origem.PNCP)
    assert radar.em_ordem([contrato, outro, licitacao, autorizacao]) == [autorizacao, outro, licitacao, contrato]


def test_cada_data_diz_o_que_e(client, trt8):
    _sinal(trt8, "autorizacao", date(2026, 6, 1), origem=Sinal.Origem.DOU)
    _sinal(trt8, "banca_contratada", date(2026, 10, 22), url=PNCP, processo_pncp=A, origem=Sinal.Origem.PNCP)
    _sinal(trt8, "licitacao_banca", date(2026, 11, 6), url=PNCP + "/l", processo_pncp=A, origem=Sinal.Origem.PNCP)
    html = client.get(radar.aplicar(trt8).url).content.decode()
    assert "publicado no DOU em" in html and "assinado em" in html and "publicado no PNCP em" in html
    assert html.index("Licitação ou aviso de contratação da banca</strong>") < html.index("Banca contratada</strong>")
