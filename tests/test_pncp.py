"""Coletor do PNCP (ADR-0008 §4), com respostas no formato real da API."""
from datetime import date

import pytest

from concursos import pncp
from concursos.models import ConcursoPage, Orgao, Sinal

OBJ = ("Contratação de instituição especializada para o planejamento, a organização e a execução de "
       "concurso público para provimento de cargos de Analista e Técnico Judiciário")


def contrato(cnpj="02390435000115", razao="TRIBUNAL REGIONAL DO TRABALHO DA 8A REGIAO", esfera="F",
             objeto=OBJ, seq=7, assinatura="2026-10-12"):
    return {"orgaoEntidade": {"cnpj": cnpj, "razaoSocial": razao, "esferaId": esfera, "poderId": "J"},
            "unidadeOrgao": {"ufSigla": "PA"}, "objetoContrato": objeto, "anoContrato": 2026,
            "sequencialContrato": seq, "dataAssinatura": assinatura,
            "dataPublicacaoPncp": "2026-10-12T10:00:00", "nomeRazaoSocialFornecedor": "CEBRASPE"}


def contratacao(cnpj="02390435000115", objeto=OBJ, esfera="F", seq=21):
    return {"orgaoEntidade": {"cnpj": cnpj, "razaoSocial": "TRIBUNAL REGIONAL DO TRABALHO DA 8A REGIAO",
                              "esferaId": esfera, "poderId": "J"},
            "unidadeOrgao": {"ufSigla": "PA"}, "objetoCompra": objeto, "anoCompra": 2026,
            "sequencialCompra": seq, "dataPublicacaoPncp": "2026-10-12T09:00:00"}


class PncpFalso:
    def __init__(self, contratos=(), contratacoes=(), recusar_em=None):
        self.contratos, self.contratacoes, self.recusar_em = list(contratos), list(contratacoes), recusar_em
        self.chamadas = []

    def __call__(self, caminho, params):
        self.chamadas.append((caminho, dict(params)))
        if self.recusar_em and len(self.chamadas) >= self.recusar_em:
            raise pncp.ErroPncp("conexão fechada")
        if caminho == "/contratos":
            return {"data": self.contratos, "totalPaginas": 1}
        dados = self.contratacoes if params["codigoModalidadeContratacao"] == 8 else []
        return {"data": dados, "totalPaginas": 1}


@pytest.mark.parametrize("objeto,sim", [
    (OBJ, True),
    ("CONTRATAÇÃO DE EMPRESA PARA ORGANIZAÇÃO DE CONCURSO PÚBLICO DESTINADO AO PROVIMENTO DE CARGOS", True),
    ("Concurso público nacional de projetos de arquitetura para a nova sede", False),
    ("Aquisição de gêneros alimentícios", False),
    ("Premiação do concurso público de fotografia", False),
])
def test_objeto_de_concurso_publico(objeto, sim):
    assert pncp.e_concurso_publico(objeto) is sim


def test_contrato_e_contratacao_viram_sinais_e_publicam_a_chamada(db, exemplo):
    falso = PncpFalso(contratos=[contrato()], contratacoes=[contratacao()])
    rel = pncp.coletar(dias=1, hoje=date(2026, 10, 13), get=falso, pausa=0)
    orgao = Orgao.objects.get(cnpj="02390435000115")
    assert orgao.nome == "Tribunal Regional do Trabalho da 8ª Regiao" and orgao.esfera == "federal"
    tipos = set(orgao.sinais.values_list("tipo", flat=True))
    assert tipos == {"banca_contratada", "licitacao_banca"}
    s7 = orgao.sinais.get(tipo="banca_contratada")
    assert s7.documento_url == "https://pncp.gov.br/app/contratos/02390435000115/2026/7"
    assert "Contratada: CEBRASPE." in s7.resumo and s7.origem == "pncp" and not s7.revisado
    s7.full_clean()                                        # o PNCP é domínio oficial
    chamada = ConcursoPage.objects.get(orgao=orgao)
    assert chamada.live and rel.chamadas == [chamada.title]
    # consultou o dia de ontem nas três consultas
    assert {c[0] for c in falso.chamadas} == {"/contratos", "/contratacoes/publicacao"}
    assert all(c[1]["dataInicial"] == "20261012" for c in falso.chamadas)


def test_rodar_de_novo_nao_duplica(db, exemplo):
    falso = PncpFalso(contratos=[contrato()])
    pncp.coletar(hoje=date(2026, 10, 13), get=falso, pausa=0)
    rel = pncp.coletar(hoje=date(2026, 10, 13), get=falso, pausa=0)
    assert rel.ja_vistos == 1 and not rel.sinais and Sinal.objects.count() == 1


def test_municipal_e_objeto_estranho_ficam_fora(db, exemplo):
    falso = PncpFalso(contratos=[contrato(esfera="M", cnpj="1"),
                                 contrato(objeto="Aquisição de gêneros alimentícios", seq=8)])
    rel = pncp.coletar(hoje=date(2026, 10, 13), get=falso, pausa=0)
    assert rel.municipais == 1 and rel.lidos == 2 and not Sinal.objects.exists()


def test_orgao_ja_cadastrado_e_reusado_pelo_cnpj(db, exemplo):
    trt8 = Orgao.objects.create(nome="TRT da 8ª Região", sigla="TRT-8", esfera="federal",
                                cnpj="02390435000115")
    pncp.coletar(hoje=date(2026, 10, 13), get=PncpFalso(contratos=[contrato()]), pausa=0)
    assert Orgao.objects.filter(cnpj="02390435000115").count() == 1
    assert trt8.sinais.count() == 1


def test_recusa_do_pncp_para_a_rodada_e_guarda_o_que_ja_leu(db, exemplo):
    falso = PncpFalso(contratos=[contrato()], recusar_em=2)
    rel = pncp.coletar(hoje=date(2026, 10, 13), get=falso, pausa=0)
    assert "conexão fechada" in rel.erro and len(rel.sinais) == 1
    assert rel.chamadas                                    # o que já leu é publicado


def test_paginacao_segue_ate_a_ultima_pagina():
    paginas = []

    def get(caminho, params):
        paginas.append((caminho, params["pagina"]))
        return {"data": [], "totalPaginas": 3 if caminho == "/contratos" else 1}

    list(pncp.publicacoes(date(2026, 10, 12), get=get, pausa=0))
    assert [p for c, p in paginas if c == "/contratos"] == [1, 2, 3]
