import json

import pytest

from concursos.models import Descoberta

URL = "/webhooks/changedetection/"
APPRISE = {
    "version": "1.0",
    "title": "Mudança: Sefaz-AL 26",
    "message": "https://www.cebraspe.org.br/concursos/SEFAZ_AL_26\n(added) Edital nº 4",
    "type": "info",
}


@pytest.fixture(autouse=True)
def token(settings):
    settings.LEXPUBLI_WEBHOOK_TOKEN = "segredo"


def post(client, corpo, **headers):
    return client.post(URL, data=json.dumps(corpo), content_type="application/json", **headers)


@pytest.mark.django_db
def test_sem_token_recusa(client):
    assert post(client, APPRISE).status_code == 403
    assert post(client, APPRISE, HTTP_X_LEXPUBLI_TOKEN="errado").status_code == 403
    assert Descoberta.objects.count() == 0


@pytest.mark.django_db
def test_token_vazio_desliga_o_webhook(client, settings):
    settings.LEXPUBLI_WEBHOOK_TOKEN = ""
    assert post(client, APPRISE, HTTP_X_LEXPUBLI_TOKEN="").status_code == 403


@pytest.mark.django_db
def test_aviso_apprise_vira_descoberta_pendente(client):
    r = post(client, APPRISE, HTTP_X_LEXPUBLI_TOKEN="segredo")
    assert r.status_code == 201
    d = Descoberta.objects.get()
    assert d.status == Descoberta.Status.PENDENTE
    assert d.fonte == "changedetection"
    assert d.fonte_url == "https://www.cebraspe.org.br/concursos/SEFAZ_AL_26"


@pytest.mark.django_db
def test_reentrega_nao_duplica(client):
    post(client, APPRISE, HTTP_X_LEXPUBLI_TOKEN="segredo")
    r = post(client, APPRISE, HTTP_X_LEXPUBLI_TOKEN="segredo")
    assert r.status_code == 200 and r.json()["duplicada"] is True
    assert Descoberta.objects.count() == 1


@pytest.mark.django_db
def test_token_por_querystring(client):
    r = client.post(URL + "?token=segredo", data=json.dumps(APPRISE), content_type="application/json")
    assert r.status_code == 201


@pytest.mark.django_db
@pytest.mark.parametrize("corpo", [[1, 2], {"title": "sem url", "message": "nada"}])
def test_corpo_invalido(client, corpo):
    assert post(client, corpo, HTTP_X_LEXPUBLI_TOKEN="segredo").status_code == 400


@pytest.mark.django_db
def test_get_nao_permitido(client):
    assert client.get(URL).status_code == 405


@pytest.mark.django_db
def test_html_do_changedetection_vira_texto(client):
    corpo = dict(APPRISE, message='https://x.gov.br/c had a change.<br>---<br>'
                                  '<span style="color: #b30000;">Edital nº 5</span>')
    post(client, corpo, HTTP_X_LEXPUBLI_TOKEN="segredo")
    d = Descoberta.objects.get()
    assert "<" not in d.resumo and "Edital nº 5" in d.resumo
    assert d.fonte_url == "https://x.gov.br/c"


# --- ligação com a Fonte do cadastro (ADR-0007) -------------------------------

def _stj(**kw):
    from concursos.models import Fonte

    return Fonte.objects.create(nome="STJ — Concursos", poder="judiciario", esfera="federal",
                                url="https://www.stj.jus.br/sites/portalp/Institucional/Concursos",
                                carreira_sugerida="tribunais", **kw)


@pytest.mark.django_db
def test_aviso_liga_a_fonte_pelo_uuid_do_watch(client):
    stj = _stj(changedetection_uuid="0b8f3f1e-6c1a-4f3e-9d65-2b1c0a9e7f10")
    corpo = dict(APPRISE, message="https://www.stj.jus.br/outra/pagina\n"
                                  "watch_uuid: 0b8f3f1e-6c1a-4f3e-9d65-2b1c0a9e7f10\n---\n"
                                  "(added) Edital nº 1 — Analista Judiciário\n---\n")
    post(client, corpo, HTTP_X_LEXPUBLI_TOKEN="segredo")
    d = Descoberta.objects.get()
    assert d.fonte_vigiada == stj
    assert d.poder == "Judiciário" and d.carreira_sugerida.startswith("Tribunais")
    assert "watch_uuid" not in d.resumo and "Edital nº 1" in d.resumo


@pytest.mark.django_db
def test_aviso_sem_uuid_liga_pela_url(client):
    stj = _stj()
    corpo = dict(APPRISE, message="http://stj.jus.br/sites/portalp/Institucional/Concursos/ "
                                  "had a change.\n---\n(added) Edital")
    post(client, corpo, HTTP_X_LEXPUBLI_TOKEN="segredo")
    assert Descoberta.objects.get().fonte_vigiada == stj


@pytest.mark.django_db
def test_aviso_de_pagina_fora_do_cadastro_fica_sem_fonte(client):
    _stj()
    post(client, APPRISE, HTTP_X_LEXPUBLI_TOKEN="segredo")       # a página da Cebraspe
    d = Descoberta.objects.get()
    assert d.fonte_vigiada is None and d.poder == "" and d.carreira_sugerida == ""


# --- fontes de notícias (ADR-0007 §3a) ------------------------------------------

def _noticias():
    from concursos.models import Fonte

    return Fonte.objects.create(nome="TRT8 — Notícias sobre concurso", poder="judiciario",
                                esfera="federal", conteudo="noticias",
                                url="https://www.trt8.jus.br/noticias?tag=concurso",
                                changedetection_uuid="11111111-2222-4333-8444-555555555555")


def _aviso(texto):
    return dict(APPRISE, title="[LexPubli] TRT8 — Notícias sobre concurso",
                message="https://www.trt8.jus.br/noticias?tag=concurso\n"
                        "watch_uuid: 11111111-2222-4333-8444-555555555555\n---\n" + texto)


@pytest.mark.django_db
def test_noticia_de_iminencia_vira_descoberta(client):
    fonte = _noticias()
    r = post(client, _aviso("(added) TRT-8 forma comissão do concurso para servidores"),
             HTTP_X_LEXPUBLI_TOKEN="segredo")
    assert r.status_code == 201 and Descoberta.objects.get().fonte_vigiada == fonte
    fonte.refresh_from_db()
    assert (fonte.avisos_recebidos, fonte.avisos_ignorados) == (1, 0)


@pytest.mark.django_db
def test_noticia_sem_concurso_e_ignorada_e_contada(client):
    fonte = _noticias()
    r = post(client, _aviso("(added) Tribunal realiza sessão solene em homenagem ao Dia do Servidor"),
             HTTP_X_LEXPUBLI_TOKEN="segredo")
    assert r.status_code == 200 and r.json()["ignorada"] is True
    assert not Descoberta.objects.exists()
    fonte.refresh_from_db()
    assert (fonte.avisos_recebidos, fonte.avisos_ignorados) == (1, 1)


@pytest.mark.django_db
def test_pagina_de_concursos_nao_tem_filtro(client):
    fonte = _stj(changedetection_uuid="0b8f3f1e-6c1a-4f3e-9d65-2b1c0a9e7f10")
    corpo = dict(APPRISE, message="https://www.stj.jus.br/x\n"
                                  "watch_uuid: 0b8f3f1e-6c1a-4f3e-9d65-2b1c0a9e7f10\n---\n"
                                  "(added) Resultado final homologado")
    assert post(client, corpo, HTTP_X_LEXPUBLI_TOKEN="segredo").status_code == 201
    fonte.refresh_from_db()
    assert fonte.avisos_recebidos == 1 and fonte.avisos_ignorados == 0
