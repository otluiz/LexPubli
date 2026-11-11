import json
import re


def test_pagina_do_concurso(client, exemplo):
    r = client.get("/sefaz-al-2026/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Auditor Fiscal da Administração Tributária Estadual" in html
    assert "R$ 25.270,68" in html
    bloco = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
    ld = json.loads(bloco)
    posto = ld["@graph"][0]
    assert posto["@type"] == "JobPosting"
    assert posto["totalJobOpenings"] == 40
    assert posto["baseSalary"]["value"]["value"] == 25270.68


def test_indice_lista_o_concurso(client, exemplo):
    html = client.get("/").content.decode()
    assert "Sefaz-AL 2026" in html and "40 vagas" in html


def test_sitemap_e_robots(client, exemplo):
    assert "/sefaz-al-2026/" in client.get("/sitemap.xml").content.decode()
    robots = client.get("/robots.txt").content.decode()
    assert "Disallow: /painel/" in robots and "Sitemap:" in robots


def test_csp_no_site_publico_e_nao_no_painel(client, exemplo):
    assert "script-src 'none'" in client.get("/sefaz-al-2026/")["Content-Security-Policy"]
    assert "Content-Security-Policy" not in client.get("/painel/login/")


def test_admin_fora_da_url_padrao(client, exemplo):
    assert client.get("/admin/").status_code == 404
    assert client.get("/painel/").status_code == 302  # pede login


def test_carregar_exemplo_e_idempotente(exemplo):
    from django.core.management import call_command
    from concursos.models import ConcursoPage, Descoberta

    call_command("carregar_exemplo", stdout=open("/dev/null", "w"))
    assert ConcursoPage.objects.count() == 1
    assert Descoberta.objects.count() == 1


# --- página inicial e chamada ao LexLearn -------------------------------------

def _datas(concurso, inicio=None, fim=None, prova=None):
    """Move as datas do concurso em relação a hoje (dias) e republica."""
    import datetime as dt
    from django.utils import timezone

    hoje = timezone.localdate()
    concurso.inscricoes_inicio = hoje + dt.timedelta(days=inicio) if inicio is not None else None
    concurso.inscricoes_fim = hoje + dt.timedelta(days=fim) if fim is not None else None
    concurso.data_prova = hoje + dt.timedelta(days=prova) if prova is not None else None
    concurso.save_revision().publish()


def test_pagina_inicial_explica_o_portal_e_agrupa_por_fase(client, exemplo):
    _datas(exemplo["concurso"], inicio=-10, fim=10)
    html = client.get("/").content.decode()
    assert "antes do edital" in html
    assert "Inscrições abertas" in html and "sefaz-al-2026" in html
    assert "No radar:" not in html                                      # grupo vazio não aparece
    assert "fontes oficiais acompanhadas" in html


# --- situação segue a data, não o status gravado ------------------------------
# O exemplo tem status "edital aberto" gravado. Em 11/11 o portal mostrava o
# selo vazio e o Sefaz-AL em "Inscrições abertas" com inscrições encerradas
# em 21/10: as propriedades usadas pelos templates não existiam, e o Django
# renderiza atributo inexistente como texto vazio, sem erro.

def test_inscricoes_encerradas_vencem_o_status_gravado(client, exemplo):
    _datas(exemplo["concurso"], inicio=-40, fim=-5)
    c = exemplo["concurso"]
    assert c.situacao == "Inscrições encerradas"
    assert c.prazo_inscricoes.startswith("inscrições encerradas em ")
    home = client.get("/").content.decode()
    assert "Edital aberto" not in home and "Inscrições abertas" not in home
    assert "Em andamento" in home
    assert "Inscrições encerradas" in client.get("/sefaz-al-2026/").content.decode()


def test_cada_fase_da_data_tem_rotulo_e_prazo(exemplo):
    c = exemplo["concurso"]
    casos = [
        (dict(inicio=-3, fim=7), "Inscrições abertas", "inscrições até "),
        (dict(inicio=5, fim=20), "Inscrições em breve", "inscrições a partir de "),
        (dict(inicio=-60, fim=-30, prova=-2), "Prova realizada", "inscrições encerradas em "),
        (dict(), "Edital aberto", ""),                    # sem data: cai no status gravado
    ]
    for datas, rotulo, prazo in casos:
        _datas(c, **datas)
        assert c.situacao == rotulo, datas
        assert c.prazo_inscricoes.startswith(prazo) and bool(c.prazo_inscricoes) == bool(prazo), datas


def test_selo_nunca_sai_vazio(client, exemplo):
    import re

    for datas in (dict(inicio=-3, fim=7), dict(inicio=-40, fim=-5), dict()):
        _datas(exemplo["concurso"], **datas)
        for url in ("/", "/sefaz-al-2026/"):
            html = client.get(url).content.decode()
            assert not re.search(r'class="selo selo-[^"]*">\s*<', html), (url, datas)


def test_so_conta_fonte_com_watch(client, exemplo):
    from concursos.models import Fonte

    Fonte.objects.create(nome="STJ", poder="judiciario", esfera="federal", ativa=True,
                         url="https://www.stj.jus.br/c", conferida_em="2026-10-13")
    Fonte.objects.create(nome="TST", poder="judiciario", esfera="federal", ativa=True,
                         url="https://www.tst.jus.br/c", conferida_em="2026-10-13",
                         changedetection_uuid="u-1")
    assert "<strong>1</strong><span>fontes oficiais acompanhadas" in client.get("/").content.decode()


def test_chamada_ao_lexlearn_em_todas_as_paginas(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = "https://app.lexlearn.exemplo"
    inicio = client.get("/").content.decode()
    concurso = client.get("/sefaz-al-2026/").content.decode()
    assert 'href="https://app.lexlearn.exemplo"' in inicio and "Começar a estudar" in inicio
    assert "Vai prestar Sefaz-AL 2026" in concurso and "da Cebraspe" in concurso
    assert 'href="https://app.lexlearn.exemplo"' in concurso


def test_sem_url_do_lexlearn_a_chamada_fica_sem_botao(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = ""
    html = client.get("/").content.decode()
    assert "estude com o LexLearn" in html and "Começar a estudar" not in html


def test_nenhum_comentario_de_template_vaza_para_a_pagina(client, exemplo, settings):
    """`{# #}` do Django e de UMA linha; em varias ele nao comenta — vira texto
    na pagina. Em 10/11 isso expunha ao visitante as notas de arquitetura
    (ADR-0005, tabnabbing, "produto pago") em todas as paginas do portal.
    Comentario de varias linhas usa a tag comment."""
    settings.LEXPUBLI_LEXLEARN_URL = "https://app.lexlearn.exemplo"
    for url in ("/", "/sefaz-al-2026/"):
        corpo = client.get(url).content.decode()
        assert "{#" not in corpo and "#}" not in corpo, f"comentario vazou em {url}"
        assert "ADR-" not in corpo, f"nota de arquitetura vazou em {url}"
