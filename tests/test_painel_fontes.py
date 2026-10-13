"""Fonte gravada no painel -> changedetection.io na hora (hooks do Wagtail)."""
import pytest
from django.urls import reverse

from concursos import changedetection
from concursos.models import Fonte
from tests.test_changedetection import NOTIF, ChangedetectionFalso

FORM = {"nome": "STJ — Concursos", "poder": "judiciario", "esfera": "federal", "onda": "A",
        "tipo": "pagina", "url": "https://www.stj.jus.br/sites/portalp/Institucional/Concursos",
        "carreira_sugerida": "tribunais", "prioridade": "2", "intervalo_horas": "6",
        "ativa": "on", "conferida_em": "2026-10-13", "motivo_inativa": ""}


@pytest.fixture
def painel(client, django_user_model):
    client.force_login(django_user_model.objects.create_superuser("adm", "a@x.br", "s"))
    return client


@pytest.fixture
def cd(monkeypatch):
    falso = ChangedetectionFalso()
    monkeypatch.setattr(changedetection, "configurado", lambda: (falso, NOTIF))
    return falso


def _mensagens(resp):
    return [str(m) for m in resp.context["messages"]] if resp.context else []


def test_criar_no_painel_cria_o_watch(db, painel, cd):
    resp = painel.post(reverse("wagtailsnippets_concursos_fonte:add"), FORM, follow=True)
    fonte = Fonte.objects.get()
    assert fonte.changedetection_uuid in cd.dados
    assert "changedetection: watch criado." in _mensagens(resp)


def test_desativar_no_painel_pausa(db, painel, cd):
    painel.post(reverse("wagtailsnippets_concursos_fonte:add"), FORM)
    fonte = Fonte.objects.get()
    dados = {**FORM, "motivo_inativa": "página mudou para JS"}
    del dados["ativa"]
    resp = painel.post(reverse("wagtailsnippets_concursos_fonte:edit", args=[fonte.pk]), dados,
                       follow=True)
    assert cd.dados[fonte.changedetection_uuid]["paused"] is True
    assert "changedetection: watch pausado." in _mensagens(resp)


def test_apagar_no_painel_apaga_o_watch(db, painel, cd):
    painel.post(reverse("wagtailsnippets_concursos_fonte:add"), FORM)
    fonte = Fonte.objects.get()
    painel.post(reverse("wagtailsnippets_concursos_fonte:delete", args=[fonte.pk]))
    assert not Fonte.objects.exists() and cd.dados == {}


def test_changedetection_fora_do_ar_nao_impede_a_gravacao(db, painel, monkeypatch):
    class Fora(ChangedetectionFalso):
        def etiqueta(self, *a, **kw):
            raise changedetection.ErroChangedetection("changedetection fora do ar")

    monkeypatch.setattr(changedetection, "configurado", lambda: (Fora(), NOTIF))
    resp = painel.post(reverse("wagtailsnippets_concursos_fonte:add"), FORM, follow=True)
    assert Fonte.objects.get().changedetection_uuid == ""
    assert any("NÃO foi atualizado" in m for m in _mensagens(resp))


def test_sem_configuracao_o_painel_so_grava(db, painel, monkeypatch):
    monkeypatch.setattr(changedetection, "configurado", lambda: None)
    resp = painel.post(reverse("wagtailsnippets_concursos_fonte:add"), FORM, follow=True)
    assert Fonte.objects.exists()
    assert not any("changedetection" in m for m in _mensagens(resp))


def test_fonte_de_agregador_nem_chega_ao_changedetection(db, painel, cd):
    resp = painel.post(reverse("wagtailsnippets_concursos_fonte:add"),
                       {**FORM, "url": "https://www.pciconcursos.com.br/x"})
    assert resp.status_code == 200 and not Fonte.objects.exists() and cd.dados == {}
