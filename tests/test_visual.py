"""SPEC-0003 — visual do portal e radar vivo. Um teste por critério de aceite.

O critério 7 (nada transborda em 360px) precisa de navegador e não roda
aqui: confere-se com o Chrome em 360px de largura, scrollWidth == 360.
"""
import datetime as dt
import re
from pathlib import Path

import pytest
from django.utils import timezone

CSS = (Path(__file__).resolve().parent.parent / "concursos/static/concursos/site.css").read_text()


def _publicar(indice, slug, titulo, dias_atras, sigla=""):
    from decimal import Decimal

    from concursos.models import Cargo, ConcursoPage, Orgao

    orgao, _ = Orgao.objects.get_or_create(slug=slug.replace("-", "_"),
                                           defaults={"nome": titulo, "sigla": sigla, "esfera": "estadual"})
    c = ConcursoPage(title=titulo, slug=slug, orgao=orgao, ano=2027, status="previsto",
                     fonte_url="https://www.ac.gov.br/concurso")
    c.cargos.add(Cargo(nome="Analista", vagas=10, salario=Decimal("9000")))
    indice.add_child(instance=c)
    c.save_revision().publish()
    ConcursoPage.objects.filter(pk=c.pk).update(
        first_published_at=timezone.now() - dt.timedelta(days=dias_atras))
    return c


def _pontos(html):
    radar = re.search(r'<figure class="radar-vivo">(.*?)</figure>', html, re.S).group(1)
    return re.findall(r'<a class="ponto[^"]*" href="([^"]+)"', radar)


# 1 ------------------------------------------------------------------------
def test_nenhuma_requisicao_a_terceiros(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = "https://app.lexlearn.exemplo"
    for url in ("/", "/sefaz-al-2026/"):
        r = client.get(url)
        html = r.content.decode()
        # o que o navegador busca sozinho: link, script, img, source, iframe
        recursos = re.findall(r'<(?:link|script|img|source|iframe)\b[^>]*\b(?:href|src)="([^"]+)"', html)
        # o canonical aponta para o próprio portal e não é baixado
        externos = [u for u in recursos if re.match(r"(https?:)?//", u) and "//testserver/" not in u]
        assert recursos and not externos, (url, externos)
        assert "http" not in r["Content-Security-Policy"]
    assert not re.search(r"@import|url\(\s*[\"']?(https?:)?//", CSS)


def test_fontes_estao_no_repositorio():
    base = Path(__file__).resolve().parent.parent / "concursos/static/concursos"
    for arquivo in re.findall(r'url\("(fontes/[^"]+)"\)', CSS):
        assert (base / arquivo).stat().st_size > 10_000, arquivo
    assert (base / "fontes/OFL-Fraunces.txt").exists() and (base / "fontes/OFL-Inter.txt").exists()


# 2 ------------------------------------------------------------------------
def test_radar_mostra_um_ponto_por_concurso_publicado(client, exemplo):
    from concursos.models import ConcursosIndexPage

    indice = ConcursosIndexPage.objects.get()
    _publicar(indice, "acre-2027", "Estado do Acre 2027", 3, sigla="AC")
    _publicar(indice, "seap-2027", "Seap 2027", 40)
    pontos = _pontos(client.get("/").content.decode())
    assert len(pontos) == 3
    assert {"/sefaz-al-2026/", "/acre-2027/", "/seap-2027/"} == set(pontos)


def test_ponto_fica_no_estado_do_orgao_e_o_mais_recente_ganha_rotulo(exemplo):
    from concursos.models import ConcursoPage, ConcursosIndexPage, Orgao
    from concursos.radar_vivo import NACIONAL, _mapa, pontos

    indice = ConcursosIndexPage.objects.get()
    ConcursoPage.objects.update(first_published_at=timezone.now() - dt.timedelta(days=30))
    acre = _publicar(indice, "acre-2027", "Estado do Acre 2027", 2, sigla="AC")
    Orgao.objects.filter(pk=acre.orgao_id).update(uf="AC")
    bacen = _publicar(indice, "bacen-2027", "Banco Central 2027", 60)
    Orgao.objects.filter(pk=bacen.orgao_id).update(esfera="federal", uf="DF")
    todos = pontos(ConcursoPage.objects.live().select_related("orgao"))
    ps = {p.concurso.slug: p for p in todos}
    assert (ps["acre-2027"].x, ps["acre-2027"].y) == (_mapa()["AC"]["x"], _mapa()["AC"]["y"])
    assert (ps["bacen-2027"].x, ps["bacen-2027"].y) == NACIONAL      # federal no DF é nacional
    assert ps["acre-2027"].recente and not ps["bacen-2027"].recente
    assert todos[0].concurso.slug == "acre-2027" and todos[0].texto_rotulo == "AC 2027"


def test_varios_no_mesmo_estado_nao_ficam_um_em_cima_do_outro(exemplo):
    from concursos.models import ConcursoPage, ConcursosIndexPage, Orgao
    from concursos.radar_vivo import pontos

    indice = ConcursosIndexPage.objects.get()
    for i in range(6):
        c = _publicar(indice, f"pr-{i}", f"Órgão {i} do Paraná", i)
        Orgao.objects.filter(pk=c.orgao_id).update(uf="PR")
    ps = [p for p in pontos(ConcursoPage.objects.live().select_related("orgao"))
          if p.concurso.slug.startswith("pr-")]
    distancias = [((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** .5 for i, a in enumerate(ps) for b in ps[i + 1:]]
    assert len(ps) == 6 and min(distancias) >= 3.4     # o núcleo tem raio 2,4: não se sobrepõem


def test_lugar_do_orgao():
    from concursos.models import Orgao

    def lugar(esfera, uf, nome="Órgão"):
        return Orgao(nome=nome, esfera=esfera, uf=uf).lugar
    assert lugar("estadual", "PE") == "PE"
    assert lugar("federal", "MS", "Conselho Regional de Medicina Veterinária do MS") == "MS"
    assert lugar("federal", "DF", "Banco Central do Brasil") == "BR"
    assert lugar("federal", "DF", "Conselho Regional de Medicina do Distrito Federal") == "DF"
    assert lugar("federal", "") == "BR"


def test_clicar_no_estado_filtra_a_lista_e_agrupa_por_estado(client, exemplo):
    from concursos.models import ConcursosIndexPage, Orgao

    indice = ConcursosIndexPage.objects.get()
    c = _publicar(indice, "seap-2027", "Seap 2027", 4)
    Orgao.objects.filter(pk=c.orgao_id).update(uf="PR")
    html = client.get("/").content.decode()
    assert 'href="?uf=PR#concursos"' in html and 'href="?uf=AL#concursos"' in html
    assert '<h3 class="lugar">Alagoas</h3>' in html and '<h3 class="lugar">Paraná</h3>' in html
    filtrado = client.get("/?uf=pr").content.decode()
    lista = filtrado[filtrado.index('id="concursos"'):]
    assert "Seap 2027" in lista and "Sefaz-AL" not in lista
    assert "Mostrando os concursos de <strong>Paraná</strong>" in filtrado
    assert "Sefaz-AL" in client.get("/?uf=XX").content.decode()        # UF sem concurso: lista inteira


def test_estados_por_regiao_nacional_primeiro():
    from types import SimpleNamespace as N

    from concursos.models import _por_lugar

    def c(uf):
        return N(orgao=N(lugar=uf))
    assert [lugar for lugar, _ in _por_lugar([c("RS"), c("PE"), c("BR"), c("AM"), c("SP")])] == \
        ["Nacional", "Amazonas", "Pernambuco", "São Paulo", "Rio Grande do Sul"]


def test_concurso_antigo_sai_do_radar_mas_fica_na_lista(client, exemplo):
    from concursos.models import ConcursoPage

    ConcursoPage.objects.update(first_published_at=timezone.now() - dt.timedelta(days=200))
    html = client.get("/").content.decode()
    assert _pontos(html) == []
    assert "sefaz-al-2026" in html


# 3 ------------------------------------------------------------------------
@pytest.mark.django_db
def test_sem_concursos_a_home_renderiza_e_o_radar_gira_vazio(client):
    from django.core.management import call_command

    from concursos.models import ConcursoPage

    call_command("carregar_exemplo", stdout=open("/dev/null", "w"))
    for c in ConcursoPage.objects.all():
        c.unpublish()
    r = client.get("/")
    html = r.content.decode()
    assert r.status_code == 200
    assert _pontos(html) == []
    assert "Nenhum concurso novo" in html and "Nenhum concurso publicado ainda." in html


# 4 ------------------------------------------------------------------------
def test_movimento_reduzido_desliga_toda_animacao():
    bloco = CSS[CSS.rindex("@media (prefers-reduced-motion: reduce)"):]
    assert re.search(r"\*,\s*\*::before,\s*\*::after\s*\{\s*animation:\s*none !important", bloco)
    assert re.search(r"\.varredor\s*\{\s*display:\s*none", bloco)
    # parado, o ponto fica no estado de base, que é visível
    assert not re.search(r"\.(nucleo|halo)[^{]*\{[^}]*opacity:\s*0[;\s}]", CSS)


# 5 ------------------------------------------------------------------------
def _tokens(bloco):
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", bloco))


def _contraste(a, b):
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
        return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]
    claro, escuro = sorted([lum(a), lum(b)], reverse=True)
    return (claro + .05) / (escuro + .05)


@pytest.mark.parametrize("tema", ["claro", "escuro"])
def test_texto_corrido_atinge_aa(tema):
    inicio_escuro = CSS.index("@media (prefers-color-scheme: dark)")
    t = _tokens(CSS[CSS.index(":root {"):inicio_escuro])
    if tema == "escuro":
        t |= _tokens(CSS[inicio_escuro:CSS.index("* { box-sizing")])
    for texto in ("tinta", "suave", "sereno", "ambar-txt", "verde"):
        for fundo in ("superficie", "cartao"):
            assert _contraste(t[texto], t[fundo]) >= 4.5, (tema, texto, fundo)


# 6 ------------------------------------------------------------------------
def test_navegacao_por_teclado(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = "https://app.lexlearn.exemplo"
    html = client.get("/").content.decode()
    assert '<a class="pular" href="#conteudo">' in html and 'id="conteudo"' in html
    nav = re.search(r'<nav class="navegacao"[^>]*>(.*?)</nav>', html, re.S).group(1)
    assert 'href="/"' in nav and 'href="https://app.lexlearn.exemplo"' in nav
    assert _pontos(html)                                   # pontos do radar são links: recebem foco
    assert ":focus-visible" in CSS and ".ponto:focus-visible" in CSS
    assert "tabindex=\"-1\"" not in html


def test_cabecalho_em_todas_as_paginas(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = "https://app.lexlearn.exemplo"
    html = client.get("/sefaz-al-2026/").content.decode()
    assert '<nav class="navegacao"' in html and "Conhecer o LexLearn" in html
    assert 'rel="noopener"' in html


def test_sem_url_do_lexlearn_o_cabecalho_nao_tem_link_morto(client, exemplo, settings):
    settings.LEXPUBLI_LEXLEARN_URL = ""
    nav = re.search(r'<nav class="navegacao"[^>]*>(.*?)</nav>', client.get("/").content.decode(), re.S)
    assert "LexLearn" not in nav.group(1)


# D6 -----------------------------------------------------------------------
def test_legenda_do_radar_conta_o_que_esta_no_banco(client, exemplo):
    html = client.get("/").content.decode()
    assert re.search(r"<strong>1</strong> concurso publicado\s+nos últimos 90 dias", html)
