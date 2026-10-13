"""Sincronização Fonte -> changedetection.io (ADR-0007 §1)."""
import io
import json
import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from concursos.changedetection import Cliente, ErroChangedetection, notificacao, sincronizar
from concursos.models import Fonte, Orgao

NOTIF = "json://web:8000/webhooks/changedetection/?+X-Lexpubli-Token=t0k3n"


class ChangedetectionFalso:
    """O mesmo contrato do Cliente, em memória."""

    def __init__(self):
        self.tags, self.dados, self.escritas = {}, {}, []

    def etiqueta(self, titulo, *, criar=True):
        for u, t in self.tags.items():
            if t == titulo:
                return u
        if not criar:
            return None
        u = str(uuid.uuid4())
        self.tags[u] = titulo
        self.escritas.append(("tag", titulo))
        return u

    def watches(self, etiqueta):
        tag = next((u for u, t in self.tags.items() if t == etiqueta), None)
        return {u: w for u, w in self.dados.items() if tag in (w.get("tags") or [])}

    def watch(self, u):
        w = self.dados.get(u)
        return dict(w, uuid=u) if w else None

    def criar(self, campos):
        u = str(uuid.uuid4())
        self.dados[u] = dict(campos)
        self.escritas.append(("criar", campos["url"]))
        return u

    def atualizar(self, u, campos):
        self.dados[u].update(campos)
        self.escritas.append(("atualizar", campos["url"]))

    def apagar(self, u):
        del self.dados[u]
        self.escritas.append(("apagar", u))


def _fonte(nome, url, ativa=True, **kw):
    return Fonte.objects.create(
        nome=nome, url=url, ativa=ativa, poder=Fonte.Poder.JUDICIARIO,
        esfera=Orgao.Esfera.FEDERAL, conferida_em="2026-10-13",
        motivo_inativa="" if ativa else "só JS", **kw)


@pytest.fixture
def cd():
    return ChangedetectionFalso()


def _sinc(cd, **kw):
    return sincronizar(Fonte.objects.filter(tipo=Fonte.Tipo.PAGINA).order_by("pk"), cd, NOTIF, **kw)


def test_cria_so_as_ativas_com_etiqueta_intervalo_e_webhook(db, cd):
    stj = _fonte("STJ", "https://www.stj.jus.br/concursos", intervalo_horas=12)
    _fonte("MPT", "https://mpt.mp.br/pgt/trabalho-mpt/procurador", ativa=False)
    rel = _sinc(cd)
    assert rel.criadas == ["STJ"] and len(cd.dados) == 1
    w = next(iter(cd.dados.values()))
    assert w["title"] == "[LexPubli] STJ"
    assert w["time_between_check"] == {"hours": 12} and w["time_between_check_use_default"] is False
    assert w["notification_urls"] == [NOTIF] and w["notification_format"] == "text"
    assert w["tags"] == [cd.etiqueta("lexpubli")] and w["paused"] is False
    stj.refresh_from_db()
    assert stj.changedetection_uuid in cd.dados


def test_rodar_de_novo_nao_escreve_nada(db, cd):
    _fonte("STJ", "https://www.stj.jus.br/concursos")
    _sinc(cd)
    antes = len(cd.escritas)
    rel = _sinc(cd)
    assert rel.iguais == ["STJ"] and len(cd.escritas) == antes


def test_mudanca_no_cadastro_atualiza_e_desativar_pausa(db, cd):
    stj = _fonte("STJ", "https://www.stj.jus.br/concursos")
    _sinc(cd)
    stj.refresh_from_db()                                   # como o painel: lê de novo
    stj.intervalo_horas = 24
    stj.save()
    rel = _sinc(cd)
    assert rel.atualizadas == ["STJ (time_between_check)"]
    stj.ativa, stj.motivo_inativa = False, "página mudou para JS"
    stj.save()
    rel = _sinc(cd)
    assert rel.pausadas and cd.dados[stj.changedetection_uuid]["paused"] is True
    assert len(cd.dados) == 1                                # pausa, não apaga (histórico)


def test_watch_apagado_na_ui_e_recriado(db, cd):
    stj = _fonte("STJ", "https://www.stj.jus.br/concursos")
    _sinc(cd)
    cd.dados.clear()
    rel = _sinc(cd)
    assert rel.criadas == ["STJ"]
    stj.refresh_from_db()
    assert stj.changedetection_uuid in cd.dados


def test_adota_watch_da_etiqueta_com_a_mesma_url(db, cd):
    tag = cd.etiqueta("lexpubli")
    cd.dados["velho"] = {"url": "https://www.stj.jus.br/concursos", "tags": [tag]}
    stj = _fonte("STJ", "https://www.stj.jus.br/concursos")
    rel = _sinc(cd)
    stj.refresh_from_db()
    assert stj.changedetection_uuid == "velho" and not rel.criadas and len(cd.dados) == 1


def test_orfao_so_sai_com_remover_e_watch_manual_nunca(db, cd):
    tag = cd.etiqueta("lexpubli")
    cd.dados["orfao"] = {"url": "https://www.tse.jus.br/x", "title": "velho", "tags": [tag]}
    cd.dados["manual"] = {"url": "https://www.cebraspe.org.br/concursos/SEFAZ_AL_26", "tags": []}
    rel = _sinc(cd)
    assert rel.orfaos == ["velho [orfao]"] and "orfao" in cd.dados
    _sinc(cd, remover_orfaos=True)
    assert "orfao" not in cd.dados and "manual" in cd.dados


def test_simular_nao_escreve_nem_la_nem_aqui(db, cd):
    stj = _fonte("STJ", "https://www.stj.jus.br/concursos")
    rel = _sinc(cd, simular=True)
    assert rel.criadas == ["STJ"] and cd.escritas == []
    stj.refresh_from_db()
    assert stj.changedetection_uuid == ""


def test_dou_fica_fora(db, cd):
    Fonte.objects.create(nome="DOU", url="https://inlabs.in.gov.br/", tipo=Fonte.Tipo.DOU,
                         poder=Fonte.Poder.EXECUTIVO, esfera=Orgao.Esfera.FEDERAL,
                         intervalo_horas=24, ativa=True, conferida_em="2026-10-13")
    assert _sinc(cd).criadas == [] and cd.dados == {}


def test_webhook_desligado_impede_a_sincronizacao():
    with pytest.raises(ErroChangedetection, match="webhook"):
        notificacao("json://web:8000/webhooks/changedetection/", "")


# --- cliente HTTP --------------------------------------------------------------

class Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_cliente_manda_a_chave_e_le_json():
    pedidos = []

    def abrir(req, timeout):
        pedidos.append(req)
        return Resposta(json.dumps({"uuid": "abc"}).encode())

    c = Cliente("http://cd:5000/", "segredo", abrir=abrir)
    assert c.criar({"url": "https://www.stj.jus.br"}) == "abc"
    req = pedidos[0]
    assert req.full_url == "http://cd:5000/api/v1/watch" and req.get_method() == "POST"
    assert req.get_header("X-api-key") == "segredo"


def test_cliente_sem_chave_recusa():
    with pytest.raises(ErroChangedetection, match="API_KEY"):
        Cliente("http://cd:5000", "")


def test_comando_sem_chave_falha_com_mensagem(db, settings):
    settings.LEXPUBLI_CHANGEDETECTION_API_KEY = ""
    with pytest.raises(CommandError, match="Settings > API"):
        call_command("sincronizar_changedetection", stdout=StringIO())


def test_corpo_da_notificacao_traz_o_uuid_do_watch(db, cd):
    _fonte("STJ", "https://www.stj.jus.br/concursos")
    _sinc(cd)
    w = next(iter(cd.dados.values()))
    assert "{{watch_uuid}}" in w["notification_body"] and w["notification_title"] == "[LexPubli] STJ"
