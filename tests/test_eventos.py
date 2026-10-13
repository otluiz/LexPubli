import pytest
from jsonschema import ValidationError

from concursos.eventos import montar_envelope, publicar_pendentes, validar
from concursos.models import Descoberta, OutboxEvent
from tests.conftest import PublicadorFalso


def aprovar(descoberta, concurso):
    descoberta.status, descoberta.concurso = Descoberta.Status.APROVADA, concurso
    descoberta.full_clean()
    descoberta.save()


def test_aprovacao_gera_um_evento_valido(exemplo):
    aprovar(exemplo["descoberta"], exemplo["concurso"])
    ev = OutboxEvent.objects.get()
    assert ev.status == OutboxEvent.Status.PENDENTE, ev.ultimo_erro
    data = ev.envelope["data"]
    assert ev.envelope["event_type"] == "contest.discovery.created"
    assert data["contest_slug"] == "sefaz_al_2026"
    assert data["organ"] == {"slug": "sefaz_al", "name": "Secretaria de Estado da Fazenda de Alagoas"}
    assert data["exam_board"]["slug"] == "cebraspe"
    assert data["positions"][0]["vacancies"] == 40
    assert data["registration"] == {"start": "2026-09-17", "end": "2026-10-21"}
    assert data["page_url"].endswith("/sefaz-al-2026/")


def test_salvar_de_novo_nao_duplica_evento(exemplo):
    d = exemplo["descoberta"]
    aprovar(d, exemplo["concurso"])
    d.titulo = "editado depois"
    d.save()
    assert OutboxEvent.objects.count() == 1


def test_pendente_e_rejeitada_nao_geram_evento(exemplo):
    d = exemplo["descoberta"]
    d.status = Descoberta.Status.REJEITADA
    d.save()
    assert OutboxEvent.objects.count() == 0
    assert d.decidida_em is not None


def test_aprovar_sem_concurso_e_recusado(exemplo):
    d = exemplo["descoberta"]
    d.status = Descoberta.Status.APROVADA
    with pytest.raises(Exception):
        d.full_clean()


def test_contrato_recusa_campo_fora_do_schema():
    env = montar_envelope("contest.discovery.created", {"contest_id": "x"})
    with pytest.raises(ValidationError):
        validar(env)


def test_contrato_recusa_tipo_sem_schema():
    with pytest.raises(ValueError):
        validar(montar_envelope("contest.qualquer.coisa", {}))


def test_envelope_em_utc_com_z():
    env = montar_envelope("contest.discovery.created", {})
    assert env["occurred_at"].endswith("Z")
    assert env["producer"] == "lexpubli"


def test_publicacao_marca_publicado(exemplo, publicador):
    aprovar(exemplo["descoberta"], exemplo["concurso"])
    assert publicar_pendentes(publicador) == 1
    ev = OutboxEvent.objects.get()
    assert ev.status == OutboxEvent.Status.PUBLICADO and ev.publicado_em
    assert publicador.enviados[0]["event_id"] == str(ev.event_id)
    assert publicar_pendentes(publicador) == 0  # nada sai duas vezes


def test_broker_fora_mantem_pendente(exemplo):
    aprovar(exemplo["descoberta"], exemplo["concurso"])
    with pytest.raises(ConnectionError):
        publicar_pendentes(PublicadorFalso(falhar=True))
    ev = OutboxEvent.objects.get()
    assert ev.status == OutboxEvent.Status.PENDENTE
    assert ev.tentativas == 1 and "broker fora do ar" in ev.ultimo_erro


def test_envelope_adulterado_no_outbox_nao_e_publicado(exemplo, publicador):
    aprovar(exemplo["descoberta"], exemplo["concurso"])
    ev = OutboxEvent.objects.get()
    ev.envelope["data"]["year"] = 1900
    ev.save()
    assert publicar_pendentes(publicador) == 0
    ev.refresh_from_db()
    assert ev.status == OutboxEvent.Status.INVALIDO
    assert publicador.enviados == []


# --- v1.1: carreira, data da prova e contest.discovery.updated (ADR-0004) ----
import datetime as dt
import json

from concursos.eventos import CONTRATOS_DIR
from concursos.models import Carreira


def anuncios():
    return list(OutboxEvent.objects.order_by("criado_em"))


def publicar_pagina(concurso):
    concurso.save_revision().publish()


def test_carreira_do_modelo_e_a_lista_do_contrato():
    common = json.loads((CONTRATOS_DIR / "common.schema.json").read_text(encoding="utf-8"))
    assert Carreira.values == common["$defs"]["career"]["enum"]


def test_anuncio_v1_1_leva_carreira_e_data_da_prova(exemplo):
    aprovar(exemplo["descoberta"], exemplo["concurso"])
    env = OutboxEvent.objects.get().envelope
    assert env["event_version"] == "1.1"
    assert (env["data"]["career"], env["data"]["exam_date"]) == ("fiscal", None)


def test_mudanca_publicada_gera_updated_com_o_que_mudou(exemplo):
    c = exemplo["concurso"]
    aprovar(exemplo["descoberta"], c)
    c.data_prova = dt.date(2026, 12, 13)
    c.status = "inscricoes_encerradas"
    publicar_pagina(c)

    criado, atualizado = anuncios()
    assert atualizado.status == OutboxEvent.Status.PENDENTE, atualizado.ultimo_erro
    env = atualizado.envelope
    assert env["event_type"] == "contest.discovery.updated"
    assert env["data"]["contest_id"] == criado.envelope["data"]["contest_id"]
    assert set(env["data"]["changed"]) == {"exam_date", "status"}
    assert env["data"]["exam_date"] == "2026-12-13"


def test_compara_com_o_ultimo_anuncio_nao_com_o_primeiro(exemplo):
    c = exemplo["concurso"]
    aprovar(exemplo["descoberta"], c)
    c.data_prova = dt.date(2026, 12, 13)
    publicar_pagina(c)
    c.status = "prova_realizada"
    publicar_pagina(c)
    assert anuncios()[-1].envelope["data"]["changed"] == ["status"]


def test_publicar_sem_mudanca_do_contrato_nao_gera_evento(exemplo):
    c = exemplo["concurso"]
    aprovar(exemplo["descoberta"], c)
    c.resumo = "<p>texto editorial novo</p>"       # não é campo do contrato
    publicar_pagina(c)
    assert len(anuncios()) == 1


def test_concurso_nunca_anunciado_nao_gera_updated(exemplo):
    c = exemplo["concurso"]
    c.carreira = Carreira.CONTROLE
    publicar_pagina(c)
    assert anuncios() == []
