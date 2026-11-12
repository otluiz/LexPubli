"""Caderno do PNCP (ADR-0012): leitura retroativa com ponto de retomada, e a
medição por trilha de carreira sobre o que foi guardado."""
import io
from datetime import date

import pytest
from django.core.management import call_command

from concursos import pncp
from concursos.trilhas import trilhas
from tests.test_pncp import PncpFalso, contrato

HOJE = date(2026, 10, 13)


def _municipal(**kw):
    x = contrato(cnpj="10091536000108", razao="MUNICIPIO DE CARUARU", esfera="M", seq=99, **kw)
    x["unidadeOrgao"] = {"ufSigla": "PE", "municipioNome": "Caruaru", "codigoIbge": "2604106",
                         "nomeUnidade": "SECRETARIA DA FAZENDA MUNICIPAL"}
    x["nomeRazaoSocialFornecedor"] = "IBAM"
    return x


def test_dia_lido_vai_ao_caderno_e_nao_e_pedido_de_novo(db, exemplo):
    falso = PncpFalso(contratos=[contrato()])
    pncp.coletar(dias=1, hoje=HOJE, get=falso, pausa=0)
    assert pncp.dias_do_caderno() == [date(2026, 10, 12)]
    pedidos = len(falso.chamadas)

    rel = pncp.coletar(dias=1, hoje=HOJE, get=falso, pausa=0)
    assert len(falso.chamadas) == pedidos                  # nada pedido de novo
    assert rel.dias_do_caderno == 1 and rel.dias_lidos == 0
    assert rel.ja_vistos == 1                               # o sinal não duplica


def test_leitura_retroativa_respeita_o_limite_e_continua_na_rodada_seguinte(db, exemplo):
    falso = PncpFalso()
    rel = pncp.coletar(desde=date(2026, 10, 10), limite_dias=1, hoje=HOJE, get=falso, pausa=0)
    assert pncp.dias_do_caderno() == [date(2026, 10, 12)]   # ontem primeiro
    assert rel.dias_pendentes == 2
    rel = pncp.coletar(desde=date(2026, 10, 10), limite_dias=1, hoje=HOJE, get=falso, pausa=0)
    assert pncp.dias_do_caderno() == [date(2026, 10, 11), date(2026, 10, 12)]
    assert (rel.dias_lidos, rel.dias_do_caderno, rel.dias_pendentes) == (1, 1, 1)


def test_dia_interrompido_nao_entra_no_caderno(db, exemplo):
    falso = PncpFalso(contratos=[contrato()], recusar_em=2)
    rel = pncp.coletar(dias=1, hoje=HOJE, get=falso, pausa=0)
    assert rel.erro and rel.dias_pendentes == 1
    assert pncp.dias_do_caderno() == []                     # a próxima rodada lê o dia inteiro
    assert len(rel.sinais) == 1                             # mas o sinal já lido ficou


def test_municipal_fica_no_caderno_mas_nao_vira_sinal(db, exemplo):
    from concursos.models import Sinal

    pncp.coletar(dias=1, hoje=HOJE, get=PncpFalso(contratos=[_municipal()]), pausa=0)
    [a] = pncp.ler_caderno(date(2026, 10, 12))
    assert (a.municipio, a.ibge, a.unidade, a.fornecedor) == (
        "Caruaru", "2604106", "SECRETARIA DA FAZENDA MUNICIPAL", "IBAM")
    assert not Sinal.objects.filter(orgao__cnpj="10091536000108").exists()


@pytest.mark.parametrize("razao, unidade, objeto, esperado", [
    ("INSTITUTO FEDERAL DE EDUCACAO, CIENCIA E TECNOLOGIA DE SERGIPE", "", "", ["rede_federal"]),
    ("CENTRO FEDERAL DE EDUCACAO TECNOLOGICA DE MINAS GERAIS", "", "", ["rede_federal"]),
    ("COLEGIO PEDRO II", "", "", ["rede_federal"]),
    ("UNIVERSIDADE FEDERAL DE PERNAMBUCO", "", "", ["universidade_federal"]),
    ("MUNICIPIO DE CARUARU", "SECRETARIA DA FAZENDA MUNICIPAL", "", ["fiscal_controle"]),
    ("MUNICIPIO DE MARINGA", "", "concurso para Auditor Fiscal de Tributos", ["fiscal_controle"]),
    ("TRIBUNAL DE CONTAS DO ESTADO DE PERNAMBUCO", "", "", ["fiscal_controle"]),
    ("CONTROLADORIA-GERAL DO MUNICIPIO DE SAO PAULO", "", "", ["fiscal_controle"]),
    ("MUNICIPIO DE OLINDA", "SECRETARIA DE SAUDE", "provimento de cargos diversos", []),
])
def test_trilhas(razao, unidade, objeto, esperado):
    assert trilhas(razao, unidade, objeto) == esperado


def test_medir_escopo_conta_por_trilha_sem_pedir_nada(db, exemplo):
    pncp.coletar(dias=1, hoje=HOJE, get=PncpFalso(contratos=[contrato(), _municipal()]), pausa=0)
    saida = io.StringIO()
    call_command("medir_escopo", "--listar", "fiscal_controle", stdout=saida)
    texto = saida.getvalue()
    assert "2 publicação(ões) de concurso público" in texto
    assert "Entram hoje: 1. A ADR-0012 acrescentaria 1 municipal(is)" in texto
    assert "MUNICIPIO DE CARUARU · Caruaru-PE" in texto and "banca: IBAM" in texto


def test_medir_escopo_com_caderno_vazio(db):
    saida = io.StringIO()
    call_command("medir_escopo", stdout=saida)
    assert "Caderno vazio" in saida.getvalue()
