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

def test_pagina_inicial_explica_o_portal_e_agrupa_por_fase(client, exemplo):
    html = client.get("/").content.decode()
    assert "Saiba do concurso antes do edital." in html
    assert "Inscrições abertas" in html and "sefaz-al-2026" in html     # o exemplo tem edital aberto
    assert "No radar" not in html                                       # grupo vazio não aparece
    assert "fontes oficiais acompanhadas" in html


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
    assert 'href="https://app.lexlearn.exemplo"' in inicio and "Conhecer o LexLearn" in inicio
    assert "Vai prestar Sefaz-AL 2026" in concurso and "da Cebraspe" in concurso
    assert 'href="https://app.lexlearn.exemplo"' in concurso


def test_sem_url_do_lexlearn_a_chamada_fica_sem_botao(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = ""
    html = client.get("/").content.decode()
    assert "estude com o LexLearn" in html and "Conhecer o LexLearn" not in html
