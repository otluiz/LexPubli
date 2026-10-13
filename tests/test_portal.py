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
