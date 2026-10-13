"""configurar_broker: vhost e usuários de permissão mínima (ADR-0005 §2a)."""
import json
import re

import pytest
from django.core.management import CommandError, call_command

from concursos.management.commands import configurar_broker as cb

ENV = {"RABBITMQ_DEFAULT_USER": "admin", "RABBITMQ_DEFAULT_PASS": "a1",
       "BROKER_LEXPUBLI_PASSWORD": "p1", "BROKER_LEXCORPUS_PASSWORD": "c1",
       "LEXPUBLI_BROKER_API": "http://broker:15672/api"}


def _perm(usuario):
    return dict(zip(("configure", "write", "read"), cb.PERMISSOES[usuario]))


def test_worker_so_publica_em_lexpubli_events():
    p = _perm("lexpubli")
    assert re.fullmatch(p["write"], "lexpubli.events")
    assert not re.fullmatch(p["write"], "lexcorpus.events")
    assert not re.fullmatch(p["read"], "lexpubli.events")


def test_lexcorpus_consome_a_fila_dele_e_responde():
    p = _perm("lexcorpus")
    assert re.fullmatch(p["read"], "lexcorpus.lexpubli.contests")
    assert re.fullmatch(p["read"], "lexpubli.events")          # bind da fila
    assert re.fullmatch(p["write"], "lexcorpus.events")        # respostas
    assert not re.fullmatch(p["write"], "lexpubli.events")     # não fala pelo LexPubli
    assert not re.fullmatch(p["read"], "outra.fila")


def test_chamadas_criam_vhost_usuarios_e_permissoes_sem_tag_de_admin():
    lista = cb.chamadas("lexpubli", {"lexpubli": "p1", "lexcorpus": "c1"})
    caminhos = [c[1] for c in lista]
    assert caminhos == ["/vhosts/lexpubli", "/users/lexpubli", "/permissions/lexpubli/lexpubli",
                        "/users/lexcorpus", "/permissions/lexpubli/lexcorpus"]
    assert all(c[0] == "PUT" for c in lista)          # PUT = idempotente
    assert all(c[2].get("tags", "") == "" for c in lista if c[1].startswith("/users/"))


def test_comando_chama_a_api_com_o_admin(monkeypatch):
    for k, v in ENV.items():
        monkeypatch.setenv(k, v)
    feitas = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def falso_urlopen(req, timeout):
        feitas.append((req.get_method(), req.full_url, json.loads(req.data), req.headers))
        return Resp()

    monkeypatch.setattr(cb.urllib.request, "urlopen", falso_urlopen)
    call_command("configurar_broker")
    assert [f[1] for f in feitas][0] == "http://broker:15672/api/vhosts/lexpubli"
    assert feitas[1][2] == {"password": "p1", "tags": ""}
    assert all(f[3]["Authorization"].startswith("Basic ") for f in feitas)


def test_sem_senhas_recusa(monkeypatch):
    for k in ENV:
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(CommandError, match="BROKER_LEXCORPUS_PASSWORD"):
        call_command("configurar_broker")
