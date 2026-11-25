"""Prefeituras na trilha fiscal e jurídica (ADR-0012 D2): "ISS Jaboatão"."""
import pytest

from concursos import orgaos, pistas, pncp
from concursos.models import Fonte, Orgao, Pista

JABOATAO, CARUARU = "MUN2607901", "MUN2604106"


@pytest.mark.parametrize("texto,esperado", [
    ("Concurso ISS Jaboatão: edital publicado", [JABOATAO]),           # apelido do catálogo
    ("Concurso Prefeitura de Jaboatão dos Guararapes: auditor fiscal", [JABOATAO]),
    ("Concurso ISS Caruaru: prova em 29/11", [CARUARU]),
    ("Concurso procurador do município de Natal", ["MUN2408102"]),      # trilha jurídica
    ("Concurso Sefin Fortaleza: auditor do tesouro municipal", ["MUN2304400"]),   # Tesouro (MT) não
    ("Concurso ISS São José dos Campos e ISS Campinas", ["MUN3549904", "MUN3509502"]),
    ("Concurso para auditor fiscal do município de Serra (ES)", ["MUN3205002"]),
    ("Concurso ISS Bom Jesus - PI: auditor", ["MUN2201903"]),           # nome repetido: a UF decide
    ("Concurso ISS Bom Jesus", []),                                     # sem UF: o curador decide
    ("Concurso Prefeitura de Natal: guarda municipal", []),             # fora das trilhas
    ("Concurso Sefaz de São Paulo: auditor fiscal", []),                # estadual, não a prefeitura
    ("Concurso Receita Federal: FGV é a banca", ["RFB"]),
])
def test_reconhece_a_prefeitura_da_trilha_fiscal_e_juridica(texto, esperado):
    assert orgaos.chaves(texto) == esperado


def test_nome_e_esfera_da_prefeitura():
    assert orgaos.nome_e_esfera(JABOATAO) == ("Prefeitura de Jaboatão dos Guararapes", "municipal")


@pytest.fixture
def gran(db):
    return Fonte.objects.create(nome="Gran — blog", tipo=Fonte.Tipo.PISTA, esfera="federal",
                                url="https://blog.grancursosonline.com.br/feed/",
                                changedetection_uuid="aaaaaaaa-1111-4222-8333-444444444444")


def test_pista_cria_a_prefeitura_com_o_cnpj_do_catalogo(gran):
    assert pistas.registrar(gran, "(added) Concurso ISS Jaboatão: edital previsto https://x.com.br/j") == 1
    p = Pista.objects.get()
    assert p.chave_orgao == JABOATAO and p.status == Pista.Status.A_BUSCAR
    o = p.orgao
    assert (o.nome, o.esfera, o.uf, o.codigo_ibge, o.cnpj) == \
        ("Prefeitura de Jaboatão dos Guararapes", "municipal", "PE", "2607901", "10377679000196")
    assert orgaos.cnpj_para_pncp(o) == "10377679000196"       # a busca oficial vai ao PNCP da prefeitura
    # de novo: a mesma prefeitura, não outra
    assert orgaos.orgao_da_chave(JABOATAO, criar=True).pk == o.pk


def test_prefeitura_criada_pelo_pncp_e_reaproveitada_e_a_camara_nao(gran):
    camara = Orgao.objects.create(nome="Câmara Municipal de Caruaru", esfera="municipal", uf="PE",
                                  codigo_ibge="2604106", cnpj="11111111000111")
    pref = Orgao.objects.create(nome="Prefeitura de Caruaru", esfera="municipal", uf="PE",
                                codigo_ibge="2604106", cnpj="10091536000113")
    assert orgaos.orgao_da_chave(CARUARU, criar=True).pk == pref.pk != camara.pk


def test_pncp_adota_a_prefeitura_que_a_pista_criou_sem_cnpj(gran):
    # Salvador: no catálogo, mas sem CNPJ (o PNCP a registra com outro nome)
    pref = orgaos.orgao_da_chave("MUN2927408", criar=True)
    assert pref.cnpj == ""
    a = pncp.Achado("licitacao_banca", "13927801000149", "MUNICIPIO DO SALVADOR", "M", "BA",
                    "concurso público para auditor fiscal de tributos municipal", None,
                    "https://pncp.gov.br/app/editais/13927801000149/2026/1", municipio="Salvador",
                    ibge="2927408", unidade="SECRETARIA DA FAZENDA")
    assert pncp.orgao_do_achado(a, pncp.Relatorio()).pk == pref.pk
    pref.refresh_from_db()
    assert pref.cnpj == "13927801000149" and Orgao.objects.filter(codigo_ibge="2927408").count() == 1
