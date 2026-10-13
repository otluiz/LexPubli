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
